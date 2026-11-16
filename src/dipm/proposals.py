"""Proposals: the model in the loop (docs/gui.md §7.3).

Claude (through `dipm mcp`, or any client of `POST /api/proposals`) never writes design
files.  It submits a **proposal**: new content for files in the design's set (`<design>.py`,
`<design>.intent.yaml`), as full text or a unified diff, against the content hashes it read.
Proposals are inert until the designer accepts one in the GUI.

Storage (gitignored, shared by the MCP server and the GUI server):

    <design dir>/.dipm/proposals/<id>.json            the proposal (see `new_proposal`)
    <design dir>/.dipm/proposals/<id>.before.mesh     geometry before (server/mesh.py format)
    <design dir>/.dipm/proposals/<id>.after.mesh      geometry after
    <design dir>/.dipm/requests/<id>.json             "Ask Claude" requests from the GUI

Lifecycle: `pending` → (evaluated in a temp copy) `ready` | `failed` → `accepted` | `rejected`.
A proposal whose base hashes no longer match the files is `stale` and cannot be applied.
Accepting writes every patched file atomically (all or nothing), records review hashes for the
addressed intent nodes (review.py) and closes their open requests.
"""
from __future__ import annotations

import datetime as _dt
import difflib
import json
import os
import re
import shutil
import tempfile
import threading
import time
import warnings

from . import intent_store
from .fileio import atomic_write, file_sha256, read_text, sha256_text
from .review import ReviewRecord, path_for as review_path_for

OPEN_STATUSES = ("pending", "evaluating", "ready", "failed")
STATUSES = OPEN_STATUSES + ("accepted", "rejected", "stale")


class ProposalError(ValueError):
    """A proposal cannot be created or applied (disallowed path, bad diff, stale base …)."""


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- the design's file set

class DesignFiles:
    """Paths that belong to one design.  Only `patchable` files may be changed by a proposal."""

    def __init__(self, design_path: str):
        self.design = os.path.abspath(design_path)
        self.dir = os.path.dirname(self.design)
        self.stem = os.path.splitext(os.path.basename(self.design))[0]
        self.intent = intent_store.path_for(self.design)
        self.review = review_path_for(self.design)
        self.lock = os.path.join(self.dir, self.stem + ".interpretations.json")
        self.record = os.path.join(self.dir, self.stem + ".resolution.json")
        self.dipm_dir = os.path.join(self.dir, ".dipm")
        self.proposals_dir = os.path.join(self.dipm_dir, "proposals")
        self.requests_dir = os.path.join(self.dipm_dir, "requests")

    @property
    def patchable(self) -> dict:
        """name (relative to the design dir) -> absolute path."""
        return {os.path.basename(self.design): self.design, os.path.basename(self.intent): self.intent}

    def name_of(self, path: str) -> str:
        """Normalize a path (basename, relative to the design dir or cwd, or absolute) to its
        name in the file set, or raise ProposalError if it is not a patchable file."""
        if not isinstance(path, str) or not path.strip():
            raise ProposalError("empty file path")
        allowed = {os.path.realpath(p): n for n, p in self.patchable.items()}
        cands = [path] if os.path.isabs(path) else [os.path.join(self.dir, path), os.path.abspath(path)]
        for c in cands:
            n = allowed.get(os.path.realpath(c))
            if n is not None:
                return n
        raise ProposalError(f"{path!r} is not in the design's file set; a proposal may only change "
                            f"{', '.join(sorted(self.patchable))}")

    def ensure_dirs(self) -> None:
        os.makedirs(self.proposals_dir, exist_ok=True)
        os.makedirs(self.requests_dir, exist_ok=True)
        gi = os.path.join(self.dipm_dir, ".gitignore")
        if not os.path.exists(gi):      # belt and braces: the repo .gitignore also lists .dipm/
            atomic_write(gi, "*\n")

    def current_hashes(self) -> dict:
        return {n: file_sha256(p) for n, p in self.patchable.items()}


# ---------------------------------------------------------------- unified diffs

_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def looks_like_diff(text: str) -> bool:
    head = text.lstrip()[:200]
    return head.startswith(("--- ", "diff --git", "@@ "))


def apply_unified_diff(base: str, diff: str) -> str:
    """Apply a unified diff to `base`.  Each hunk's context and removed lines must match, at
    the stated line or (if line numbers are off) at exactly one other place."""
    lines = base.splitlines(keepends=True)
    hunks, cur = [], None
    for raw in diff.splitlines(keepends=True):
        if raw.startswith(("--- ", "+++ ", "diff ", "index ")) and cur is None:
            continue
        m = _HUNK.match(raw)
        if m:
            cur = {"start": int(m.group(1)), "old": [], "new": []}
            hunks.append(cur)
            continue
        if cur is None:
            continue
        if raw.startswith("\\"):            # "\ No newline at end of file": strip it from the last line
            for key in ("old", "new"):
                if cur[key] and cur[key][-1][1] == cur["last"]:
                    cur[key][-1] = (cur[key][-1][0], cur[key][-1][1].rstrip("\n"))
            continue
        tag, body = (raw[0], raw[1:]) if raw[:1] in (" ", "-", "+") else (" ", raw)
        if raw in ("\n", ""):
            tag, body = " ", "\n"
        cur["last"] = body
        if tag in (" ", "-"):
            cur["old"].append((tag, body))
        if tag in (" ", "+"):
            cur["new"].append((tag, body))
    if not hunks:
        raise ProposalError("the diff has no hunks (@@ … @@)")
    offset = 0
    for k, h in enumerate(hunks):
        old = [b for _t, b in h["old"]]
        new = [b for _t, b in h["new"]]
        want = max(0, h["start"] - 1 + offset) if old else max(0, h["start"] + offset)

        def matches(at):
            seg = lines[at:at + len(old)]
            return len(seg) == len(old) and all(a.rstrip("\r\n") == b.rstrip("\r\n") for a, b in zip(seg, old))

        if not matches(want):
            spots = [i for i in range(len(lines) - len(old) + 1) if matches(i)]
            if len(spots) != 1:
                raise ProposalError(f"hunk {k + 1} does not apply: its context/removed lines "
                                    f"{'are not found' if not spots else 'match several places'} in the base file")
            want = spots[0]
        lines[want:want + len(old)] = new
        offset += len(new) - len(old)
    return "".join(lines)


def text_diff(name: str, before: str | None, after: str | None) -> str:
    return "".join(difflib.unified_diff((before or "").splitlines(keepends=True),
                                        (after or "").splitlines(keepends=True),
                                        fromfile=f"a/{name}", tofile=f"b/{name}", n=3))


# ---------------------------------------------------------------- loading and building

def load_and_build(design_path: str, params: dict | None = None, resolve: bool = True) -> dict:
    """Fresh import of a design file, its lock and intent file, then a build.

    Returns {design, build, values, intent (plain | None), intent_error, interp_note}."""
    from .cli import _attach_lock, load_design
    design = load_design(design_path)
    _attach_lock(design, design_path, None, None)
    note = ""
    if resolve:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            design.ensure_interpretations()
        note = "; ".join(str(w.message) for w in caught)
    values = design.resolve_params(params or {})
    b = design.build(values, on_fail="record")
    ipath = design.intent_file or intent_store.path_for(design_path)
    intent, ierr = None, None
    if os.path.exists(ipath):
        try:
            intent = intent_store.load(ipath).to_plain()
        except intent_store.IntentSchemaError as e:
            ierr = e.errors
    return {"design": design, "build": b, "values": values, "intent": intent, "intent_error": ierr,
            "interp_note": note}


def build_summary(design, b, intent: dict | None = None, stale: dict | None = None, record_path: str | None = None) -> dict:
    """A compact, model-readable build report (MCP `build`, proposal evaluations).  `status` is
    tiered (kernel / intent checks / margins), never a bare PASS (B1)."""
    from .assess import assess
    from .resolution import ResolutionRecord
    from .server.serialize import build_payload
    a = assess(design, b, intent, ResolutionRecord.load(record_path) if record_path else None)
    p = build_payload(design, b, None, intent=_intent_arg(intent, stale), assessment=a)
    feats = [{"id": f["id"], "index": f["index"], "op": f["op"], "lowered_from": f["lowered_from"],
              "serves": f["serves"], "status": f["status"], "uses": f["uses"], "params": f["params"],
              "detail": f["detail"],
              "failed_checks": [c for c in f["checks"] if not c["ok"]], "error": f["error"]}
             for f in p["features"]]
    interp = p["interpretations"]
    checks = [{"id": c["id"], "node": c["node"], "state": c["state"], "plain": c["plain"],
               "headline": ({k: c["headline"][k] for k in ("name", "unit", "nominal", "worst", "limit", "limit_worst",
                                                             "margin", "margin_worst")} if c.get("headline") else None),
               "reason": c.get("reason", "")} for c in p["intent_checks"]]
    return {"status": p["status"], "kernel": "pass" if p["ok"] else "fail", "ok": p["ok"], "params": p["params"],
            "errors": p["errors"], "intent_checks": checks,
            "context": p["context"], "orientation": ({k: p["orientation"].get(k) for k in ("label", "up", "rationale",
                                                                                          "made_by", "reviewed")}
                                                     if p["orientation"] else None),
            "features": feats, "signature": p["signature"], "diagnostics": p["diagnostics"],
            "interpretations": {"source": interp["source"],
                                "slots": [{"id": s["id"], "chosen": s.get("chosen"), "made_by": s.get("made_by"),
                                           "sensitivity": s.get("sensitivity")} for s in interp["slots"]],
                                "questions": interp["questions"], "notices": interp["notices"]},
            "stale_nodes": sorted((stale or {}).keys())}


def _intent_arg(intent, stale) -> dict | None:
    if intent is None:
        return None
    return {"plain": intent, "stale": stale or {}}


# ---------------------------------------------------------------- face matching (changed faces)

def _surface_signature(face) -> tuple:
    """The face's underlying surface, rounded: planes by normal + offset, cylinders by axis +
    radius, cones by apex + axis + angle.  A plane whose boundary changed (a hole moved in it)
    keeps its signature, so only faces that really moved or changed shape are highlighted."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere
    from OCP.TopoDS import TopoDS

    from . import kernel as K
    r = lambda x: round(float(x), 4)   # noqa: E731
    s = BRepAdaptor_Surface(TopoDS.Face(face))
    t = s.GetType()
    if t == GeomAbs_Plane:
        ax = s.Plane().Axis()
        d, p = ax.Direction(), ax.Location()
        sign = 1 if (d.X(), d.Y(), d.Z()) >= (0, 0, 0) else -1
        n = (r(sign * d.X()), r(sign * d.Y()), r(sign * d.Z()))
        return ("plane", n, r(n[0] * p.X() + n[1] * p.Y() + n[2] * p.Z()))
    if t == GeomAbs_Cylinder:
        c = s.Cylinder()
        ax = c.Axis()
        d, p = ax.Direction(), ax.Location()
        # a point on the axis, canonical: the axis point closest to the origin
        k = -(p.X() * d.X() + p.Y() * d.Y() + p.Z() * d.Z())
        q = (r(p.X() + k * d.X()), r(p.Y() + k * d.Y()), r(p.Z() + k * d.Z()))
        return ("cylinder", tuple(abs(r(v)) for v in (d.X(), d.Y(), d.Z())), q, r(c.Radius()))
    if t == GeomAbs_Cone:
        c = s.Cone()
        a, d = c.Apex(), c.Axis().Direction()
        return ("cone", (r(a.X()), r(a.Y()), r(a.Z())), (r(d.X()), r(d.Y()), r(d.Z())), r(c.SemiAngle()))
    if t == GeomAbs_Sphere:
        c = s.Sphere()
        p = c.Location()
        return ("sphere", (r(p.X()), r(p.Y()), r(p.Z())), r(c.Radius()))
    c = K.centroid(face)
    return ("other", K.surface_type(face), r(K.area(face)), (r(c.x), r(c.y), r(c.z)))


def face_signatures(b) -> list:
    if b is None or b.shape is None:
        return []
    out = []
    for f in b.faces():
        w = b.why(f)
        tag = str(w.entries[0].tag) if w.entries else "untracked"
        out.append((tag, _surface_signature(f)))
    return out


def face_outlines(b) -> list:
    """Per face: (area, edge count, rounded bounding box), to tell a face whose surface stayed
    but whose outline changed (a plane with a hole moved in it; NOTES #53 change)."""
    from . import kernel as K
    if b is None or b.shape is None:
        return []
    out = []
    for f in b.faces():
        lo, hi = K.bbox(f)
        out.append((round(K.area(f), 3), len(K.subshapes(f, K.KINDS["edge"])),
                    tuple(round(v, 3) for v in (lo.x, lo.y, lo.z, hi.x, hi.y, hi.z))))
    return out


def outline_changed(before_sigs: list, after_sigs: list, before_out: list, after_out: list,
                    changed_before: list, changed_after: list) -> tuple[list, list]:
    """Faces matched by (tag, surface) on both sides whose outline differs (lighter tint)."""
    cb, ca = set(changed_before), set(changed_after)
    pool: dict = {}
    for i, s in enumerate(before_sigs):
        if i not in cb:
            pool.setdefault(s, []).append(i)
    ob, oa = [], []
    for j, s in enumerate(after_sigs):
        if j in ca or not pool.get(s):
            continue
        i = pool[s].pop(0)
        if before_out[i] != after_out[j]:
            ob.append(i)
            oa.append(j)
    return sorted(ob), sorted(oa)


def changed_faces(before: list, after: list) -> tuple[list, list]:
    """(changed face ids in before, changed face ids in after): faces whose (genealogy tag,
    surface) has no counterpart on the other side (multiset difference)."""
    from collections import Counter
    cb, ca = Counter(before), Counter(after)

    def pick(sigs, other):
        left, out = Counter(other), []
        for i, s in enumerate(sigs):
            if left[s] > 0:
                left[s] -= 1
            else:
                out.append(i)
        return out

    return pick(before, ca), pick(after, cb)


# ---------------------------------------------------------------- semantic diff

def _nodes_flat(intent: dict | None) -> dict:
    out: dict = {}

    def walk(lst, parent):
        for n in lst or []:
            out[n["id"]] = {"parent": parent, "statement": n.get("statement", ""),
                            "checks": n.get("checks") or [], "assumptions": n.get("assumptions") or []}
            walk(n.get("children"), n["id"])

    walk((intent or {}).get("intents"), None)
    return out


def intent_diff(before: dict | None, after: dict | None) -> dict:
    a, b = _nodes_flat(before), _nodes_flat(after)
    out = {"added": [], "removed": [], "moved": [], "changed": []}
    for nid in b:
        if nid not in a:
            out["added"].append({"id": nid, "statement": b[nid]["statement"], "parent": b[nid]["parent"]})
    for nid in a:
        if nid not in b:
            out["removed"].append({"id": nid, "statement": a[nid]["statement"]})
            continue
        if a[nid]["parent"] != b[nid]["parent"]:
            out["moved"].append({"id": nid, "from": a[nid]["parent"], "to": b[nid]["parent"]})
        ch = {}
        if a[nid]["statement"] != b[nid]["statement"]:
            ch["statement"] = {"before": a[nid]["statement"], "after": b[nid]["statement"]}
        for key in ("checks", "assumptions"):
            ia = {x.get("id"): x for x in a[nid][key]}
            ib = {x.get("id"): x for x in b[nid][key]}
            d = {"added": [ib[k] for k in ib if k not in ia], "removed": [ia[k] for k in ia if k not in ib],
                 "changed": [{"before": ia[k], "after": ib[k]} for k in ia if k in ib and ia[k] != ib[k]]}
            if any(d.values()):
                ch[key] = d
        if ch:
            out["changed"].append({"id": nid, **ch})
    return out


FEATURE_KEYS = ("op", "lowered_from", "serves", "uses", "params", "detail", "status")


def feature_diff(before: dict, after: dict) -> dict:
    fa = {f["id"]: f for f in before["features"]}
    fb = {f["id"]: f for f in after["features"]}
    out = {"added": [k for k in fb if k not in fa], "removed": [k for k in fa if k not in fb], "changed": []}
    for k in fb:
        if k in fa:
            ch = {key: {"before": fa[k].get(key), "after": fb[k].get(key)}
                  for key in FEATURE_KEYS if fa[k].get(key) != fb[k].get(key)}
            if ch:
                out["changed"].append({"id": k, **ch})
    return out


def interpretation_diff(before: dict, after: dict) -> dict:
    sa = {s["id"]: s for s in before["interpretations"]["slots"]}
    sb = {s["id"]: s for s in after["interpretations"]["slots"]}
    return {"added": [sb[k] for k in sb if k not in sa], "removed": [sa[k] for k in sa if k not in sb],
            "changed": [{"id": k, "before": sa[k]["chosen"], "after": sb[k]["chosen"]}
                        for k in sb if k in sa and sa[k]["chosen"] != sb[k]["chosen"]],
            "questions": [len(before["interpretations"]["questions"]), len(after["interpretations"]["questions"])],
            "notices": [len(before["interpretations"]["notices"]), len(after["interpretations"]["notices"])]}


def check_diff(before: dict, after: dict) -> dict:
    fa = {f["id"]: f["status"] for f in before["features"]}
    ib = {c["id"]: c["state"] for c in before.get("intent_checks") or []}
    return {"before": {"status": before["status"]["headline"], "kernel": before["kernel"], "errors": len(before["errors"])},
            "after": {"status": after["status"]["headline"], "kernel": after["kernel"], "errors": len(after["errors"])},
            "intent": [{"id": c["id"], "before": ib.get(c["id"]), "after": c["state"]}
                       for c in after.get("intent_checks") or [] if ib.get(c["id"]) != c["state"]],
            "features": [{"id": f["id"], "before": fa.get(f["id"]), "after": f["status"],
                          "failed_checks": f["failed_checks"]} for f in after["features"]],
            "diagnostics_after": after["diagnostics"]}


# ---------------------------------------------------------------- the store

class ProposalStore:
    """Proposals and requests for one design (files under `<design dir>/.dipm/`)."""

    _lock = threading.RLock()

    def __init__(self, design_path: str):
        self.files = DesignFiles(design_path)

    # -------------------------------------------------------------- basic IO
    def _ppath(self, pid: str) -> str:
        if not re.fullmatch(r"[pr]\d+", pid or ""):
            raise ProposalError(f"bad id {pid!r}")
        return os.path.join(self.files.proposals_dir, pid + ".json")

    def mesh_path(self, pid: str, which: str) -> str:
        if which not in ("before", "after"):
            raise ProposalError("which must be before|after")
        self._ppath(pid)
        return os.path.join(self.files.proposals_dir, f"{pid}.{which}.mesh")

    def _alloc(self, d: str, prefix: str) -> tuple[str, str]:
        os.makedirs(d, exist_ok=True)
        nums = [int(m.group(1)) for f in os.listdir(d) if (m := re.fullmatch(prefix + r"(\d+)\.json", f))]
        n = max(nums, default=0) + 1
        while True:
            pid = f"{prefix}{n}"
            path = os.path.join(d, pid + ".json")
            try:
                fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)   # claims the id across processes
                os.close(fd)
                return pid, path
            except FileExistsError:
                n += 1

    def get(self, pid: str) -> dict:
        path = self._ppath(pid)
        if not os.path.exists(path):
            raise ProposalError(f"no proposal {pid}")
        for _ in range(5):
            try:
                with open(path, encoding="utf-8") as fh:
                    return json.load(fh)
            except json.JSONDecodeError:      # being created right now
                time.sleep(0.05)
        raise ProposalError(f"proposal {pid} is unreadable")

    def save(self, p: dict) -> None:
        atomic_write(self._ppath(p["id"]), json.dumps(p, indent=2, ensure_ascii=False) + "\n")

    def list(self) -> list:
        d = self.files.proposals_dir
        if not os.path.isdir(d):
            return []
        ids = sorted((f[:-5] for f in os.listdir(d) if re.fullmatch(r"p\d+\.json", f)), key=lambda x: int(x[1:]))
        out = []
        for pid in ids:
            try:
                out.append(self.refresh(self.get(pid)))
            except ProposalError:
                continue
        return out

    def refresh(self, p: dict) -> dict:
        """Mark an open proposal stale if a file it is based on changed since."""
        if p.get("status") in OPEN_STATUSES:
            cur = self.files.current_hashes()
            bad = [n for n, h in (p.get("base_hashes") or {}).items() if cur.get(n) != h]
            if bad:
                p["status"] = "stale"
                p["status_detail"] = f"{', '.join(bad)} changed since this proposal was made; it cannot be applied"
                p.setdefault("feedback", []).append({"at": _now(), "kind": "stale", "by": "dipm",
                                                     "comment": p["status_detail"]})
                with self._lock:
                    self.save(p)
        return p

    # -------------------------------------------------------------- creating
    def create(self, summary: str, rationale: str, files: dict, base_hashes: dict, addresses_nodes=(),
               revises: str | None = None, source: str = "mcp") -> dict:
        """Validate and store a proposal (status `pending`, or `stale` if its base is out of date).

        files: {path: new full text | unified diff}; base_hashes: {path: sha256 of the content
        the change was made against} (every patched file needs one)."""
        if not isinstance(files, dict) or not files:
            raise ProposalError("files must map at least one path to new text or a unified diff")
        if not str(summary or "").strip():
            raise ProposalError("a proposal needs a summary")
        base = {}
        for path, h in (base_hashes or {}).items():
            base[self.files.name_of(path)] = h
        cur = self.files.current_hashes()
        patches, stale = {}, []
        for path, content in files.items():
            name = self.files.name_of(path)
            if not isinstance(content, str):
                raise ProposalError(f"{name}: content must be text (the new file, or a unified diff)")
            if name not in base:
                raise ProposalError(f"{name}: missing base hash (get_source returns it)")
            if base[name] != cur.get(name):
                stale.append(name)
            kind = "diff" if looks_like_diff(content) else "full"
            entry = {"kind": kind, "submitted": content if kind == "diff" else None}
            base_text = read_text(self.files.patchable[name]) if os.path.exists(self.files.patchable[name]) else ""
            if kind == "diff":
                if name in stale:
                    entry["new_text"] = None
                else:
                    entry["new_text"] = apply_unified_diff(base_text, content)
            else:
                entry["new_text"] = content
            if entry["new_text"] is not None:
                entry["new_hash"] = sha256_text(entry["new_text"])
                entry["diff"] = text_diff(name, base_text, entry["new_text"])
                if name.endswith(intent_store.SUFFIX):
                    try:     # schema errors are the author's problem: refuse early, with the message
                        intent_store.loads(entry["new_text"])
                    except intent_store.IntentSchemaError as e:
                        raise ProposalError(f"{name}: {e}") from None
            patches[name] = entry
        nodes = [str(n) for n in (addresses_nodes or [])]
        if revises:
            self.get(revises)
        with self._lock:
            self.files.ensure_dirs()
            pid, _path = self._alloc(self.files.proposals_dir, "p")
            p = {"id": pid, "created": _now(), "summary": str(summary).strip(), "rationale": str(rationale or "").strip(),
                 "addresses_nodes": nodes, "revises": revises, "source": source,
                 "base_hashes": {n: base[n] for n in patches}, "patches": patches,
                 "status": "stale" if stale else "pending",
                 "status_detail": (f"{', '.join(stale)} changed since the base hash was read; re-read with "
                                   f"get_source and propose again") if stale else "",
                 "evaluation": None, "feedback": []}
            self.save(p)
        return p

    # -------------------------------------------------------------- evaluating
    def evaluate(self, pid: str, params: dict | None = None, view_params: dict | None = None) -> dict:
        """Build the proposal in a temp copy and store the evaluation (status ready | failed).
        The verdict uses `params` (default: the design's defaults) plus the sweep; the
        before/after geometry the designer looks at is built at `view_params` (the GUI's
        current parameters, NOTES #53 change) when given."""
        p = self.refresh(self.get(pid))
        if p["status"] not in ("pending", "evaluating", "ready", "failed"):
            return p
        p["status"] = "evaluating"
        self.save(p)
        t0 = time.perf_counter()
        try:
            ev = self._evaluate(p, params, view_params)
            p["evaluation"] = ev
            p["status"] = "ready"
            p["status_detail"] = ("" if not ev.get("failing_checks") else
                                  "the proposed design fails checks: " + ", ".join(ev["failing_checks"]))
        except Exception as e:   # noqa: BLE001 - a broken proposal is reported, not raised
            p["evaluation"] = {"ok": False, "error": f"{type(e).__name__}: {e}",
                               "ms": round((time.perf_counter() - t0) * 1000, 1)}
            p["status"] = "failed"
            p["status_detail"] = f"evaluation failed: {type(e).__name__}: {e}"
        with self._lock:             # the designer may have acted meanwhile (accept holds this lock)
            cur = self.get(pid)
            if cur.get("status") in ("accepted", "rejected"):
                return cur
            self.save(p)
        return self.refresh(p)

    def _evaluate(self, p: dict, params: dict | None, view_params: dict | None = None) -> dict:
        t0 = time.perf_counter()
        F = self.files
        before = load_and_build(F.design, params)
        review = ReviewRecord.load(F.review)
        stale_before = review.stale(before["intent"]) if before["intent"] is not None else {}
        tmp = tempfile.mkdtemp(prefix="dipm-proposal-")
        try:
            for src in (F.design, F.intent, F.lock, F.review, F.record):
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(tmp, os.path.basename(src)))
            for f in os.listdir(F.dir):                    # preferences next to the design
                if f.endswith(".prefs.json"):
                    shutil.copy2(os.path.join(F.dir, f), os.path.join(tmp, f))
            for name, entry in p["patches"].items():
                atomic_write(os.path.join(tmp, name), entry["new_text"])
            tdesign = os.path.join(tmp, os.path.basename(F.design))
            after = load_and_build(tdesign, params)
            if after["intent_error"]:
                raise ProposalError("intent file: " + "; ".join(after["intent_error"]))
            # staleness after: the review record with the addressed nodes accepted
            rev_after = ReviewRecord(F.review, dict(review.reviewed), True)
            if after["intent"] is not None:
                rev_after.mark(after["intent"], p.get("addresses_nodes") or [])
            stale_after = rev_after.stale(after["intent"]) if after["intent"] is not None else {}
            sb = build_summary(before["design"], before["build"], before["intent"], stale_before, F.record)
            sa = build_summary(after["design"], after["build"], after["intent"], stale_after,
                               os.path.join(tmp, os.path.basename(F.record)))
            # sweep the proposed design over the stability sample points (checks across the ranges)
            from .interpret import sample_points
            sweep = []
            for pt in sample_points(after["design"]):
                try:
                    bb = after["design"].build(pt, on_fail="record")
                    if not bb.ok:
                        sweep.append({"params": pt, "errors": [str(e) for e in bb.errors][:3]})
                except Exception as e:   # noqa: BLE001
                    sweep.append({"params": pt, "errors": [f"{type(e).__name__}: {e}"]})
            n_points = len(sample_points(after["design"]))
            view = self._view_geometry(p["id"], before["design"], after["design"], before["build"], after["build"],
                                       view_params)
            # checks that fail and would need "Accept anyway…" (#54): kernel failures at the
            # defaults or in the sweep, and failing intent checks at the addressed nodes or
            # beneath them (a pre-existing failure elsewhere, e.g. R.c1, does not block an A.3 fix)
            failing = self._failing_checks(sa, sweep, after["intent"], p.get("addresses_nodes") or [])
            # the lock the proposed design resolved to, written on accept so it is not stale
            lock_text = None
            d = after["design"]
            if d.lock is not None and d.interpretation is not None:
                lock_text = d.interpretation.to_json()
            idiff = intent_diff(before["intent"], after["intent"])
            ev = {
                "ok": bool(sa["ok"] and not sweep),
                "failing_checks": failing, "needs_override": bool(failing),
                "params": {k: v for k, v in sa["params"].items()},
                "before": {"status": sb["status"], "kernel": sb["kernel"], "ok": sb["ok"],
                           "stale_nodes": sb["stale_nodes"], "intent_checks": sb["intent_checks"]},
                "after": {"status": sa["status"], "kernel": sa["kernel"], "ok": sa["ok"], "errors": sa["errors"],
                          "stale_nodes": sa["stale_nodes"], "intent_checks": sa["intent_checks"]},
                "sweep": {"points": n_points, "failing": sweep},
                "semantic_diff": {"intent": idiff, "features": feature_diff(sb, sa),
                                  "checks": check_diff(sb, sa), "interpretations": interpretation_diff(sb, sa)},
                "text_diff": {n: e.get("diff", "") for n, e in p["patches"].items()},
                **view,
                "interp_note": after["interp_note"],
                "lock": lock_text,
                "ms": round((time.perf_counter() - t0) * 1000, 1),
            }
            return ev
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _view_geometry(self, pid: str, dbefore, dafter, bbefore, bafter, view_params: dict | None) -> dict:
        """Meshes, changed and outline-changed faces and face tags, at `view_params` when they
        differ from the builds' own parameters (NOTES #53 change)."""
        from .server.mesh import mesh_bytes
        vp = None
        if view_params:
            try:
                vb = dbefore.resolve_params(view_params)
                va = dafter.resolve_params({k: v for k, v in view_params.items() if k in dafter.params})
                if vb != bbefore.params:
                    bbefore = dbefore.build(vb, on_fail="record")
                if va != bafter.params:
                    bafter = dafter.build(va, on_fail="record")
                vp = {k: v for k, v in vb.items()}
            except Exception:   # noqa: BLE001 - fall back to the verdict builds
                vp = None
        meshes = {}
        for which, b in (("before", bbefore), ("after", bafter)):
            if b.shape is not None:
                mid, data = mesh_bytes(b.shape)
                with open(self.mesh_path(pid, which), "wb") as fh:
                    fh.write(data)
                meshes[which] = mid
        sb, sa = face_signatures(bbefore), face_signatures(bafter)
        cb, ca = changed_faces(sb, sa)
        ob, oa = outline_changed(sb, sa, face_outlines(bbefore), face_outlines(bafter), cb, ca)
        return {"meshes": meshes, "view_params": vp or dict(bafter.params),
                "changed_faces": {"before": cb, "after": ca, "outline_before": ob, "outline_after": oa},
                "face_tags": {"before": [t for t, _s in sb], "after": [t for t, _s in sa]}}

    def view(self, pid: str, params: dict) -> dict:
        """Rebuild only the before/after geometry of an evaluated proposal at `params` (the GUI's
        current parameters).  The verdict is unchanged."""
        p = self.refresh(self.get(pid))
        ev = p.get("evaluation") or {}
        if not ev or ev.get("error"):
            raise ProposalError(f"{pid} has no evaluation to view")
        F = self.files
        tmp = tempfile.mkdtemp(prefix="dipm-view-")
        try:
            for src in (F.design, F.intent, F.lock, F.review):
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(tmp, os.path.basename(src)))
            for name, entry in p["patches"].items():
                atomic_write(os.path.join(tmp, name), entry["new_text"])
            if ev.get("lock"):
                atomic_write(os.path.join(tmp, os.path.basename(F.lock)), ev["lock"])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                before = load_and_build(F.design, None)
                after = load_and_build(os.path.join(tmp, os.path.basename(F.design)), None)
            view = self._view_geometry(pid, before["design"], after["design"], before["build"], after["build"], params)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        with self._lock:
            p = self.get(pid)
            p["evaluation"] = {**(p.get("evaluation") or {}), **view}
            self.save(p)
        return self.refresh(p)

    @staticmethod
    def _failing_checks(sa: dict, sweep: list, intent: dict | None, nodes: list) -> list:
        out = []
        if not sa["ok"]:
            out += [f"kernel: {e.get('feature') or 'build'} {e.get('invariant') or e.get('kind')}" for e in sa["errors"]]
        if sweep:
            out.append(f"kernel: {len(sweep)} sweep point(s) fail")
        from .connections import file_parents
        parents = file_parents(intent) or {}

        def under(n):
            while n is not None:
                if n in nodes:
                    return True
                n = parents.get(n)
            return False

        for c in sa.get("intent_checks") or []:
            if c["state"] != "failing":
                continue
            if under(c["node"]):
                out.append(c["id"])
        return out

    def claude_prompt(self) -> str:
        """The copyable prompt for "Queue for Claude" (#55): nothing is pushed to Claude."""
        n = len(self.requests("open"))
        return (f"Use the dipm MCP server for {os.path.basename(self.files.design)}: call get_requests and "
                f"get_stale_nodes, read the design with get_source, and handle the {n} open request(s) by "
                "submitting a proposal for each with propose_patch (never edit the design files directly).")

    # -------------------------------------------------------------- deciding
    def accept(self, pid: str, comment: str = "", override_reason: str | None = None) -> dict:
        """Apply the proposal's patches atomically (all or nothing), write the resolved lock,
        record review hashes for the addressed nodes, close their requests.  A proposal that
        fails checks needs `override_reason` ("Accept anyway…", #54): the override (failing
        checks, reason, time) is recorded in the review record for the addressed nodes."""
        from .interpret import Interpretation, Preferences, lock_key, prefs_path_from_lock, LockSpec
        with self._lock:
            p = self.refresh(self.get(pid))
            if p["status"] == "stale":
                raise ProposalError(f"{pid} is stale: {p.get('status_detail')}")
            if p["status"] != "ready":
                raise ProposalError(f"{pid} cannot be accepted while {p['status']}")
            cur = self.files.current_hashes()
            for n, h in p["base_hashes"].items():
                if cur.get(n) != h:
                    raise ProposalError(f"{n} changed since {pid} was made")
            ev0 = p.get("evaluation") or {}
            failing = list(ev0.get("failing_checks") or ([] if ev0.get("ok", True) else ["kernel"]))
            reason = (override_reason or "").strip()
            if failing and not reason:
                raise ProposalError(f"{pid} fails checks ({', '.join(failing)}); accept anyway needs a reason")
            rec = ReviewRecord.load(self.files.review)
            # write every file: temps first, then rename; roll back on failure
            targets = {self.files.patchable[n]: e["new_text"] for n, e in p["patches"].items()}
            backups = {t: (read_text(t) if os.path.exists(t) else None) for t in targets}
            done = []
            try:
                for t, text in targets.items():
                    atomic_write(t, text)
                    done.append(t)
            except BaseException:
                for t in done:
                    if backups[t] is None:
                        os.unlink(t)
                    else:
                        atomic_write(t, backups[t])
                raise
            written = list(targets)
            # the interpretations lock resolved during evaluation, if it is valid here
            ev = p.get("evaluation") or {}
            if ev.get("lock") and os.path.basename(self.files.design) in p["patches"]:
                try:
                    interp = Interpretation.from_json(ev["lock"])
                    spec = LockSpec(self.files.design, self.files.lock)
                    if interp.key == lock_key(self.files.design, Preferences.load(prefs_path_from_lock(spec))):
                        atomic_write(self.files.lock, ev["lock"])
                        written.append(self.files.lock)
                except Exception:   # noqa: BLE001 - the server re-resolves a stale lock anyway
                    pass
            # review: the addressed nodes' new content is accepted
            reviewed = []
            if os.path.exists(self.files.intent):
                doc = intent_store.load(self.files.intent).to_plain()
                reviewed = rec.mark(doc, p.get("addresses_nodes") or [])
                if failing:
                    rec.override(reviewed or (p.get("addresses_nodes") or []), failing, reason, _now(), pid)
                if reviewed or failing:
                    rec.save()
                    written.append(self.files.review)
            p["status"] = "accepted"
            p["status_detail"] = f"applied {', '.join(os.path.basename(w) for w in written)}"
            p["accepted"] = {"at": _now(), "written": [os.path.basename(w) for w in written], "reviewed": reviewed,
                             **({"override": {"failing": failing, "reason": reason}} if failing else {})}
            p.setdefault("feedback", []).append({"at": _now(), "kind": "accept anyway" if failing else "accept",
                                                 "by": "designer", "comment": reason if failing else comment})
            self.save(p)
            self.close_requests(p.get("addresses_nodes") or [], pid)
            return p

    def reject(self, pid: str, comment: str = "") -> dict:
        with self._lock:
            p = self.refresh(self.get(pid))
            if p["status"] == "accepted":
                raise ProposalError(f"{pid} was already accepted")
            p["status"] = "rejected"
            p["status_detail"] = comment.strip() or "rejected"
            p.setdefault("feedback", []).append({"at": _now(), "kind": "reject", "by": "designer",
                                                 "comment": comment.strip()})
            self.save(p)
            return p

    def feedback(self, pid: str | None = None) -> list:
        ps = [self.refresh(self.get(pid))] if pid else self.list()
        return [{"id": p["id"], "status": p["status"], "summary": p["summary"], "revises": p.get("revises"),
                 "addresses_nodes": p.get("addresses_nodes", []), "feedback": p.get("feedback", []),
                 "status_detail": p.get("status_detail", "")} for p in ps]

    # -------------------------------------------------------------- requests ("Ask Claude")
    def create_request(self, node: str, note: str, change: dict | None) -> dict:
        with self._lock:
            self.files.ensure_dirs()
            rid, _ = self._alloc(self.files.requests_dir, "r")
            r = {"id": rid, "created": _now(), "node": node, "note": (note or "").strip(), "change": change,
                 "status": "open", "proposals": []}
            atomic_write(os.path.join(self.files.requests_dir, rid + ".json"),
                         json.dumps(r, indent=2, ensure_ascii=False) + "\n")
            return r

    def requests(self, status: str | None = None) -> list:
        d = self.files.requests_dir
        if not os.path.isdir(d):
            return []
        out = []
        for f in sorted((f for f in os.listdir(d) if re.fullmatch(r"r\d+\.json", f)), key=lambda x: int(x[1:-5])):
            try:
                with open(os.path.join(d, f), encoding="utf-8") as fh:
                    r = json.load(fh)
            except (OSError, json.JSONDecodeError):
                continue
            if status is None or r.get("status") == status:
                out.append(r)
        return out

    def close_requests(self, nodes, pid: str) -> None:
        for r in self.requests("open"):
            if r.get("node") in nodes:
                r["status"] = "answered"
                r["proposals"] = list(dict.fromkeys((r.get("proposals") or []) + [pid]))
                atomic_write(os.path.join(self.files.requests_dir, r["id"] + ".json"),
                             json.dumps(r, indent=2, ensure_ascii=False) + "\n")

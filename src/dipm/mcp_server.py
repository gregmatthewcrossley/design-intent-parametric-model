"""`python -m dipm mcp <design.py>`: a stdio MCP server for one design (docs/gui.md §7.3).

It lets a model (e.g. a Claude Code session) read the design, build it, explain faces, see
which intent nodes are stale, and **propose** changes.  It never writes design files: a
proposal is stored under `<design dir>/.dipm/proposals/`, evaluated in a temp copy, and shown
in the `dipm serve` GUI, where the designer accepts or rejects it (with a comment that comes
back through `get_proposal_feedback`).

Tools: get_design, get_intent, build, why, get_stale_nodes, get_requests, get_source,
propose_patch, list_proposals, get_proposal_feedback; and the purpose -> geometry loop
(iteration 4, docs/purpose-loop.md): get_impact, get_check_vocabulary, get_components,
propose_purposes, evaluate, propose_alternatives.

Started by a headless Claude run (iteration 4b, claude_runner.py), the environment carries
DIPM_RUN (the run id) and DIPM_REQUESTS (the request ids it handles): get_requests then lists
those requests, and every proposal made here carries the run id and is linked to them.
"""
from __future__ import annotations

import os
import threading
import warnings

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import intent_store
from .fileio import file_sha256, read_text
from .proposals import ProposalError, ProposalStore, build_summary, load_and_build
from .review import ReviewRecord

#: every tool this server registers (claude_runner allows exactly these, nothing else)
TOOL_NAMES = ("get_design", "get_intent", "build", "why", "get_stale_nodes", "get_requests", "get_source",
              "propose_patch", "list_proposals", "get_proposal_feedback", "get_impact", "get_check_vocabulary",
              "get_components", "propose_purposes", "evaluate", "propose_alternatives")

INSTRUCTIONS = """\
dipm: a design environment.  A design is a purpose tree (<design>.intent.yaml: statements, checks,
assumptions, components) plus a deterministic solution in the embedded-Python DSL (<design>.py), whose
features name the purposes they serve in tags=intent("A.3", ...).  Geometry is rebuilt from text.
You never write files: you propose, dipm evaluates, the designer decides in the GUI.

When a purpose changed (get_requests / get_stale_nodes show it), run the purpose -> geometry loop:
1. get_impact: which nodes, checks, assumptions and features the change invalidated, and why.
2. Re-plan purposes first.  get_check_vocabulary and get_components, then propose_purposes with the
   revised intent file (full text or diff; base hash from get_source).  Every check you add or change
   must carry a binding: a vocabulary form whose parameters name exports/features/components, or
   {form: descriptive, reason: ...} when it cannot be computed (it then shows as not run, never as
   passing).  Off-the-shelf things the design must fit go in components (from the pack, or written out
   with their source; status proposed).  Never mark anything accepted: the designer accepts.
3. Geometry: write the design program.  Use evaluate(files, label=..., purpose=<purpose proposal id>)
   as your inner loop: it builds the candidate and returns every check with margins.  Each label has a
   budget (default 6 attempts).  Export the faces your bindings name (d.export("cradle_seat", ...)).
4. propose_alternatives with 2 or 3 alternatives (label, summary, rationale, files).  An alternative
   that still fails is submitted honestly as failing, with its best attempt.
For small edits to an existing solution, propose_patch still works.  Prefer relations to literals,
keep feature ids and intent ids stable.
"""


class DesignContext:
    """The design behind the server; reloaded when any of its files change on disk."""

    def __init__(self, design_path: str):
        self.path = os.path.abspath(design_path)
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        self.store = ProposalStore(self.path)
        self.files = self.store.files
        # a headless Claude run (claude_runner.py) passes its id and requests in the environment
        self.store.run_id = os.environ.get("DIPM_RUN") or None
        self.store.run_requests = tuple(x for x in (os.environ.get("DIPM_REQUESTS") or "").split(",") if x.strip())
        self._key = None
        self._cur = None
        self._lock = threading.Lock()

    def active_requests(self) -> list:
        """The requests to work on: a run's own requests (whatever their state), else the open ones."""
        if self.store.run_requests:
            return [r for r in self.store.requests() if r["id"] in self.store.run_requests]
        return self.store.requests("open")

    def _files_key(self) -> tuple:
        F = self.files
        return tuple(file_sha256(p) for p in (F.design, F.intent, F.lock, F.review))

    def current(self, params: dict | None = None) -> dict:
        """{design, build, intent, intent_error, stale, summary} at `params` (default: defaults)."""
        with self._lock:
            key = self._files_key()
            if params or self._cur is None or key != self._key:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        res = load_and_build(self.path, params)
                    except Exception as e:   # noqa: BLE001
                        raise ToolError(f"cannot load/build {os.path.basename(self.path)}: {type(e).__name__}: {e}")
                rec = ReviewRecord.load(self.files.review)
                stale = {}
                if res["intent"] is not None:
                    stale = rec.stale(res["intent"])      # no automatic baseline (#48)
                res["stale"] = stale
                res["summary"] = build_summary(res["design"], res["build"], res["intent"], stale, self.files.record)
                if params:
                    return res
                self._cur, self._key = res, key
            return self._cur


def build_server(design_path: str) -> MCPServer:
    ctx = DesignContext(design_path)
    server = MCPServer("dipm", instructions=INSTRUCTIONS)

    @server.tool()
    def get_design() -> dict:
        """The design: name, files, declared parameters (defaults, ranges, choices), and the
        ordered features with the intent nodes they serve."""
        from .server.serialize import design_info
        cur = ctx.current()
        info = design_info(cur["design"], ctx.path)
        return {"name": info["name"], "doc": info["doc"], "design_file": ctx.path,
                "intent_file": ctx.files.intent if os.path.exists(ctx.files.intent) else None,
                "patchable_files": sorted(ctx.files.patchable), "params": info["params"],
                "features": [{"id": f["id"], "op": f["op"], "tags": [t["text"] for t in f["tags"]]}
                             for f in info["features"]],
                "exports": sorted(cur["design"].exports)}

    @server.tool()
    def get_intent() -> dict:
        """The intent tree from <design>.intent.yaml (statements, checks, assumptions, nesting),
        its sha256, the stale nodes, and intent<->feature diagnostics."""
        cur = ctx.current()
        path = ctx.files.intent
        if not os.path.exists(path):
            return {"file": None, "note": "this design has no intent file; the tree is derived from feature tags",
                    "tree": cur["summary"]["diagnostics"]}
        return {"file": path, "sha256": file_sha256(path), "doc": cur["intent"], "errors": cur["intent_error"],
                "stale_nodes": sorted(cur["stale"]), "diagnostics": cur["summary"]["diagnostics"]}

    @server.tool()
    def build(params: dict | None = None) -> dict:
        """Build the current design (optionally with parameter overrides) and return the report
        summary: status, per-feature status and failed checks, interpretations, diagnostics."""
        try:
            return ctx.current(params or None)["summary"]
        except ToolError:
            raise
        except Exception as e:   # noqa: BLE001
            raise ToolError(str(e)) from None

    @server.tool()
    def why(face_id: int, params: dict | None = None) -> dict:
        """'Why is this here?' for face `face_id` (0-based, the GUI's face ids at the same
        parameters): the feature and role that created it, its intent tags and history."""
        cur = ctx.current(params or None)
        b = cur["build"]
        if b.shape is None:
            raise ToolError("the build has no geometry")
        faces = b.faces()
        if not 0 <= face_id < len(faces):
            raise ToolError(f"face_id must be in 0..{len(faces) - 1}")
        w = b.why(faces[face_id])
        return {"face_id": face_id, "text": str(w), "intent_nodes": w.intent_nodes(),
                "entries": [{"tag": str(e.tag), "feature": e.feature, "op": e.op, "lowered_from": e.lowered_from,
                             "intent": [str(t) for t in e.intent], "instance_intent": [str(t) for t in e.instance_intent]}
                            for e in w.entries]}

    def _stale_list(cur) -> list:
        nodes = (cur["summary"] or {}).get("features", [])
        out = []
        open_reqs = ctx.active_requests()
        for nid, info in sorted(cur["stale"].items()):
            feats = [f["id"] for f in nodes if nid in f["serves"] or
                     any(nid == t.node for t in _tags_of(cur["design"], f["id"]))]
            out.append({"id": nid, "statement": info["current"]["statement"],
                        "reviewed": info["reviewed"], "current": info["current"], "changed": info["changed"],
                        "new_node": info["new"], "features": feats,
                        "requests": [r for r in open_reqs if r.get("node") == nid]})
        return out

    @server.tool()
    def get_stale_nodes() -> dict:
        """Intent nodes whose content changed since their solution was last reviewed: what they
        said then and now, the features that realize them, and open 'Ask Claude' requests."""
        cur = ctx.current()
        return {"stale": _stale_list(cur), "requests": ctx.active_requests()}

    @server.tool()
    def get_requests(status: str = "open") -> dict:
        """'Ask Claude' requests from the GUI (status: open | running | proposed | failed | answered
        | all), each with the node, the designer's note and the intent change.  In a run started
        by dipm, the default lists that run's requests.  Proposals you submit are linked to the
        requests for the nodes they address (and to the run's requests)."""
        if status == "open" and ctx.store.run_requests:
            return {"requests": ctx.active_requests(), "run": ctx.store.run_id}
        return {"requests": ctx.store.requests(None if status == "all" else status)}

    @server.tool()
    def get_source() -> dict:
        """The design's patchable files with their text and sha256 (use these as base_hashes)."""
        out = {}
        for name, path in sorted(ctx.files.patchable.items()):
            if os.path.exists(path):
                text = read_text(path)
                out[name] = {"path": path, "sha256": file_sha256(path), "text": text}
        return {"files": out, "base_hashes": {n: f["sha256"] for n, f in out.items()}}

    @server.tool()
    def propose_patch(summary: str, rationale: str, files: dict[str, str], base_hashes: dict[str, str],
                      addresses_nodes: list[str] | None = None, revises: str | None = None,
                      requests: list[str] | None = None) -> dict:
        """Propose a change.  `files` maps a patchable path (e.g. "shelf_bracket.py") to its new
        full text or a unified diff; `base_hashes` maps the same paths to the sha256 you read
        with get_source.  Nothing is written: the proposal is evaluated in a temp copy and
        waits for the designer.  `requests`: the request ids it answers (also linked by node).
        Returns the evaluation (checks, semantic and text diffs)."""
        try:
            p = ctx.store.create(summary, rationale, files, base_hashes, addresses_nodes or [], revises, "mcp",
                                 requests=requests)
        except ProposalError as e:
            raise ToolError(str(e)) from None
        if p["status"] == "pending":
            p = ctx.store.evaluate(p["id"])
        return _proposal_view(p, full=True)

    @server.tool()
    def get_impact() -> dict:
        """Stage 1 of the loop: the purpose tree against its review baseline.  Every node, check,
        assumption and feature is classified changed | invalidated | survives, with reasons
        (meaning, supports, source, nesting, features), plus the open requests and loop state."""
        from .impact import impact_for
        cur = ctx.current()
        if cur["intent"] is None:
            raise ToolError("this design has no intent file")
        rep = impact_for(ctx.path, cur["intent"], cur["summary"])
        rep["requests"] = ctx.active_requests()
        rep["loop"] = ctx.store.loop_state()
        return rep

    @server.tool()
    def get_check_vocabulary() -> dict:
        """The computable check forms (relations, pack rules, fit against components, hand
        calculations, tool access): parameters, an example binding each, and how a binding reads.
        Also how values and references are written."""
        from .vocabulary import vocabulary
        return {"forms": vocabulary(),
                "values": {"reference": "an export name (cradle_seat, export:cradle_seat), a feature id "
                                        "(A.P.holes: hole centres and axes), or a structural reference "
                                        "(R.body.side(wall))",
                           "number": "'12', '12 mm' or an expression of parameters ('6*t')",
                           "range": "'6..14' (nominal = midpoint), '10 (6..14)', a number, or component:<id> for "
                                    "a component's mass",
                           "vector": "X, -Z or '0,0,1'", "component": "a component id from the intent file",
                           "meta": "made_by (model), status (proposed; only the designer accepts), note"},
                "where": "intent file: checks[].binding (a flow mapping of text values)"}

    @server.tool()
    def get_components() -> dict:
        """Component envelopes declared in the intent file (with ranges, source, review state) and
        the starter component pack (every entry a placeholder)."""
        from .components import components_of, errors, pack_listing
        cur = ctx.current()
        return {"declared": [c.as_dict() for c in components_of(cur["intent"]).values()],
                "errors": errors(cur["intent"]), "pack": pack_listing(),
                "format": "components: [{id, statement, shape: cylinder|box, diameter|size, length, mass, pack, "
                          "source, made_by: model, status: proposed}]; box size 'along x across x down' (mm)"}

    @server.tool()
    def propose_purposes(summary: str, rationale: str, intent_file: str, base_hash: str,
                         addresses_nodes: list[str] | None = None, revises: str | None = None,
                         requests: list[str] | None = None) -> dict:
        """Propose a revised purpose tree: the intent file only (full text or a unified diff
        against the sha256 from get_source).  Every added or changed check must be bound to a
        vocabulary form or marked descriptive; bindings and components are validated now.  The
        designer reviews it as a tree diff before any geometry exists."""
        try:
            p = ctx.store.create_purpose(summary, rationale, intent_file, base_hash, addresses_nodes or [], revises,
                                         requests=requests)
        except ProposalError as e:
            raise ToolError(str(e)) from None
        if p["status"] == "pending":
            p = ctx.store.evaluate(p["id"])
        return _proposal_view(p, full=True)

    @server.tool()
    def evaluate(files: dict[str, str] | None = None, label: str = "", purpose: str | None = None,
                 summary: str = "") -> dict:
        """Your inner loop: build candidate texts (design .py and/or intent file, full text or
        diff) without proposing them, optionally against a purpose proposal (its intent text is
        used).  Returns the tiered report: kernel, every intent check with margins or why it did
        not run, the sweep over the parameter ranges.  With `label` the attempt counts against
        that alternative's budget (default 6) and goes into its attempt log."""
        try:
            return ctx.store.evaluate_candidate(files or {}, label, purpose, summary)
        except ProposalError as e:
            raise ToolError(str(e)) from None

    @server.tool()
    def propose_alternatives(summary: str, rationale: str, alternatives: list[dict], base_hashes: dict[str, str],
                             addresses_nodes: list[str] | None = None, purpose: str | None = None,
                             requests: list[str] | None = None) -> dict:
        """Submit 2 or 3 geometry alternatives: [{label, summary, rationale, files: {path: text}}].
        Each is evaluated (checks with margins, which ran, did not run or failed, what it assumed)
        and carries its attempt log; with `purpose`, the purpose proposal's intent text goes with
        each one.  Nothing is written until the designer accepts one."""
        try:
            ps = ctx.store.create_alternatives(summary, rationale, alternatives, base_hashes, addresses_nodes or [],
                                               purpose, requests=requests)
        except ProposalError as e:
            raise ToolError(str(e)) from None
        out = []
        for p in ps:
            if p["status"] == "pending":
                p = ctx.store.evaluate(p["id"])
            out.append(_proposal_view(p, full=False))
        return {"group": ps[0]["group"], "alternatives": out}

    @server.tool()
    def list_proposals() -> dict:
        """Every proposal for this design with its status (pending, ready, failed, accepted,
        rejected, stale)."""
        return {"proposals": [_proposal_view(p) for p in ctx.store.list()]}

    @server.tool()
    def get_proposal_feedback(proposal_id: str | None = None) -> dict:
        """The designer's decisions and comments, for one proposal or all of them."""
        try:
            return {"feedback": ctx.store.feedback(proposal_id)}
        except ProposalError as e:
            raise ToolError(str(e)) from None

    return server


def _tags_of(design, fid: str) -> list:
    for f in design.features:
        if f.id == fid:
            out = list(f.tags)
            for ts in getattr(f, "instance_tags", None) or ():
                out += [t for t in (ts if isinstance(ts, (list, tuple)) else [ts]) if hasattr(t, "node")]
            return out
    return []


def _proposal_view(p: dict, full: bool = False) -> dict:
    ev = p.get("evaluation") or {}
    v = {"id": p["id"], "kind": p.get("kind", "patch"), "status": p["status"],
         "status_detail": p.get("status_detail", ""), "summary": p["summary"],
         "created": p["created"], "addresses_nodes": p.get("addresses_nodes", []), "revises": p.get("revises"),
         "files": sorted(p.get("patches", {})), "checks_pass": ev.get("ok") if ev else None,
         "failing_checks": ev.get("failing_checks") if ev else None}
    for k in ("group", "alternative", "purpose", "validation", "requests", "run"):
        if p.get(k) is not None:
            v[k] = p[k]
    if p.get("kind") == "geometry":
        v["attempts"] = p.get("attempts", [])
        after = (ev or {}).get("after") or {}
        v["status_tiers"] = (after.get("status") or {}).get("headline")
        v["checks"] = [{"id": c["id"], "state": c["state"], "plain": c.get("plain"), "reason": c.get("reason", ""),
                        "headline": c.get("headline")} for c in after.get("intent_checks") or []]
        v["assumed"] = (ev or {}).get("assumed", [])
    if p.get("kind") == "purpose" and ev.get("purpose"):
        v["checks"] = [{k: c[k] for k in ("id", "node", "statement", "form", "reads_as", "state", "reason")}
                       for c in ev["purpose"]["checks"]]
    if full and ev:
        v["evaluation"] = {k: ev[k] for k in ("ok", "failing_checks", "before", "after", "sweep", "semantic_diff",
                                               "text_diff", "changed_faces", "error", "ms") if k in ev}
    if full:
        v["feedback"] = p.get("feedback", [])
    return v


def main(design_path: str) -> int:
    server = build_server(design_path)
    server.run("stdio")
    return 0

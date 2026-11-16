"""The machine-written resolution record: assumed context and inferred print orientation
(docs/gui.md §8.2 3E.6 and 3E.10, §8.6 decision 3; tolerance-uncertainty.md §4.2).

`<design>.resolution.json` sits next to the interpretations lock and, like it, is written by
dipm, never by hand.  It holds two kinds of **model-made, unreviewed** assumptions:

* **Context defaults** (3E.6).  When the intent file's `context` does not state the process,
  material, layer height or nozzle, the FDM pack's defaults are assumed (PLA, FDM, 0.4 mm
  nozzle, 0.2 mm layers) and recorded here with `made_by: model, status: proposed`.  Context
  the designer wrote in the intent file is `made_by: user` and counts as reviewed.
* **Print orientation** (3E.10).  Candidate build directions are scored and the best one is
  recorded with its rationale, the runner-up and the numbers.  The renderer never picks a
  direction on its own: it draws layer lines along whatever this record (or the intent file)
  says.

**Nothing here writes the intent file.**  Accepting (`accept_context_ops`,
`accept_orientation_ops`) returns intent_store edit operations that the server applies with a
base-hash check, on the designer's click.  Once accepted, the value lives in the intent file
(`context:` keys; a root assumption with `about: print_orientation`) and inference never
replaces it.  Inference reruns only on request (`force=True`) or when its inputs change: the
key is the default build's role-geometry fingerprint plus the process.

Orientation scoring (all numbers in mm, mm², mm³, measured on the deterministic tessellation):
for each candidate "up" (the opposite of the outward normal of one of the largest planar faces
with distinct normals), every facet whose outward normal points down more steeply than the
pack's overhang limit (45° from vertical) and is not on the bed is an **overhang**; its
**support volume** is its projected area times its height above the bed (an upper bound: it
ignores part material underneath).  **Bed contact** is the area of facets lying on the bed.
Horizontal holes up to the pack's bridging limit are not counted (they bridge).  Cost =
overhang + w_support × support − w_bed × bed contact (placeholder weights, packs.FDM).
"""
from __future__ import annotations

import hashlib
import json
import math
import os

from . import packs
from .fileio import atomic_write

SUFFIX = ".resolution.json"
CONTEXT_KEYS = ("process", "material", "layer_height", "nozzle")
ORIENTATION_ABOUT = "print_orientation"


def path_for(design_file: str) -> str:
    return os.path.splitext(os.path.abspath(design_file))[0] + SUFFIX


# ---------------------------------------------------------------- the record file

class ResolutionRecord:
    """{"dipm_resolution": 1, "design", "context": {...}, "orientation": {...}}; stable key order,
    no timestamps (commit it next to the design, like the lock)."""

    def __init__(self, path: str | None, data: dict | None = None, exists: bool = False):
        self.path = path
        self.data = data or {}
        self.exists = exists

    @classmethod
    def load(cls, path: str | None) -> "ResolutionRecord":
        if not path or not os.path.exists(path):
            return cls(path, {}, False)
        try:
            with open(path, encoding="utf-8") as fh:
                return cls(path, json.load(fh), True)
        except (OSError, json.JSONDecodeError):
            return cls(path, {}, False)

    def text(self) -> str:
        return json.dumps({"dipm_resolution": 1, **{k: self.data[k] for k in ("design", "context", "orientation")
                                                    if k in self.data}}, indent=2, ensure_ascii=False) + "\n"

    def save(self) -> bool:
        """Write if the content changed.  Returns whether it wrote."""
        if not self.path:
            return False
        new = self.text()
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as fh:
                if fh.read() == new:
                    self.exists = True
                    return False
        atomic_write(self.path, new)
        self.exists = True
        return True


# ---------------------------------------------------------------- context (3E.6)

def context_items(intent_context: dict | None) -> dict:
    """key -> {value, made_by, status, reviewed, source} for the context the checks and the
    renderer use.  Stated keys (intent file) are the designer's; missing ones are assumed."""
    stated = {str(k): str(v) for k, v in (intent_context or {}).items()}
    out = {}
    for k, v in stated.items():
        out[k] = {"value": v, "made_by": "user", "status": "stated", "reviewed": True, "source": "intent file"}
    proc = packs.process(stated.get("process", packs.FDM["defaults"]["process"]))
    if "process" not in stated:
        out["process"] = _assumed(packs.FDM["defaults"]["process"])
    if proc is not None:
        for k in ("material", "layer_height", "nozzle"):
            if k not in stated:
                out[k] = _assumed(proc["defaults"][k])
    return {k: out[k] for k in sorted(out, key=lambda k: (CONTEXT_KEYS.index(k) if k in CONTEXT_KEYS else 9, k))}


def _assumed(value: str) -> dict:
    return {"value": value, "made_by": "model", "status": "proposed", "reviewed": False,
            "source": f"{packs.FDM['pack']} pack default ({packs.FDM['version']}), tolerance-uncertainty §4.2"}


def context_values(items: dict) -> dict:
    return {k: v["value"] for k, v in items.items()}


def context_summary(items: dict) -> str:
    """'PLA · FDM 0.2 mm' (the header chip, gui.md §8.3 item 4)."""
    v = context_values(items)
    proc = {"fdm_printing": "FDM"}.get(v.get("process", ""), v.get("process", "?"))
    layer = v.get("layer_height")
    return " · ".join(x for x in (v.get("material"), f"{proc} {layer}" if layer else proc) if x)


def accept_context_ops(items: dict, values: dict | None = None) -> list:
    """intent_store ops that write the (assumed or changed) context into the intent file."""
    fields = {k: str(v["value"]) for k, v in items.items() if k in CONTEXT_KEYS}
    fields.update({k: str(v) for k, v in (values or {}).items() if v not in (None, "")})
    return [{"op": "set_context", "fields": fields}]


# ---------------------------------------------------------------- orientation (3E.10)

def accepted_orientation(intent_plain: dict | None) -> dict | None:
    """The orientation the designer accepted (a root assumption `about: print_orientation`)."""
    for root in (intent_plain or {}).get("intents") or []:
        for a in root.get("assumptions") or []:
            if a.get("about") == ORIENTATION_ABOUT:
                try:
                    up = [float(x) for x in str(a.get("value", "")).split(",")]
                except ValueError:
                    continue
                if len(up) == 3:
                    return {"up": up, "label": a.get("statement", ""), "assumption_id": a["id"],
                            "made_by": a.get("made_by", "model"), "status": a.get("status", "accepted"),
                            "reviewed": a.get("status") == "accepted", "rationale": a.get("rationale", ""),
                            "source": "intent file"}
    return None


def orientation_key(build, ctx_values: dict) -> str:
    sig = build.signature
    blob = json.dumps({"roles": sig.roles_geom if sig else None, "VEFRSH": list(sig.VEFRSH) if sig else None,
                       "process": ctx_values.get("process"), "pack": packs.FDM["version"]}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _face_names(build) -> dict:
    """face index -> a readable name: a named export ('wall face'), else its genealogy tag."""
    from . import kernel as K
    faces = build.faces()
    smap = K.ShapeMap()
    for f in faces:
        smap.Add(f)
    names = {}
    for name, ref in build.design.exports.items():
        try:
            shapes = build.resolve(ref)
        except Exception:   # noqa: BLE001 - an export that does not resolve just has no name
            continue
        for s in shapes:
            i = smap.FindIndex(s) - 1
            if i >= 0 and i not in names:
                names[i] = name.replace("_", " ")
    for i, f in enumerate(faces):
        if i not in names:
            w = build.ledger.who(f)
            names[i] = str(w[0].tag) if w else f"face {i}"
    return names


def _bridgeable(build, up, bridge_max: float) -> set:
    """Faces of horizontal round holes small enough to bridge (cylinders/cones whose axis is
    perpendicular to `up` and whose extent across the axis is at most `bridge_max`)."""
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cone, GeomAbs_Cylinder
    from OCP.TopoDS import TopoDS
    out = set()
    for i, f in enumerate(build.faces()):
        s = BRepAdaptor_Surface(TopoDS.Face(f))
        t = s.GetType()
        if t not in (GeomAbs_Cylinder, GeomAbs_Cone):
            continue
        ax = (s.Cylinder() if t == GeomAbs_Cylinder else s.Cone()).Axis().Direction()
        if abs(ax.X() * up[0] + ax.Y() * up[1] + ax.Z() * up[2]) > 0.1:
            continue
        if t == GeomAbs_Cylinder:
            size = 2 * s.Cylinder().Radius()
        else:
            from . import kernel as K
            lo, hi = K.bbox(f)
            ext = [hi.x - lo.x, hi.y - lo.y, hi.z - lo.z]
            along = [abs(ax.X()), abs(ax.Y()), abs(ax.Z())]
            size = max(e for e, a in zip(ext, along) if a < 0.9)
        if size <= bridge_max + 1e-9:
            out.add(i)
    return out


def facet_table(shape):
    """(areas, unit normals, centroids, face id per facet) from the deterministic tessellation."""
    import numpy as np

    from .server.mesh import tessellate
    t = tessellate(shape)
    P, N, I, FR = t["positions"].reshape(-1, 3), t["normals"].reshape(-1, 3), t["indices"].reshape(-1, 3), \
        t["face_ranges"].reshape(-1, 2)
    a, b, c = P[I[:, 0]], P[I[:, 1]], P[I[:, 2]]
    cr = np.cross(b - a, c - a)
    area = 0.5 * np.linalg.norm(cr, axis=1)
    nv = N[I[:, 0]] + N[I[:, 1]] + N[I[:, 2]]          # vertex normals are outward (mesh.py)
    nn = np.linalg.norm(nv, axis=1)
    nn[nn == 0] = 1.0
    nv = nv / nn[:, None]
    face = np.zeros(len(I), dtype=int)
    for fid, (s, n) in enumerate(FR):
        face[s:s + n] = fid
    return area, nv, (a + b + c) / 3.0, face, P


def score_orientation(table, up, bridge: set, overhang_deg: float, w_support: float, w_bed: float) -> dict:
    import numpy as np
    area, nv, cen, face, P = table
    u = np.asarray(up, dtype=float)
    u = u / np.linalg.norm(u)
    h0 = float((P @ u).min())
    h = cen @ u - h0
    d = -(nv @ u)                         # downward component of the outward normal
    bed = (d > 0.999) & (h < 1e-3)
    lim = math.sin(math.radians(overhang_deg)) + 1e-6
    keep = np.array([f not in bridge for f in face])
    over = (d > lim) & ~bed & keep
    over_area = float(area[over].sum())
    support = float((area[over] * d[over] * h[over]).sum())
    bed_area = float(area[bed].sum())
    cost = over_area + w_support * support - w_bed * bed_area
    return {"up": [round(float(x), 6) + 0.0 for x in u], "overhang_mm2": round(over_area, 1),
            "support_mm3": round(support, 1), "bed_mm2": round(bed_area, 1), "cost": round(cost, 2),
            "overhang_faces": sorted({int(f) for f in face[over]})}


def infer_orientation(build, ctx_values: dict) -> dict | None:
    """Score candidate build directions for the assumed process (3E.10).  None if the process
    has no orientation model (only FDM in this iteration) or there is no solid."""
    from . import kernel as K
    pk = packs.process(ctx_values.get("process"))
    if pk is None or build.shape is None:
        return None
    faces = build.faces()
    planar = []
    for i, f in enumerate(faces):
        if K.is_planar(f):
            n = K.face_normal(f, build.shape)
            c = K.centroid(f)
            planar.append((K.area(f), i, (n.x, n.y, n.z), (c.x, c.y, c.z)))
    planar.sort(key=lambda x: (-round(x[0], 6), x[1]))
    names = _face_names(build)
    seen, cands = set(), []
    for area, i, n, _c in planar:
        key = tuple(round(v, 3) for v in n)
        if key in seen:
            continue
        seen.add(key)
        cands.append((i, n, area))
        if len(cands) >= pk["orientation"]["candidates"]:
            break
    table = facet_table(build.shape)
    P = table[4]

    def on_bed(n):
        """The largest planar face with outward normal n lying on the bed when up = -n (it
        names the candidate: "wall face down"); the candidate face itself if none does."""
        up = (-n[0], -n[1], -n[2])
        h0 = min(float(p[0] * up[0] + p[1] * up[1] + p[2] * up[2]) for p in P)
        best = None
        for area, i, m, c in planar:
            if all(abs(a - b) < 1e-3 for a, b in zip(m, n)) and abs(sum(a * u for a, u in zip(c, up)) - h0) < 1e-3:
                if best is None or area > best[0]:
                    best = (area, i)
        return best
    bridge_max = pk["horizontal_hole_max_d"]["value"]
    o = pk["orientation"]
    scored = []
    for i, n, area in cands:
        bed = on_bed(n)
        if bed is not None:
            area, i = bed
        up = [-n[0], -n[1], -n[2]]
        s = score_orientation(table, up, _bridgeable(build, up, bridge_max), pk["overhang_max_deg"]["value"],
                              o["w_support"], o["w_bed"])
        s.update({"down_face": names.get(i, f"face {i}"), "down_face_id": i, "down_face_area_mm2": round(area, 1)})
        scored.append(s)
    scored.sort(key=lambda s: (s["cost"], s["down_face_id"]))
    best = scored[0]
    second = scored[1] if len(scored) > 1 else None
    rationale = (f"Print with the {best['down_face']} down: {best['overhang_mm2']:,.0f} mm² overhang beyond "
                 f"{pk['overhang_max_deg']['value']:g}°, {best['support_mm3']:,.0f} mm³ support, "
                 f"{best['bed_mm2']:,.0f} mm² on the bed")
    if second:
        rationale += (f"; runner-up {second['down_face']} down: {second['overhang_mm2']:,.0f} mm² overhang, "
                      f"{second['support_mm3']:,.0f} mm³ support, {second['bed_mm2']:,.0f} mm² on the bed")
    rationale += (f". Horizontal holes up to Ø{bridge_max:g} mm bridge and are not counted; cost = overhang + "
                  f"{o['w_support']:g}×support − {o['w_bed']:g}×bed contact (placeholder weights)")
    return {"up": best["up"], "label": f"Print with the {best['down_face']} down", "chosen": best,
            "runner_up": second, "candidates": scored, "rationale": rationale, "made_by": "model",
            "status": "proposed", "reviewed": False, "pack": f"{pk['pack']}@{pk['version']}"}


def orientation_for(build, intent_plain: dict | None, record: ResolutionRecord | None, ctx_values: dict,
                    key_build=None, force: bool = False) -> tuple[dict | None, bool]:
    """(orientation in use, record changed?).  An accepted orientation in the intent file always
    wins and is never re-inferred.  Otherwise the record's inference is used while its key
    (the default build's geometry + process) matches; it is re-inferred when the key changed,
    when there is none, or on request (`force`).  `key_build` is the build the key and the
    inference come from (the defaults build); it falls back to `build`."""
    acc = accepted_orientation(intent_plain)
    kb = key_build or build
    if acc is not None:
        return {**acc, "inference": (record.data.get("orientation") if record else None)}, False
    if packs.process(ctx_values.get("process")) is None or kb is None or kb.shape is None:
        return None, False
    key = orientation_key(kb, ctx_values)
    cur = (record.data.get("orientation") if record else None) or None
    if cur and cur.get("key") == key and not force:
        return {**cur, "source": "resolution record"}, False
    inf = infer_orientation(kb, ctx_values)
    if inf is None:
        return None, False
    inf["key"] = key
    changed = False
    if record is not None:
        record.data["orientation"] = inf
        changed = True
    return {**inf, "source": "resolution record" if record is not None and record.path else "inferred in memory"}, changed


def accept_orientation_ops(orientation: dict, root_id: str = "R") -> list:
    """intent_store ops that record the orientation as an accepted root assumption."""
    up = ",".join(f"{v:g}" for v in orientation["up"])
    return [{"op": "add_assumption", "id": root_id, "assumption": {
        "statement": orientation.get("label") or f"Print with up = ({up})",
        "made_by": "model", "rationale": orientation.get("rationale", ""), "status": "accepted",
        "about": ORIENTATION_ABOUT, "value": up}}]


def record_context(record: ResolutionRecord, items: dict) -> bool:
    """Store the assumed (unreviewed) context items in the record.  Returns whether it changed."""
    assumed = {k: {kk: v[kk] for kk in ("value", "made_by", "status", "source")}
               for k, v in items.items() if not v["reviewed"]}
    new = {"assumed": assumed}
    if record.data.get("context") != new:
        record.data["context"] = new
        return True
    return False

"""Component envelopes (docs/purpose-loop.md §3 step 4).

Off-the-shelf things a design must fit (a fishing rod, a reel) are **component envelopes**:
simple parametric solids with ranges.  They are declared in the intent file's top-level
`components:` list, either from a component pack entry (`pack: fishing_rod_blank`, a
hand-written starter set in `packs.COMPONENTS`, every value a placeholder) or written out with
their source stated (a model-made, unreviewed assumption until the designer accepts it):

    components:
      - {id: rod, statement: Rod blank where the holder grips it, shape: cylinder,
         diameter: "6..14 mm", length: "1800 mm", mass: "0.2..1 kg", pack: fishing_rod_blank,
         source: "packs.COMPONENTS (placeholder)", made_by: model, status: proposed}
      - {id: reel, statement: Spinning reel under the rod, shape: box,
         size: "90..140 x 60..90 x 90..130 mm", made_by: model, status: proposed}

A value is `"nom"`, `"lo..hi"` (nominal = midpoint) or `"nom (lo..hi)"`, with an optional unit.
A box `size` is `along x across x down`: along the axis of the part it hangs from, across it,
and down from that axis (negative `down` = above).  Checks bind to components by id
(`vocabulary.py`: holds_cylinder, retention, clears_box, load); the poses come from those
checks, and the GUI ghosts the components there.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import packs
from .quantity import Quantity

SHAPES = ("cylinder", "box")
_NUM = r"[-+]?\d+(?:\.\d+)?"
_RANGE_RE = re.compile(rf"^\s*(?:(?P<nom>{_NUM})\s*\(\s*(?P<lo1>{_NUM})\s*\.\.\s*(?P<hi1>{_NUM})\s*\)"
                       rf"|(?P<lo2>{_NUM})\s*\.\.\s*(?P<hi2>{_NUM})|(?P<one>{_NUM}))\s*(?P<unit>[a-zA-Z°]*)\s*$")


class ComponentError(ValueError):
    pass


def parse_range(text, unit: str = "", label: str = "", source: str = "", made_by: str = "model",
                placeholder: bool = False) -> Quantity:
    """'6..14 mm' -> Quantity(10, 6, 14); '10 (6..14)'; '12'.  Raises ComponentError."""
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        v = float(text)
        return Quantity(v, v, v, unit, source, made_by, label, placeholder)
    m = _RANGE_RE.match(str(text or ""))
    if not m:
        raise ComponentError(f"{label or 'value'}: '{text}' is not a number or range (e.g. '10', '6..14 mm', "
                             "'10 (6..14) mm')")
    u = m.group("unit") or unit
    if m.group("one") is not None:
        v = float(m.group("one"))
        return Quantity(v, v, v, u, source, made_by, label, placeholder)
    if m.group("nom") is not None:
        nom, lo, hi = float(m.group("nom")), float(m.group("lo1")), float(m.group("hi1"))
    else:
        lo, hi = float(m.group("lo2")), float(m.group("hi2"))
        nom = 0.5 * (lo + hi)
    if lo > hi:
        lo, hi = hi, lo
    if not lo <= nom <= hi:
        raise ComponentError(f"{label or 'value'}: nominal {nom} outside {lo}..{hi}")
    return Quantity(nom, lo, hi, u, source, made_by, label, placeholder)


def _pack_q(entry: dict, label: str, source: str) -> Quantity:
    return Quantity(entry["value"], entry["lo"], entry["hi"], entry.get("unit", ""), source, "pack default", label,
                    bool(entry.get("placeholder", True)))


@dataclass
class Component:
    id: str
    shape: str
    statement: str = ""
    dims: dict = field(default_factory=dict)        # name -> Quantity (diameter, length, along, across, down)
    mass: Quantity | None = None
    pack: str = ""
    source: str = ""
    made_by: str = "model"
    status: str = "proposed"
    placeholder: bool = True

    @property
    def reviewed(self) -> bool:
        return self.status == "accepted"

    def as_dict(self) -> dict:
        return {"id": self.id, "shape": self.shape, "statement": self.statement,
                "dims": {k: q.as_dict() for k, q in self.dims.items()},
                "mass": self.mass.as_dict() if self.mass else None, "pack": self.pack, "source": self.source,
                "made_by": self.made_by, "status": self.status, "reviewed": self.reviewed,
                "placeholder": self.placeholder}


def parse_component(c: dict) -> Component:
    """A plain intent-file component entry -> Component (dims as Quantities)."""
    cid = str(c.get("id") or "")
    shape = str(c.get("shape") or "")
    pack_name = str(c.get("pack") or "")
    pk = packs.COMPONENTS.get(pack_name) if pack_name else None
    if pack_name and pk is None:
        raise ComponentError(f"component {cid}: no pack entry '{pack_name}' (known: {', '.join(sorted(packs.COMPONENTS))})")
    if not shape and pk is not None:
        shape = pk["shape"]
    if shape not in SHAPES:
        raise ComponentError(f"component {cid}: shape must be one of {', '.join(SHAPES)}; got '{shape}'")
    made_by = str(c.get("made_by") or "model")
    src = str(c.get("source") or (f"packs.COMPONENTS.{pack_name}" if pk else ""))
    dims: dict = {}
    placeholder = bool(pk is not None)
    if shape == "cylinder":
        for k in ("diameter", "length"):
            if c.get(k):
                dims[k] = parse_range(c[k], "mm", f"{cid} {k}", src, made_by)
            elif pk is not None and k in pk:
                dims[k] = _pack_q(pk[k], f"{cid} {k}", src)
        if "diameter" not in dims:
            raise ComponentError(f"component {cid}: a cylinder needs a diameter (or a pack)")
        dims.setdefault("length", Quantity(1000.0, 1000.0, 1000.0, "mm", src, made_by, f"{cid} length"))
    else:
        if c.get("size"):
            parts = [p.strip() for p in re.split(r"\s*[x×]\s*", str(c["size"]).replace("mm", "").strip())]
            if len(parts) != 3:
                raise ComponentError(f"component {cid}: size must be 'along x across x down' (mm); got '{c['size']}'")
            for k, t in zip(("along", "across", "down"), parts):
                dims[k] = parse_range(t, "mm", f"{cid} {k}", src, made_by)
        elif pk is not None:
            for k in ("along", "across", "down"):
                dims[k] = _pack_q(pk["size"][k], f"{cid} {k}", src)
        else:
            raise ComponentError(f"component {cid}: a box needs size 'along x across x down' (or a pack)")
    mass = None
    if c.get("mass"):
        mass = parse_range(c["mass"], "kg", f"{cid} mass", src, made_by)
    elif pk is not None and "mass" in pk:
        mass = _pack_q(pk["mass"], f"{cid} mass", src)
    return Component(cid, shape, str(c.get("statement") or ""), dims, mass, pack_name, src, made_by,
                     str(c.get("status") or "proposed"), placeholder)


def components_of(intent_plain: dict | None) -> dict:
    """id -> Component for a plain intent document; entries that fail to parse are skipped
    here (the schema reports them, `errors()` lists them)."""
    out = {}
    for c in (intent_plain or {}).get("components") or []:
        try:
            comp = parse_component(c)
        except ComponentError:
            continue
        out[comp.id] = comp
    return out


def errors(intent_plain: dict | None) -> list:
    out = []
    for c in (intent_plain or {}).get("components") or []:
        try:
            parse_component(c)
        except ComponentError as e:
            out.append(str(e))
    return out


def pack_listing() -> list:
    """The starter component pack, for `get_components` (every entry a placeholder)."""
    out = []
    for name, e in sorted(packs.COMPONENTS.items()):
        d = {"pack": name, "shape": e["shape"], "label": e["label"], "placeholder": True,
             "note": e.get("note") or "not from a cited source"}
        if e["shape"] == "cylinder":
            d["dims"] = {k: {kk: e[k][kk] for kk in ("value", "lo", "hi", "unit")} for k in ("diameter", "length")}
        else:
            d["dims"] = {k: {kk: v[kk] for kk in ("value", "lo", "hi", "unit")} for k, v in e["size"].items()}
        if "mass" in e:
            d["mass"] = {kk: e["mass"][kk] for kk in ("value", "lo", "hi", "unit")}
        out.append(d)
    return out

"""Placeholder rule-pack data (GUI iteration 3, docs/gui.md §8.2 3E.2, 3E.6, 3E.7).

**Every number in this module is a PLACEHOLDER unless its entry says otherwise.**  None of it
comes from a cited source: it stands in for the versioned, sourced rule packs of
architecture §4.6 (`fdm_printing`, `materials`, `fasteners`, `anchors`) so that checks have
ranges to propagate and the renderer has a process to draw.  Like the fastener stand-ins
(NOTES DECISIONS #9), replace each value with pack data that carries a citation before
trusting a margin computed from it.  NOTES DECISIONS #58 lists them.

The one source of truth rule (tolerance-uncertainty.md §4.2) holds here: the same process
entry gives the checks their tolerances *and* the GUI its layer pitch, extrusion width and
detail flags (`appearance()`), so the render cannot disagree with the checks.

Entries that are *not* placeholders are marked `"placeholder": False` with what they are:
standard gravity (an SI-defined constant) and the major diameters of numbered machine
screws (ASME B1.1: #6 = 0.138 in, #8 = 0.164 in, #10 = 0.190 in; M sizes are nominal).
"""
from __future__ import annotations

PLACEHOLDER_NOTE = ("placeholder value, not from a cited source (src/dipm/packs.py; NOTES DECISIONS #58); "
                    "replace with sourced pack data before relying on it")

G_STANDARD = 9.80665        # m/s², standard gravity (SI definition; not a placeholder)


def _v(value, lo=None, hi=None, unit="", note: str = PLACEHOLDER_NOTE, placeholder: bool = True) -> dict:
    """A pack value with an optional range [lo, hi] (worst-case propagation, tolerance §2)."""
    return {"value": value, "lo": value if lo is None else lo, "hi": value if hi is None else hi,
            "unit": unit, "placeholder": placeholder, "note": note}


# ---------------------------------------------------------------- processes

FDM = {
    "pack": "fdm_printing",
    "version": "0.0-placeholder",
    # tolerance-uncertainty §4.2 default context: PLA on a standard FDM printer
    "defaults": {"process": "fdm_printing", "material": "PLA", "nozzle": "0.4 mm", "layer_height": "0.2 mm"},
    # ± process variation of printed geometry (not a bias: as-made prediction is out of scope, gui.md §8.5)
    "position_tolerance": _v(0.1, unit="mm"),        # relative position of two printed features
    "dimension_tolerance": _v(0.15, unit="mm"),      # a printed wall / thickness (tolerance §2 example)
    "extrusion_width_factor": _v(1.125),             # extrusion width = factor × nozzle (0.45 mm on 0.4)
    "overhang_max_deg": _v(45.0, unit="deg"),        # R.c2: printable without supports
    "bridge_max_mm": _v(10.0, unit="mm"),            # horizontal holes up to this Ø bridge without support
    "across_layer_strength_ratio": _v(0.5, 0.4, 0.6),   # R.a2 "≈ 50 % of in-layer"; range is a placeholder
    # print-orientation scoring (3E.10): cost = overhang mm² + w_support × support mm³ − w_bed × bed mm²
    "orientation": {"candidates": 6, "w_support": 0.02, "w_bed": 0.1, "placeholder": True},
    # process appearance (3E.7): shading only (normal/roughness), never colour
    "appearance": {"top_line_angle_deg": 45.0,
                   "flags": {"layer_lines": True, "top_lines": True, "z_seam": False, "elephant_foot": False,
                             "support_scars": False}},
}

PROCESSES = {"fdm_printing": FDM}
LAYER_HEIGHTS = ("0.1 mm", "0.15 mm", "0.2 mm", "0.28 mm")
NOZZLES = ("0.25 mm", "0.4 mm", "0.6 mm")

# ---------------------------------------------------------------- materials

MATERIALS = {
    # in-layer tensile strength of printed parts (MPa) and surface roughness for the renderer (0..1)
    "PLA": {"tensile_mpa": _v(50.0, 40.0, 60.0, "MPa"), "roughness": 0.62, "label": "PLA"},
    "PETG": {"tensile_mpa": _v(45.0, 38.0, 52.0, "MPa"), "roughness": 0.38, "label": "PETG"},
    "ABS": {"tensile_mpa": _v(35.0, 30.0, 40.0, "MPa"), "roughness": 0.55, "label": "ABS"},
}

# ---------------------------------------------------------------- wall anchors (context `install`)

ANCHORS = {
    # pull-out capacity of one wall fixing, along the screw axis
    "drywall with anchors": {"pullout_n": _v(200.0, 150.0, 250.0, "N"), "label": "drywall anchor"},
    "wood stud": {"pullout_n": _v(800.0, 600.0, 1000.0, "N"), "label": "wood screw in a stud"},
}
DEFAULT_INSTALL = "drywall with anchors"

# ---------------------------------------------------------------- screws (reference objects)

SCREW_MAJOR_MM = {   # not placeholders: ASME B1.1 numbered sizes (inch × 25.4), ISO nominal M sizes
    "#6": 3.505, "#8": 4.166, "#10": 4.826, "M3": 3.0, "M4": 4.0, "M5": 5.0,
}
SCREW_REFERENCE_LENGTH_MM = _v(25.0, unit="mm")   # length of the ghosted reference screw (placeholder)

# ---------------------------------------------------------------- human scale (reference objects)

# ID-1 card: ISO/IEC 7810 (85.60 × 53.98 mm, 3.18 mm corner radius); not a placeholder
ID1_CARD_MM = {"width": 85.60, "height": 53.98, "corner_radius": 3.18, "thickness": 0.76, "placeholder": False,
               "note": "ISO/IEC 7810 ID-1"}
# Fingertip and hand: placeholders PENDING an ANSUR II lookup (Gordon et al. 2014); not yet verified
FINGERTIP_MM = {"breadth": 16.0, "length": 25.0, "placeholder": True,
                "note": "placeholder; to be sized from ANSUR II (not yet looked up)"}
HAND_MM = {"length": 190.0, "breadth": 85.0, "placeholder": True,
           "note": "placeholder; to be sized from ANSUR II (not yet looked up)"}

# ---------------------------------------------------------------- margin states

THIN_FRACTION = 0.10   # a margin below 10 % of the limit is "thin" (placeholder policy, NOTES #59)


def mm(text) -> float:
    """'0.2 mm' -> 0.2 (context values are text in the intent file)."""
    s = str(text).strip().lower().replace("mm", "").strip()
    return float(s)


def process(name: str | None) -> dict | None:
    return PROCESSES.get(str(name or ""))


def material(name: str | None) -> dict | None:
    return MATERIALS.get(str(name or "").upper()) or MATERIALS.get(str(name or ""))


def appearance(context: dict) -> dict | None:
    """What the renderer needs from the process pack (3E.7): layer pitch, extrusion width,
    detail flags and the material's roughness.  None for processes without appearance data."""
    p = process(context.get("process"))
    if p is None:
        return None
    try:
        layer = mm(context.get("layer_height", p["defaults"]["layer_height"]))
        nozzle = mm(context.get("nozzle", p["defaults"]["nozzle"]))
    except ValueError:
        layer, nozzle = mm(p["defaults"]["layer_height"]), mm(p["defaults"]["nozzle"])
    m = material(context.get("material")) or MATERIALS["PLA"]
    return {"process": p["pack"], "pack_version": p["version"], "layer_pitch": layer,
            "extrusion_width": round(nozzle * p["extrusion_width_factor"]["value"], 4), "nozzle": nozzle,
            "top_line_angle_deg": p["appearance"]["top_line_angle_deg"], "flags": dict(p["appearance"]["flags"]),
            "roughness": m["roughness"], "material": m["label"], "placeholder": True}

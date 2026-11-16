"""Rod holder: seeded from the shelf bracket (examples/shelf_bracket.py) on 2026-11-16.

The author changed the bracket's root purpose to "Support a fishing rod on a wall"
(docs/purpose-loop.md §4).  That edit lives in `rod_holder.intent.yaml`; this program is
still the bracket's geometry, unchanged except for its name, so the purpose -> geometry loop
(dipm mcp: get_impact, propose_purposes, evaluate, propose_alternatives) has something to
start from.  The review record `rod_holder.review.json` is the bracket's, so the impact report
compares the new purpose with the shelf purposes the solution was reviewed against.

Run:  .venv/bin/python -m dipm build examples/rod_holder.py
"""
from dipm import (Design, X, Y, Z, centered_on, centerline, clearance, clearance_diameter, countersink,
                  distribute, edge_distance, exactly, face_point, intent, plain, tool_access_radius)
from dipm.checks import cantilever_load, overhang, tool_access
from dipm.intent_layer import TOOL_ACCESS_DIAMETER
from dipm.sketch import YZ, Profile


def make_design(shelf_hole_u: float = 0.75) -> Design:
    """Build the bracket design.  `shelf_hole_u` is an intent constant (B.1 "toward the
    front", architecture §8.5 `u=0.75`), exposed only so tests can build the spike-01
    negative control (u=0.4 lands the shelf screw on the gusset)."""
    d = Design("rod_holder", doc="seeded from the shelf bracket; purpose changed to a fishing rod")
    d.use_intent(__file__)     # intent tree: rod_holder.intent.yaml (statements, checks, assumptions)

    # --- R parameters: the only literals (architecture §8.1) -----------------------------
    shelf_depth = d.param("shelf_depth", 200.0, range=(180.0, 300.0), doc="shelf depth the arm supports")
    t = d.param("t", 5.0, range=(4.0, 8.0), doc="material thickness")
    screw = d.param("screw", "#8", choices=("#6", "#8", "#10"), unit="", doc="screw size (A.P and B.1)")

    leg = 0.75 * shelf_depth
    arm = 0.8 * shelf_depth
    width = 6 * t
    gusset_size = 0.4 * shelf_depth

    # --- R skeleton: L profile on the side plane, symmetric extrude ------------------------
    L = Profile(
        YZ,
        points={"wall_bot": (0.0, 0.0), "leg_bot": (t, 0.0), "inner": (t, leg - t),
                "arm_under_tip": (arm, leg - t), "arm_top_tip": (arm, leg), "wall_top": (0.0, leg)},
        edge_names={"wall_bot-leg_bot": "leg_end", "leg_bot-inner": "mount", "inner-arm_under_tip": "arm_under",
                    "arm_under_tip-arm_top_tip": "arm_tip", "arm_top_tip-wall_top": "shelf",
                    "wall_top-wall_bot": "wall"},
        winding="ccw", name="L")
    body = d.extrude("R.body", L, distance=width, symmetric=True, tags=intent("R", "skeleton"))

    wall_face = body.side("wall")
    mount_face = body.side("mount")
    shelf_face = body.side("shelf")
    inner_corner = body.lateral_edge("inner", card=exactly(2))   # split in two by the gusset

    # --- C gusset (placed before the screw pattern, which must avoid it: R.c4) -------------
    G = Profile(
        YZ,
        points={"corner": (t, leg - t), "down": (t, leg - t - gusset_size), "out": (t + gusset_size, leg - t)},
        edge_names={"corner-down": "on_mount", "down-out": "hypotenuse", "out-corner": "on_arm"},
        winding="ccw", name="gusset")
    gusset = d.extrude("C.gusset", G, distance=t, symmetric=True, mode="add",
                       tags=(intent("C", "gusset"),))
    gusset_footprint_bottom = gusset.lateral_edge("down")

    # --- A.P wall screw pattern (§8.3 consolidation; §8.4a option 2: below the gusset) -----
    screw_zone = centerline(mount_face, Z).before(gusset_footprint_bottom, clearance=tool_access_radius(screw))
    wall_pts = distribute(along=screw_zone, count=2,
                          inset=(edge_distance(clearance_diameter(screw)), 0.0))   # spread as far as allowed
    holes = d.hole("A.P.holes", on=mount_face, at=wall_pts, spec=countersink(screw),
           tags=(intent("A.P", "pattern"), intent("A", "wall_mount")),
           instance_tags=["A.P.1", "A.P.2"])

    # --- A.3 cable pass-through: centred on the plate, independent of the pattern ----------
    # Which "centre" is interpreted (DECISIONS #8 -> #24): the face centroid lies under the
    # gusset and is eliminated; the exposed-region midpoint is the plate below the gusset.
    d.hole("A.3.cable", on=mount_face, at=centered_on(mount_face), spec=plain(8.0),
           tags=(intent("A.3", "hole"), intent("A", "wall_mount")))

    # --- B.1 shelf screw: toward the front, centred across the width, through the arm ------
    d.hole("B.1.screw", on=shelf_face, at=face_point(shelf_face, along=(Y, shelf_hole_u), across=(X, 0.5)),
           spec=clearance(screw),
           tags=(intent("B.1", "hole"), intent("B", "shelf_support")))

    # --- R.c2 printable: inner-corner fillet, radius follows t -----------------------------
    fillet = d.fillet("R.fillet", inner_corner, radius=t, tags=intent("R", "fillet"))

    # --- named exports (architecture §2.3), watched by the stability harness ---------------
    d.export("wall_face", wall_face)
    d.export("mount_face", mount_face)
    d.export("shelf_face", shelf_face)
    d.export("gusset_hyp", gusset.side("hypotenuse"))
    d.export("corner_blend", fillet.blend(of=inner_corner, card=exactly(2)))

    # --- executable intent checks (docs/gui.md §8.2 3E.3): statements live in the intent file,
    # the grounding lives here.  R.c1 is expected to FAIL (architecture §8.4a); it is reported,
    # not tuned away.
    d.check("R.c1", cantilever_load(            # rung 2 hand calc: pivot model, anchors, arm bending
        load_kg=20.0, load_range=(0.0, 30.0),   # architecture §8.1 `load: 20 kg`; R.a1 range (tolerance §2)
        safety_factor=2.0,                      # "safety factor ≥ 2" in the R.c1 statement
        anchors=holes, section_width=width, section_depth=t, section_at=t + gusset_size,
        involves=(body.side("shelf"), body.side("arm_under"), body.side("arm_tip"))))
    d.check("R.c2", overhang())                 # in the inferred / accepted print orientation (3E.10)
    d.check("R.c4", tool_access(holes, diameter=TOOL_ACCESS_DIAMETER, length=150.0,
                                involves=(gusset.side("hypotenuse"),)))
    d.use_lock(__file__)       # resolved interpretations: rod_holder.interpretations.json
    return d


design = make_design()

if __name__ == "__main__":
    from dipm.report import build_report
    print(build_report(design.build(on_fail="record")))

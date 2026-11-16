"""Rod holder, alternative "V-saddle": a 100° V-notch that centres every blank, screws below it.

One of a pair of wall holders for a fishing rod lying parallel to the wall (rod_holder.intent.yaml,
R.a4).  Axes: X along the rod (symmetric about X=0), Y out from the wall (wall face at Y=0), Z up.
The YZ profile is extruded along X.  The print orientation is dipm's inference (model-made, not
reviewed): with a 90° V and an 8 mm arm it chose "wall face down", which put the arm's bending
across the layers and failed C.c1 (attempt 1).  This version is sized to pass in either orientation:
a 12 mm arm (C.c1 holds at the worst across-layer ratio, 0.3) and flanks 40° from vertical, inside the
45° overhang rule if it is printed wall-down (R.c2).

    R    Support a fishing rod on a wall   -> R.body
    ├─ A.P  Wall screw pattern             -> A.P.holes, below the saddle by the tool-access radius
    ├─ B    Cradle: holds the rod blank    -> the V: flanks 50° from horizontal, apex under the rod's axis
    └─ C    Arm: carries the cradle        -> the solid under the V (C.c1 checks its root)

A V seats every diameter on the same vertical line through the apex, so the reel's distance from
the wall (B.c5) does not depend on the blank, and each blank touches two lines, not a flat floor.
The rim is `depth` above the apex; a blank of radius r rests 1.31·r above the apex, so it needs
about depth − 0.31·r of lift to leave (B.c2).
"""
from dipm import Design, X, Z, centerline, clearance_diameter, countersink, distribute, edge_distance, intent
from dipm.intent_layer import tool_access_radius
from dipm.sketch import YZ, Profile


def make_design() -> Design:
    d = Design("rod_holder", doc="V-saddle: 100° V-notch on a solid arm, screws below it")
    d.use_intent(__file__)
    t = d.param("t", 5.0, range=(4.0, 6.0), doc="wall plate thickness")
    width = d.param("width", 24.0, range=(20.0, 30.0), doc="holder width along the rod")
    arm_t = d.param("arm_t", 12.0, range=(10.0, 14.0), doc="arm thickness at the root and under the apex")
    standoff = d.param("standoff", 55.0, range=(50.0, 65.0), doc="wall to the V's apex (the rod axis line)")
    depth = d.param("depth", 14.0, range=(12.0, 18.0), doc="rim height above the apex")
    screw = d.param("screw", "#8", choices=("#6", "#8", "#10"), unit="", doc="wall screw size")
    apex, rim, top = 70.0, 4.0, 96.0
    spread = 1.19                       # rim offset per mm of depth: a 100° V (flanks 40° from vertical)

    P = Profile(
        YZ,
        points={"wall_bot": (0.0, 0.0), "plate_bot": (t, 0.0), "arm_root": (t, apex - arm_t),
                "tip_lo": (standoff + spread * depth + rim, apex - arm_t),
                "tip_hi": (standoff + spread * depth + rim, apex + depth),
                "rim_front": (standoff + spread * depth, apex + depth), "v_apex": (standoff, apex),
                "rim_back": (standoff - spread * depth, apex + depth), "plate_top": (t, top), "wall_top": (0.0, top)},
        edge_names={"wall_bot-plate_bot": "bottom", "plate_bot-arm_root": "plate_front",
                    "arm_root-tip_lo": "arm_under", "tip_lo-tip_hi": "nose", "tip_hi-rim_front": "rim_top",
                    "rim_front-v_apex": "flank_front", "v_apex-rim_back": "flank_back",
                    "rim_back-plate_top": "back_slope", "plate_top-wall_top": "top", "wall_top-wall_bot": "wall"},
        winding="ccw", name="saddle")
    body = d.extrude("R.body", P, distance=width, symmetric=True, tags=intent("R", "skeleton"))

    plate_front = body.side("plate_front")
    zone = centerline(plate_front, Z).before(body.side("arm_under"), clearance=tool_access_radius(screw) + 3.0)
    pts = distribute(along=zone, count=2, inset=(edge_distance(clearance_diameter(screw)) + 2.0, 0.0))
    d.hole("A.P.holes", on=plate_front, at=pts, spec=countersink(screw),
           tags=(intent("A.P", "pattern"), intent("A", "wall_mount")), instance_tags=["A.P.1", "A.P.2"])

    # B: the blank only meets rounded edges (B.c3); the apex is rounded too, below every blank's contact
    d.fillet("B.round", [body.lateral_edge(p) for p in ("rim_front", "rim_back", "tip_hi")], radius=2.0,
             tags=intent("B", "rounded rims"))
    d.fillet("B.apex", body.lateral_edge("v_apex"), radius=1.5, tags=intent("B", "rounded apex"))

    d.export("wall_face", body.side("wall"))
    d.export("cradle_seat", body.side("flank_front"))
    d.export("plate_front", plate_front)
    d.use_lock(__file__)
    return d


design = make_design()

if __name__ == "__main__":
    from dipm.report import build_report
    print(build_report(design.build(on_fail="record")))

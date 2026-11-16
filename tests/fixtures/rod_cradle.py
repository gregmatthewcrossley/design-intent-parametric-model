"""Test fixture: a U-cradle rod holder (iteration 4 vocabulary tests).

YZ profile extruded symmetric along X (the rod axis): a wall plate (y 0..t, z 0..top), an arm
along the bottom of the cradle at z = floor-a..floor, and a lip at the arm's end rising `lip`
above the floor.  Two countersunk wall screws in the plate below the arm, one horizontal
hole through the lip (for the bridging form).  Every geometric quantity is a parameter, so
tests can make each form pass or fail by construction.

    escape lift toward the lip = lip;  toward the plate = top − floor
"""
from dipm import Design, X, Z, countersink, face_point, intent, plain
from dipm.sketch import YZ, Profile


def make_design(t: float = 5.0, width: float = 20.0, floor: float = 60.0, a: float = 6.0, gap: float = 20.0,
                tl: float = 5.0, lip: float = 12.0, top: float = 80.0, lip_hole: float = 4.0, screw_u=(0.2, 0.6)):
    d = Design("rod_cradle")
    y2 = t + gap + tl
    P = Profile(YZ, points={"o": (0.0, 0.0), "b": (t, 0.0), "arm_lo": (t, floor - a), "tip_lo": (y2, floor - a),
                            "tip_hi": (y2, floor + lip), "lip_in_hi": (y2 - tl, floor + lip),
                            "lip_in_lo": (y2 - tl, floor), "floor_in": (t, floor), "back_top": (t, top),
                            "wall_top": (0.0, top)},
                edge_names={"o-b": "bottom", "b-arm_lo": "front_low", "arm_lo-tip_lo": "arm_under",
                            "tip_lo-tip_hi": "lip_out", "tip_hi-lip_in_hi": "lip_top",
                            "lip_in_hi-lip_in_lo": "lip_in", "lip_in_lo-floor_in": "floor",
                            "floor_in-back_top": "back", "back_top-wall_top": "top", "wall_top-o": "wall"},
                winding="ccw", name="cradle")
    body = d.extrude("R.body", P, distance=width, symmetric=True, tags=intent("R", "skeleton"))
    wall = body.side("wall")
    front = body.side("front_low")
    pts = [face_point(front, along=(Z, u), across=(X, 0.5)) for u in screw_u]
    d.hole("A.P.holes", on=front, at=pts, spec=countersink("#8"), tags=(intent("A.P", "pattern"),),
           instance_tags=["A.P.1", "A.P.2"])
    if lip_hole:
        d.hole("B.lip", on=body.side("lip_out"), at=face_point(body.side("lip_out"), along=(Z, 0.5), across=(X, 0.5)),
               spec=plain(lip_hole), tags=(intent("B", "hole"),))
    d.export("wall_face", wall)
    d.export("cradle_seat", body.side("floor"))
    d.export("lip_top", body.side("lip_top"))
    d.export("back", body.side("back"))
    d.export("front_low", body.side("front_low"))
    return d


design = make_design()

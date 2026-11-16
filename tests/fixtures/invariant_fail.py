"""GUI fixture (docs/gui.md §6 criterion 7): a parameter that makes an invariant fail.

A plate with a rib underneath.  The hole is explicitly `through(t)` ("through this plate").
Slide `hole_u` over the rib (about 0.63..0.87) and the hole turns blind: ΔH fails (spike 01's
negative control), the failing feature's faces are tinted, and the last good model stays.
"""
from dipm import XY, Design, Profile, X, Y, face_point, intent, plain, through
from dipm.sketch import rect_points


def make_design() -> Design:
    d = Design("invariant_fail", doc="GUI fixture: hole_u over the rib makes ΔH fail")
    t = d.param("t", 5.0, range=(4.0, 8.0), doc="plate thickness")
    u = d.param("hole_u", 0.3, range=(0.1, 0.9), unit="", doc="hole position along the plate")
    plate = d.extrude("R.plate", Profile(XY, rect_points(0.0, 0.0, 80.0, 30.0)), t,
                      tags=intent("R", "skeleton", "plate"))
    d.extrude("S.rib", Profile(XY.offset(-15.0), rect_points(50.0, 0.0, 70.0, 30.0)), 15.0, mode="add",
              tags=intent("S", "rib", "stiffening rib under the plate"))
    d.hole("H.hole", plate.cap("END"), face_point(plate.cap("END"), along=(X, u), across=(Y, 0.5)), plain(5.0),
           through(t), tags=intent("H", "hole", "through hole in the plate"))
    d.label_intent("R", "Plate with a hole")
    d.use_lock(__file__)
    return d


design = make_design()

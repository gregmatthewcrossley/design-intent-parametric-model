"""GUI fixture (docs/gui.md §6 criterion 6): divergent readings that produce a question.

A C-channel on its side: top plate z 0..5, web x 0..5, bottom flange below an air gap g.
The drain hole H on the top face has material *behind* it across the gap, so `through_plate`
(top plate only) and `through_all` (both flanges) both pass every check but give different
geometry: the interpretations panel asks which one is meant.
"""
from dipm import XY, Design, Profile, X, Y, face_point, intent, plain
from dipm.sketch import XZ, rect_points


def make_design() -> Design:
    d = Design("channel_question", doc="GUI fixture: a hole whose extent is a real question")
    g = d.param("g", 10.0, range=(6.0, 12.0), doc="air gap between the flanges")
    u = d.param("hole_u", 0.75, range=(0.4, 0.9), unit="", doc="hole position along the top plate")
    top = d.extrude("R.top", Profile(XY, rect_points(0.0, 0.0, 40.0, 30.0)), 5.0,
                    tags=intent("R", "skeleton", "top flange"))
    lower = Profile(XZ.offset(-30.0), points={"a": (0.0, 0.0), "b": (0.0, -(g + 5.0)), "c": (40.0, -(g + 5.0)),
                                              "d": (40.0, -g), "e": (5.0, -g), "f": (5.0, 0.0)},
                    winding=None, name="lower")
    d.extrude("R.lower", lower, distance=30.0, mode="add", tags=intent("R", "skeleton", "web and lower flange"))
    d.hole("D.drain", top.cap("END"), face_point(top.cap("END"), along=(X, u), across=(Y, 0.5)), plain(4.0),
           tags=intent("D", "hole", "drain hole through the channel"))
    d.label_intent("R", "C-channel")
    d.use_lock(__file__)
    return d


design = make_design()

"""GUI fixture (docs/gui.md §2 item 9, §6 criterion 9): every connection diagnostic.

* `X.untagged` has no intent tag                         -> "no intent"
* intent `B` is labelled but nothing realizes it          -> "intent with no feature"
* `A.1.shared` serves both A.1 and C.1                   -> "serves several intents"
* `D.1.drain` is placed from A.1's hole                  -> cross-intent dependency (false coupling?)
"""
from dipm import XY, Design, Profile, X, Y, centerline, face_point, intent, plain
from dipm.sketch import rect_points


def make_design() -> Design:
    d = Design("diagnostics", doc="GUI fixture: connection diagnostics")
    t = d.param("t", 5.0, range=(3.0, 8.0), doc="plate thickness")
    plate = d.extrude("R.plate", Profile(XY, rect_points(0.0, 0.0, 80.0, 40.0)), t,
                      tags=intent("R", "skeleton", "plate"))
    top = plate.cap("END")
    shared = d.hole("A.1.shared", top, face_point(top, along=(X, 0.2), across=(Y, 0.5)), plain(5.0),
                    tags=(intent("A.1", "hole", "mounting hole"), intent("C.1", "hole", "also a vent")))
    d.hole("X.untagged", top, face_point(top, along=(X, 0.5), across=(Y, 0.5)), plain(4.0))
    # placed relative to A.1's hole wall: a dependency between unrelated intents
    vent_zone = centerline(top, X).before(shared.wall(0), clearance=4.0)
    d.hole("D.1.drain", top, vent_zone.midpoint(), plain(3.0),
           tags=intent("D.1", "hole", "drain placed next to the mounting hole"))
    d.label_intent("R", "Vented plate").label_intent("A", "Mounting").label_intent("B", "Cable routing")
    d.label_intent("C", "Ventilation").label_intent("D", "Drainage")
    d.use_lock(__file__)
    return d


design = make_design()

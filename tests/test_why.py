"""'Why is this here?': genealogy of any face or edge of the final solid (GUI core query)."""
from dipm import edges_between


def test_every_face_has_a_genealogy(bracket_build):
    b = bracket_build
    for f in b.faces():
        w = b.why(f)
        assert w.entries, str(w)


def test_why_countersink_names_pattern_instance(bracket, bracket_build):
    b = bracket_build
    (f,) = b.resolve(bracket.feature("A.P.holes").countersink(1))
    w = b.why(f)
    (e,) = w.entries
    assert str(e.tag) == "A.P.holes.countersink(1)"
    assert e.lowered_from == "hole(countersink, through_plate)" and e.op == "cut"
    assert w.intent_nodes() == ["A.P.2", "A.P", "A"]
    assert "Cone" in w.descriptor


def test_why_cable_hole_and_fillet(bracket, bracket_build):
    b = bracket_build
    (f,) = b.resolve(bracket.feature("A.3.cable").wall(0))
    assert b.why(f).intent_nodes() == ["A.3", "A"]
    for f in b.resolve(bracket.feature("R.fillet").blend()):
        w = b.why(f)
        assert w.intent_nodes() == ["R"] and w.entries[0].tag.role == "blend"


def test_why_mount_face_shows_history(bracket, bracket_build):
    b = bracket_build
    (f,) = b.resolve(bracket.feature("R.body").side("mount"))
    (e,) = b.why(f).entries
    assert [x[0] for x in e.events] == ["C.gusset", "A.P.holes", "A.3.cable", "R.fillet"]
    assert "skeleton@R" in str(b.why(f))


def test_untracked_edge_is_explained_by_adjacent_faces(bracket, bracket_build):
    b = bracket_build
    body = bracket.feature("R.body")
    (e,) = b.resolve(edges_between(body.side("wall"), body.cap("START")))
    w = b.why(e)
    assert not w.entries and len(w.derived_from) == 2
    tags = sorted(str(x.entries[0].tag) for x in w.derived_from)
    assert tags == ["R.body.cap(START)", "R.body.side(wall)"]
    assert "edges_between" in str(w)


def test_lateral_edge_is_tracked(bracket, bracket_build):
    b = bracket_build
    (e,) = b.resolve(bracket.feature("R.body").lateral_edge("wall_bot"))
    assert str(b.why(e).entries[0].tag) == "R.body.lateral_edge(wall_bot)"

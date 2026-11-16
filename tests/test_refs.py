"""Reference layer (dsl.md §3.4): resolution, cardinality, policies, derived refs, follow-Generated."""
import pytest

from dipm import (ERROR_ON_MERGE, ERROR_ON_SPLIT, YZ, CardinalityError, Design, PolicyError, Profile,
                  at_least, edges_between, exactly, intent, one)
from dipm import kernel as K

from conftest import block


def test_extrude_roles_resolve_one_each():
    d, E = block()
    b = d.build()
    for r in [E.cap("START"), E.cap("END")] + [E.side(s) for s in ("a-b", "b-c", "c-d", "d-a")]:
        (f,) = b.resolve(r)
        assert f.ShapeType() == K.KINDS["face"]
    # outward normals come from the face as oriented in the solid
    assert K.face_normal(b.resolve(E.cap("END"))[0], b.shape).rounded(6) == (0.0, 0.0, 1.0)
    assert K.face_normal(b.resolve(E.cap("START"))[0], b.shape).rounded(6) == (0.0, 0.0, -1.0)
    assert K.face_normal(b.resolve(E.side("a-b"))[0], b.shape).rounded(6) == (0.0, -1.0, 0.0)
    assert len(b.resolve(E.lateral_edge("a"))) == 1


def test_cardinality_mismatch_is_a_clear_error():
    d, E = block()
    b = d.build()
    with pytest.raises(CardinalityError) as ei:
        b.resolve(E.side("a-b").expect(exactly(2)))
    err = ei.value
    assert err.expected == "exactly(2)" and err.got == 1
    assert "E.side(a-b)" in str(err) and "cardinality" in str(err)


def test_unknown_role_resolves_to_zero_and_fails_one():
    d, E = block()
    b = d.build()
    with pytest.raises(CardinalityError):
        b.resolve(E.side("nope"))
    assert b.resolve(E.side("nope").expect(at_least(0))) == []


def test_cardinality_error_inside_build_names_the_feature():
    d, E = block()
    d.fillet("F", E.lateral_edge("a", card=exactly(3)), 2.0, tags=intent("R", "fillet"))
    with pytest.raises(CardinalityError) as ei:
        d.build()
    assert ei.value.feature == "F"
    assert "fillet@R" in str(ei.value)


def _l_with_gusset():
    d = Design("lg")
    L = Profile(YZ, {"a": (0.0, 0.0), "b": (5.0, 0.0), "inner": (5.0, 45.0), "c": (50.0, 45.0),
                     "d": (50.0, 50.0), "e": (0.0, 50.0)})
    body = d.extrude("E", L, 30.0, symmetric=True)
    G = Profile(YZ, {"corner": (5.0, 45.0), "down": (5.0, 25.0), "out": (25.0, 45.0)})
    d.extrude("G", G, 5.0, symmetric=True, mode="add")
    return d, body


def test_split_is_an_event_and_error_on_split_rejects_it():
    d, body = _l_with_gusset()
    b = d.build()
    inner = body.lateral_edge("inner", card=exactly(2))
    assert len(b.resolve(inner)) == 2                       # propagate_all: split2 accepted
    assert b.ledger.entries("E", "lateral_edge", "inner")[0].genealogy == (("G", "split2"),)
    with pytest.raises(PolicyError, match="split"):
        b.resolve(inner.with_policy(ERROR_ON_SPLIT))


def test_merge_event_and_error_on_merge():
    d, E = block()
    M = d.mirror("M", (0.0, 0.0, 0.0), (1.0, 0.0, 0.0))   # image touches along E.side(d-a); clean merges caps
    b = d.build()
    end = b.resolve(E.cap("END"))
    img = b.resolve(M.image(of=E.cap("END")))
    assert end[0].IsSame(img[0])                           # two references alias one face
    assert any(ev == "merged" for _, ev in b.ledger.entries("E", "cap", "END")[0].genealogy)
    with pytest.raises(PolicyError, match="merged"):
        b.resolve(E.cap("END").with_policy(ERROR_ON_MERGE))
    # the face on the mirror plane is gone (declared 0)
    assert b.resolve(E.side("d-a").expect(exactly(0))) == []


def test_edges_between_is_a_structural_derived_reference():
    d, E = block()
    b = d.build()
    (e,) = b.resolve(edges_between(E.side("a-b"), E.cap("END")))
    assert K.length(e) == pytest.approx(40.0)
    with pytest.raises(CardinalityError):
        b.resolve(edges_between(E.side("a-b"), E.side("c-d")))   # opposite faces share nothing


def test_draft_needs_follow_generated_and_edges_between():
    """Spike 02 §1.6: drafted faces only via Generated; no edge history at all."""
    d, E = block()
    sides = [E.side(s) for s in ("a-b", "b-c", "c-d", "d-a")]
    d.draft("D", sides, 5.0)
    b = d.build()
    for s in sides:
        (f,) = b.resolve(s)
        assert b.ledger.who(f)[0].genealogy == (("D", "regenerated"),)
    with pytest.raises(CardinalityError):
        b.resolve(E.lateral_edge("b"))                      # edge history dropped by the kernel
    assert len(b.resolve(edges_between(E.side("a-b"), E.side("b-c"), one()))) == 1


def test_isdeleted_is_not_trusted_after_fillet():
    """Fillet's IsDeleted reports untouched edges as deleted (spike 01 §2.1); the ledger ignores it."""
    d, E = block()
    d.fillet("F", E.lateral_edge("a"), 3.0)
    b = d.build()
    assert len(b.resolve(E.lateral_edge("c"))) == 1        # untouched edge still resolves
    assert any(op == "F" for _, op, _, _ in b.ledger.isdeleted_disagreements)


def test_no_ordinals_in_reference_api():
    """References are (feature, role, source): there is no index-based accessor."""
    d, E = block()
    assert not hasattr(E, "face") and not hasattr(E, "faces")
    assert str(E.side("a-b")) == "E.side(a-b)"

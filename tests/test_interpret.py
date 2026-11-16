"""Interpretations of ambiguous intent words (architecture §10 item 2, §4.8; src/dipm/interpret.py)."""
import json
import textwrap
import warnings

import pytest

from dipm import XY, Design, Profile, X, Y, centered_on, face_point, plain, through
from dipm import kernel as K
from dipm.interpret import (Interpretation, Preferences, grade_sensitivity, read_lock, resolve, sample_points,
                            write_lock)
from dipm.cli import main
from dipm.report import build_report
from dipm.sketch import rect_points

from conftest import EXAMPLE


# ---------------------------------------------------------------- designs used here

def channel_design(name="channel", extent=None):
    """A C-channel on its side: top plate z 0..5, web x 0..5, bottom flange z -g-5..-g.  The hole H
    on the top face (x=30) has material *behind* it across an air gap, so through_plate (top
    plate only) and through_all (both flanges) pass every check but give different geometry."""
    from dipm.sketch import XZ
    d = Design(name)
    g = d.param("g", 10.0, range=(6.0, 12.0), doc="air gap between the flanges")
    top = d.extrude("E", Profile(XY, rect_points(0.0, 0.0, 40.0, 30.0)), 5.0)
    # web and bottom flange: one L profile in the XZ plane (u = X, v = Z), extruded y 30 -> 0
    lower = Profile(XZ.offset(-30.0), points={"a": (0.0, 0.0), "b": (0.0, -(g + 5.0)), "c": (40.0, -(g + 5.0)),
                                              "d": (40.0, -g), "e": (5.0, -g), "f": (5.0, 0.0)},
                    winding=None, name="lower")
    d.extrude("L", lower, distance=30.0, mode="add")
    d.hole("H", top.cap("END"), face_point(top.cap("END"), along=(X, 0.75), across=(Y, 0.5)), plain(4.0), extent)
    return d


# ---------------------------------------------------------------- the bracket (architecture §8)

@pytest.fixture(scope="module")
def bracket_interp(bracket):
    return resolve(bracket)          # fresh resolution, not the lock


def test_bracket_zero_questions_and_expected_choices(bracket_interp):
    it = bracket_interp
    assert it.questions == []
    by = {a.id: a for a in it.assumptions}
    assert list(by) == ["A.P.holes/hole.extent", "A.3.cable/centered_on.point", "A.3.cable/hole.extent",
                        "B.1.screw/hole.extent"]
    for sid in ("A.P.holes/hole.extent", "A.3.cable/hole.extent", "B.1.screw/hole.extent"):
        a = by[sid]
        assert a.chosen == "through_plate" and a.made_by == "pack default" and a.status == "proposed"
        assert a.sensitivity == "insensitive" and a.alternatives == ["through_all", "up_to_next"] and a.eliminated == []
        assert a.feasible == ["through_plate", "through_all", "up_to_next"] and a.resolution == "unconfirmed"   # B3
    c = by["A.3.cable/centered_on.point"]
    assert c.chosen == "exposed_region_midpoint" and c.made_by == "model"
    (e,) = c.eliminated                              # elimination with a recorded reason
    assert e["reading"] == "face_centroid" and e["feature"] == "A.3.cable"
    assert e["check"] == "relation: centre inside face" and e["failed_points"] == e["of_points"] == 9
    assert "between_siblings" not in c.readings      # opt-in only
    # DECISIONS #32: face_centroid is structurally impossible (not on the face) and the survivor's
    # tool meets nothing the default would not have: an ordinary elimination, no notice
    assert it.notices == [] and c.sensitivity == "forced"          # B4: only one survives
    assert "no extra interaction" in c.sensitivity_detail


def test_committed_lock_matches_a_fresh_resolution(bracket, bracket_interp):
    """The lock next to the example is up to date (rerun `dipm interpret` if this fails)."""
    lk = read_lock(bracket.lock.lock)
    assert lk is not None and lk.choices == bracket_interp.choices
    assert bracket.ensure_interpretations() is not None and bracket._interp_source.startswith("lock")


def test_resolution_is_deterministic(bracket, bracket_interp):
    """Same inputs -> identical record, also when warm-started from other choices."""
    again = resolve(bracket, initial={"B.1.screw/hole.extent": "through_all",
                                      "A.3.cable/centered_on.point": "face_centroid"})
    assert again.to_json() == bracket_interp.to_json()


def test_report_has_interpretations_section(bracket_build):
    out = build_report(bracket_build)
    assert "Interpretations (4 slot(s), 0 question(s), 0 notice(s); lock" in out
    assert "eliminated face_centroid" in out and "NOTICE" not in out


def test_default_overridden_notice_on_spike01_negative_control(bracket_mod, bracket):
    """u=0.4 lands B.1 on the gusset: through_plate goes blind (ΔH) and is eliminated, while
    through_all drills through the gusset and survives.  No intent-level check can tell that this
    is wrong yet (tool access, NOTES TODO 4), so it must be loud: a default-overridden notice."""
    d = bracket_mod.make_design(shelf_hole_u=0.4)
    it = resolve(d, initial=dict(bracket.interpretations))
    b1 = it.assumption("B.1.screw/hole.extent")
    assert b1.chosen == "through_all" and b1.sensitivity == "high" and b1.made_by == "model"
    (e,) = b1.eliminated
    assert e["reading"] == "through_plate" and e["check"] == "delta_H"
    assert b1.alternatives == ["up_to_next"]
    notes = [n for n in it.notices if n.id == "B.1.screw/hole.extent"]
    assert [n.kind for n in notes] == ["default_overridden"] and "tool" in notes[0].text
    assert "also interacts with C.gusset" in notes[0].text   # DECISIONS #32: the extra interaction is named
    assert it.questions == []                         # survivors agree: not a question


# ---------------------------------------------------------------- divergence, questions, preferences

def test_material_behind_the_plate_makes_readings_diverge():
    d = channel_design()
    it = resolve(d)
    a = it.assumption("H/hole.extent")
    assert a.eliminated == [] and a.chosen == "through_plate"
    assert a.alternatives == ["through_all", "up_to_next"]
    assert a.sensitivity == "high" and "topology differs" in a.sensitivity_detail
    (q,) = it.questions
    assert q.id == "H/hole.extent" and q.default == "through_plate"
    assert [o["reading"] for o in q.options] == ["through_plate", "through_all", "up_to_next"]
    # the geometry really differs: through_all pierces both flanges
    b_plate = d.build(interpretations=it.choices)
    b_all = d.build(interpretations={"H/hole.extent": "through_all"})
    assert b_plate.ok and b_all.ok
    assert b_plate.signature.VEFRSH[5] == 1 and b_all.signature.VEFRSH[5] == 2


def test_sensitivity_zero_means_no_question():
    d = Design("plate")
    E = d.extrude("E", Profile(XY, rect_points(0.0, 0.0, 40.0, 30.0)), d.param("t", 5.0, range=(3.0, 8.0)))
    d.hole("H", E.cap("END"), centered_on(E.cap("END")), plain(4.0))
    it = resolve(d)
    assert it.questions == [] and it.notices == []
    assert {a.id: (a.chosen, a.sensitivity) for a in it.assumptions} == {
        "H/centered_on.point": ("face_centroid", "insensitive"), "H/hole.extent": ("through_plate", "insensitive")}


def test_preference_selects_and_suppresses_the_question(tmp_path):
    d = channel_design()
    for key in ("hole.extent@channel:H", "hole.extent@channel:*", "hole.extent@*"):
        prefs = Preferences(str(tmp_path / "p.json"), {key: {"reading": "through_all"}})
        it = resolve(d, prefs)
        a = it.assumption("H/hole.extent")
        assert a.chosen == "through_all" and a.made_by == "user preference" and a.status == "accepted", key
        assert it.questions == [] and key in a.rationale
    # a preference that a check eliminates is overridden, loudly
    blocked = Preferences(None, {"hole.extent@*": {"reading": "through_plate"}})
    d2 = channel_design("backed")
    d2.features[-1] = d2.features[-1].__class__(**{**d2.features[-1].__dict__,
                                                  "at": face_point(d2.feature("E").cap("END"), along=(X, 0.0625),
                                                                   across=(Y, 0.5))})
    it2 = resolve(d2, blocked)
    a2 = it2.assumption("H/hole.extent")
    assert a2.chosen != "through_plate" and any(n.kind == "preference_overridden" for n in it2.notices)


def test_explicit_extent_bypasses_interpretation():
    d = channel_design(extent=through(5.0))
    it = resolve(d)
    (a,) = it.assumptions
    assert a.made_by == "author" and a.status == "accepted" and a.chosen == "through(5.0)" and it.questions == []


def test_opt_in_between_siblings_can_raise_a_question():
    """`between_siblings` couples a feature to its siblings, so it is offered only on request.
    Two holes left of centre: the three 'centres' all pass and all differ."""
    d = Design("siblings")
    E = d.extrude("E", Profile(XY, rect_points(0.0, 0.0, 60.0, 30.0)), 5.0)
    top = E.cap("END")
    d.hole("S", top, [face_point(top, along=(X, 0.2), across=(Y, 0.5)),
                      face_point(top, along=(X, 0.4), across=(Y, 0.5))], plain(4.0))
    d.hole("C", top, centered_on(top, consider=("between_siblings",)), plain(4.0))
    it = resolve(d)
    a = it.assumption("C/centered_on.point")
    assert a.readings == ["face_centroid", "exposed_region_midpoint", "between_siblings"]
    assert a.eliminated == [] and a.chosen == "face_centroid"
    (q,) = [q for q in it.questions if q.id == "C/centered_on.point"]
    assert len(q.options) == 3
    pts = {}
    for r in a.readings:
        b = d.build(interpretations={**it.choices, "C/centered_on.point": r})
        pts[r] = b.record("C").detail["centres"][0]
    assert pts["exposed_region_midpoint"].x == pytest.approx(30.0)
    assert pts["between_siblings"].x == pytest.approx(18.0)
    assert 30.0 < pts["face_centroid"].x < 31.0           # area centroid shifted by the two holes


def test_exposed_region_midpoint_on_the_bracket(bracket, bracket_build):
    """The cable hole lands mid-way up the plate below the gusset footprint, as DECISIONS #8 did by hand."""
    (f,) = bracket_build.resolve(bracket.feature("A.3.cable").wall(0))
    c = K.centroid(f)
    assert (c.x, c.z) == pytest.approx((0.0, (0.75 * 200 - 5 - 0.4 * 200) / 2))


# ---------------------------------------------------------------- lock, CLI, grading

def test_lock_round_trip(tmp_path):
    d = channel_design()
    it = resolve(d)
    p = tmp_path / "x.interpretations.json"
    write_lock(it, str(p))
    back = read_lock(str(p))
    assert back.to_json() == it.to_json()
    assert d.build(interpretations=back.choices).canonical() == d.build(interpretations=it.choices).canonical()


DESIGN_SRC = textwrap.dedent('''
    import sys
    sys.path.insert(0, {tests!r})
    from test_interpret import channel_design
    design = channel_design()
''')


def _design_file(tmp_path):
    import pathlib
    f = tmp_path / "chan.py"
    f.write_text(DESIGN_SRC.format(tests=str(pathlib.Path(__file__).parent)))
    return f


def test_cli_interpret_answer_build_round_trip(tmp_path, capsys):
    f = _design_file(tmp_path)
    prefs = tmp_path / "prefs.json"
    lock = tmp_path / "chan.interpretations.json"
    assert main(["interpret", str(f)]) == 0
    out = capsys.readouterr().out
    assert "QUESTION H/hole.extent" in out and "python -m dipm answer" in out and lock.exists()
    assert json.loads(lock.read_text())["choices"] == {"H/hole.extent": "through_plate"}
    assert main(["answer", str(f), "H/hole.extent", "through_all", "--prefs", str(prefs), "--note", "drain"]) == 0
    out = capsys.readouterr().out
    assert "recorded hole.extent@channel:H = through_all" in out and "QUESTION" not in out
    assert json.loads(prefs.read_text())["answers"] == {"hole.extent@channel:H": {"reading": "through_all",
                                                                                  "note": "drain"}}
    lk = read_lock(str(lock))
    assert lk.choices == {"H/hole.extent": "through_all"} and lk.questions == [] and lk.prefs == "prefs.json"
    # an ordinary build reads the lock (and its preferences) without re-resolving
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert main(["build", str(f)]) == 0
    out = capsys.readouterr().out
    assert "H/hole.extent  -> through_all   [made_by: user preference; status: accepted" in out
    assert "hole(plain, through_all)" in out
    assert main(["answer", str(f), "H/hole.extent", "sideways", "--prefs", str(prefs)]) == 2


def test_stale_lock_is_re_resolved_with_a_warning(tmp_path):
    from dipm.cli import load_design
    f = _design_file(tmp_path)
    assert main(["interpret", str(f)]) == 0
    f.write_text(f.read_text() + "# edited\n")
    d = load_design(str(f)).use_lock(str(f))
    with pytest.warns(UserWarning, match="stale"):
        b = d.build()
    assert b.interpretation_source == "resolved in memory" and b.ok


def test_unchecked_defaults_without_a_lock():
    d = channel_design()
    b = d.build()
    assert b.interpretation is None and [(u.id, u.reading, u.source) for u in b.slots] == [
        ("H/hole.extent", "through_plate", "unchecked default")]
    assert "Interpretations: UNCHECKED" in build_report(b)


def test_sample_points_are_the_stability_points(bracket):
    pts = sample_points(bracket)
    assert pts[0] == bracket.defaults() and len(pts) == 9


def test_grade_sensitivity_rule():
    """B4 (NOTES #61): forced vs insensitive, then graded by geometric distance, not volume."""
    assert grade_sensitivity(1, 0.0, False) == "forced"
    assert grade_sensitivity(0, None, False) == "forced"
    assert grade_sensitivity(3, 0.0, False) == "insensitive"
    assert grade_sensitivity(2, 0.2, False) == "low"
    assert grade_sensitivity(2, 2.0, False) == "medium"
    assert grade_sensitivity(2, 7.5, False) == "high"
    assert grade_sensitivity(2, 0.0, True) == "high"
    assert grade_sensitivity(2, None, False) == "high"


def test_interpretation_json_has_assumption_fields(bracket_interp):
    d = json.loads(bracket_interp.to_json())
    a = d["assumptions"][1]
    for k in ("id", "statement", "chosen", "alternatives", "eliminated", "sensitivity", "made_by", "rationale",
              "status", "supports"):
        assert k in a, k
    assert Interpretation.from_json(bracket_interp.to_json()).choices == bracket_interp.choices


def test_interactions_and_uses_on_the_bracket(bracket_build):
    """What each feature references, reads and touches (DECISIONS #32, #33)."""
    b = bracket_build
    touched = b.touched()
    assert sorted(touched["B.1.screw"]) == ["R.body"] and sorted(touched["C.gusset"]) == ["R.body"]
    assert b.references("A.P.holes") == ["R.body", "C.gusset"]
    assert b.references("A.3.cable") == ["R.body"]
    assert b.uses("A.3.cable") == ["R.body", "C.gusset"]        # the exposed region is bounded by the gusset
    assert b.interactions("A.3.cable") == frozenset({"R.body"})


def test_ref_features_longest_id_wins():
    from dipm.program import ref_features
    ids = ["A.P", "A.P.holes", "R.body", "C.gusset"]
    assert ref_features("A.P.holes.wall(0)", ids) == ["A.P.holes"]
    assert ref_features("edges_between(R.body.side(a), C.gusset.side(b))", ids) == ["R.body", "C.gusset"]
    assert ref_features("R.fillet.blend(R.body.lateral_edge(inner))", ids + ["R.fillet"]) == ["R.fillet", "R.body"]

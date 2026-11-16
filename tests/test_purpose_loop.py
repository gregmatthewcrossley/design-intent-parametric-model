"""Iteration 4: the purpose -> geometry loop (docs/purpose-loop.md §5).

* every check vocabulary form passes and fails by construction and reports margins (criterion 3);
* the impact report on the rod holder (criterion 1);
* purpose proposals: bindings validated on submit, descriptive checks shown not run (criterion 2);
* evaluate (the inner loop) and its budget; alternatives;
* an end-to-end run through the MCP tools with a stub model (criterion 4);
* nothing writes the design files but an accepted proposal (criterion 6);
* the pack data and its placeholder flags match the report (criterion 7).
"""
from __future__ import annotations

import asyncio
import functools
import json
import math
import pathlib
import sys

import pytest

from dipm import intent_store, packs
from dipm.checks import evaluate_checks
from dipm.components import ComponentError, parse_component, parse_range
from dipm.fileio import file_sha256, read_text
from dipm.impact import impact, impact_for
from dipm.proposals import ProposalError, ProposalStore, load_and_build
from dipm.review import ReviewRecord
from dipm.vocabulary import FORMS, describe, validate_binding, vocabulary

from conftest import copy_rod_holder

sys.path.insert(0, str(pathlib.Path(__file__).parent / "fixtures"))
import rod_cradle  # noqa: E402
import rod_loop  # noqa: E402

COMPS = [{"id": "rod", "shape": "cylinder", "diameter": "6..14 mm", "length": "1800", "mass": "0.2..1"},
         {"id": "reel", "shape": "box", "size": "90..140 x 60..90 x 90..130"}]
CTX = {"process": "fdm_printing", "material": "PETG", "nozzle": "0.4 mm", "layer_height": "0.2 mm"}
SIDE_DOWN = {"up": [1.0, 0.0, 0.0], "label": "side down", "made_by": "model"}


@functools.lru_cache(maxsize=None)
def _built(**kw):
    d = rod_cradle.make_design(**kw)
    return d, d.build()


def run(binding, orientation=SIDE_DOWN, comps=COMPS, **design_kw):
    d, b = _built(**design_kw)
    assert b.ok
    doc = {"design": "rod_cradle", "components": comps,
           "intents": [{"id": "R", "statement": "test", "checks": [{"id": "R.c1", "kind": "relation", "statement": "t",
                                                                     "binding": binding}]}]}
    (r,) = evaluate_checks(d, b, doc, CTX, orientation)
    return r


def margins_ok(r):
    assert r.ran, r.reason
    assert r.terms
    for t in r.terms:
        for k in ("nominal", "worst", "limit", "limit_worst", "margin", "margin_worst"):
            assert math.isfinite(getattr(t, k)), (t.name, k)
    h = r.headline()
    assert h is not None and h.state == r.state
    return h


# ---------------------------------------------------------------- vocabulary: every form, pass and fail

CASES = {
    "coincident": ({"a": "cradle_seat", "b": "R.body.side(floor)"}, {}, {"a": "cradle_seat", "b": "lip_top"}, {}),
    "centered_on": ({"item": "A.P.holes", "on": "front_low", "axes": "X"}, {},
                    {"item": "A.P.holes", "on": "front_low", "axes": "Z"}, {}),
    "symmetric_about": ({"items": "A.P.holes", "about": "wall_face", "normal": "X"}, {},
                        {"items": "A.P.holes", "about": "wall_face", "normal": "Z"}, {}),
    "parallel": ({"a": "wall_face", "b": "back"}, {}, {"a": "wall_face", "b": "cradle_seat"}, {}),
    "distance_between": ({"a": "lip_top", "b": "cradle_seat", "min": "10"}, {},
                         {"a": "lip_top", "b": "cradle_seat", "min": "15"}, {}),
    "inside_face": ({"items": "A.P.holes", "margin": "0"}, {}, {"items": "A.P.holes", "margin": "20"}, {}),
    "min_wall": ({}, {}, {"min": "10"}, {}),
    "hole_edge_distance": ({"holes": "A.P.holes", "factor": "1"}, {}, {"holes": "A.P.holes", "factor": "5"}, {}),
    "bridging": ({"max": "20"}, {}, {"max": "5"}, {}),
    "holds_cylinder": ({"component": "rod", "seat": "cradle_seat"}, {},
                       {"component": "rod", "seat": "cradle_seat"}, {"gap": 10.0}),
    "retention": ({"component": "rod", "seat": "cradle_seat", "min_lift": "5"}, {},
                  {"component": "rod", "seat": "cradle_seat", "min_lift": "15"}, {}),
    "clears_box": ({"component": "reel", "hangs_from": "rod", "seat": "cradle_seat", "along": "90..200"}, {"gap": 95.0},
                   {"component": "reel", "hangs_from": "rod", "seat": "cradle_seat", "along": "90..200"}, {}),
    "anchor_pullout": ({"anchors": "A.P.holes", "load": "0.2..1", "at": "component:rod", "seat": "cradle_seat"}, {},
                       {"anchors": "A.P.holes", "load": "200", "at": "component:rod", "seat": "cradle_seat"}, {}),
    "bending": ({"load": "component:rod", "at": "lip_top", "section_width": "20", "section_depth": "6",
                 "section_at": "5"}, {},
                {"load": "300", "at": "lip_top", "section_width": "20", "section_depth": "6", "section_at": "5"}, {}),
    "load": ({"anchors": "A.P.holes", "load": "component:rod", "at": "component:rod", "seat": "cradle_seat",
              "section_width": "20", "section_depth": "6", "section_at": "5"}, {},
             {"anchors": "A.P.holes", "load": "50", "at": "component:rod", "seat": "cradle_seat"}, {}),
    "tool_access": ({"holes": "A.P.holes"}, {}, {"holes": "A.P.holes"}, {"screw_u": (0.2, 0.95)}),
}


def test_every_form_has_a_case():
    assert set(CASES) | {"overhang"} == set(FORMS)
    assert {f["form"] for f in vocabulary()} == set(FORMS) | {"descriptive"}
    for f in vocabulary():
        assert f["example"]["form"] == f["form"] and f["reads_as"]


@pytest.mark.parametrize("form", sorted(CASES))
def test_form_passes_and_fails_with_margins(form):
    good, good_kw, bad, bad_kw = CASES[form]
    r = run({"form": form, **good}, **good_kw)
    h = margins_ok(r)
    assert r.state in ("ample", "thin"), (form, r.state, [(t.name, t.margin_worst) for t in r.terms])
    assert h.margin_worst >= 0
    r2 = run({"form": form, **bad}, **bad_kw)
    h2 = margins_ok(r2)
    assert r2.state == "failing", (form, [(t.name, t.margin_worst) for t in r2.terms])
    assert h2.margin_worst < 0
    assert r.binding["form"] == form and r.spec_made_by == "model" and not r.binding_reviewed
    assert r.binding_text and r.method_assumptions


def test_overhang_form_passes_side_down_and_fails_upright():
    r = run({"form": "overhang"})
    assert margins_ok(r) and r.state == "ample"
    up = {"up": [0.0, 0.0, 1.0], "label": "upright", "made_by": "model"}
    r2 = run({"form": "overhang"}, orientation=up)       # the arm's underside overhangs 90°
    assert margins_ok(r2).margin_worst < 0 and r2.state == "failing"
    r3 = run({"form": "overhang", "limit": "90"}, orientation=up)
    assert r3.state != "failing"


def test_fit_numbers_match_the_construction():
    """Escape lift toward the lip = lip height (12); toward the plate = top − floor (20)."""
    r = run({"form": "retention", "component": "rod", "seat": "cradle_seat", "min_lift": "0"})
    lifts = {t.name: t.nominal for t in r.terms}
    assert lifts["Ø6 lift toward +u"] == pytest.approx(12.0, abs=0.3)
    assert lifts["Ø14 lift toward −u"] == pytest.approx(20.0, abs=0.3)
    h = run({"form": "holds_cylinder", "component": "rod", "seat": "cradle_seat"})
    (g,) = h.ghosts
    assert g["shape"] == "cylinder" and g["diameter"] == 10.0 and g["center"][2] == pytest.approx(65.0, abs=0.05)


def test_descriptive_and_unresolvable_bindings_are_not_run():
    r = run({"form": "descriptive", "reason": "needs a person"})
    assert r.state == "not run" and "descriptive" in r.reason and not r.terms
    r = run({"form": "holds_cylinder", "component": "rod", "seat": "no_such_export"})
    assert r.state == "not run" and "no_such_export" in r.reason
    r = run({"form": "holds_cylinder", "component": "ghost", "seat": "cradle_seat"})
    assert r.state == "not run" and "invalid" in r.reason
    r = run({"form": "tool_access", "holes": "lip_top"})
    assert r.state == "not run" and "not a hole feature" in r.reason


def test_validate_binding_messages():
    comps = {"rod": parse_component(COMPS[0])}
    assert validate_binding({"form": "holds_cylinder", "component": "rod", "seat": "s"}, comps) == []
    e = validate_binding({"form": "hold_cylinder"}, comps)
    assert "did you mean 'holds_cylinder'" in e[0]
    e = validate_binding({"form": "retention", "component": "rod", "seat": "s"}, comps)
    assert any("min_lift" in x for x in e)
    e = validate_binding({"form": "retention", "component": "rod", "seat": "s", "min_lift": "5", "lift": "2"}, comps)
    assert any("unknown parameter 'lift'" in x for x in e)
    e = validate_binding({"form": "parallel", "a": "x", "b": "y", "tolerance_deg": "abc+"}, comps)
    assert e
    assert validate_binding({"form": "descriptive"}, comps)[0].endswith("why it cannot be computed)")
    assert "Descriptive, not run" in describe({"form": "descriptive", "reason": "r"})
    assert "Ø6–14 mm cylinder" in describe({"form": "holds_cylinder", "component": "rod", "seat": "s"}, comps)


def test_component_ranges_and_pack():
    q = parse_range("6..14 mm")
    assert (q.nominal, q.lo, q.hi, q.unit) == (10.0, 6.0, 14.0, "mm")
    q = parse_range("10 (6..14)")
    assert (q.nominal, q.lo, q.hi) == (10.0, 6.0, 14.0)
    with pytest.raises(ComponentError):
        parse_range("six")
    c = parse_component({"id": "rod", "pack": "fishing_rod_blank"})
    assert c.shape == "cylinder" and c.dims["diameter"].lo == 6.0 and c.placeholder and c.mass.hi == 1.0
    b = parse_component({"id": "reel", "shape": "box", "size": "90..140 x 60..90 x 90..130 mm"})
    assert b.dims["across"].hi == 90.0
    with pytest.raises(ComponentError):
        parse_component({"id": "x", "shape": "box"})


def test_intent_file_round_trips_bindings_and_components():
    doc = intent_store.loads(rod_loop.PURPOSE_TEXT)
    assert intent_store.canonical(intent_store.dumps(doc)) == intent_store.dumps(doc)
    plain = doc.to_plain()
    assert plain["components"][0]["id"] == "rod"
    c = [x for x in plain["intents"][0]["children"][1]["checks"] if x["id"] == "B.c1"][0]
    assert c["binding"]["form"] == "holds_cylinder"
    intent_store.apply_ops(doc, [{"op": "set_binding", "id": "B", "check_id": "B.c1", "status": "accepted"},
                                 {"op": "edit_component", "component_id": "rod", "fields": {"status": "accepted"}}])
    p2 = doc.to_plain()
    assert p2["components"][0]["status"] == "accepted"
    with pytest.raises(intent_store.IntentSchemaError):
        intent_store.loads(rod_loop.PURPOSE_TEXT.replace("shape: cylinder", "shape: tube"))


# ---------------------------------------------------------------- impact (criterion 1)

def test_impact_shelf_to_fishing_rod():
    r = impact_for("tests/fixtures/rod_holder/rod_holder.py")
    cls = lambda k, i: r[k][i]["class"]  # noqa: E731
    assert cls("nodes", "R") == "changed"
    assert cls("nodes", "B") == "invalidated" and cls("nodes", "B.1") == "invalidated"
    assert cls("assumptions", "R.a1") == "invalidated"
    assert cls("nodes", "A") == "survives" and cls("checks", "R.c2") == "survives"
    assert r["terms"]["removed"] == ["shelf"] and set(r["terms"]["added"]) == {"fishing", "rod"}
    assert any("shelf" in x for x in r["nodes"]["B"]["reasons"])
    assert any("nested under B" in x for x in r["nodes"]["B.1"]["reasons"])
    assert any("supports R.c1" in x for x in r["assumptions"]["R.a1"]["reasons"])


def test_impact_propagates_through_source_supports_and_features():
    doc = intent_store.load("examples/shelf_bracket.intent.yaml")
    rec = ReviewRecord.load("examples/shelf_bracket.review.json")
    assert not impact(doc.to_plain(), rec.reviewed)["any_change"]
    intent_store.apply_ops(doc, [{"op": "edit_check", "id": "R", "check_id": "R.c4",
                                  "fields": {"statement": "Every wall screw can be driven by a right-angle driver"}}])
    feats = [{"id": "C.gusset", "serves": ["C"], "uses": []}, {"id": "A.P.holes", "serves": ["A.P"], "uses": ["C.gusset"]}]
    r = impact(doc.to_plain(), rec.reviewed, feats)
    assert r["checks"]["R.c4"]["class"] == "changed"
    assert r["checks"]["A.P.c4"]["class"] == "invalidated"            # source: R.c4
    assert r["assumptions"]["R.a3"]["class"] == "invalidated"          # supports R.c4
    assert r["nodes"]["A.P"]["class"] == "invalidated"                 # its own check
    assert r["nodes"]["A"]["class"] == "survives"
    # features: C invalidated by meaning -> the hole pattern that uses the gusset follows
    doc2 = intent_store.load("examples/shelf_bracket.intent.yaml")
    intent_store.apply_ops(doc2, [{"op": "edit_statement", "id": "R", "statement": "Support a planter on a wall"}])
    rec2 = {**rec.reviewed, "C": {"hash": "x", "content": {"statement": "Stiffening: gusset under the shelf",
                                                            "checks": [], "assumptions": []}}}
    r2 = impact(doc2.to_plain(), rec2, feats)
    assert r2["features"]["A.P.holes"]["class"] in ("survives", "invalidated")
    assert r2["nodes"]["C"]["class"] == "changed"


# ---------------------------------------------------------------- purpose proposals (criterion 2)

@pytest.fixture
def rod(tmp_path):
    return copy_rod_holder(tmp_path)


def _ihash(design):
    return file_sha256(str(design.with_name("rod_holder.intent.yaml")))


def test_purpose_proposal_requires_bindings_and_refuses_self_acceptance(rod):
    st = ProposalStore(str(rod))
    unbound = rod_loop.PURPOSE_TEXT.replace(
        ', binding: {form: holds_cylinder, component: rod, seat: cradle_seat, axis: X, made_by: model, status: proposed}',
        "")
    with pytest.raises(ProposalError, match="B.c1: bind it"):
        st.create_purpose("s", "r", unbound, _ihash(rod), ["R"])
    with pytest.raises(ProposalError, match="only the designer accepts"):
        st.create_purpose("s", "r", rod_loop.PURPOSE_TEXT.replace("seat: cradle_seat, axis: X, made_by: model, status: proposed",
                                                                  "seat: cradle_seat, axis: X, made_by: model, status: accepted"),
                          _ihash(rod), ["R"])
    with pytest.raises(ProposalError, match="did you mean"):
        st.create_purpose("s", "r", rod_loop.PURPOSE_TEXT.replace("form: retention", "form: retain"), _ihash(rod), ["R"])
    with pytest.raises(ProposalError, match="no component 'reel2'"):
        st.create_purpose("s", "r", rod_loop.PURPOSE_TEXT.replace("component: reel,", "component: reel2,"),
                          _ihash(rod), ["R"])


def test_purpose_with_descriptive_check_is_accepted_as_not_run(rod):
    """Criterion 2: the unbindable check B.c3 goes through only as 'descriptive, not run'."""
    st = ProposalStore(str(rod))
    before = {n: file_sha256(str(rod.with_name(n))) for n in ("rod_holder.py", "rod_holder.review.json")}
    p = st.create_purpose("rod purposes", "re-plan for a rod", rod_loop.PURPOSE_TEXT, _ihash(rod), ["R", "B"])
    assert p["kind"] == "purpose" and p["validation"]["descriptive"] == ["B.c3"]
    p = st.evaluate(p["id"])
    assert p["status"] == "ready" and not p["evaluation"]["needs_override"]
    rows = {c["id"]: c for c in p["evaluation"]["purpose"]["checks"]}
    assert rows["B.c3"]["state"] == "not run" and rows["B.c3"]["reads_as"].startswith("Descriptive, not run")
    # bindings to geometry the bracket-shaped solution lacks are not run, never passed
    assert rows["B.c1"]["state"] == "not run" and "cradle_seat" in rows["B.c1"]["reason"]
    assert rows["R.c4"]["form"] == "tool_access" and rows["R.c4"]["state"] in ("failing", "thin", "ample")
    assert "purposes are reviewed as text" in p["status_detail"]
    acc = st.accept(p["id"])
    assert acc["status"] == "accepted" and acc["accepted"]["reviewed"] == []
    # only the intent file was written; the solution stays stale against the new purposes
    assert {n: file_sha256(str(rod.with_name(n))) for n in before} == before
    res = load_and_build(str(rod))
    stale = ReviewRecord.load(str(rod.with_name("rod_holder.review.json"))).stale(res["intent"])
    assert "R" in stale and "B" in stale
    from dipm.assess import assess
    a = assess(res["design"], res["build"], res["intent"])
    c3 = [c for c in a.checks if c.id == "B.c3"][0]
    assert c3.state == "not run" and c3.reason.startswith("descriptive, not run") and not c3.terms


def test_accept_to_try_and_designer_edits(rod):
    st = ProposalStore(str(rod))
    p = st.evaluate(st.create_purpose("rod", "r", rod_loop.PURPOSE_TEXT, _ihash(rod), ["R"])["id"])
    t = st.try_purpose(p["id"])
    assert t["status"] == "trying"
    q = st.edit_purpose(p["id"], [{"op": "edit_assumption", "id": "R", "assumption_id": "R.a1",
                                   "fields": {"statement": "Rod and reel weigh up to 1.5 kg"}}], "heavier reels")
    assert q["source"] == "designer" and q["revises"] == p["id"]
    doc = intent_store.loads(q["patches"]["rod_holder.intent.yaml"]["new_text"]).to_plain()
    a1 = doc["intents"][0]["assumptions"][0]
    assert a1["made_by"] == "user" and "1.5 kg" in a1["statement"]
    assert st.get(p["id"])["status"] == "rejected"


# ---------------------------------------------------------------- evaluate, budget, alternatives

def test_evaluate_budget_and_attempt_log(rod):
    st = ProposalStore(str(rod))
    p = st.evaluate(st.create_purpose("rod", "r", rod_loop.PURPOSE_TEXT, _ihash(rod), ["R"])["id"])
    st.save_loop({**st.loop_state(), "budget": 2})
    r1 = st.evaluate_candidate({"rod_holder.py": "this is not python ("}, "A", p["id"], "syntax error")
    assert r1["loaded"] is False and r1["attempt"] == 1
    r2 = st.evaluate_candidate({"rod_holder.py": rod_loop.design_text(12.0, 60.0, label="A")}, "A", p["id"], "U cradle")
    assert r2["loaded"] and r2["attempt"] == 2 and r2["kernel"] == "pass"
    ids = {c["id"]: c for c in r2["intent_checks"]}
    assert ids["B.c1"]["state"] in ("ample", "thin") and ids["B.c3"]["state"] == "not run"
    assert ids["B.c1"]["form"] == "holds_cylinder" and ids["B.c1"]["ghosts"]
    with pytest.raises(ProposalError, match="budget"):
        st.evaluate_candidate({"rod_holder.py": rod_loop.design_text(label="A")}, "A", p["id"])
    log = st.loop_state()["attempts"]["A"]
    assert [a["n"] for a in log] == [1, 2] and log[0]["error"] and log[1]["kernel"] == "pass"
    # no label: no budget, nothing logged
    st.evaluate_candidate({"rod_holder.py": rod_loop.design_text(label="A")}, "", p["id"])
    assert len(st.loop_state()["attempts"]["A"]) == 2


def test_alternatives_group_carry_purpose_and_accept_closes_siblings(rod):
    st = ProposalStore(str(rod))
    p = st.evaluate(st.create_purpose("rod", "r", rod_loop.PURPOSE_TEXT, _ihash(rod), ["R", "B"])["id"])
    base = {"rod_holder.py": file_sha256(str(rod))}
    alt = lambda lab, lip, so: {"label": lab, "summary": f"{lab}", "rationale": "r",  # noqa: E731
                                "files": {"rod_holder.py": rod_loop.design_text(lip, so, label=lab)}}
    with pytest.raises(ProposalError, match="2 or 3"):
        st.create_alternatives("s", "r", [alt("A", 12, 60)], base, ["R"], p["id"])
    with pytest.raises(ProposalError, match="distinct label"):
        st.create_alternatives("s", "r", [alt("A", 12, 60), alt("A", 3, 60)], base, ["R"], p["id"])
    ps = st.create_alternatives("rod holders", "r", [alt("A", 12, 60), alt("B", 3, 60)], base, ["R", "B"], p["id"])
    assert len({q["group"] for q in ps}) == 1 and ps[0]["group"] == ps[0]["id"]
    assert all("rod_holder.intent.yaml" in q["patches"] and q["purpose"] == p["id"] for q in ps)
    a, b = (st.evaluate(q["id"]) for q in ps)
    sa = {c["id"]: c["state"] for c in a["evaluation"]["after"]["intent_checks"]}
    sb = {c["id"]: c["state"] for c in b["evaluation"]["after"]["intent_checks"]}
    assert sa["B.c2"] != "failing" and sb["B.c2"] == "failing"      # B's 3 mm lip: honest failure
    assert sa["B.c3"] == sb["B.c3"] == "not run"
    assert any(x["kind"] == "component" for x in a["evaluation"]["assumed"])
    with pytest.raises(ProposalError, match="accept anyway needs a reason"):
        st.accept(b["id"])
    acc = st.accept(a["id"], override_reason="R.c3 not run is fine" if a["evaluation"]["failing_checks"] else None)
    assert acc["status"] == "accepted"
    assert st.get(b["id"])["status"] == "rejected" and "accepted instead" in st.get(b["id"])["status_detail"]
    assert st.get(p["id"])["status"] == "accepted"
    assert "R" in acc["accepted"]["reviewed"]
    assert read_text(str(rod)) == rod_loop.design_text(12, 60, label="A")


def test_proposals_and_requests_are_scoped_per_design(tmp_path):
    from conftest import copy_bracket
    rod = copy_rod_holder(tmp_path)
    br = copy_bracket(tmp_path)
    sr, sb = ProposalStore(str(rod)), ProposalStore(str(br))
    sr.create_request("R", "rod", None)
    sb.create_request("A.3", "bracket", None)
    assert [r["node"] for r in sr.requests()] == ["R"] and [r["node"] for r in sb.requests()] == ["A.3"]
    p = sr.create_purpose("rod", "r", rod_loop.PURPOSE_TEXT, _ihash(rod), ["R"])
    assert [q["id"] for q in sr.list()] == [p["id"]] and sb.list() == []
    with pytest.raises(ProposalError):
        sb.get(p["id"])


# ---------------------------------------------------------------- end to end through MCP (criterion 4, 6)

def test_end_to_end_loop_through_mcp_with_a_stub_model(rod):
    from mcp import Client

    from dipm.mcp_server import build_server
    files = ("rod_holder.py", "rod_holder.intent.yaml", "rod_holder.review.json", "rod_holder.interpretations.json")
    snap = {f: file_sha256(str(rod.with_name(f))) for f in files}

    async def main():
        async with Client(build_server(str(rod))) as c:
            async def call(name, args=None):
                r = await c.call_tool(name, args or {})
                assert not r.is_error, r.content[0].text
                return json.loads(r.content[0].text)
            imp = await call("get_impact")
            assert imp["nodes"]["B"]["class"] == "invalidated" and imp["nodes"]["A"]["class"] == "survives"
            voc = await call("get_check_vocabulary")
            assert {f["form"] for f in voc["forms"]} >= {"holds_cylinder", "retention", "clears_box", "descriptive"}
            comps = await call("get_components")
            assert any(p["pack"] == "fishing_rod_blank" for p in comps["pack"])
            src = await call("get_source")
            pp = await call("propose_purposes", {"summary": "Re-plan for a fishing rod", "rationale": "stub",
                                                 "intent_file": rod_loop.PURPOSE_TEXT,
                                                 "base_hash": src["base_hashes"]["rod_holder.intent.yaml"],
                                                 "addresses_nodes": ["R", "B"]})
            assert pp["kind"] == "purpose" and pp["status"] == "ready"
            assert {c["id"]: c["state"] for c in pp["checks"]}["B.c3"] == "not run"
            for lab, lip in (("U", 12.0), ("low lip", 3.0)):
                ev = await call("evaluate", {"files": {"rod_holder.py": rod_loop.design_text(lip, 60.0, label=lab)},
                                             "label": lab, "purpose": pp["id"], "summary": "first try"})
                assert ev["kernel"] == "pass" and ev["attempt"] == 1
            alts = [{"label": lab, "summary": f"{lab} cradle", "rationale": "stub",
                     "files": {"rod_holder.py": rod_loop.design_text(lip, so, label=lab)}}
                    for lab, lip, so in (("U", 12.0, 60.0), ("low lip", 3.0, 60.0), ("close", 12.0, 35.0))]
            out = await call("propose_alternatives", {"summary": "Three cradles", "rationale": "stub",
                                                      "alternatives": alts,
                                                      "base_hashes": {"rod_holder.py": src["base_hashes"]["rod_holder.py"]},
                                                      "addresses_nodes": ["R", "B"], "purpose": pp["id"]})
            assert len(out["alternatives"]) == 3
            states = {}
            for v in out["alternatives"]:
                assert v["kind"] == "geometry" and v["status"] == "ready" and v["purpose"] == pp["id"]
                ch = {c["id"]: c["state"] for c in v["checks"]}
                states[v["alternative"]] = ch
                assert ch["B.c1"] != "not run" and ch["B.c3"] == "not run" and ch["R.c3"] == "not run"
                assert v["status_tiers"].startswith("Kernel ✓")
            assert states["U"]["B.c2"] in ("ample", "thin") and states["low lip"]["B.c2"] == "failing"
            assert states["close"]["B.c4"] == "failing"                          # the reel meets the wall
            assert [a["n"] for a in out["alternatives"][0]["attempts"]] == [1]
            lst = await call("list_proposals")
            assert sum(1 for p in lst["proposals"] if p["kind"] == "geometry") == 3
    asyncio.run(main())
    # criterion 6: the tools wrote nothing but proposals
    assert {f: file_sha256(str(rod.with_name(f))) for f in files} == snap


# ---------------------------------------------------------------- change notification (server)

def test_gui_purpose_edit_opens_one_request(rod):
    from starlette.testclient import TestClient

    from dipm.server.app import create_app
    app = create_app(str(rod), watch_files=False)
    with TestClient(app) as cl:
        h = cl.get("/api/intent").json()["hash"]
        r = cl.patch("/api/intent", json={"base_hash": h, "ops": [{"op": "edit_statement", "id": "A",
                                                                     "statement": "Wall mounting, hidden screws"}]})
        assert r.status_code == 200 and r.json()["requests_created"]
        h = r.json()["intent"]["hash"]
        r2 = cl.patch("/api/intent", json={"base_hash": h, "ops": [{"op": "edit_statement", "id": "A",
                                                                      "statement": "Wall mounting, two screws"}]})
        assert r2.json()["requests_created"] == []
        reqs = cl.get("/api/requests").json()
        assert reqs["waiting"] == 1 and reqs["requests"][0]["kind"] == "purpose edit"
        b = cl.post("/api/build", json={}).json()
        assert b["impact"]["nodes"]["R"]["class"] == "changed" and b["impact"]["nodes"]["B"]["class"] == "invalidated"
        assert b["components"] == [] and b["ghosts"] == []


# ---------------------------------------------------------------- pack data (criterion 7)

def test_pack_data_matches_the_report():
    F, M, A, S = packs.FDM, packs.MATERIALS, packs.ANCHORS, packs.SAFETY_FACTORS
    ph = lambda e: e["placeholder"]  # noqa: E731
    # FDM process (report table rows)
    assert ph(F["position_tolerance"]) and F["position_tolerance"]["status"] == "provisional"
    assert F["position_tolerance"]["value"] == 0.1 and F["position_tolerance"]["scale"] == 0.0015
    d = F["dimension_tolerance"]
    assert not ph(d) and d["bias"] == -0.10 and d["value"] == 0.10 and d["symmetric_fallback"] == 0.2
    assert ph(F["z_tolerance"]) and F["z_tolerance"]["bias"] == 0.05
    assert not ph(F["extrusion_width_factor"]) and F["extrusion_width_factor"]["value"] == 1.125
    assert not ph(F["overhang_max_deg"]) and (F["overhang_max_deg"]["lo"], F["overhang_max_deg"]["hi"]) == (40.0, 60.0)
    assert ph(F["bridge_max_mm"]) and ph(F["horizontal_hole_max_d"]) and F["horizontal_hole_max_d"]["value"] == 10.0
    assert not ph(F["vertical_hole_undersize"]) and F["vertical_hole_undersize"]["value"] == -0.15
    assert ph(F["horizontal_hole_undersize"]) and ph(F["elephant_foot_per_side"])
    assert not ph(F["thin_wall_delta"]) and F["thin_wall_delta"]["value"] == -0.03
    r = F["across_layer_strength_ratio"]
    assert not ph(r) and (r["value"], r["lo"], r["hi"]) == (0.5, 0.3, 0.8)
    # materials
    for m, (v, lo, hi) in {"PLA": (50, 40, 58), "PETG": (45, 32, 52), "ABS": (33, 25, 40)}.items():
        t = M[m]["tensile_mpa"]
        assert (t["value"], t["lo"], t["hi"]) == (v, lo, hi) and not ph(t) and "short-term" in t["basis"]
        assert not ph(M[m]["flexural_mpa"]) and M[m]["flexural_mpa"]["governing"] is False
        assert ph(M[m]["sustained_derate"]) and M[m]["sustained_derate"]["status"] == "provisional"
        assert not ph(M[m]["hdt_c"])
    assert M["PLA"]["sustained_derate"]["value"] == 0.3 and M["PETG"]["sustained_derate"]["value"] == 0.4
    # anchors: mean ultimate with basis and the source's own factor
    plug = A["drywall with anchors"]
    assert packs.DEFAULT_INSTALL == "drywall with anchors" and "plastic plug" in plug["label"]
    assert (plug["tension_n"]["value"], plug["tension_n"]["lo"], plug["tension_n"]["hi"]) == (250, 130, 450)
    assert plug["tension_n"]["basis"] == "mean ultimate" and plug["tension_n"]["source_sf"] == 2.0 and not ph(plug["tension_n"])
    assert (plug["shear_n"]["value"], plug["shear_n"]["lo"], plug["shear_n"]["hi"]) == (600, 310, 1050)
    assert A["drywall, plastic toggle"]["tension_n"]["value"] == 640
    assert A["drywall, metal strap toggle"]["tension_n"]["value"] == 1000
    wood = A["wood stud"]["tension_n"]
    assert (wood["value"], wood["lo"], wood["hi"]) == (2500, 1800, 5200) and ph(wood) and wood["status"] == "provisional"
    # safety factors per protected quantity
    assert [S[k]["value"] for k in ("drywall anchor", "wood screw", "printed sustained", "printed short-term")] == [4, 5, 4, 2]
    # human scale, screws
    assert packs.HAND_MM["placeholder"] is False and packs.HAND_MM["length"] == 190.0
    assert packs.FINGERTIP_MM["placeholder"] is True and packs.FINGERTIP_MM["breadth"] == 18.0
    assert packs.SCREW_REFERENCE_LENGTH_MM["placeholder"] is True
    # every value says what it is; sourced ones cite
    for name, e in packs.entries().items():
        assert e["note"] and e["status"] in ("sourced", "provisional", "placeholder"), name
        assert e["placeholder"] == (e["status"] != "sourced"), name
        if e["status"] != "placeholder":
            assert e["sources"] and all(s in packs.SOURCES for s in e["sources"]), name
            assert e["basis"], name


def test_rc1_sf_is_not_double_counted():
    """SF 4 on PETG short-term strength; the sustained derate is reference data only."""
    from dipm.checks import material_sf, anchor_sf
    assert material_sf("sustained") == (4.0, "printed sustained")
    assert material_sf("short") == (2.0, "printed short-term")
    assert material_sf("sustained", floor=2.0)[0] == 4.0

    class E:
        context = {"install": "wood stud"}
    assert anchor_sf(E())[1] == 5.0
    E.context = {}
    assert anchor_sf(E())[1] == 4.0

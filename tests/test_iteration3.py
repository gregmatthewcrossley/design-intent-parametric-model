"""GUI iteration 3 engine work (docs/gui.md §8.2, 3E.1–3E.10) and the iteration-2 review
changes (B9: NOTES #44, #45, #48, #49, #53, #54, #55; B3–B6)."""
import json
import os
import sys

import pytest
from starlette.testclient import TestClient

from dipm import checks, display, interpret, quantity
from dipm.assess import assess_file
from dipm.checks import classify
from dipm.fileio import file_sha256
from dipm.proposals import ProposalError, ProposalStore, outline_changed
from dipm.quantity import Quantity, propagate, register_sampler, worst_margin
from dipm.server.app import create_app

from conftest import EXAMPLE, a3_offset_patch, copy_bracket


# ---------------------------------------------------------------- quantities (3E.2)

def test_propagate_worst_case_corners():
    q = {"a": Quantity(2.0, 1.0, 3.0), "b": Quantity(4.0, 4.0, 4.0), "c": Quantity(1.0, 0.5, 2.0)}
    p = propagate(lambda a, b, c: a * b / c, q)
    assert p.nominal == 8.0 and p.lo == pytest.approx(2.0) and p.hi == pytest.approx(24.0)
    assert p.at_hi == {"a": 3.0, "b": 4.0, "c": 0.5} and p.evaluations == 1 + 4   # b unranged


def test_worst_margin_senses_with_ranged_limit():
    x = {"v": Quantity(10.0, 9.0, 11.0), "lim": Quantity(12.0, 10.5, 13.0)}
    r = worst_margin(lambda v, lim: v, lambda v, lim: lim, "<=", x)
    assert r["margin"] == pytest.approx(2.0) and r["margin_worst"] == pytest.approx(-0.5)
    assert r["worst"] == 11.0 and r["limit_worst"] == 10.5
    r = worst_margin(lambda v, lim: v, lambda v, lim: lim, ">=", x)
    assert r["margin"] == pytest.approx(-2.0) and r["margin_worst"] == pytest.approx(-4.0)
    with pytest.raises(ValueError):
        worst_margin(lambda v, lim: v, lambda v, lim: lim, "<", x)


def test_sampling_is_a_hook_only():
    q = {"a": Quantity(1.0, 0.0, 2.0)}
    with pytest.raises(NotImplementedError, match="hook"):
        propagate(lambda a: a, q, method="sample")
    register_sampler("_test", lambda f, inputs, opts: {"nominal": 1.0, "lo": 0.1, "hi": 1.9, "evaluations": 7})
    try:
        p = propagate(lambda a: a, q, method="_test")
        assert (p.lo, p.hi, p.method, p.evaluations) == (0.1, 1.9, "_test", 7)
    finally:
        quantity._SAMPLERS.pop("_test", None)


def test_classify_bands():
    assert classify(-0.1, 10.0) == ("failing", -0.01)
    assert classify(0.5, 10.0)[0] == "thin"            # below 10 % of the limit
    assert classify(2.0, 10.0)[0] == "ample"
    assert classify(1.0, 0.0, thin_abs=2.0) == ("thin", None)
    assert classify(3.0, 0.0, thin_abs=2.0)[0] == "ample"


# ---------------------------------------------------------------- the bracket's honest results (3E.1–3E.3, 3E.10)

@pytest.fixture(scope="module")
def bracket_assessment(bracket, bracket_build):
    a, _rec = assess_file(bracket, bracket_build, str(EXAMPLE))
    return a


def _check(a, cid):
    return next(c for c in a.checks if c.id == cid)


def test_rc1_load_fails_with_the_expected_order_of_magnitude(bracket_assessment):
    """architecture §8.4a: upper-anchor pull-out ≈ 600 N at 20 kg, ≈ 1.2 kN with SF 2."""
    c = _check(bracket_assessment, "R.c1")
    assert c.state == "failing" and c.rung == 2 and c.plain.startswith("Holds 20 kg")
    t = {x.name: x for x in c.terms}
    anc = t["upper anchor pull-out × SF"]
    assert anc.nominal == pytest.approx(1216, rel=0.02) and anc.limit == 200.0 and anc.limit_worst == 150.0
    assert anc.margin < 0 and anc.margin_worst < anc.margin and anc.state == "failing"
    bend = t["arm bending stress × SF"]
    assert bend.nominal == pytest.approx(235, rel=0.02) and bend.limit == pytest.approx(45.0)   # PETG, in-layer
    assert bend.margin < 0 and bend.state == "failing"
    assert any("pivots rigidly" in m for m in c.method_assumptions)
    assert c.assumptions[0]["id"] == "R.a1" and c.faces


def test_rc4_tool_access_touches_and_fails_at_worst_case(bracket_assessment):
    c = _check(bracket_assessment, "R.c4")
    t = {x.name: x for x in c.terms}
    up, low = t["screw 1 driver clearance"], t["screw 0 driver clearance"]
    assert 0 <= up.nominal <= 0.01 and up.margin_worst < 0 and up.state == "failing"
    assert low.nominal == pytest.approx(41.0, abs=0.05) and low.state == "ample"
    assert c.state == "failing" and c.governing == up.name


def test_rc2_overhang_ample_in_the_inferred_orientation(bracket_assessment):
    c = _check(bracket_assessment, "R.c2")
    assert c.state == "ample" and c.headline().limit == 45.0


def test_tiered_status_never_says_pass(bracket_assessment, bracket_build):
    st = bracket_assessment.status
    assert st["headline"] == "Kernel ✓ · Intent checks 3 of 11 run · 2 failing"
    assert st["intent"]["failing_ids"] == ["R.c1", "R.c4"] and st["intent"]["not_run"] == 8
    assert "PASS" not in json.dumps(st)
    from dipm.report import build_report
    out = build_report(bracket_build, assessment=bracket_assessment)
    assert "PASS" not in out and "Result: kernel invariants pass · intent checks: 3 of 11 run, 2 failing" in out


def test_cli_report_has_no_bare_pass(capsys):
    from dipm.cli import main
    assert main(["build", str(EXAMPLE)]) == 3
    out = capsys.readouterr().out
    assert "PASS" not in out and "[FAILING] R.c1" in out


def test_orientation_inference_on_the_bracket(bracket_assessment):
    o = bracket_assessment.orientation
    assert o["chosen"]["down_face"] == "shelf face" and o["up"] == [0.0, 0.0, -1.0]
    assert o["runner_up"]["down_face"] == "wall face"
    assert o["chosen"]["overhang_mm2"] == 0 and o["chosen"]["bed_mm2"] > o["runner_up"]["bed_mm2"]
    sides = [c for c in o["candidates"] if c["up"][0] != 0]
    assert len(sides) == 2 and all(c["overhang_mm2"] > 3000 for c in sides)
    assert "4,784 mm²" in o["rationale"] and "runner-up wall face down" in o["rationale"]
    assert o["made_by"] == "model" and not o["reviewed"]


# ---------------------------------------------------------------- record until accepted (3E.6, 3E.10)

def _intent(design):
    return design.with_name("shelf_bracket.intent.yaml")


def test_record_until_accepted(tmp_path):
    design = copy_bracket(tmp_path)
    rec = design.with_name("shelf_bracket.resolution.json")
    rec.unlink()
    before = _intent(design).read_bytes()
    with TestClient(create_app(str(design), watch_files=False)) as c:
        b = c.post("/api/build", json={}).json()
        assert rec.exists() and _intent(design).read_bytes() == before        # nothing writes the intent file
        data = json.loads(rec.read_text())
        assert set(data["context"]["assumed"]) == {"layer_height", "nozzle"}
        assert data["context"]["assumed"]["layer_height"]["made_by"] == "model"
        assert data["orientation"]["label"] == "Print with the shelf face down"
        assert b["orientation"]["reviewed"] is False and b["provenance"]["orientation"]["guess"]
        assert b["context"]["items"]["material"]["reviewed"] and not b["context"]["items"]["nozzle"]["reviewed"]
        # accept the orientation: a root assumption in the intent file
        j = c.post("/api/orientation", json={"action": "accept"}).json()
        from dipm import intent_store
        root = intent_store.load(str(_intent(design))).to_plain()["intents"][0]
        (a4,) = [a for a in root["assumptions"] if a.get("about") == "print_orientation"]
        assert a4["status"] == "accepted" and a4["value"] == "0,0,-1" and a4["made_by"] == "model"
        assert "runner-up wall face down" in a4["rationale"]
        assert j["build"]["orientation"]["reviewed"] is True
        k = c.post("/api/orientation", json={"action": "infer"}).json()
        assert "never replaces" in k["note"] and k["build"]["orientation"]["reviewed"] is True
        assert c.post("/api/orientation", json={"action": "accept"}).status_code == 400
        # accept the context
        j = c.post("/api/context", json={"action": "accept"}).json()
        assert "layer_height: 0.2 mm" in _intent(design).read_text()
        assert not j["build"]["context"]["assumed"]


def test_no_context_assumes_pla_fdm(tmp_path):
    design = copy_bracket(tmp_path)
    p = _intent(design)
    p.write_text("".join(l for l in p.read_text().splitlines(True) if not l.startswith("context:")))
    with TestClient(create_app(str(design), watch_files=False)) as c:
        b = c.post("/api/build", json={}).json()
    assert b["context"]["summary"] == "PLA · FDM 0.2 mm" and b["context"]["assumed"]
    assert b["appearance"]["layer_pitch"] == 0.2 and b["appearance"]["build_direction"] == [0.0, 0.0, -1.0]
    # PLA: the bending limit becomes PLA's (placeholder 50 MPa)
    rc1 = next(c for c in b["intent_checks"] if c["id"] == "R.c1")
    bend = next(t for t in rc1["terms"] if t["name"].startswith("arm bending"))
    assert bend["limit"] == pytest.approx(50.0)


def test_inference_reruns_only_when_inputs_change(tmp_path):
    design = copy_bracket(tmp_path)
    rec = design.with_name("shelf_bracket.resolution.json")
    with TestClient(create_app(str(design), watch_files=False)) as c:
        c.post("/api/build", json={})
        key = json.loads(rec.read_text())["orientation"]["key"]
        mtime = rec.stat().st_mtime_ns
        c.post("/api/build", json={"params": {"shelf_depth": 260}})        # not an input: keyed on the defaults
        assert json.loads(rec.read_text())["orientation"]["key"] == key and rec.stat().st_mtime_ns == mtime
        j = c.post("/api/orientation", json={"action": "infer"}).json()
        assert j["note"] == "re-inferred" and json.loads(rec.read_text())["orientation"]["key"] == key


# ---------------------------------------------------------------- /api/display (3E.8)

def test_display_stub_and_match(monkeypatch):
    mac = {"id": 1, "name": "Built-in Retina Display", "builtin": True, "main": True, "mm": [301.8, 196.0],
           "px": [1800, 1169], "origin": [0, 0]}
    tv = {"id": 2, "name": "TV", "builtin": False, "mm": [0, 0], "px": [1920, 1080], "origin": [1800, 0]}
    monkeypatch.setenv("DIPM_DISPLAY_STUB", json.dumps([mac, tv]))
    with TestClient(create_app(str(EXAMPLE), watch_files=False)) as c:
        j = c.get("/api/display").json()
        assert j["source"] == "stub" and [d["plausible"] for d in j["displays"]] == [True, False]
        assert "no physical size" in j["displays"][1]["implausible_reason"]
        m = c.get("/api/display?width=1800&height=1169&dpr=2").json()["match"]
        assert m["index"] == 0 and m["display"]["name"] == "Built-in Retina Display"
        m = c.get("/api/display?width=1920&height=1080&dpr=1&internal=false").json()["match"]
        assert m["index"] == 1


def test_display_provider_and_unknown_platform(monkeypatch):
    monkeypatch.delenv("DIPM_DISPLAY_STUB", raising=False)
    display.set_provider(lambda: {"source": "stub", "displays": [{"id": 9, "mm": [500, 300], "px": [2560, 1536]}]})
    try:
        d = display.displays()
        assert d["displays"][0]["name"] == "Display 9" and d["displays"][0]["plausible"]
    finally:
        display.set_provider(None)
    monkeypatch.setattr(sys, "platform", "linux")
    d = display.displays()
    assert d["source"] == "unknown" and d["displays"] == []
    assert display.match(d, {"width": 1800, "height": 1169})["index"] is None


# ---------------------------------------------------------------- B9: iteration-2 review changes

def test_no_automatic_baseline_and_first_open_review(tmp_path):
    design = copy_bracket(tmp_path)
    review = design.with_name("shelf_bracket.review.json")
    review.unlink()
    with TestClient(create_app(str(design), watch_files=False)) as c:
        b = c.post("/api/build", json={}).json()
        assert not b["intent"]["review_exists"] and not review.exists()
        assert {n["review_state"] for n in b["tree"]["nodes"].values()} == {"unreviewed"}
        c.post("/api/review", json={"action": "one_by_one"})
        assert json.loads(review.read_text()) == {"version": 1, "reviewed": {}}
        j = c.post("/api/review", json={"action": "all"}).json()
        assert set(json.loads(review.read_text())["reviewed"]) == set(j["build"]["tree"]["nodes"])
        assert {n["review_state"] for n in j["build"]["tree"]["nodes"].values()} == {"reviewed"}


def test_rename_migrates_preferences_and_optionally_feature_ids(tmp_path):
    design = copy_bracket(tmp_path)
    prefs = design.with_name("shelf_bracket.prefs.json")
    prefs.write_text(json.dumps({"dipm_preferences": 1, "answers": {
        "hole.extent@shelf_bracket:A.3": {"reading": "through_plate"},
        "hole.extent@shelf_bracket:A.P": {"reading": "through_plate"}}}))
    with TestClient(create_app(str(design), prefs=str(prefs), watch_files=False)) as c:
        h = c.get("/api/intent").json()
        j = c.post("/api/intent/rename", json={"base_hash": h["hash"], "design_hash": h["design_hash"],
                                               "old": "A.3", "new": "A.C"}).json()
        assert j["migrated_preferences"] == 1 and not j["renamed_features"]
        answers = json.loads(prefs.read_text())["answers"]
        assert "hole.extent@shelf_bracket:A.C" in answers and "hole.extent@shelf_bracket:A.3" not in answers
        assert '"A.3.cable"' in design.read_text()                # feature ids untouched by default
        h = c.get("/api/intent").json()
        j = c.post("/api/intent/rename", json={"base_hash": h["hash"], "design_hash": h["design_hash"],
                                               "old": "A.P", "new": "A.W", "rename_features": True}).json()
        assert j["renamed_features"] and '"A.W.holes"' in design.read_text() and '"A.P.holes"' not in design.read_text()
        assert '"A.3.cable"' in design.read_text()
        b = c.post("/api/build", json={}).json()
        assert b["kernel_ok"] and "A.W.holes" in [f["id"] for f in b["features"]]


def test_codemod_feature_rename_unit():
    from dipm.codemod import rename_intent_id
    src = 'd.hole("A.3.cable", on=f, at=p, spec=s, tags=(intent("A.3", "hole"),))\nd.hole("A.30.x", f, p, s)\n'
    out, n = rename_intent_id(src, "A.3", "A.C")
    assert '"A.3.cable"' in out and 'intent("A.C"' in out and n == 1
    out, n = rename_intent_id(src, "A.3", "A.C", rename_features=True)
    assert '"A.C.cable"' in out and '"A.30.x"' in out and n == 2


def test_outline_changed_unit():
    sb = [("t1", "plane"), ("t2", "cyl"), ("t3", "cone")]
    sa = [("t1", "plane"), ("t2", "cyl"), ("t4", "cone")]
    ob, oa = outline_changed(sb, sa, [(1.0,), (2.0,), (3.0,)], [(1.5,), (2.0,), (3.0,)], [2], [2])
    assert (ob, oa) == ([0], [0])


def test_proposal_view_params_and_verdict_at_defaults(tmp_path):
    design = copy_bracket(tmp_path)
    st = ProposalStore(str(design))
    base = {"shelf_bracket.py": file_sha256(str(design))}
    p = st.create("A.3 offset", "r", {"shelf_bracket.py": a3_offset_patch(design.read_text())}, base, ["A.3"])
    ev = st.evaluate(p["id"], view_params={"shelf_depth": 250})["evaluation"]
    assert ev["view_params"]["shelf_depth"] == 250 and ev["params"]["shelf_depth"] == 200
    assert {"outline_before", "outline_after"} <= set(ev["changed_faces"])
    assert ev["failing_checks"] == [] and not ev["needs_override"]


def test_accept_anyway_records_an_override(tmp_path):
    design = copy_bracket(tmp_path)
    st = ProposalStore(str(design))
    base = {"shelf_bracket.py": file_sha256(str(design))}
    # addresses R: R.c1 (and R.c4) fail there, so accepting needs a reason (#54)
    new = design.read_text().replace('doc="architecture.md §8 worked example"', 'doc="worked example (renamed)"')
    p = st.create("doc tweak", "r", {"shelf_bracket.py": new}, base, ["R"])
    p = st.evaluate(p["id"])
    ev = p["evaluation"]
    assert ev["needs_override"] and "R.c1" in ev["failing_checks"] and "R.c4" in ev["failing_checks"]
    with pytest.raises(ProposalError, match="needs a reason"):
        st.accept(p["id"])
    with TestClient(create_app(str(design), watch_files=False)) as c:
        r = c.post(f"/api/proposals/{p['id']}/accept", json={})
        assert r.status_code == 409
        j = c.post(f"/api/proposals/{p['id']}/accept", json={"override_reason": "load case under review"}).json()
        assert j["proposal"]["status"] == "accepted"
        ov = json.loads(design.with_name("shelf_bracket.review.json").read_text())["overrides"]["R"]
        assert ov["reason"] == "load case under review" and "R.c1" in ov["failing"] and ov["proposal"] == p["id"]
        assert j["build"]["tree"]["nodes"]["R"]["review_state"] == "reviewed_failing"
        assert j["build"]["tree"]["nodes"]["A"]["review_state"] == "reviewed"


def test_requests_waiting_and_prompt(tmp_path):
    design = copy_bracket(tmp_path)
    with TestClient(create_app(str(design), watch_files=False)) as c:
        c.post("/api/requests", json={"node": "A.3", "note": "n"})
        j = c.get("/api/requests").json()
        assert j["waiting"] == 1 and "get_requests" in j["prompt"] and "propose_patch" in j["prompt"]
        assert c.get("/api/proposals").json()["waiting"] == 1


def test_lock_key_includes_lowering_code(bracket, monkeypatch):
    from dipm.interpret import Preferences, lock_key, read_lock
    k = lock_key(bracket.lock.design_file, Preferences())
    assert k["code_sha256"] == interpret.code_digest() and k["packages"]["cadquery-ocp-novtk"]
    assert read_lock(bracket.lock.lock).key == k                    # the committed lock is fresh
    monkeypatch.setattr(interpret, "code_digest", lambda: "0" * 64)
    assert read_lock(bracket.lock.lock).key != lock_key(bracket.lock.design_file, Preferences())


def test_tags_read_statements_from_the_intent_file(bracket_build):
    from dipm import Design, XY, Profile, intent
    from dipm.sketch import rect_points
    f = next(f for f in bracket_build.faces()
             if any(str(e.tag) == "A.P.holes.countersink(1)" for e in bracket_build.ledger.who(f)))
    text = str(bracket_build.why(f))
    assert "pattern@A.P (Wall screw pattern)" in text and "hole@A.P.2 (Upper wall screw hole)" in text
    d = Design("nofile")
    d.extrude("E", Profile(XY, rect_points(0.0, 0.0, 10.0, 10.0)), 2.0, tags=intent("R", "skeleton", "a note"))
    b = d.build()
    assert "skeleton@R (a note)" in str(b.why(b.faces()[0]))


def test_provenance_and_feasible_vs_meant(tmp_path):
    design = copy_bracket(tmp_path)
    sid = "A.3.cable/centered_on.point"
    with TestClient(create_app(str(design), watch_files=False)) as c:
        b = c.post("/api/build", json={}).json()
        pv = b["provenance"]
        assert pv[f"slot:{sid}"]["guess"] and pv["assumption:R.a1"]["guess"] and pv["context:nozzle"]["guess"]
        assert not pv["context:material"]["guess"]
        slot = next(s for s in b["interpretations"]["slots"] if s["id"] == sid)
        assert slot["feasible"] == ["exposed_region_midpoint"] and slot["resolution"] == "unconfirmed"
        assert all(s["resolution"] == "unconfirmed" for s in b["interpretations"]["slots"])
        j = c.post("/api/review", json={"action": "accept_item", "key": f"slot:{sid}",
                                        "value": slot["chosen"]}).json()
        assert not j["build"]["provenance"][f"slot:{sid}"]["guess"]
        h = c.get("/api/intent").json()["hash"]
        r = c.request("PATCH", "/api/intent", json={"base_hash": h, "ops": [
            {"op": "edit_assumption", "id": "R", "assumption_id": "R.a1", "fields": {"status": "accepted"}}]}).json()
        assert not r["build"]["provenance"]["assumption:R.a1"]["guess"]


def test_intent_file_header_note():
    head = EXAMPLE.with_name("shelf_bracket.intent.yaml").read_text().split("design:")[0]
    assert "A comment belongs to the item above it" in head

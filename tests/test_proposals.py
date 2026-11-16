"""Proposals (docs/gui.md §7.3): create -> evaluate -> accept / reject -> feedback, stale bases,
disallowed paths, unified diffs; over the shared store and the GUI server's HTTP API."""
import json
import os

import pytest
from starlette.testclient import TestClient

from dipm.fileio import file_sha256
from dipm.proposals import ProposalError, ProposalStore, apply_unified_diff, text_diff
from dipm.server.app import create_app

from conftest import a3_offset_patch, copy_bracket


@pytest.fixture()
def design(tmp_path):
    return copy_bracket(tmp_path)


def base(design):
    return {"shelf_bracket.py": file_sha256(str(design)),
            "shelf_bracket.intent.yaml": file_sha256(str(design.with_name("shelf_bracket.intent.yaml")))}


def test_unified_diff_round_trip_and_offsets():
    a = "".join(f"line {i}\n" for i in range(30))
    b = a.replace("line 7\n", "line seven\n").replace("line 20\n", "")
    d = text_diff("x", a, b)
    assert apply_unified_diff(a, d) == b
    shifted = d.replace("@@ -5,", "@@ -9,")                # wrong line numbers, unique context: still applies
    assert apply_unified_diff(a, shifted) == b
    with pytest.raises(ProposalError, match="does not apply"):
        apply_unified_diff(a.replace("line 6\n", "line six\n"), d)


def test_disallowed_paths_and_missing_base_are_rejected(design, tmp_path):
    st = ProposalStore(str(design))
    for bad in ("../etc/passwd", "/etc/hosts", "other.py", "shelf_bracket.interpretations.json",
                str(tmp_path / "shelf_bracket.review.json")):
        with pytest.raises(ProposalError, match="not in the design's file set"):
            st.create("s", "r", {bad: "x"}, {bad: "0"})
    with pytest.raises(ProposalError, match="missing base hash"):
        st.create("s", "r", {"shelf_bracket.py": "x"}, {})
    with pytest.raises(ProposalError, match="schema|unknown key|must"):
        st.create("s", "r", {"shelf_bracket.intent.yaml": "design: x\nintents: []\n"}, base(design))
    assert st.list() == []                                  # nothing stored for a refused proposal


def test_lifecycle_evaluate_accept_records_review_and_clears_staleness(design):
    intent = design.with_name("shelf_bracket.intent.yaml")
    review = design.with_name("shelf_bracket.review.json")
    new_intent = intent.read_text().replace("Cable pass-through, centered on the plate",
                                            "Cable pass-through, offset 10 mm above the lower screw")
    intent.write_text(new_intent)                            # the designer's intent edit: A.3 is now stale
    st = ProposalStore(str(design))
    p = st.create("A.3: 10 mm above the lower screw", "follow the new intent",
                  {"shelf_bracket.py": a3_offset_patch(design.read_text())}, base(design), ["A.3"])
    assert p["status"] == "pending" and p["id"] == "p1"
    assert os.path.exists(os.path.join(design.parent, ".dipm", "proposals", "p1.json"))
    p = st.evaluate("p1")
    assert p["status"] == "ready", p.get("status_detail")
    ev = p["evaluation"]
    assert ev["ok"] and ev["after"]["status"] == "PASS" and ev["sweep"]["failing"] == []
    assert ev["before"]["stale_nodes"] == ["A.3"] and ev["after"]["stale_nodes"] == []
    ch = {c["id"]: c for c in ev["semantic_diff"]["features"]["changed"]}
    assert ch["A.3.cable"]["detail"]["before"]["centres"] == [[0.0, 5.0, 32.5]]
    assert ch["A.3.cable"]["detail"]["after"]["centres"][0][2] == pytest.approx(19.0)    # 9 + 10 mm
    assert [s["id"] for s in ev["semantic_diff"]["interpretations"]["removed"]] == ["A.3.cable/centered_on.point"]
    assert "-    d.hole(\"A.3.cable\", on=mount_face, at=centered_on(mount_face)" in ev["text_diff"]["shelf_bracket.py"]
    assert len(ev["changed_faces"]["after"]) == 1 and ev["face_tags"]["after"][ev["changed_faces"]["after"][0]] == \
        "A.3.cable.wall(0)"
    assert os.path.getsize(st.mesh_path("p1", "after")) > 1000
    assert "at=centered_on(mount_face)" in design.read_text()               # inert until accepted
    p = st.accept("p1")
    assert p["status"] == "accepted" and "offset(wall_pts[0], Z, 10.0)" in design.read_text()
    assert p["accepted"]["reviewed"] == ["A.3"]
    rec = json.loads(review.read_text())
    assert rec["reviewed"]["A.3"]["content"]["statement"].endswith("lower screw")
    lock = json.loads(design.with_name("shelf_bracket.interpretations.json").read_text())
    assert lock["key"]["design_source_sha256"] == file_sha256(str(design))  # the resolved lock came along
    with pytest.raises(ProposalError):
        st.accept("p1")


def test_reject_with_comment_feedback_and_revision(design):
    st = ProposalStore(str(design))
    p = st.create("A.3 offset 12", "first try", {"shelf_bracket.py": a3_offset_patch(design.read_text(), 12.0)},
                  base(design), ["A.3"])
    st.evaluate(p["id"])
    st.reject(p["id"], "The intent says 10 mm, not 12.")
    fb = st.feedback(p["id"])[0]
    assert fb["status"] == "rejected" and fb["feedback"][-1] == {**fb["feedback"][-1], "kind": "reject",
                                                                  "comment": "The intent says 10 mm, not 12."}
    q = st.create("A.3 offset 10", "per feedback", {"shelf_bracket.py": a3_offset_patch(design.read_text(), 10.0)},
                  base(design), ["A.3"], revises=p["id"])
    assert q["revises"] == "p1" and q["id"] == "p2"
    with pytest.raises(ProposalError):
        st.accept(p["id"])                                  # rejected proposals cannot be applied


def test_stale_base_is_marked_and_not_applicable(design):
    st = ProposalStore(str(design))
    old = base(design)
    design.write_text(design.read_text() + "\n# edited by hand\n")
    p = st.create("late", "r", {"shelf_bracket.py": a3_offset_patch(design.read_text())}, old, ["A.3"])
    assert p["status"] == "stale" and "changed since" in p["status_detail"]
    # a proposal that goes stale after evaluation
    q = st.create("fresh", "r", {"shelf_bracket.py": a3_offset_patch(design.read_text())}, base(design), ["A.3"])
    st.evaluate(q["id"])
    design.write_text(design.read_text() + "# another edit\n")
    assert st.get(q["id"])["status"] == "ready"
    assert [x["status"] for x in st.list()] == ["stale", "stale"]
    with pytest.raises(ProposalError, match="stale"):
        st.accept(q["id"])


def test_unified_diff_proposal_for_the_intent_file(design):
    intent = design.with_name("shelf_bracket.intent.yaml")
    new = intent.read_text().replace("statement: Shelf support", "statement: Shelf support from below")
    st = ProposalStore(str(design))
    p = st.create("rename B", "r", {str(intent): text_diff("shelf_bracket.intent.yaml", intent.read_text(), new)},
                  base(design), ["B"])
    assert p["patches"]["shelf_bracket.intent.yaml"]["kind"] == "diff"
    p = st.evaluate(p["id"])
    assert p["evaluation"]["semantic_diff"]["intent"]["changed"] == [
        {"id": "B", "statement": {"before": "Shelf support", "after": "Shelf support from below"}}]
    st.accept(p["id"])
    assert intent.read_text() == new


def test_http_api_create_accept_reject_and_requests(design):
    with TestClient(create_app(str(design), watch_files=False)) as c:
        c.post("/api/build", json={})
        h = c.get("/api/intent").json()["hash"]
        r = c.request("PATCH", "/api/intent", json={"base_hash": h, "ops": [
            {"op": "edit_statement", "id": "A.3", "statement": "Cable pass-through, offset 10 mm above the lower screw"}]})
        assert r.json()["build"]["tree"]["nodes"]["A.3"]["stale"]
        req = c.post("/api/requests", json={"node": "A.3", "note": "keep it clear of the countersink"}).json()
        assert req["status"] == "open" and req["change"]["reviewed"]["statement"].endswith("centered on the plate")
        assert c.post("/api/requests", json={"node": "ZZ"}).status_code == 400
        src = {"shelf_bracket.py": a3_offset_patch(design.read_text())}
        assert c.post("/api/proposals", json={"summary": "x", "files": {"../x": "y"}, "base_hashes": {}}).status_code == 400
        r = c.post("/api/proposals", json={"summary": "A.3 offset", "rationale": "r", "files": src,
                                           "base_hashes": base(design), "addresses_nodes": ["A.3"]})
        assert r.status_code == 201
        pid = r.json()["id"]
        ProposalStore(str(design)).evaluate(pid)            # (the server also evaluates in a background thread)
        for _ in range(100):
            if c.get(f"/api/proposals/{pid}").json()["status"] == "ready":
                break
            import time
            time.sleep(0.1)
        p = c.get(f"/api/proposals/{pid}").json()
        assert p["status"] == "ready" and "lock" not in p["evaluation"]
        assert c.get(f"/api/proposals/{pid}/mesh/after").status_code == 200
        assert c.get(f"/api/proposals/{pid}/mesh/sideways").status_code == 404
        j = c.post(f"/api/proposals/{pid}/accept", json={}).json()
        assert j["proposal"]["status"] == "accepted"
        b = j["build"]
        assert b["status"] == "PASS" and not b["tree"]["nodes"]["A.3"]["stale"] and b["stale"] == {}
        cable = next(f for f in b["features"] if f["id"] == "A.3.cable")
        assert cable["detail"]["centres"][0][2] == pytest.approx(19.0)
        lst = c.get("/api/proposals").json()
        assert lst["requests"][0]["status"] == "answered" and lst["requests"][0]["proposals"] == [pid]
        assert c.post(f"/api/proposals/{pid}/reject", json={"comment": "too late"}).status_code == 409

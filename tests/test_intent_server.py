"""GUI iteration 2a over HTTP (docs/gui.md §7.2): GET/PATCH /api/intent, staleness and review,
diagnostics, file watching of the intent file and the review record."""
import asyncio
import json

import pytest
from starlette.testclient import TestClient

from dipm.connections import diagnostics, intent_tree
from dipm.fileio import file_sha256
from dipm.server.app import Session, create_app

from conftest import EXAMPLE, copy_bracket


@pytest.fixture()
def bracket_copy(tmp_path):
    return copy_bracket(tmp_path)


@pytest.fixture()
def client(bracket_copy):
    with TestClient(create_app(str(bracket_copy), watch_files=False)) as c:
        c.post("/api/build", json={})
        yield c


def patch(c, ops, base=None):
    h = base if base is not None else c.get("/api/intent").json()["hash"]
    return c.request("PATCH", "/api/intent", json={"base_hash": h, "ops": ops})


def test_tree_from_intent_file_matches_iteration_1(client):
    j = client.post("/api/build", json={}).json()
    assert j["tree"]["from_file"] and j["tree"]["order"] == ["R", "A", "A.P", "A.P.1", "A.P.2", "A.3", "B", "B.1", "C"]
    n = j["tree"]["nodes"]
    assert n["R"]["label"] == "Support a shelf on a wall" and n["A.3"]["statement"].startswith("Cable pass-through")
    assert [c["id"] for c in n["R"]["checks"]] == ["R.c1", "R.c2", "R.c3", "R.c4"]
    assert [a["id"] for a in n["R"]["assumptions"]] == ["R.a1", "R.a2", "R.a3"]
    assert all(x["status"] == "ok" and not x["stale"] for x in n.values())
    assert j["stale"] == {} and j["diagnostics"]["missing_in_file"] == []
    i = client.get("/api/intent").json()
    assert i["exists"] and i["doc"]["design"] == "shelf_bracket" and i["stale"] == {}
    assert i["review_exists"]          # the baseline is persisted the first time the intent is served


def test_edit_statement_marks_node_and_features_stale_then_review_clears(client, bracket_copy):
    r = patch(client, [{"op": "edit_statement", "id": "A.3", "statement": "Cable pass-through, offset 10 mm above the lower screw"}])
    assert r.status_code == 200, r.text
    b = r.json()["build"]
    assert b["tree"]["nodes"]["A.3"]["stale"] and not b["tree"]["nodes"]["A"]["stale"]
    f = {x["id"]: x for x in b["features"]}
    assert f["A.3.cable"]["stale"] == ["A.3"] and f["A.P.holes"]["stale"] == []
    st = b["stale"]["A.3"]
    assert st["changed"] == ["statement"] and st["reviewed"]["statement"] == "Cable pass-through, centered on the plate"
    review = bracket_copy.with_name("shelf_bracket.review.json")
    assert review.exists()                                # baseline persisted when first served
    r = patch(client, [{"op": "mark_reviewed", "ids": ["A.3"]}])
    b = r.json()["build"]
    assert not b["tree"]["nodes"]["A.3"]["stale"] and b["stale"] == {}
    rec = json.loads(review.read_text())
    assert rec["reviewed"]["A.3"]["content"]["statement"].endswith("lower screw")


def test_add_child_delete_move_and_checks_over_http(client):
    b = patch(client, [{"op": "add_child", "parent": "B", "statement": "Second shelf screw"}]).json()["build"]
    assert "B.2" in b["tree"]["nodes"] and b["tree"]["nodes"]["B.2"]["parent"] == "B"
    assert "B.2" in b["diagnostics"]["no_feature"]          # honest diagnostic: nothing realizes it yet
    b = patch(client, [{"op": "delete", "id": "C"}]).json()["build"]
    assert "C" not in b["tree"]["nodes"]
    assert b["diagnostics"]["no_intent"] == ["C.gusset"]     # criterion 4: its feature now has no intent
    assert b["diagnostics"]["missing_in_file"] == ["C"]      # and the DSL still says tags=intent("C", ...)
    assert b["tree"]["missing"] == {"C": ["C.gusset"]}
    b = patch(client, [{"op": "move", "id": "A.3", "parent": "B"}]).json()["build"]
    assert b["tree"]["nodes"]["A.3"]["parent"] == "B" and b["tree"]["order"].index("A.3") > b["tree"]["order"].index("B")
    f = {x["id"]: x for x in b["features"]}
    assert f["A.3.cable"]["serves"] == ["A.3", "A"]       # A is no longer an ancestor of A.3: both are served
    assert {"feature": "A.3.cable", "nodes": ["A.3", "A"]} in b["diagnostics"]["multi_intent"]
    b = patch(client, [{"op": "add_check", "id": "A.3", "check": {"kind": "rule", "statement": "Ø ≤ 10 mm"}},
                       {"op": "edit_check", "id": "A.3", "check_id": "A.3.c1", "fields": {"priority": "should"}},
                       {"op": "remove_check", "id": "A.3", "check_id": "A.3.c2"},
                       {"op": "edit_assumption", "id": "R", "assumption_id": "R.a3",
                        "fields": {"status": "accepted", "rationale": "drill bits ship with a long holder"}}]).json()["build"]
    cs = b["tree"]["nodes"]["A.3"]["checks"]
    assert [c["id"] for c in cs] == ["A.3.c1", "A.3.c3", "A.3.c4"] and cs[0]["priority"] == "should"
    a3 = b["tree"]["nodes"]["R"]["assumptions"][2]
    assert a3["status"] == "accepted" and a3["rationale"].startswith("drill")
    assert b["tree"]["nodes"]["R"]["stale"]                 # assumptions are part of the node's content


def test_bad_ops_and_schema_violations_are_400(client):
    assert patch(client, [{"op": "edit_statement", "id": "nope", "statement": "x"}]).status_code == 400
    r = patch(client, [{"op": "edit_check", "id": "R", "check_id": "R.c1", "fields": {"kind": "vibes"}}])
    assert r.status_code == 400 and "must be one of" in r.json()["error"]
    assert patch(client, [{"op": "frobnicate"}]).status_code == 400


def test_stale_base_hash_is_409_with_current_state(client, bracket_copy):
    intent = bracket_copy.with_name("shelf_bracket.intent.yaml")
    h0 = client.get("/api/intent").json()["hash"]
    intent.write_text(intent.read_text().replace("Shelf support", "Shelf support, edited in an editor"))
    r = patch(client, [{"op": "edit_statement", "id": "A.3", "statement": "GUI edit"}], base=h0)
    assert r.status_code == 409
    j = r.json()
    assert j["conflict"] and j["current"]["hash"] == file_sha256(str(intent)) != h0
    assert "edited in an editor" in intent.read_text() and "GUI edit" not in intent.read_text()
    assert patch(client, [{"op": "edit_statement", "id": "A.3", "statement": "GUI edit"}],
                 base=j["current"]["hash"]).status_code == 200          # re-apply on the current file


def test_design_without_intent_file_keeps_iteration_1_behaviour(tmp_path):
    import shutil
    src = EXAMPLE.parent
    for f in ("shelf_bracket.py", "shelf_bracket.interpretations.json"):
        shutil.copy(src / f, tmp_path / f)
    with TestClient(create_app(str(tmp_path / "shelf_bracket.py"), watch_files=False)) as c:
        j = c.post("/api/build", json={}).json()
        assert not j["tree"]["from_file"] and j["tree"]["order"] == ["R", "A", "A.P", "A.P.1", "A.P.2", "A.3", "B", "B.1", "C"]
        assert j["diagnostics"]["missing_in_file"] == [] and not j["intent"]["exists"]
        assert c.request("PATCH", "/api/intent", json={"base_hash": None, "ops": []}).status_code == 400


def test_diagnostics_missing_in_file(bracket, bracket_build):
    plain = {"design": "x", "intents": [{"id": "R", "statement": "root", "children": [
        {"id": "A", "statement": "a", "children": [{"id": "A.P", "statement": "p"}]}]}]}
    t = intent_tree(bracket, bracket_build, intent=plain)
    d = diagnostics(bracket, t, {})
    assert d["missing_in_file"] == ["C", "A.P.1", "A.P.2", "A.3", "B.1", "B"]   # first use in build order
    assert d["no_intent"] == ["C.gusset", "B.1.screw"]       # A.3.cable still serves A
    assert t["order"] == ["R", "A", "A.P"] and t["nodes"]["A"].label == "a"
    assert t["nodes"]["A"].realized_by == ["A.3.cable"] and t["nodes"]["A.P"].realized_by == ["A.P.holes"]


def test_watcher_reloads_intent_and_review(bracket_copy):
    s = Session(str(bracket_copy))
    s.load()
    s.build()
    events = []
    s.publish = events.append
    intent = bracket_copy.with_name("shelf_bracket.intent.yaml")
    assert s.intent_paths() <= s.watched()
    intent.write_text(intent.read_text().replace("Stiffening: gusset", "Stiffening: one gusset"))
    asyncio.run(s.on_files_changed({str(intent)}))
    kinds = [e["type"] for e in events]
    assert kinds == ["intent-changed", "rebuilt"]
    b = events[1]["build"]
    assert b["tree"]["nodes"]["C"]["label"] == "Stiffening: one gusset at the inner corner" and b["tree"]["nodes"]["C"]["stale"]
    # an invalid save keeps the last good document and reports the error
    events.clear()
    intent.write_text(intent.read_text().replace("statement: Wall mounting", "statment: Wall mounting"))
    asyncio.run(s.on_files_changed({str(intent)}))
    b = events[-1]["build"]
    assert b["intent"]["error"] and "unknown key 'statment'" in b["intent"]["error"][0]
    assert b["tree"]["nodes"]["C"]["label"] == "Stiffening: one gusset at the inner corner"
    # the review record is watched too
    events.clear()
    review = bracket_copy.with_name("shelf_bracket.review.json")
    review.write_text(json.dumps({"version": 1, "reviewed": {}}))
    asyncio.run(s.on_files_changed({str(review)}))
    assert events and events[-1]["type"] == "rebuilt"
    assert all(n["stale"] for n in events[-1]["build"]["tree"]["nodes"].values() if n["in_file"])

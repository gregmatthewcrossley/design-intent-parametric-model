"""The 'rename id' action (docs/gui.md §7.4): LibCST codemod over intent-id literals, plus the
intent file and the review record, through POST /api/intent/rename."""
from starlette.testclient import TestClient

from dipm.codemod import rename_intent_id
from dipm.server.app import create_app

from conftest import copy_bracket

SRC = '''from dipm import intent
d.hole("A.P.holes", on=f, at=p,   # A.P: the pattern
       tags=(intent("A.P", "pattern", "wall screw pattern"), intent('A', "wall_mount")),
       instance_tags=["A.P.1", "A.P.2"])
d.hole("A.3.cable", tags=intent(node="A.3", word="hole"))
note = "A.P is mentioned here but this is not an intent literal"
'''


def test_codemod_rewrites_only_intent_literals_and_keeps_formatting():
    out, n = rename_intent_id(SRC, "A.P", "A.W")
    assert n == 3
    assert 'intent("A.W", "pattern", "wall screw pattern")' in out and 'instance_tags=["A.W.1", "A.W.2"]' in out
    assert 'd.hole("A.P.holes"' in out and "# A.P: the pattern" in out and '"A.P is mentioned here' in out
    assert "intent('A', \"wall_mount\")" in out                  # unrelated ids and quote styles untouched
    out2, n2 = rename_intent_id(SRC, "A.3", "A.4")
    assert n2 == 1 and 'intent(node="A.4", word="hole")' in out2
    assert rename_intent_id(SRC, "A.3x", "Q") == (SRC, 0)


def test_rename_endpoint_updates_file_dsl_and_review(tmp_path):
    design = copy_bracket(tmp_path)
    with TestClient(create_app(str(design), watch_files=False)) as c:
        c.post("/api/build", json={})
        i = c.get("/api/intent").json()
        r = c.post("/api/intent/rename", json={"base_hash": i["hash"], "design_hash": i["design_hash"],
                                               "old": "A.3", "new": "A.C"})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["renamed_literals"] == 1
        b = j["build"]
        assert "A.C" in b["tree"]["nodes"] and "A.3" not in b["tree"]["nodes"]
        assert b["diagnostics"]["missing_in_file"] == [] and b["stale"] == {}   # review hashes moved with it
        assert 'intent("A.C", "hole"' in design.read_text()
        assert {"A.C.c1", "A.C.c2", "A.C.c3"} <= {c_["id"] for c_ in b["tree"]["nodes"]["A.C"]["checks"]}
        assert c.post("/api/intent/rename", json={"base_hash": i["hash"], "design_hash": i["design_hash"],
                                                  "old": "A.C", "new": "A.3"}).status_code == 409
        i = c.get("/api/intent").json()
        assert c.post("/api/intent/rename", json={"base_hash": i["hash"], "design_hash": i["design_hash"],
                                                  "old": "A.C", "new": "B"}).status_code == 400   # id taken

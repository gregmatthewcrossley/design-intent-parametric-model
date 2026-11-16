"""`dipm serve` (docs/gui.md §5, §6): every endpoint, mesh format and determinism, the answer
round trip, failure payloads and file-change events."""
import asyncio
import json
import pathlib
import shutil
import threading
import time

import numpy as np
import pytest
from starlette.testclient import TestClient

from dipm.server.app import Session, create_app
from dipm.server.mesh import decode, mesh_bytes

from conftest import EXAMPLE

FIX = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app(str(EXAMPLE), watch_files=False)) as c:
        yield c


@pytest.fixture(scope="module")
def bracket_payload(client):
    r = client.post("/api/build", json={"params": {}})
    assert r.status_code == 200
    return r.json()


def _copy_fixture(tmp_path, name):
    for suffix in (".py", ".interpretations.json"):
        src = FIX / (name + suffix)
        if src.exists():
            shutil.copy(src, tmp_path / (name + suffix))
    return tmp_path / (name + ".py")


# ---------------------------------------------------------------- /api/design, /api/build

def test_design_endpoint(client):
    d = client.get("/api/design").json()
    assert d["name"] == "shelf_bracket" and d["file"].endswith("shelf_bracket.py")
    by = {p["name"]: p for p in d["params"]}
    assert by["shelf_depth"]["range"] == [180.0, 300.0] and by["shelf_depth"]["kind"] == "range"
    assert by["screw"]["choices"] == ["#6", "#8", "#10"] and by["screw"]["kind"] == "choice"
    assert [f["id"] for f in d["features"]] == ["R.body", "C.gusset", "A.P.holes", "A.3.cable", "B.1.screw",
                                                "R.fillet"]


def test_build_bracket_tree_and_status(bracket_payload):
    """Criterion 1: the tree shows R, A, A.P, A.P.1, A.P.2, A.3, B, B.1, C, all green."""
    j = bracket_payload
    assert j["status"] == "PASS" and j["ok"] and j["mesh_id"]
    assert j["tree"]["order"] == ["R", "A", "A.P", "A.P.1", "A.P.2", "A.3", "B", "B.1", "C"]
    nodes = j["tree"]["nodes"]
    assert all(n["status"] == "ok" for n in nodes.values())
    assert nodes["R"]["label"] == "Support a shelf on a wall" and nodes["A.P"]["label"] == "wall screw pattern"
    assert nodes["A.P"]["realized_by"] == ["A.P.holes"] and nodes["A"]["realized_by"] == []
    assert nodes["A.P.2"]["instances"] == [["A.P.holes", "1"]]
    assert j["coverage"] == {"faces": 19, "with_genealogy": 19}


def test_build_features_uses_params(bracket_payload):
    """Criterion 9: six features linked to intents; uses A.P.holes/A.3.cable -> C.gusset; parameter links."""
    f = {x["id"]: x for x in bracket_payload["features"]}
    assert [x["id"] for x in bracket_payload["features"]] == list(f)
    assert all(x["serves"] for x in f.values())
    assert f["A.P.holes"]["serves"] == ["A.P"] and f["R.fillet"]["serves"] == ["R"]
    assert "C.gusset" in f["A.P.holes"]["uses"] and "C.gusset" in f["A.3.cable"]["uses"]
    assert "screw" in f["A.P.holes"]["params"] and "screw" in f["B.1.screw"]["params"]
    driven = [k for k, x in f.items() if "shelf_depth" in x["params_all"]]
    assert driven == list(f)            # shelf_depth drives everything (directly or through uses)
    assert [k for k, x in f.items() if "shelf_depth" in x["params"]] == ["R.body", "C.gusset"]
    names = {c["name"] for c in f["R.body"]["checks"]}
    assert {"validity", "euler", "delta_H", "delta_S", "volume_sign"} <= names
    assert f["A.P.holes"]["refs"] and f["A.P.holes"]["refs_ok"]


def test_build_interpretations_four_slots_no_questions_no_notices(bracket_payload):
    """Criterion 5 (as amended by DECISIONS #32): four slots, zero questions, zero notices."""
    it = bracket_payload["interpretations"]
    assert [s["id"] for s in it["slots"]] == ["A.P.holes/hole.extent", "A.3.cable/centered_on.point",
                                              "A.3.cable/hole.extent", "B.1.screw/hole.extent"]
    assert it["questions"] == [] and it["notices"] == [] and it["source"].startswith("lock")
    c = it["slots"][1]
    assert c["chosen"] == "exposed_region_midpoint" and c["eliminated"][0]["reading"] == "face_centroid"


def test_countersink_face_genealogy(bracket_payload):
    """Criterion 3: a countersink face explains itself as A.P.holes.countersink(1) · hole@A.P.2 · pattern@A.P."""
    (face,) = [f for f in bracket_payload["faces"] if f["entries"] and f["entries"][0]["tag"] ==
               "A.P.holes.countersink(1)"]
    e = face["entries"][0]
    assert [t["text"] for t in e["instance_intent"]] == ["hole@A.P.2"]
    assert "pattern@A.P (wall screw pattern)" in [t["text"] for t in e["intent"]]
    assert face["nodes"][0] == "A.P.2" and face["surface"] == "Cone"


def _faces_of_node(payload, node):
    def under(n):
        return n == node or n.startswith(node + ".")
    return [f for f in payload["faces"] if any(under(n) for n in f["nodes"])]


def test_tree_node_selects_its_faces(bracket_payload):
    """Criterion 4: A.P selects both screw holes' faces and nothing else."""
    sel = _faces_of_node(bracket_payload, "A.P")
    assert {f["entries"][0]["tag"] for f in sel} == {"A.P.holes.wall(0)", "A.P.holes.wall(1)",
                                                     "A.P.holes.countersink(0)", "A.P.holes.countersink(1)"}
    assert {f["entries"][0]["tag"] for f in _faces_of_node(bracket_payload, "A.P.2")} == {
        "A.P.holes.wall(1)", "A.P.holes.countersink(1)"}


def test_edges_explained(bracket_payload):
    edges = bracket_payload["edges"]
    assert edges and all(e["entries"] or e["derived_from"] or e["degenerated"] for e in edges)


def test_bad_parameters_are_400(client):
    r = client.post("/api/build", json={"params": {"shelf_depth": 1000}})
    assert r.status_code == 400 and "outside declared range" in r.json()["error"]
    assert client.post("/api/build", json={"params": {"nope": 1}}).status_code == 400
    assert client.post("/api/build", content=b"{not json", headers={"content-type": "application/json"}
                       ).status_code == 400


def test_parameter_edit_rebuilds(client):
    """Criterion 2 (engine side): shelf_depth 300 rebuilds; holes re-spread; the cable stays mid-plate."""
    a = client.post("/api/build", json={"params": {"shelf_depth": 200}}).json()
    b = client.post("/api/build", json={"params": {"shelf_depth": 300}}).json()
    assert b["status"] == "PASS" and a["mesh_id"] != b["mesh_id"]
    ca = {f["id"]: f["detail"] for f in a["features"]}
    cb = {f["id"]: f["detail"] for f in b["features"]}
    assert ca["A.P.holes"]["centres"] != cb["A.P.holes"]["centres"]
    z = cb["A.3.cable"]["centres"][0][2]
    assert z == pytest.approx((0.75 * 300 - 5 - 0.4 * 300) / 2)
    client.post("/api/build", json={"params": {"shelf_depth": 200}})


# ---------------------------------------------------------------- /api/mesh

def test_mesh_format_matches_genealogy(client, bracket_payload):
    r = client.get(f"/api/mesh/{bracket_payload['mesh_id']}")
    assert r.status_code == 200 and r.headers["content-type"] == "application/octet-stream"
    m = decode(r.content)
    nf, ne = len(bracket_payload["faces"]), len(bracket_payload["edges"])
    assert m["face_ranges"].shape == (nf, 2) and m["edge_ranges"].shape == (ne, 2)
    # face ranges tile the triangle list in face-id order
    starts, counts = m["face_ranges"][:, 0], m["face_ranges"][:, 1]
    assert starts[0] == 0 and np.all(starts[1:] == starts[:-1] + counts[:-1])
    assert counts.sum() == len(m["indices"]) and np.all(counts > 0)
    assert m["indices"].max() < len(m["positions"])
    assert np.allclose(np.linalg.norm(m["normals"], axis=1), 1.0, atol=1e-4)
    e_starts, e_counts = m["edge_ranges"][:, 0], m["edge_ranges"][:, 1]
    assert e_counts.sum() == len(m["edge_points"])
    assert all((e_counts[e["id"]] == 0) == e["degenerated"] for e in bracket_payload["edges"])


def test_mesh_is_deterministic(bracket, bracket_build):
    a = mesh_bytes(bracket_build.shape)
    b = mesh_bytes(bracket.build().shape)
    assert a == b
    # meshing a copy leaves the solid's canonical BRep bytes untouched
    assert bracket_build.canonical() == bracket.build().canonical()


def test_mesh_is_deterministic_across_processes(bracket_payload):
    import subprocess
    import sys
    code = ("import warnings; warnings.simplefilter('ignore');"
            "from dipm.cli import load_design; from dipm.server.mesh import mesh_bytes;"
            f"d = load_design({str(EXAMPLE)!r}); d.use_lock({str(EXAMPLE)!r});"
            "print(mesh_bytes(d.build().shape)[0])")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == bracket_payload["mesh_id"]


def test_unknown_mesh_is_404(client):
    assert client.get("/api/mesh/deadbeef").status_code == 404


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "<" in r.text


# ---------------------------------------------------------------- /api/answer (criterion 6)

def test_answer_round_trip(tmp_path):
    f = _copy_fixture(tmp_path, "question_channel")
    with TestClient(create_app(str(f), watch_files=False)) as c:
        j = c.post("/api/build", json={}).json()
        (q,) = j["interpretations"]["questions"]
        assert q["id"] == "D.drain/hole.extent" and [o["reading"] for o in q["options"]] == [
            "through_plate", "through_all", "up_to_next"]
        assert j["tree"]["nodes"]["D"]["status"] == "warn"
        assert j["signature"]["VEFRSH"][5] == 1
        r = c.post("/api/answer", json={"assumption_id": q["id"], "reading": "through_all"})
        assert r.status_code == 200
        k = r.json()
        assert k["interpretations"]["questions"] == [] and k["answer"]["key"] == "hole.extent@channel_question:D"
        slot = k["interpretations"]["slots"][0]
        assert slot["chosen"] == "through_all" and slot["made_by"] == "user preference"
        assert k["signature"]["VEFRSH"][5] == 2 and k["mesh_id"] != j["mesh_id"]       # rebuilt
        prefs = json.loads((tmp_path / "question_channel.prefs.json").read_text())
        assert prefs["answers"] == {"hole.extent@channel_question:D": {"reading": "through_all"}}
        lock = json.loads((tmp_path / "question_channel.interpretations.json").read_text())
        assert lock["choices"] == {"D.drain/hole.extent": "through_all"} and lock["prefs"] == \
            "question_channel.prefs.json"
        # same semantics as `dipm answer`: bad ids and readings are rejected
        assert c.post("/api/answer", json={"assumption_id": "nope", "reading": "x"}).status_code == 400
        assert c.post("/api/answer", json={"assumption_id": q["id"], "reading": "sideways"}).status_code == 400
        assert c.post("/api/answer", json={}).status_code == 400
    # a fresh server reads the answered lock and its preferences: no question
    with TestClient(create_app(str(f), watch_files=False)) as c:
        j = c.post("/api/build", json={}).json()
        assert j["interpretations"]["questions"] == [] and j["interpretations"]["source"].startswith("lock")


# ---------------------------------------------------------------- failure (criterion 7)

def test_failed_build_payload_keeps_last_good_model():
    with TestClient(create_app(str(FIX / "invariant_fail.py"), watch_files=False)) as c:
        good = c.post("/api/build", json={"params": {"hole_u": 0.3}}).json()
        assert good["status"] == "PASS"
        bad = c.post("/api/build", json={"params": {"hole_u": 0.75}}).json()
        assert bad["status"] == "FAIL" and bad["failing"] == ["H.hole"] and bad["error_count"] == 1
        f = {x["id"]: x for x in bad["features"]}
        assert f["H.hole"]["status"] == "fail" and f["H.hole"]["error"]["invariant"] == "delta_H"
        assert [c_["ok"] for c_ in f["H.hole"]["checks"] if c_["name"] == "delta_H"] == [False]
        assert bad["tree"]["nodes"]["H"]["status"] == "fail" and bad["tree"]["nodes"]["R"]["status"] == "fail"
        assert bad["tree"]["nodes"]["S"]["status"] == "ok"
        assert any(x["failing"] for x in bad["faces"]) and not all(x["failing"] for x in bad["faces"])
        assert bad["last_good_mesh_id"] == good["mesh_id"] and bad["mesh_id"] != good["mesh_id"]
        assert c.get(f"/api/mesh/{good['mesh_id']}").status_code == 200


# ---------------------------------------------------------------- diagnostics fixture

def test_diagnostics_fixture():
    with TestClient(create_app(str(FIX / "diagnostics.py"), watch_files=False)) as c:
        j = c.post("/api/build", json={}).json()
    d = j["diagnostics"]
    assert d["no_intent"] == ["X.untagged"] and d["no_feature"] == ["B"]
    assert d["multi_intent"] == [{"feature": "A.1.shared", "nodes": ["A.1", "C.1"]}]
    assert d["cross_intent"] == [{"from": "D.1.drain", "to": "A.1.shared", "from_nodes": ["D.1"],
                                  "to_nodes": ["A.1", "C.1"]}]
    f = {x["id"]: x for x in j["features"]}
    assert f["X.untagged"]["serves"] == [] and f["D.1.drain"]["uses"] == ["R.plate", "A.1.shared"]


def test_bracket_cross_intent_dependencies(bracket_payload):
    d = bracket_payload["diagnostics"]
    assert d["no_intent"] == [] and d["no_feature"] == [] and d["multi_intent"] == []
    assert [(x["from"], x["to"]) for x in d["cross_intent"]] == [("A.P.holes", "C.gusset"),
                                                                 ("A.3.cable", "C.gusset")]


# ---------------------------------------------------------------- live reload (criterion 8)

def test_session_reload_keeps_params_and_resolves_stale_lock(tmp_path):
    f = _copy_fixture(tmp_path, "question_channel")
    s = Session(str(f))
    s.load()
    s.build({"g": 8.0})
    assert not s.needs_resolve
    f.write_text(f.read_text() + "\n# edited\n")
    t0 = time.perf_counter()
    s.load()
    p = s.build()
    assert time.perf_counter() - t0 < 1.0                       # no blocking re-resolution
    assert s.needs_resolve and p["resolving"] and p["params"]["g"] == 8.0
    assert p["interpretations"]["source"] == "stale lock (re-resolving)"
    s.resolve_now()
    p = s.build()
    assert not p["resolving"] and p["interpretations"]["source"].startswith("resolved in memory")


def test_session_events_on_file_change(tmp_path):
    """on_files_changed publishes design-changed then rebuilt; own writes and unrelated files are ignored."""
    f = _copy_fixture(tmp_path, "invariant_fail")
    s = Session(str(f))
    s.load()
    s.build({"hole_u": 0.2})

    async def run():
        s.loop = asyncio.get_running_loop()
        q = asyncio.Queue()
        s.listeners.add(q)
        await s.on_files_changed({str(tmp_path / "unrelated.txt")})
        assert q.empty()
        f.write_text(f.read_text().replace('"plate with a hole"', '"plate with a hole!"'))
        await s.on_files_changed({str(f)})
        a, b = await asyncio.wait_for(q.get(), 5), await asyncio.wait_for(q.get(), 5)
        return a, b

    a, b = asyncio.run(run())
    assert a["type"] == "design-changed" and a["design"]["name"] == "invariant_fail"
    assert b["type"] == "rebuilt" and b["build"]["params"]["hole_u"] == 0.2 and b["build"]["status"] == "PASS"


def test_websocket_pushes_rebuild_on_save(tmp_path):
    """End to end through watchfiles and the WebSocket: save the file, get `rebuilt` within ~1 s."""
    f = _copy_fixture(tmp_path, "invariant_fail")
    app = create_app(str(f), watch_files=True)
    got, err = [], []
    with TestClient(app) as c:
        c.post("/api/build", json={"params": {"hole_u": 0.2}})
        with c.websocket_connect("/api/events") as ws:
            assert ws.receive_json()["type"] == "hello"

            def reader():
                try:
                    while True:
                        m = ws.receive_json()
                        got.append((time.perf_counter(), m))
                        if m["type"] == "rebuilt":
                            return
                except Exception as e:   # noqa: BLE001
                    err.append(e)

            th = threading.Thread(target=reader, daemon=True)
            th.start()
            time.sleep(0.5)                      # let the watcher settle
            t0 = time.perf_counter()
            f.write_text(f.read_text() + "\n# saved\n")
            th.join(10)
            assert not th.is_alive(), "no rebuilt event within 10 s"
    types = [m["type"] for _, m in got]
    assert types[:2] == ["design-changed", "rebuilt"], (types, err)
    assert got[1][1]["build"]["params"]["hole_u"] == 0.2
    assert got[1][0] - t0 < 1.5


def test_answer_writes_are_not_reloaded_as_external_changes(tmp_path):
    """The prefs/lock writes of /api/answer must not come back through the watcher as a reload
    with a stale lock (that briefly resurrected the answered question)."""
    f = _copy_fixture(tmp_path, "question_channel")
    s = Session(str(f))
    s.load()
    s.build()
    seen = []
    orig = s._answer_locked

    def spy(*a, **k):
        seen.append(set(s.writing))
        return orig(*a, **k)

    s._answer_locked = spy
    s.answer("D.drain/hole.extent", "through_all")
    prefs, lock = (str((tmp_path / n).resolve()) for n in ("question_channel.prefs.json",
                                                          "question_channel.interpretations.json"))
    assert seen == [{prefs, lock}] and s.writing == set()
    assert s.is_own_write(prefs) and s.is_own_write(lock)
    gen = s.generation

    async def run():
        s.loop = asyncio.get_running_loop()
        await s.on_files_changed({prefs, lock})

    asyncio.run(run())
    assert s.generation == gen          # ignored: no reload

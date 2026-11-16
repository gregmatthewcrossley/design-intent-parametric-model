"""`dipm mcp` (docs/gui.md §7.3) through the official SDK's in-memory client: every tool, the
proposal path, and that MCP tools never write design files."""
import asyncio
import json

import pytest
from mcp import Client

from dipm.fileio import file_sha256
from dipm.mcp_server import build_server
from dipm.proposals import ProposalStore

from conftest import a3_offset_patch, copy_bracket

TOOLS = {"get_design", "get_intent", "build", "why", "get_stale_nodes", "get_requests", "get_source",
         "propose_patch", "list_proposals", "get_proposal_feedback"}


def run(design, script):
    async def main():
        async with Client(build_server(str(design))) as c:
            async def call(name, args=None):
                r = await c.call_tool(name, args or {})
                text = r.content[0].text if r.content else ""
                return (json.loads(text) if not r.is_error else None), r.is_error, text
            return await script(c, call)
    return asyncio.run(main())


def snapshot(design):
    return {p.name: file_sha256(str(p)) for p in design.parent.iterdir() if p.is_file()}


def test_read_tools(tmp_path):
    design = copy_bracket(tmp_path)

    async def script(c, call):
        names = {t.name for t in (await c.list_tools()).tools}
        assert names == TOOLS
        d, err, _ = await call("get_design")
        assert not err and d["name"] == "shelf_bracket" and d["patchable_files"] == ["shelf_bracket.intent.yaml",
                                                                                     "shelf_bracket.py"]
        assert [f["id"] for f in d["features"]] == ["R.body", "C.gusset", "A.P.holes", "A.3.cable", "B.1.screw", "R.fillet"]
        i, _, _ = await call("get_intent")
        assert i["doc"]["intents"][0]["id"] == "R" and i["stale_nodes"] == [] and i["sha256"]
        b, _, _ = await call("build", {"params": {"shelf_depth": 300}})
        assert b["status"] == "PASS" and b["params"]["shelf_depth"] == 300
        bad, err, text = await call("build", {"params": {"shelf_depth": 1000}})
        assert err and "shelf_depth" in text
        w, _, _ = await call("why", {"face_id": 0})
        assert w["entries"][0]["feature"] == "R.body"
        _, err, text = await call("why", {"face_id": 999})
        assert err and "face_id must be in" in text
        s, _, _ = await call("get_source")
        assert s["base_hashes"]["shelf_bracket.py"] == file_sha256(str(design))
        assert "make_design" in s["files"]["shelf_bracket.py"]["text"]
        st, _, _ = await call("get_stale_nodes")
        assert st == {"stale": [], "requests": []}
        lp, _, _ = await call("list_proposals")
        assert lp == {"proposals": []}

    run(design, script)


def test_stale_nodes_requests_propose_feedback(tmp_path):
    design = copy_bracket(tmp_path)
    intent = design.with_name("shelf_bracket.intent.yaml")
    intent.write_text(intent.read_text().replace("Cable pass-through, centered on the plate",
                                                 "Cable pass-through, offset 10 mm above the lower screw"))
    ProposalStore(str(design)).create_request("A.3", "keep 1 mm clear of the countersink", None)
    before = snapshot(design)

    async def script(c, call):
        st, _, _ = await call("get_stale_nodes")
        (a3,) = st["stale"]
        assert a3["id"] == "A.3" and a3["changed"] == ["statement"]
        assert a3["reviewed"]["statement"] == "Cable pass-through, centered on the plate"
        assert a3["statement"].endswith("lower screw") and a3["features"] == ["A.3.cable"]
        assert a3["requests"][0]["note"] == "keep 1 mm clear of the countersink"
        rq, _, _ = await call("get_requests")
        assert [r["node"] for r in rq["requests"]] == ["A.3"]
        src, _, _ = await call("get_source")
        _, err, text = await call("propose_patch", {"summary": "x", "rationale": "r",
                                                    "files": {"../../etc/passwd": "x"}, "base_hashes": {}})
        assert err and "not in the design's file set" in text
        new = a3_offset_patch(src["files"]["shelf_bracket.py"]["text"])
        p, err, text = await call("propose_patch", {
            "summary": "A.3: offset 10 mm above the lower screw", "rationale": "the intent changed",
            "files": {"shelf_bracket.py": new}, "base_hashes": src["base_hashes"], "addresses_nodes": ["A.3"]})
        assert not err, text
        assert p["status"] == "ready" and p["checks_pass"] and p["evaluation"]["after"]["status"] == "PASS"
        assert p["evaluation"]["after"]["stale_nodes"] == []
        assert "offset(wall_pts[0], Z, 10.0)" in p["evaluation"]["text_diff"]["shelf_bracket.py"]
        # stale base: refused for application, marked stale
        old = dict(src["base_hashes"], **{"shelf_bracket.py": "0" * 64})
        q, _, _ = await call("propose_patch", {"summary": "late", "rationale": "", "files": {"shelf_bracket.py": new},
                                               "base_hashes": old})
        assert q["status"] == "stale"
        lp, _, _ = await call("list_proposals")
        assert [(x["id"], x["status"]) for x in lp["proposals"]] == [("p1", "ready"), ("p2", "stale")]
        return p["id"]

    pid = run(design, script)
    after = snapshot(design)
    assert {k: v for k, v in after.items()} == before          # MCP tools never write design files
    ProposalStore(str(design)).reject(pid, "Use 10 mm from the hole centre, not the edge.")

    async def script2(c, call):
        fb, _, _ = await call("get_proposal_feedback", {"proposal_id": pid})
        assert fb["feedback"][0]["status"] == "rejected"
        assert fb["feedback"][0]["feedback"][-1]["comment"] == "Use 10 mm from the hole centre, not the edge."
        allfb, _, _ = await call("get_proposal_feedback")
        assert len(allfb["feedback"]) == 2
        _, err, _ = await call("get_proposal_feedback", {"proposal_id": "p99"})
        assert err

    run(design, script2)


def test_stdio_server_via_the_claude_simulator(tmp_path):
    """`python -m dipm mcp <design>` over stdio (what Claude Code launches), driven by the e2e
    tests' scripted stand-in for Claude."""
    import subprocess
    import sys
    from conftest import ROOT
    design = copy_bracket(tmp_path)
    sim = ROOT / "gui" / "e2e" / "simulate_claude.py"
    out = subprocess.run([sys.executable, str(sim), str(design), "propose", "10"], capture_output=True, text=True,
                         timeout=120, check=True).stdout
    p = json.loads(out)
    assert p["id"] == "p1" and p["status"] == "ready" and p["checks_pass"]
    fb = json.loads(subprocess.run([sys.executable, str(sim), str(design), "feedback", "p1"], capture_output=True,
                                   text=True, timeout=120, check=True).stdout)
    assert fb["feedback"][0]["id"] == "p1"

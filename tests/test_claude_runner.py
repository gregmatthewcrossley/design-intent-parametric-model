"""Iteration 4b (docs/purpose-loop.md §7): dipm starts headless Claude Code for queued requests.

Never the real `claude`: every run here uses the stub tests/fixtures/fake_claude (a shell wrapper
around fake_claude.py) through DIPM_CLAUDE_BIN.  The stub checks the flags, starts the MCP server
from the generated config and calls dipm's tools over stdio, printing stream-json."""
import asyncio
import json
import os
import sys
import time

import pytest
from mcp import Client

from dipm import claude_runner as cr
from dipm.claude_runner import RunError, Runner, StreamParser
from dipm.mcp_server import TOOL_NAMES, build_server
from dipm.proposals import ProposalStore

from conftest import ROOT, a3_offset_patch, copy_bracket

STUB = str(ROOT / "tests" / "fixtures" / "fake_claude")


@pytest.fixture
def stub(monkeypatch, tmp_path):
    """Use the stub binary; returns a setter for its mode (and where it records its argv)."""
    rec = tmp_path / "stub-argv.json"
    monkeypatch.setenv("DIPM_CLAUDE_BIN", STUB)
    monkeypatch.setenv("DIPM_STUB_RECORD", str(rec))
    monkeypatch.setenv("DIPM_STUB_MODE", "patch")
    monkeypatch.delenv("DIPM_STUB_DELAY", raising=False)
    monkeypatch.delenv("DIPM_CLAUDE_TIMEOUT", raising=False)

    def mode(m, **env):
        monkeypatch.setenv("DIPM_STUB_MODE", m)
        for k, v in env.items():
            monkeypatch.setenv(k, str(v))
        return rec
    return mode


@pytest.fixture
def bracket(tmp_path):
    d = tmp_path / "design"
    d.mkdir()
    design = copy_bracket(d)
    intent = design.with_name("shelf_bracket.intent.yaml")
    intent.write_text(intent.read_text().replace("Cable pass-through, centered on the plate",
                                                 "Cable pass-through, offset 10 mm above the lower screw"))
    return design


def wait(cond, timeout=60.0, every=0.1):
    t0 = time.time()
    while time.time() - t0 < timeout:
        v = cond()
        if v:
            return v
        time.sleep(every)
    raise AssertionError("timed out waiting")


def finished(runner: Runner, rid: str, timeout=90.0) -> dict:
    wait(lambda: runner.current is None or runner.current["id"] != rid, timeout)
    return runner.get(rid)


# ---------------------------------------------------------------- the command line (restricted tools)

def test_command_line_is_headless_and_restricted(tmp_path):
    cmd = cr.command("/bin/claude", "do the thing", "/x/run1.mcp.json")
    assert cmd[:3] == ["/bin/claude", "-p", "do the thing"]
    opt = lambda n: cmd[cmd.index(n) + 1]  # noqa: E731
    assert opt("--output-format") == "stream-json" and "--verbose" in cmd
    assert opt("--mcp-config") == "/x/run1.mcp.json" and "--strict-mcp-config" in cmd
    assert opt("--tools") == ""                         # no built-in tools at all
    allowed = opt("--allowedTools").split(",")
    assert allowed == [f"mcp__dipm__{n}" for n in TOOL_NAMES] and all(a.startswith("mcp__dipm__") for a in allowed)
    denied = set(opt("--disallowedTools").split(","))
    assert {"Bash", "Edit", "Write", "Read", "WebFetch", "WebSearch", "NotebookEdit"} <= denied
    assert opt("--permission-mode") == "dontAsk"         # anything else is denied, never prompted
    assert "--model" not in cmd and "--dangerously-skip-permissions" not in cmd
    assert cr.command("c", "p", "f", model="sonnet")[-2:] == ["--model", "sonnet"]
    # no variadic option is last or directly before the prompt
    for v in ("--mcp-config", "--tools", "--allowedTools", "--disallowedTools"):
        assert cmd[cmd.index(v) + 2].startswith("--")


def test_mcp_config_runs_this_python_and_tool_names_match_the_server(bracket):
    cfg = cr.mcp_config(str(bracket), "run7", ["r1", "r2"])["mcpServers"]["dipm"]
    assert cfg["command"] == sys.executable and cfg["args"] == ["-m", "dipm", "mcp", str(bracket)]
    assert cfg["env"]["DIPM_RUN"] == "run7" and cfg["env"]["DIPM_REQUESTS"] == "r1,r2"

    async def names():
        async with Client(build_server(str(bracket))) as c:
            return {t.name for t in (await c.list_tools()).tools}
    assert asyncio.run(names()) == set(TOOL_NAMES)


def test_find_claude(monkeypatch, tmp_path):
    monkeypatch.setenv("DIPM_CLAUDE_BIN", str(tmp_path / "nope"))
    a = cr.find_claude()
    assert not a["ok"] and "DIPM_CLAUDE_BIN" in a["reason"]
    monkeypatch.setenv("DIPM_CLAUDE_BIN", STUB)
    assert cr.find_claude() == {"ok": True, "bin": STUB, "source": "DIPM_CLAUDE_BIN", "reason": ""}
    monkeypatch.delenv("DIPM_CLAUDE_BIN")
    monkeypatch.setenv("PATH", str(tmp_path))            # no claude on PATH
    a = cr.find_claude()
    assert not a["ok"] and "not on PATH" in a["reason"]


def test_repo_root(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    (tmp_path / "repo" / "examples").mkdir()
    assert cr.repo_root(str(tmp_path / "repo" / "examples" / "x.py")) == str(tmp_path / "repo")
    (tmp_path / "loose").mkdir()
    assert cr.repo_root(str(tmp_path / "loose" / "x.py")) == str(tmp_path / "loose")
    assert cr.repo_root(str(ROOT / "examples" / "rod_holder.py")) == str(ROOT)


# ---------------------------------------------------------------- a stub run, end to end (criterion 1)

def test_stub_run_proposes_and_links_the_request(bracket, stub, monkeypatch):
    rec = stub("patch")
    monkeypatch.setenv("CLAUDECODE", "1")                # an enclosing Claude Code session
    st = ProposalStore(str(bracket))
    r = st.create_request("A.3", "keep it clear of the countersink", None)
    events = []
    runner = Runner(st, events.append)
    run = runner.start(trigger="queue")
    assert st.request(r["id"])["status"] == "running" and run["requests"] == [r["id"]]
    with pytest.raises(RunError) as e:                   # one run at a time per design
        runner.start(trigger="button")
    assert e.value.code == "busy"
    fin = finished(runner, run["id"])
    assert fin["status"] == "done", fin["reason"]
    (pid,) = fin["proposals"]
    req = st.request(r["id"])
    assert req["status"] == "proposed" and req["proposals"] == [pid] and req["runs"] == [run["id"]]
    p = st.get(pid)
    assert p["requests"] == [r["id"]] and p["run"] == run["id"] and p["status"] == "ready"
    texts = [s["text"] for s in fin["steps"]]
    assert texts[0].startswith("Claude started") and "reading the requests" in texts
    assert f"submitted patch {pid}" in texts and texts[-1].startswith("finished")
    assert fin["usage_line"].startswith("$0.04 · 36,810 in / 1,830 out tokens")
    # the transcript is the stream, verbatim
    lines = open(runner.transcript_path(run["id"]), encoding="utf-8").read().splitlines()
    assert json.loads(lines[0])["subtype"] == "init" and json.loads(lines[-1])["type"] == "result"
    # what the stub saw: the flags, the config, the repo root as cwd, no nested-session env
    seen = json.loads(rec.read_text())
    assert seen["argv"][seen["argv"].index("--tools") + 1] == ""
    assert seen["config"]["mcpServers"]["dipm"]["env"]["DIPM_REQUESTS"] == r["id"]
    assert os.path.realpath(seen["cwd"]) == os.path.realpath(str(bracket.parent))
    assert seen["env"]["CLAUDECODE"] is None
    assert any(ev["type"] == "claude-run" and ev["status"]["running"] for ev in events)
    assert events[-1]["type"] == "proposals-changed"
    # the design files were not touched
    assert "fake claude" not in bracket.read_text()


def test_rogue_tool_call_is_denied_and_reported(bracket, stub):
    stub("rogue")
    st = ProposalStore(str(bracket))
    st.create_request("A.3", "", None)
    runner = Runner(st)
    fin = finished(runner, runner.start()["id"])
    assert fin["status"] == "done" and fin["denied_tools"] == ["Bash"]
    assert any(s["kind"] == "warn" and "Bash" in s["text"] for s in fin["steps"])
    assert any(s["kind"] == "error" and "denied" in s["text"] for s in fin["steps"])


# ---------------------------------------------------------------- cancel and timeout (criterion 2)

def test_cancel_kills_the_run_and_fails_its_requests(bracket, stub):
    stub("hang")
    st = ProposalStore(str(bracket))
    r = st.create_request("A.3", "", None)
    runner = Runner(st)
    run = runner.start()
    wait(lambda: any(s["text"] == "reading the requests" for s in runner.current["steps"]), 60)
    pid = run["pid"]
    runner.cancel(run["id"])
    fin = finished(runner, run["id"], 15)
    assert fin["status"] == "cancelled" and fin["reason"] == "cancelled by the designer"
    req = st.request(r["id"])
    assert req["status"] == "failed" and "cancelled" in req["status_detail"]
    assert not cr._pid_alive(pid)
    with pytest.raises(RunError):
        runner.cancel(run["id"])
    # a failed request is not auto-run again, but "Run Claude now" may retry it
    assert runner.runnable() == [] and [x["id"] for x in runner.runnable(include_failed=True)] == [r["id"]]


def test_timeout_stops_the_run(bracket, stub):
    stub("hang", DIPM_CLAUDE_TIMEOUT=3)
    st = ProposalStore(str(bracket))
    r = st.create_request("A.3", "", None)
    runner = Runner(st)
    assert runner.settings()["timeout_s"] == 3
    fin = finished(runner, runner.start()["id"], 30)
    assert fin["status"] == "timeout" and "timeout" in fin["reason"]
    assert st.request(r["id"])["status"] == "failed"


# ---------------------------------------------------------------- missing binary, not logged in (criterion 3)

def test_missing_binary_falls_back_to_the_prompt(bracket, monkeypatch, tmp_path):
    monkeypatch.setenv("DIPM_CLAUDE_BIN", str(tmp_path / "no-claude"))
    st = ProposalStore(str(bracket))
    r = st.create_request("A.3", "", None)
    runner = Runner(st)
    with pytest.raises(RunError) as e:
        runner.start()
    assert e.value.code == "unavailable"
    monkeypatch.setenv("DIPM_CLAUDE_AUTORUN", "1")
    assert runner.auto() == (None, f"DIPM_CLAUDE_BIN={tmp_path / 'no-claude'} is not an executable file")
    s = runner.status()
    assert not s["available"]["ok"] and s["waiting"] == 1 and "get_requests" in s["prompt"]
    assert st.request(r["id"])["status"] == "open" and runner.runs() == []


def test_not_logged_in_reverts_requests_and_pauses_auto_run(bracket, stub, monkeypatch):
    stub("notloggedin")
    monkeypatch.setenv("DIPM_CLAUDE_AUTORUN", "1")
    st = ProposalStore(str(bracket))
    r = st.create_request("A.3", "", None)
    runner = Runner(st)
    run, why = runner.auto()
    fin = finished(runner, run["id"], 30)
    assert fin["status"] == "failed" and fin["auth_error"] and "not logged in" in fin["reason"]
    assert st.request(r["id"])["status"] == "open"        # Claude never saw it: the prompt fallback applies
    s = runner.status()
    assert s["available"]["login"] == "failed" and "log in" in s["available"]["reason"]
    st.create_request("A.3", "again", None)
    assert runner.auto() == (None, "Claude Code is not logged in")
    stub("noop")
    fin = finished(runner, runner.start(trigger="button")["id"])   # the button tries again
    assert fin["status"] == "done" and not runner.auth_failed


def test_crash_fails_with_the_reason(bracket, stub):
    stub("crash")
    st = ProposalStore(str(bracket))
    r = st.create_request("A.3", "", None)
    runner = Runner(st)
    fin = finished(runner, runner.start()["id"], 30)
    assert fin["status"] == "failed" and "exited with 2" in fin["reason"] and "crashed on purpose" in fin["reason"]
    assert st.request(r["id"])["status"] == "failed"


# ---------------------------------------------------------------- no re-run of answered requests (criterion 4)

def test_request_answered_by_a_pending_proposal_is_not_rerun(bracket, stub):
    st = ProposalStore(str(bracket))
    r = st.create_request("A.3", "", None)
    py = bracket.name
    p = st.create("A.3 offset", "r", {py: a3_offset_patch(bracket.read_text())},
                  {py: st.files.current_hashes()[py]}, ["A.3"], source="mcp")
    assert p["requests"] == [r["id"]]                     # linked at submission, not at acceptance
    assert st.request(r["id"])["status"] == "proposed"
    runner = Runner(st)
    assert runner.runnable(include_failed=True) == []
    with pytest.raises(RunError) as e:
        runner.start(trigger="button")
    assert e.value.code == "nothing" and runner.runs() == []
    # rejected: the request is open again, and runnable
    st.reject(p["id"], "not like that")
    req = st.request(r["id"])
    assert req["status"] == "open" and p["id"] in req["status_detail"]
    assert [x["id"] for x in runner.runnable()] == [r["id"]]


def test_request_lifecycle_through_purposes_and_acceptance(tmp_path):
    from conftest import copy_rod_holder
    sys.path.insert(0, str(ROOT / "tests" / "fixtures"))
    import rod_loop
    from dipm.fileio import file_sha256
    rod = copy_rod_holder(tmp_path)
    st = ProposalStore(str(rod))
    r = st.create_request("R", "", None)
    p = st.create_purpose("rod", "r", rod_loop.PURPOSE_TEXT, file_sha256(str(rod.with_name("rod_holder.intent.yaml"))),
                          ["R", "B"])
    assert st.request(r["id"])["status"] == "proposed"
    st.evaluate(p["id"])
    st.try_purpose(p["id"])                               # accepted to try: the geometry is still to do
    req = st.request(r["id"])
    assert req["status"] == "open" and "still to be proposed" in req["status_detail"]
    alts = [{"label": lab, "summary": lab, "files": {"rod_holder.py": rod_loop.design_text(12, so, label=lab)}}
            for lab, so in (("A", 45.0), ("B", 65.0))]
    ps = st.create_alternatives("alts", "r", alts, {"rod_holder.py": file_sha256(str(rod))}, ["R", "B"], purpose=p["id"])
    assert st.request(r["id"])["status"] == "proposed"
    q = st.evaluate(ps[0]["id"])
    st.accept(q["id"], override_reason="prototype" if q["evaluation"].get("failing_checks") else None)
    req = st.request(r["id"])
    assert req["status"] == "answered" and ps[0]["id"] in req["status_detail"]


def test_legacy_open_request_is_migrated_to_its_pending_answer(bracket):
    st = ProposalStore(str(bracket))
    py = bracket.name
    old = {"id": "r1", "created": "2026-11-16T18:15:44Z", "node": "A.3", "note": "", "change": None,
           "status": "open", "proposals": [], "design": "shelf_bracket", "kind": "queue"}
    a = st.create("first", "", {py: a3_offset_patch(bracket.read_text())}, {py: st.files.current_hashes()[py]}, ["A.3"])
    b = st.create("second", "", {py: a3_offset_patch(bracket.read_text(), 9.0)}, {py: st.files.current_hashes()[py]},
                  ["A.3"])
    (bracket.parent / ".dipm" / "requests" / "r1.json").write_text(json.dumps(old))   # written by iteration 4
    (r,) = st.requests()
    assert r["status"] == "proposed" and r["proposals"] == [b["id"]] and r["v"] == 2 and "migration" in r["migrated"]
    assert json.loads((bracket.parent / ".dipm" / "requests" / "r1.json").read_text())["proposals"] == [b["id"]]


# ---------------------------------------------------------------- queueing behind a run, MCP in a run

def test_requests_queued_during_a_run_start_the_next_one(bracket, stub, monkeypatch):
    stub("noop", DIPM_STUB_DELAY=1.5)
    monkeypatch.setenv("DIPM_CLAUDE_AUTORUN", "1")
    st = ProposalStore(str(bracket))
    r1 = st.create_request("A.3", "", None)
    runner = Runner(st)
    run1, _ = runner.auto()
    r2 = st.create_request("B", "", None)
    run, why = runner.auto()
    assert run is None and "already working" in why       # queued behind run1
    fin1 = finished(runner, run1["id"])
    assert fin1["status"] == "done" and st.request(r1["id"])["status"] == "failed"   # answered with nothing
    assert "without submitting a proposal" in st.request(r1["id"])["status_detail"]
    run2 = wait(lambda: runner.current, 10)
    assert run2["requests"] == [r2["id"]]
    assert finished(runner, run2["id"])["status"] == "done"


def test_mcp_in_a_run_lists_and_links_the_runs_requests(bracket, monkeypatch):
    st = ProposalStore(str(bracket))
    r1 = st.create_request("A.3", "", None)
    r2 = st.create_request("R", "", None)
    st.update_request(r1["id"], status="running")
    monkeypatch.setenv("DIPM_RUN", "run3")
    monkeypatch.setenv("DIPM_REQUESTS", r1["id"])
    py = bracket.name

    async def script():
        async with Client(build_server(str(bracket))) as c:
            rq = json.loads((await c.call_tool("get_requests", {})).content[0].text)
            assert rq["run"] == "run3" and [r["id"] for r in rq["requests"]] == [r1["id"]]
            src = json.loads((await c.call_tool("get_source", {})).content[0].text)
            bad = await c.call_tool("propose_patch", {"summary": "x", "rationale": "", "files": {py: "y"},
                                                      "base_hashes": src["base_hashes"], "requests": ["r99"]})
            assert bad.is_error and "no request r99" in bad.content[0].text
            p = json.loads((await c.call_tool("propose_patch", {
                "summary": "offset", "rationale": "", "files": {py: a3_offset_patch(src["files"][py]["text"])},
                "base_hashes": src["base_hashes"], "addresses_nodes": ["A.3"], "requests": [r2["id"]]})).content[0].text)
            return p
    p = asyncio.run(script())
    assert sorted(p["requests"]) == sorted([r1["id"], r2["id"]]) and p["run"] == "run3"
    assert st.request(r1["id"])["status"] == "running"     # the run decides when it ends
    assert st.request(r2["id"])["status"] == "proposed"


# ---------------------------------------------------------------- the stream parser (defensive)

def test_stream_parser_is_defensive():
    ps = StreamParser({"V-saddle": 1})
    for line in ("", "not json", "[1, 2]", '{"type": "assistant", "message": "oops"}', '{"type": "mystery"}',
                 '{"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "zz"}]}}'):
        assert ps.feed_line(line) == []
    ps.feed({"type": "system", "subtype": "init", "model": "m", "session_id": "s",
             "mcp_servers": [{"name": "dipm", "status": "failed"}]})
    assert ps.steps[-1]["kind"] == "error" and "did not start (failed)" in ps.steps[-1]["text"]
    ps.feed({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": "a", "name": "mcp__dipm__evaluate", "input": {"label": "V-saddle"}},
        {"type": "tool_use", "id": "b", "name": "mcp__dipm__get_impact", "input": {}},
        {"type": "tool_use", "id": "c", "name": "mcp__dipm__propose_alternatives", "input": {"alternatives": [{}, {}, {}]}},
        {"type": "tool_use", "id": "d", "name": "WebFetch", "input": {}},
        {"type": "text", "text": "  "}]}})
    assert [s["text"] for s in ps.steps[-4:]] == ["evaluating attempt 2 of 'V-saddle'", "reading the impact report",
                                                  "submitting 3 alternatives", "tried WebFetch (not allowed)"]
    ps.feed({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": "a", "content": json.dumps({"attempt": 2, "status": {"headline": "Kernel ✓"}})},
        {"type": "tool_result", "tool_use_id": "c", "content": [{"type": "text", "text": json.dumps(
            {"group": "p7", "alternatives": [{"id": "p7"}, {"id": "p8"}, {"id": "p9"}]})}]},
        {"type": "tool_result", "tool_use_id": "b", "is_error": True, "content": "Error executing tool get_impact: boom\nmore"}]}})
    assert [s["text"] for s in ps.steps[-3:]] == ["attempt 2 of 'V-saddle': Kernel ✓",
                                                  "submitted 3 alternatives (p7, p8, p9)",
                                                  "get_impact refused: Error executing tool get_impact: boom"]
    assert ps.proposals == ["p7", "p8", "p9"]
    ps.feed({"type": "result", "subtype": "success", "is_error": True, "result": "Invalid API key · Please run /login"})
    assert ps.auth_error and ps.steps[-1]["kind"] == "error"
    assert cr.usage_line({"total_cost_usd": 1.5, "usage": {"input_tokens": 1000, "output_tokens": 20},
                          "num_turns": 1, "duration_ms": 125000}) == "$1.50 · 1,000 in / 20 out tokens · 1 turn · 2 min 5 s"
    assert cr.usage_line({}) == "" and cr.usage_line({"usage": "x"}) == ""


def test_prompt_carries_the_request_and_the_loop_instructions(bracket):
    from dipm.mcp_server import INSTRUCTIONS
    st = ProposalStore(str(bracket))
    change = {"reviewed": {"statement": "Support a shelf on a wall"}, "current": {"statement": "Support a fishing rod"},
              "changed": ["statement"], "new": False}
    r = st.create_request("R", "make it hold a rod", change)
    text = cr.build_prompt(st, [r])
    assert f"{r['id']} · node R" in text and 'was "Support a shelf on a wall", now "Support a fishing rod"' in text
    assert "make it hold a rod" in text and INSTRUCTIONS.strip() in text and "only the dipm MCP tools" in text


# ---------------------------------------------------------------- HTTP API

def test_http_api_auto_run_settings_cancel_transcript(bracket, stub):
    from starlette.testclient import TestClient

    from dipm.server.app import create_app
    stub("patch")
    with TestClient(create_app(str(bracket), watch_files=False)) as c:
        s = c.get("/api/claude").json()
        assert s["available"]["ok"] and s["settings"]["auto_run"] is False and s["run"] is None   # tests: env off
        assert c.post("/api/claude/run", json={}).status_code == 409           # nothing to run
        j = c.post("/api/claude/settings", json={"auto_run": True, "model": "sonnet"}).json()
        assert j["settings"]["auto_run"] is True and j["settings"]["model"] == "sonnet"
        saved = json.loads((bracket.parent / ".dipm" / "runs" / "shelf_bracket.settings.json").read_text())
        assert saved == {"auto_run": True, "model": "sonnet"}
        assert c.post("/api/claude/settings", json={"model": "x; rm -rf /"}).status_code == 400
        c.post("/api/claude/settings", json={"model": ""})
        # queuing a request starts a run
        req = c.post("/api/requests", json={"node": "A.3", "note": "n"}).json()
        assert req["run"]["status"] == "running" and req["status"] == "running"
        rid = req["run"]["id"]
        assert c.post("/api/claude/run", json={}).json()["code"] in ("busy", "nothing")
        wait(lambda: not c.get("/api/claude").json()["running"], 90)
        s = c.get("/api/claude").json()
        assert s["run"]["id"] == rid and s["run"]["status"] == "done" and s["run"]["usage_line"]
        assert s["runs"][0]["proposals"] == s["run"]["proposals"]
        reqs = c.get("/api/requests").json()
        assert reqs["requests"][0]["status"] == "proposed" and reqs["waiting"] == 0
        t = c.get(f"/api/claude/runs/{rid}/transcript")
        assert t.status_code == 200 and t.headers["content-type"].startswith("text/plain")
        assert json.loads(t.text.splitlines()[-1])["type"] == "result"
        assert c.get("/api/claude/runs/run99/transcript").status_code == 404
        assert c.get("/api/claude/runs/..%2Fx/transcript").status_code == 404
        assert c.post("/api/claude/cancel", json={}).status_code == 409
        assert c.post("/api/claude/frobnicate", json={}).status_code == 404

"""A stub `claude -p` for the iteration-4b tests (docs/purpose-loop.md §7).  Never the real one.

Run through the `fake_claude` shell wrapper (DIPM_CLAUDE_BIN=tests/fixtures/fake_claude).  It
checks the flags the way dipm uses them, records its argv, then plays a model: it starts the MCP
server from the generated --mcp-config (exactly as Claude Code would), calls dipm's tools over
stdio, and prints Claude Code's stream-json events (system/init, assistant tool_use, user
tool_result, result) on stdout.

    DIPM_STUB_MODE    patch (default) | loop | noop | hang | notloggedin | crash | rogue
    DIPM_STUB_DELAY   seconds between steps (default 0)
    DIPM_STUB_RECORD  write {argv, cwd, config, env} here as JSON

patch: propose_patch adding a comment to the design (one evaluation).  loop: the rod holder's
purpose -> geometry loop with the fixed texts of rod_loop.py (a purpose proposal, labelled
evaluate attempts, 2 alternatives).  rogue: tries Bash first (denied), then patch.
"""
import asyncio
import json
import os
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SESSION = str(uuid.uuid4())
MODE = os.environ.get("DIPM_STUB_MODE", "patch")
DELAY = float(os.environ.get("DIPM_STUB_DELAY", "0") or 0)
T0 = time.time()
TURNS = 0


def emit(ev: dict) -> None:
    ev.setdefault("session_id", SESSION)
    sys.stdout.write(json.dumps(ev) + "\n")
    sys.stdout.flush()


def opt(argv, name):
    if name in argv:
        i = argv.index(name)
        return argv[i + 1] if i + 1 < len(argv) else None
    return None


def check_flags(argv) -> dict:
    """Refuse a command line the real CLI would refuse, or one that is not locked down."""
    errors = []
    if "-p" not in argv and "--print" not in argv:
        errors.append("not headless: -p missing")
    if opt(argv, "--output-format") != "stream-json":
        errors.append("--output-format stream-json missing")
    if "--verbose" not in argv:
        errors.append("Error: When using --print, --output-format=stream-json requires --verbose")
    if opt(argv, "--tools") != "":
        errors.append('built-in tools not disabled (--tools "")')
    if "--strict-mcp-config" not in argv or not opt(argv, "--mcp-config"):
        errors.append("--mcp-config/--strict-mcp-config missing")
    allowed = [t for t in (opt(argv, "--allowedTools") or "").replace(" ", ",").split(",") if t]
    if not allowed or any(not t.startswith("mcp__dipm__") for t in allowed):
        errors.append(f"allowed tools are not only dipm's: {allowed}")
    if opt(argv, "--permission-mode") != "dontAsk":
        errors.append("--permission-mode dontAsk missing")
    if errors:
        sys.stderr.write("\n".join(errors) + "\n")
        sys.exit(1)
    return {"prompt": argv[argv.index("-p") + 1], "config": opt(argv, "--mcp-config"), "allowed": allowed,
            "model": opt(argv, "--model")}


class Model:
    def __init__(self, client, allowed):
        self.c, self.allowed, self.n = client, set(allowed), 0

    async def call(self, tool: str, args: dict | None = None):
        global TURNS
        TURNS += 1
        if DELAY:
            await asyncio.sleep(DELAY)
        self.n += 1
        tid = f"toolu_stub_{self.n:03d}"
        name = tool if tool in ("Bash",) else f"mcp__dipm__{tool}"
        emit({"type": "assistant", "parent_tool_use_id": None,
              "message": {"id": f"msg_stub_{self.n}", "type": "message", "role": "assistant", "model": "claude-stub",
                          "content": [{"type": "tool_use", "id": tid, "name": name, "input": args or {}}],
                          "usage": {"input_tokens": 1200, "output_tokens": 80}}})
        if name not in self.allowed:
            emit({"type": "user", "parent_tool_use_id": None, "message": {"role": "user", "content": [
                {"tool_use_id": tid, "type": "tool_result", "is_error": True,
                 "content": f"Permission to use {name} has been denied."}]}})
            return None
        r = await self.c.call_tool(tool, args or {})
        text = r.content[0].text if r.content else ""
        emit({"type": "user", "parent_tool_use_id": None, "message": {"role": "user", "content": [
            {"tool_use_id": tid, "type": "tool_result", "is_error": bool(r.is_error),
             "content": [{"type": "text", "text": text}]}]}})
        if r.is_error:
            raise RuntimeError(text)
        return json.loads(text) if text.strip().startswith("{") else text

    def say(self, text: str) -> None:
        emit({"type": "assistant", "parent_tool_use_id": None,
              "message": {"id": f"msg_stub_say_{self.n}", "type": "message", "role": "assistant",
                          "model": "claude-stub", "content": [{"type": "text", "text": text}],
                          "usage": {"input_tokens": 300, "output_tokens": 40}}})


async def patch(m: Model) -> str:
    rq = await m.call("get_requests")
    reqs = rq["requests"]
    src = await m.call("get_source")
    name = next(n for n in src["files"] if n.endswith(".py"))
    text = src["files"][name]["text"] + f"\n# fake claude: answered {', '.join(r['id'] for r in reqs)}\n"
    nodes = sorted({r["node"] for r in reqs})
    m.say("A comment is the smallest change that answers this; proposing it.")
    p = await m.call("propose_patch", {"summary": "Stub answer: a comment", "rationale": "fake claude",
                                       "files": {name: text}, "base_hashes": {name: src["base_hashes"][name]},
                                       "addresses_nodes": nodes})
    return f"Proposed {p['id']} for {', '.join(r['id'] for r in reqs)}."


async def loop(m: Model) -> str:
    import rod_loop
    await m.call("get_requests")
    await m.call("get_impact")
    await m.call("get_check_vocabulary")
    await m.call("get_components")
    src = await m.call("get_source")
    intent = next(n for n in src["files"] if n.endswith(".intent.yaml"))
    design = next(n for n in src["files"] if n.endswith(".py"))
    m.say("The shelf purposes are invalidated; re-planning them for a rod cradle first.")
    p = await m.call("propose_purposes", {"summary": "Rod holder purposes: cradle, retention, reel clearance",
                                          "rationale": "The root purpose changed from a shelf to a fishing rod.",
                                          "intent_file": rod_loop.PURPOSE_TEXT,
                                          "base_hash": src["base_hashes"][intent], "addresses_nodes": ["R", "B"]})
    plan = {"Compact": [(4.0, 45.0, "first cradle, 4 mm lip"), (12.0, 45.0, "lip raised to 12 mm")],
            "Stand-off": [(12.0, 65.0, "rod 65 mm out so the reel clears the wall")]}
    alts = []
    for label, attempts in plan.items():
        for lip, so, summary in attempts:
            await m.call("evaluate", {"files": {design: rod_loop.design_text(lip, so, label=label[0])},
                                      "label": label, "purpose": p["id"], "summary": summary})
        lip, so, summary = attempts[-1]
        alts.append({"label": label, "summary": f"{label}: {summary}", "rationale": summary,
                     "files": {design: rod_loop.design_text(lip, so, label=label[0])}})
    g = await m.call("propose_alternatives", {"summary": "Rod holder alternatives", "rationale": "two cradles",
                                              "alternatives": alts, "base_hashes": {design: src["base_hashes"][design]},
                                              "addresses_nodes": ["R", "B"], "purpose": p["id"]})
    ids = [a["id"] for a in g["alternatives"]]
    return f"Proposed purposes {p['id']} and {len(ids)} alternatives ({', '.join(ids)})."


async def main() -> int:
    argv = sys.argv[1:]
    a = check_flags(argv)
    rec = os.environ.get("DIPM_STUB_RECORD")
    with open(a["config"], encoding="utf-8") as fh:
        cfg = json.load(fh)
    if rec:
        with open(rec, "w", encoding="utf-8") as fh:
            json.dump({"argv": argv, "cwd": os.getcwd(), "config": cfg,
                       "env": {k: os.environ.get(k) for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")}}, fh)
    srv = cfg["mcpServers"]["dipm"]
    emit({"type": "system", "subtype": "init", "cwd": os.getcwd(), "tools": a["allowed"], "model": a["model"] or "claude-stub",
          "permissionMode": "dontAsk", "apiKeySource": "none",
          "mcp_servers": [{"name": "dipm", "status": "connected"}]})
    if MODE == "notloggedin":
        emit({"type": "result", "subtype": "success", "is_error": True, "duration_ms": 120, "num_turns": 1,
              "result": "Not logged in · Please run /login", "total_cost_usd": 0})
        return 1
    if MODE == "crash":
        sys.stderr.write("Error: the stub crashed on purpose\n")
        return 2
    from mcp import Client, StdioServerParameters
    params = StdioServerParameters(command=srv["command"], args=srv["args"], env={**os.environ, **(srv.get("env") or {})},
                                   cwd=os.getcwd())
    async with Client(params) as c:
        m = Model(c, a["allowed"])
        if MODE == "hang":
            await m.call("get_requests")
            await asyncio.sleep(3600)
            return 0
        if MODE == "noop":
            await m.call("get_requests")
            summary = "Nothing to change: the solution still fits."
        elif MODE == "loop":
            summary = await loop(m)
        else:
            if MODE == "rogue":
                await m.call("Bash", {"command": "ls"})
            summary = await patch(m)
    m.say(summary)
    emit({"type": "result", "subtype": "success", "is_error": False, "duration_ms": int((time.time() - T0) * 1000),
          "duration_api_ms": 900, "num_turns": TURNS + 1, "result": summary, "total_cost_usd": 0.0421,
          "usage": {"input_tokens": 5210, "cache_creation_input_tokens": 1200, "cache_read_input_tokens": 30400,
                    "output_tokens": 1830}})
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

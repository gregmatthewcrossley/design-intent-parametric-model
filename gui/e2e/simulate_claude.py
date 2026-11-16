"""A scripted stand-in for Claude in the e2e tests (docs/gui.md §7.3).

Talks to `python -m dipm mcp <design>` over stdio with the official MCP SDK client, exactly as
Claude Code would, and makes the A.3 change: "centered on the plate" -> "offset <mm> mm above
the lower screw".

    python simulate_claude.py <design.py> propose <mm> [<revises>]   -> prints the proposal JSON
    python simulate_claude.py <design.py> feedback [<proposal id>]   -> prints get_proposal_feedback
"""
import asyncio
import json
import os
import sys

from mcp import Client, StdioServerParameters


def a3_patch(py: str, mm: float) -> str:
    out = py.replace("at=centered_on(mount_face)", f"at=offset(wall_pts[0], Z, {mm})")
    out = out.replace("centered_on, centerline,", "centered_on, centerline, offset,")
    return out.replace('"cable pass-through, centred on the plate"', f'"cable pass-through, {mm:g} mm above the lower screw"')


async def main(design: str, cmd: str, args: list) -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "dipm", "mcp", design],
                                   env={**os.environ, "PYTHONWARNINGS": "ignore"})
    async with Client(params) as c:
        async def call(name, a=None):
            r = await c.call_tool(name, a or {})
            if r.is_error:
                raise SystemExit(f"{name} failed: {r.content[0].text}")
            return json.loads(r.content[0].text)

        if cmd == "feedback":
            print(json.dumps(await call("get_proposal_feedback", {"proposal_id": args[0]} if args else {})))
            return
        stale = await call("get_stale_nodes")
        nodes = [s["id"] for s in stale["stale"]] or ["A.3"]
        src = await call("get_source")
        mm = float(args[0])
        new = a3_patch(src["files"][os.path.basename(design)]["text"], mm)
        p = await call("propose_patch", {
            "summary": f"A.3: place the cable hole {mm:g} mm above the lower wall screw",
            "rationale": "A.3's intent changed from 'centered on the plate' to an offset from the lower screw; "
                         "the placement becomes a relation to the A.P pattern's first point.",
            "files": {os.path.basename(design): new}, "base_hashes": src["base_hashes"],
            "addresses_nodes": [n for n in nodes if n == "A.3"] or ["A.3"],
            **({"revises": args[1]} if len(args) > 1 else {})})
        print(json.dumps(p))


if __name__ == "__main__":
    asyncio.run(main(os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3:]))

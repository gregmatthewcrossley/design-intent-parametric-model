"""`python -m dipm mcp <design.py>`: a stdio MCP server for one design (docs/gui.md §7.3).

It lets a model (e.g. a Claude Code session) read the design, build it, explain faces, see
which intent nodes are stale, and **propose** changes.  It never writes design files: a
proposal is stored under `<design dir>/.dipm/proposals/`, evaluated in a temp copy, and shown
in the `dipm serve` GUI, where the designer accepts or rejects it (with a comment that comes
back through `get_proposal_feedback`).

Tools: get_design, get_intent, build, why, get_stale_nodes, get_requests, get_source,
propose_patch, list_proposals, get_proposal_feedback.
"""
from __future__ import annotations

import os
import threading
import warnings

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import intent_store
from .fileio import file_sha256, read_text
from .proposals import ProposalError, ProposalStore, build_summary, load_and_build
from .review import ReviewRecord

INSTRUCTIONS = """\
dipm: design-intent parametric CAD.  A design is an intent tree (<design>.intent.yaml: statements,
checks, assumptions) plus a deterministic solution in the embedded-Python DSL (<design>.py), whose
features name the intent nodes they serve in tags=intent("A.3", ...).  Geometry is rebuilt from text.

Typical loop when the designer clicks "Ask Claude" on a stale intent node:
1. get_stale_nodes (or get_requests): which nodes changed, what they said when last reviewed, the
   designer's note, and the features that realize them.
2. get_intent, get_source (texts + sha256 base hashes), build / why to understand the geometry.
3. propose_patch with the full new text (or a unified diff) of <design>.py and/or
   <design>.intent.yaml, the base_hashes from get_source, and addresses_nodes.  You cannot write
   files; the proposal is evaluated (build, checks over the parameter ranges, interpretations,
   semantic diff, geometry before/after) and the designer accepts or rejects it in the GUI.
4. get_proposal_feedback: if rejected, read the comment and propose again with revises=<id>.
Prefer relations to literals (e.g. offset(wall_pts[0], Z, 10.0) rather than at((0, 5, 19))), keep
feature ids and intent ids stable, and keep the tag notes in sync with the intent statements.
"""


class DesignContext:
    """The design behind the server; reloaded when any of its files change on disk."""

    def __init__(self, design_path: str):
        self.path = os.path.abspath(design_path)
        if not os.path.exists(self.path):
            raise FileNotFoundError(self.path)
        self.store = ProposalStore(self.path)
        self.files = self.store.files
        self._key = None
        self._cur = None
        self._lock = threading.Lock()

    def _files_key(self) -> tuple:
        F = self.files
        return tuple(file_sha256(p) for p in (F.design, F.intent, F.lock, F.review))

    def current(self, params: dict | None = None) -> dict:
        """{design, build, intent, intent_error, stale, summary} at `params` (default: defaults)."""
        with self._lock:
            key = self._files_key()
            if params or self._cur is None or key != self._key:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    try:
                        res = load_and_build(self.path, params)
                    except Exception as e:   # noqa: BLE001
                        raise ToolError(f"cannot load/build {os.path.basename(self.path)}: {type(e).__name__}: {e}")
                rec = ReviewRecord.load(self.files.review)
                stale = {}
                if res["intent"] is not None:
                    rec.baseline(res["intent"])
                    stale = rec.stale(res["intent"])
                res["stale"] = stale
                res["summary"] = build_summary(res["design"], res["build"], res["intent"], stale)
                if params:
                    return res
                self._cur, self._key = res, key
            return self._cur


def build_server(design_path: str) -> MCPServer:
    ctx = DesignContext(design_path)
    server = MCPServer("dipm", instructions=INSTRUCTIONS)

    @server.tool()
    def get_design() -> dict:
        """The design: name, files, declared parameters (defaults, ranges, choices), and the
        ordered features with the intent nodes they serve."""
        from .server.serialize import design_info
        cur = ctx.current()
        info = design_info(cur["design"], ctx.path)
        return {"name": info["name"], "doc": info["doc"], "design_file": ctx.path,
                "intent_file": ctx.files.intent if os.path.exists(ctx.files.intent) else None,
                "patchable_files": sorted(ctx.files.patchable), "params": info["params"],
                "features": [{"id": f["id"], "op": f["op"], "tags": [t["text"] for t in f["tags"]]}
                             for f in info["features"]],
                "exports": sorted(cur["design"].exports)}

    @server.tool()
    def get_intent() -> dict:
        """The intent tree from <design>.intent.yaml (statements, checks, assumptions, nesting),
        its sha256, the stale nodes, and intent<->feature diagnostics."""
        cur = ctx.current()
        path = ctx.files.intent
        if not os.path.exists(path):
            return {"file": None, "note": "this design has no intent file; the tree is derived from feature tags",
                    "tree": cur["summary"]["diagnostics"]}
        return {"file": path, "sha256": file_sha256(path), "doc": cur["intent"], "errors": cur["intent_error"],
                "stale_nodes": sorted(cur["stale"]), "diagnostics": cur["summary"]["diagnostics"]}

    @server.tool()
    def build(params: dict | None = None) -> dict:
        """Build the current design (optionally with parameter overrides) and return the report
        summary: status, per-feature status and failed checks, interpretations, diagnostics."""
        try:
            return ctx.current(params or None)["summary"]
        except ToolError:
            raise
        except Exception as e:   # noqa: BLE001
            raise ToolError(str(e)) from None

    @server.tool()
    def why(face_id: int, params: dict | None = None) -> dict:
        """'Why is this here?' for face `face_id` (0-based, the GUI's face ids at the same
        parameters): the feature and role that created it, its intent tags and history."""
        cur = ctx.current(params or None)
        b = cur["build"]
        if b.shape is None:
            raise ToolError("the build has no geometry")
        faces = b.faces()
        if not 0 <= face_id < len(faces):
            raise ToolError(f"face_id must be in 0..{len(faces) - 1}")
        w = b.why(faces[face_id])
        return {"face_id": face_id, "text": str(w), "intent_nodes": w.intent_nodes(),
                "entries": [{"tag": str(e.tag), "feature": e.feature, "op": e.op, "lowered_from": e.lowered_from,
                             "intent": [str(t) for t in e.intent], "instance_intent": [str(t) for t in e.instance_intent]}
                            for e in w.entries]}

    def _stale_list(cur) -> list:
        nodes = (cur["summary"] or {}).get("features", [])
        out = []
        open_reqs = ctx.store.requests("open")
        for nid, info in sorted(cur["stale"].items()):
            feats = [f["id"] for f in nodes if nid in f["serves"] or
                     any(nid == t.node for t in _tags_of(cur["design"], f["id"]))]
            out.append({"id": nid, "statement": info["current"]["statement"],
                        "reviewed": info["reviewed"], "current": info["current"], "changed": info["changed"],
                        "new_node": info["new"], "features": feats,
                        "requests": [r for r in open_reqs if r.get("node") == nid]})
        return out

    @server.tool()
    def get_stale_nodes() -> dict:
        """Intent nodes whose content changed since their solution was last reviewed: what they
        said then and now, the features that realize them, and open 'Ask Claude' requests."""
        cur = ctx.current()
        return {"stale": _stale_list(cur), "requests": ctx.store.requests("open")}

    @server.tool()
    def get_requests(status: str = "open") -> dict:
        """'Ask Claude' requests from the GUI (status: open | answered | all), each with the
        node, the designer's note and the intent change."""
        return {"requests": ctx.store.requests(None if status == "all" else status)}

    @server.tool()
    def get_source() -> dict:
        """The design's patchable files with their text and sha256 (use these as base_hashes)."""
        out = {}
        for name, path in sorted(ctx.files.patchable.items()):
            if os.path.exists(path):
                text = read_text(path)
                out[name] = {"path": path, "sha256": file_sha256(path), "text": text}
        return {"files": out, "base_hashes": {n: f["sha256"] for n, f in out.items()}}

    @server.tool()
    def propose_patch(summary: str, rationale: str, files: dict[str, str], base_hashes: dict[str, str],
                      addresses_nodes: list[str] | None = None, revises: str | None = None) -> dict:
        """Propose a change.  `files` maps a patchable path (e.g. "shelf_bracket.py") to its new
        full text or a unified diff; `base_hashes` maps the same paths to the sha256 you read
        with get_source.  Nothing is written: the proposal is evaluated in a temp copy and
        waits for the designer.  Returns the evaluation (checks, semantic and text diffs)."""
        try:
            p = ctx.store.create(summary, rationale, files, base_hashes, addresses_nodes or [], revises, "mcp")
        except ProposalError as e:
            raise ToolError(str(e)) from None
        if p["status"] == "pending":
            p = ctx.store.evaluate(p["id"])
        return _proposal_view(p, full=True)

    @server.tool()
    def list_proposals() -> dict:
        """Every proposal for this design with its status (pending, ready, failed, accepted,
        rejected, stale)."""
        return {"proposals": [_proposal_view(p) for p in ctx.store.list()]}

    @server.tool()
    def get_proposal_feedback(proposal_id: str | None = None) -> dict:
        """The designer's decisions and comments, for one proposal or all of them."""
        try:
            return {"feedback": ctx.store.feedback(proposal_id)}
        except ProposalError as e:
            raise ToolError(str(e)) from None

    return server


def _tags_of(design, fid: str) -> list:
    for f in design.features:
        if f.id == fid:
            out = list(f.tags)
            for ts in getattr(f, "instance_tags", None) or ():
                out += [t for t in (ts if isinstance(ts, (list, tuple)) else [ts]) if hasattr(t, "node")]
            return out
    return []


def _proposal_view(p: dict, full: bool = False) -> dict:
    ev = p.get("evaluation") or {}
    v = {"id": p["id"], "status": p["status"], "status_detail": p.get("status_detail", ""), "summary": p["summary"],
         "created": p["created"], "addresses_nodes": p.get("addresses_nodes", []), "revises": p.get("revises"),
         "files": sorted(p.get("patches", {})), "checks_pass": ev.get("ok") if ev else None}
    if full and ev:
        v["evaluation"] = {k: ev[k] for k in ("ok", "before", "after", "sweep", "semantic_diff", "text_diff",
                                               "changed_faces", "error", "ms") if k in ev}
    if full:
        v["feedback"] = p.get("feedback", [])
    return v


def main(design_path: str) -> int:
    server = build_server(design_path)
    server.run("stdio")
    return 0

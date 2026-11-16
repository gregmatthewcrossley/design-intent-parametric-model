"""`dipm serve`: a local web GUI for one design (docs/gui.md §2, §5).

    GET  /api/design          name, doc, file, parameters
    POST /api/build {params}  build result (features, checks, intent tree, interpretations,
                              genealogy tables, diagnostics, mesh id)
    GET  /api/mesh/{id}       binary mesh (mesh.py)
    POST /api/answer {assumption_id, reading, scope?, note?}
                              record a preference exactly like `dipm answer`, re-resolve,
                              rewrite the lock, rebuild
    WS   /api/events          {"type": "design-changed" | "rebuilt" | "design-error" | "resolving", ...}

Bound to 127.0.0.1 only.  The design file, its lock and its preferences are watched; on a
change the design module is re-imported fresh (cli.load_design never caches it) and rebuilt
with the current parameters.  A stale lock does not block the rebuild: the old choices are
used at once and interpretations are re-resolved in a background thread, followed by a second
`rebuilt` event (NOTES DECISIONS #34).
"""
from __future__ import annotations

import asyncio
import collections
import hashlib
import json
import os
import threading
import traceback
import warnings

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from ..errors import DipmError, ParameterError
from .mesh import mesh_bytes
from .serialize import build_payload, design_info

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
MESH_CACHE = 16


def _sha(path: str | None) -> str | None:
    if not path or not os.path.exists(path):
        return None
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class Session:
    """Server-side state for one design file.  Builds are serialized by `build_lock`;
    interpretation resolution runs in its own thread and never blocks a build."""

    def __init__(self, path: str, prefs: str | None = None, lock: str | None = None):
        self.path = os.path.abspath(path)
        self.prefs_arg = os.path.abspath(prefs) if prefs else None
        self.lock_arg = os.path.abspath(lock) if lock else None
        self.design = None
        self.design_error: str | None = None
        self.params: dict = {}
        self.generation = 0
        self.last_payload: dict | None = None
        self.last_good_mesh: str | None = None
        self.meshes: collections.OrderedDict = collections.OrderedDict()
        self.build_lock = threading.Lock()
        self.resolving = False
        self.own_writes: dict = {}          # path -> sha256 of content this server wrote
        self.writing: set = set()            # paths this server is writing right now (watcher ignores them)
        self.listeners: set = set()          # asyncio.Queue per websocket
        self.loop: asyncio.AbstractEventLoop | None = None
        self.resolve_thread: threading.Thread | None = None
        self.needs_resolve = False

    # ------------------------------------------------------------------ files
    @property
    def lock_path(self) -> str | None:
        return self.design.lock.lock if self.design is not None and self.design.lock else None

    def prefs_path(self) -> str | None:
        """Preferences file: --prefs, else the one the lock records, else None (until an answer)."""
        if self.prefs_arg:
            return self.prefs_arg
        if self.design is not None and self.design.lock is not None:
            from ..interpret import prefs_path_from_lock
            return prefs_path_from_lock(self.design.lock)
        return None

    def default_prefs_path(self) -> str:
        return os.path.splitext(self.path)[0] + ".prefs.json"

    def watched(self) -> set:
        from ..interpret import lock_path_for
        out = {self.path, self.lock_arg or lock_path_for(self.path)}
        p = self.prefs_path()
        out.add(p or self.default_prefs_path())
        return {os.path.realpath(x) for x in out if x}     # realpath: watchfiles reports resolved paths

    # ------------------------------------------------------------------ design loading
    def load(self) -> None:
        """(Re)import the design module fresh and attach its lock without blocking on a
        stale/missing lock (the background resolver handles that)."""
        from ..cli import _attach_lock, load_design
        from ..interpret import Preferences, lock_key, prefs_path_from_lock, read_lock
        self.generation += 1
        try:
            design = load_design(self.path)
        except BaseException as e:   # SystemExit from load_design, syntax errors, anything in user code
            self.design_error = "".join(traceback.format_exception_only(type(e), e)).strip()
            raise
        _attach_lock(design, self.path, self.lock_arg, self.prefs_arg)
        spec = design.lock
        prefs = Preferences.load(prefs_path_from_lock(spec))
        lk = read_lock(spec.lock)
        fresh = lk is not None and lk.key == lock_key(spec.design_file, prefs)
        design.prefs = prefs
        if fresh:
            design.interpretation, design.interpretations = lk, dict(lk.choices)
            design._interp_source = f"lock {os.path.basename(spec.lock)}"
            self.needs_resolve = False
        elif lk is not None:
            design.interpretation, design.interpretations = lk, dict(lk.choices)
            design._interp_source = "stale lock (re-resolving)"
            self.needs_resolve = True
        else:
            self.needs_resolve = True
        self.design, self.design_error = design, None
        self.params = self._carry_params(self.params)

    def _carry_params(self, old: dict) -> dict:
        """Keep the current parameter values that are still declared and valid."""
        out = {}
        for k, v in old.items():
            p = self.design.params.get(k)
            if p is None:
                continue
            try:
                p.validate(v)
                out[k] = v
            except (ValueError, TypeError):
                pass
        return out

    # ------------------------------------------------------------------ building
    def build(self, params: dict | None = None) -> dict:
        """Build with `params` (merged over the current ones) and return the payload."""
        if self.design is None:
            raise RuntimeError(self.design_error or "no design loaded")
        with self.build_lock:
            design = self.design
            merged = {**self.params, **(params or {})}
            values = design.resolve_params(merged)        # raises ParameterError
            self.params = {k: values[k] for k in merged if k in values}
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                if design.interpretation is None and design.lock is not None:
                    b = design.build(values, on_fail="record", interpretations={}, prefs=design.prefs)
                else:
                    b = design.build(values, on_fail="record")
            mesh_id = None
            if b.shape is not None:
                mesh_id, data = mesh_bytes(b.shape)
                self.meshes[mesh_id] = data
                self.meshes.move_to_end(mesh_id)
                while len(self.meshes) > MESH_CACHE:
                    old, _ = self.meshes.popitem(last=False)
                    if old == self.last_good_mesh:        # keep the last good model available
                        self.meshes[old] = _
                        self.meshes.move_to_end(old, last=False)
                        if len(self.meshes) > MESH_CACHE:
                            self.meshes.popitem(last=False)
                        break
            notes = [str(w.message) for w in caught]
            if self.needs_resolve or self.resolving:
                notes.append("interpretations are being re-resolved; a second update will follow")
            payload = build_payload(design, b, mesh_id, notes)
            payload["file"] = self.path
            payload["generation"] = self.generation
            payload["resolving"] = bool(self.needs_resolve or self.resolving)
            if b.ok and mesh_id:
                self.last_good_mesh = mesh_id
            payload["last_good_mesh_id"] = self.last_good_mesh
            self.last_payload = payload
            return payload

    def resolve_now(self) -> None:
        """Resolve interpretations (blocking) for the current design generation."""
        from ..interpret import load_or_resolve
        gen, design = self.generation, self.design
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            interp, prefs, fresh = load_or_resolve(design, design.lock)
        if gen != self.generation:
            return
        design.interpretation, design.interpretations, design.prefs = interp, dict(interp.choices), prefs
        design._interp_source = (f"lock {os.path.basename(design.lock.lock)}" if fresh else
                                 "resolved in memory (lock stale; run `dipm interpret` to update it)")
        self.needs_resolve = False

    def resolve_in_background(self) -> None:
        if not self.needs_resolve or self.resolving:
            return
        self.resolving = True
        gen = self.generation

        def run():
            try:
                self.resolve_now()
                if gen == self.generation:
                    payload = self.build()
                    self.publish({"type": "rebuilt", "reason": "resolved", "build": payload})
            except Exception as e:   # noqa: BLE001 - reported to the browser
                self.publish({"type": "design-error", "message": f"resolution failed: {e}"})
            finally:
                self.resolving = False
                if gen != self.generation and self.needs_resolve:
                    self.resolve_in_background()

        self.resolve_thread = threading.Thread(target=run, name="dipm-resolve", daemon=True)
        self.resolve_thread.start()

    # ------------------------------------------------------------------ answers
    def answer(self, assumption_id: str, reading: str, scope: str = "node", note: str = "") -> dict:
        """Same semantics as `dipm answer`: record, re-resolve, rewrite the lock, then rebuild."""
        prefs = self.prefs_path() or self.default_prefs_path()
        lock_file = self.design.lock.lock if self.design.lock else None
        mine = {os.path.realpath(p) for p in (prefs, lock_file) if p}
        self.writing |= mine
        try:
            payload = self._answer_locked(assumption_id, reading, scope, note, prefs)
        finally:
            for p in mine:
                self.own_writes[p] = _sha(p)
            self.writing -= mine
        return payload

    def _answer_locked(self, assumption_id: str, reading: str, scope: str, note: str, prefs: str) -> dict:
        from ..cli import record_answer
        from ..interpret import write_lock
        with self.build_lock:
            key, warn = record_answer(self.design, self.path, assumption_id, reading, prefs, scope, note,
                                      self.lock_arg)
            self.prefs_arg = prefs
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                interp = self.design.ensure_interpretations(force=True)
            write_lock(interp, self.design.lock.lock)
            self.needs_resolve = False
        payload = self.build()
        payload["answer"] = {"key": key, "warning": warn, "prefs": prefs}
        return payload

    # ------------------------------------------------------------------ events
    def publish(self, msg: dict) -> None:
        """Thread-safe: queue `msg` for every websocket."""
        if self.loop is None:
            return
        for q in list(self.listeners):
            self.loop.call_soon_threadsafe(q.put_nowait, msg)

    def is_own_write(self, path: str) -> bool:
        exp = self.own_writes.get(path)
        return exp is not None and exp == _sha(path)

    async def on_files_changed(self, paths: set) -> None:
        """Watcher callback: reload (design file) and rebuild, keeping the current parameters."""
        paths = {os.path.realpath(p) for p in paths} & self.watched()
        paths = {p for p in paths if p not in self.writing and not self.is_own_write(p)}
        if not paths:
            return
        try:
            await asyncio.to_thread(self.load)
        except BaseException:   # noqa: BLE001
            self.publish({"type": "design-error", "message": self.design_error or "reload failed"})
            return
        self.publish({"type": "design-changed", "design": design_info(self.design, self.path),
                      "changed": sorted(os.path.relpath(p) for p in paths)})
        try:
            payload = await asyncio.to_thread(self.build)
        except DipmError as e:
            self.publish({"type": "design-error", "message": str(e)})
            return
        self.publish({"type": "rebuilt", "reason": "file-changed", "build": payload})
        self.resolve_in_background()


async def watch(session: Session, stop: asyncio.Event) -> None:
    from watchfiles import awatch
    dirs = sorted({os.path.dirname(p) for p in session.watched()})
    async for changes in awatch(*dirs, stop_event=stop, debounce=120, step=30, recursive=False):
        await session.on_files_changed({p for _, p in changes})


def create_app(design_path: str, prefs: str | None = None, lock: str | None = None, watch_files: bool = True,
               static_dir: str = STATIC_DIR) -> Starlette:
    session = Session(design_path, prefs, lock)
    session.load()

    async def api_design(request: Request):
        if session.design is None:
            return JSONResponse({"error": session.design_error}, status_code=500)
        return JSONResponse({**design_info(session.design, session.path), "current_params": session.params,
                             "resolving": bool(session.needs_resolve or session.resolving)})

    async def api_build(request: Request):
        try:
            body = await request.json() if (await request.body()) else {}
        except json.JSONDecodeError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        params = body.get("params") or {}
        if not isinstance(params, dict):
            return JSONResponse({"error": "params must be an object"}, status_code=400)
        try:
            payload = await asyncio.to_thread(session.build, params)
        except ParameterError as e:
            return JSONResponse({"error": e.message, "kind": "ParameterError"}, status_code=400)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=500)
        session.resolve_in_background()
        return JSONResponse(payload)

    async def api_mesh(request: Request):
        data = session.meshes.get(request.path_params["id"])
        if data is None:
            return JSONResponse({"error": "unknown mesh id (evicted or never built)"}, status_code=404)
        return Response(data, media_type="application/octet-stream",
                        headers={"Cache-Control": "public, max-age=31536000, immutable"})

    async def api_answer(request: Request):
        from ..cli import AnswerError
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return JSONResponse({"error": "body must be JSON"}, status_code=400)
        aid, reading = body.get("assumption_id"), body.get("reading")
        if not aid or not reading:
            return JSONResponse({"error": "assumption_id and reading are required"}, status_code=400)
        try:
            payload = await asyncio.to_thread(session.answer, aid, reading, body.get("scope", "node"),
                                              body.get("note", ""))
        except AnswerError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        session.publish({"type": "rebuilt", "reason": "answer", "build": payload})
        return JSONResponse(payload)

    async def events(ws: WebSocket):
        await ws.accept()
        q: asyncio.Queue = asyncio.Queue()
        session.listeners.add(q)
        try:
            await ws.send_json({"type": "hello", "generation": session.generation})
            while True:
                getter = asyncio.ensure_future(q.get())
                recv = asyncio.ensure_future(ws.receive_text())
                done, pending = await asyncio.wait({getter, recv}, return_when=asyncio.FIRST_COMPLETED)
                for p in pending:
                    p.cancel()
                if recv in done:
                    recv.result()          # raises WebSocketDisconnect when the client leaves
                    continue
                await ws.send_json(getter.result())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            session.listeners.discard(q)

    async def index(request: Request):
        page = os.path.join(static_dir, "index.html")
        if os.path.exists(page):
            return FileResponse(page)
        return HTMLResponse("<h1>dipm</h1><p>The GUI is not built. Run <code>npm ci && npm run build</code> in "
                            "<code>gui/</code>; the API is live under <code>/api</code>.</p>")

    routes = [Route("/api/design", api_design), Route("/api/build", api_build, methods=["POST"]),
              Route("/api/mesh/{id}", api_mesh), Route("/api/answer", api_answer, methods=["POST"]),
              WebSocketRoute("/api/events", events), Route("/", index)]
    if os.path.isdir(os.path.join(static_dir, "assets")):
        routes.append(Mount("/assets", StaticFiles(directory=os.path.join(static_dir, "assets")), name="assets"))
    if os.path.isdir(os.path.join(static_dir, "fonts")):
        routes.append(Mount("/fonts", StaticFiles(directory=os.path.join(static_dir, "fonts")), name="fonts"))

    import contextlib

    @contextlib.asynccontextmanager
    async def lifespan(app):
        session.loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        task = asyncio.create_task(watch(session, stop)) if watch_files else None
        try:
            yield
        finally:
            stop.set()
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

    app = Starlette(routes=routes, lifespan=lifespan)
    app.state.session = session
    return app


def serve(design_path: str, port: int = 8765, open_browser: bool = True, prefs: str | None = None) -> int:
    """Run the server on 127.0.0.1 (never another interface).  Tries the next ports if busy."""
    import socket
    import webbrowser

    import uvicorn
    host = "127.0.0.1"
    for p in range(port, port + 20):
        with socket.socket() as s:
            try:
                s.bind((host, p))
                break
            except OSError:
                continue
    else:
        print(f"no free port in {port}..{port + 19}")
        return 1
    try:
        app = create_app(design_path, prefs)
    except BaseException as e:   # noqa: BLE001
        print(f"cannot load {design_path}: {e}")
        return 2
    url = f"http://{host}:{p}/"
    print(f"dipm: serving {os.path.relpath(design_path)} at {url}  (Ctrl-C to stop)", flush=True)
    if not os.path.exists(os.path.join(STATIC_DIR, "index.html")):
        print("dipm: the GUI is not built; run `npm ci && npm run build` in gui/ (the API works without it)")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=p, log_level="warning")
    return 0

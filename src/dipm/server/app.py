"""`dipm serve`: a local web GUI for one design (docs/gui.md §2, §5).

    GET  /api/design          name, doc, file, parameters
    POST /api/build {params}  build result (features, checks, intent tree, interpretations,
                              genealogy tables, diagnostics, mesh id)
    GET  /api/mesh/{id}       binary mesh (mesh.py)
    POST /api/answer {assumption_id, reading, scope?, note?}
                              record a preference exactly like `dipm answer`, re-resolve,
                              rewrite the lock, rebuild
    WS   /api/events          {"type": "design-changed" | "rebuilt" | "design-error" | "intent-changed"
                               | "proposals-changed", ...}

Iteration 2 (docs/gui.md §7):

    GET   /api/intent                     the intent file as data, its hash, stale nodes, errors
    PATCH /api/intent {base_hash, ops}    edit it (intent_store.apply_op ops, plus
                                          {"op": "mark_reviewed", "ids": [...]}); 409 + the current
                                          state if the file changed since `base_hash`
    GET   /api/proposals                  proposals (shared with `dipm mcp`), newest last
    POST  /api/proposals {summary, rationale, files, base_hashes, addresses_nodes, revises?}
    GET   /api/proposals/{id}             one proposal with its evaluation
    GET   /api/proposals/{id}/mesh/{before|after}
    POST  /api/proposals/{id}/accept {comment?}    apply atomically, record reviews, rebuild
    POST  /api/proposals/{id}/reject {comment}     feedback for get_proposal_feedback
    GET   /api/requests, POST /api/requests {node, note}   "Ask Claude" requests
    POST  /api/intent/rename {base_hash, design_hash, old, new, rename_features?}
                                          rename an intent id in the file and the DSL (LibCST codemod);
                                          migrates saved preferences (#49)

Iteration 3 (docs/gui.md §8):

    GET   /api/display[?width&height&dpr&label&internal&left&top]
                                          physical display sizes from the OS (display.py) and the
                                          display the browser is on
    POST  /api/context {base_hash, action: accept | set, values?}
                                          write the assumed (or changed) context into the intent file
    POST  /api/orientation {action: infer | accept, base_hash?}
                                          re-infer the print orientation (resolution record) or
                                          accept it into the intent file's root assumptions
    POST  /api/review {action: all | one_by_one | accept_item, base_hash?, key?, value?}
                                          first-open review prompt (#48); accept a model-made item
    POST  /api/proposals/{id}/view {params}   before/after meshes at the GUI's parameters (#53)
    POST  /api/proposals/{id}/accept {comment?, override_reason?}   "Accept anyway…" (#54)

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

from .. import intent_store
from ..errors import DipmError, ParameterError
from ..fileio import file_sha256
from ..proposals import ProposalError, ProposalStore
from ..review import ReviewRecord
from .mesh import mesh_bytes
from .serialize import build_payload, design_info, jsonable

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
        # iteration 2: intent file, review record, proposals (docs/gui.md §7)
        self.store = ProposalStore(self.path)
        self.files = self.store.files
        self.intent_doc: intent_store.IntentDoc | None = None
        self.intent_error: list | None = None
        self.review: ReviewRecord | None = None
        self.last_build = None                # (design, Build, mesh_id, notes) for re-serializing
        self.intent_lock = threading.Lock()
        self.evaluating: set = set()
        # iteration 3: the machine-written resolution record (assumed context, print orientation)
        from ..resolution import ResolutionRecord, path_for as record_path_for
        self.record_path = record_path_for(self.path)
        self.record = ResolutionRecord.load(self.record_path)
        self.key_build = None                 # the defaults build (orientation key / inference)
        self.force_orientation = False

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

    @property
    def intent_path(self) -> str:
        d = self.design
        return (d.intent_file if d is not None and d.intent_file else None) or intent_store.path_for(self.path)

    def design_paths(self) -> set:
        from ..interpret import lock_path_for
        out = {self.path, self.lock_arg or lock_path_for(self.path)}
        p = self.prefs_path()
        out.add(p or self.default_prefs_path())
        return {os.path.realpath(x) for x in out if x}     # realpath: watchfiles reports resolved paths

    def intent_paths(self) -> set:
        return {os.path.realpath(self.intent_path), os.path.realpath(self.files.review),
                os.path.realpath(self.record_path)}

    def proposal_dirs(self) -> set:
        return {os.path.realpath(self.files.proposals_dir), os.path.realpath(self.files.requests_dir)}

    def watched(self) -> set:
        return self.design_paths() | self.intent_paths()

    # ------------------------------------------------------------------ intent file and review
    def load_intent(self) -> None:
        """(Re)read the intent file and the review record.  An invalid file keeps the last good
        document and reports the errors; no file means the iteration-1 tag-derived tree."""
        path = self.intent_path
        if not os.path.exists(path):
            self.intent_doc, self.intent_error = None, None
        else:
            try:
                self.intent_doc, self.intent_error = intent_store.load(path), None
            except intent_store.IntentSchemaError as e:
                self.intent_error = e.errors
        # no automatic baseline (NOTES #48 change): without a review record nothing is reviewed,
        # and the GUI asks once (POST /api/review all | one_by_one)
        self.review = ReviewRecord.load(self.files.review)
        from ..resolution import ResolutionRecord
        self.record = ResolutionRecord.load(self.record_path)

    def intent_arg(self) -> dict | None:
        if self.intent_doc is None:
            return None
        plain = self.intent_doc.to_plain()
        return {"plain": plain, "stale": self.review.stale(plain) if self.review else {}, "review": self.review}

    def assessment(self, design, b):
        """Context, orientation, intent checks, tiered status (assess.py).  Writes the resolution
        record (machine-written, never the intent file) when its content changed."""
        from ..assess import assess
        ia = self.intent_arg()
        plain = ia["plain"] if ia else None
        reviewed = (set(self.review.reviewed) - set(ia["stale"])) if (ia and self.review) else set()
        a = assess(design, b, plain, self.record, reviewed, key_build=self.key_build or b,
                   force_orientation=self.force_orientation)
        self.force_orientation = False
        if a.record_changed:
            rp = os.path.realpath(self.record_path)
            self.writing.add(rp)
            try:
                self.record.save()
            except OSError:
                pass
            finally:
                self.own_writes[rp] = _sha(rp)
                self.writing.discard(rp)
        return a

    def payload(self, design, b, mesh_id, notes) -> dict:
        return build_payload(design, b, mesh_id, notes, intent=self.intent_arg(), assessment=self.assessment(design, b))

    def intent_info(self) -> dict:
        path = self.intent_path
        info = {"file": path, "exists": os.path.exists(path), "hash": file_sha256(path),
                "design_hash": file_sha256(self.path),
                "loaded_hash": self.intent_doc.hash if self.intent_doc else None,
                "error": self.intent_error, "doc": None, "stale": {}, "review_file": self.files.review,
                "review_exists": bool(self.review and self.review.exists)}
        if self.intent_doc is not None:
            plain = self.intent_doc.to_plain()
            info["doc"] = plain
            info["stale"] = jsonable(self.review.stale(plain)) if self.review else {}
        return info

    def dsl_ids(self) -> set:
        out = set()
        for f in self.design.features if self.design else ():
            out |= {t.node for t in f.tags}
            for ts in getattr(f, "instance_tags", None) or ():
                out |= {t if isinstance(t, str) else t.node for t in (ts if isinstance(ts, (list, tuple)) else [ts])}
        return out

    def patch_intent(self, base_hash: str | None, ops: list) -> dict:
        """Apply edit ops to the intent file (all or nothing) against `base_hash`."""
        path = self.intent_path
        with self.intent_lock:
            if not os.path.exists(path):
                raise intent_store.IntentOpError("this design has no intent file "
                                                 f"({os.path.basename(path)}); create one to edit intent")
            cur = file_sha256(path)
            if base_hash != cur:
                raise intent_store.IntentConflict(path, base_hash, cur)
            doc = intent_store.load(path)
            before = doc.to_plain()
            file_ops = [o for o in ops if o.get("op") != "mark_reviewed"]
            results = intent_store.apply_ops(doc, file_ops, taken=self.dsl_ids()) if file_ops else []
            review = ReviewRecord.load(self.files.review)
            write_review = False
            mine = {os.path.realpath(path), os.path.realpath(self.files.review)}
            self.writing |= mine
            try:
                if file_ops:
                    intent_store.save(doc, path, base_hash=base_hash)
                plain = doc.to_plain()
                for o in ops:
                    if o.get("op") == "mark_reviewed":
                        ids = o.get("ids") or ([o["id"]] if o.get("id") else [])
                        if o.get("all"):
                            ids = [i for i in doc.node_ids()]
                        results.append({"reviewed": review.mark(plain, ids)})
                        write_review = True
                if write_review:
                    review.save()
            finally:
                for p in mine:
                    self.own_writes[p] = _sha(p)
                self.writing -= mine
            self.load_intent()
        return {"results": results}

    def rename_id(self, base_hash: str | None, design_hash: str | None, old: str, new: str,
                  rename_features: bool = False) -> dict:
        """The explicit 'rename id' action (gui.md §7.4): the intent file, the DSL's intent-id
        literals (codemod.rename_intent_id, LibCST), the review record and the saved preferences
        (#49), written together.  `rename_features` also renames matching feature ids
        (`A.3.cable` -> `A.C.cable`); off by default."""
        from ..codemod import rename_intent_id
        from ..fileio import atomic_write, read_text
        from ..interpret import Preferences
        path = self.intent_path
        with self.intent_lock, self.build_lock:
            cur, dcur = file_sha256(path), file_sha256(self.path)
            if base_hash != cur or design_hash != dcur:
                raise intent_store.IntentConflict(path if base_hash != cur else self.path,
                                                  base_hash if base_hash != cur else design_hash,
                                                  cur if base_hash != cur else dcur)
            doc = intent_store.load(path)
            review = ReviewRecord.load(self.files.review)
            was_stale = set(review.stale(doc.to_plain()))
            intent_store.rename_id_in_doc(doc, old, new)
            intent_text = intent_store.dumps(doc)
            py_text, n = rename_intent_id(read_text(self.path), old, new, rename_features=rename_features)
            # saved preferences follow the intent node (#49): `<word>.<slot>@<design>:<old...>`
            prefs_file = self.prefs_path() or self.default_prefs_path()
            prefs = Preferences.load(prefs_file)
            migrated = prefs.rename_node(self.design.name if self.design else "", old, new)
            # a rename is not an intent change: nodes that were reviewed stay reviewed under the new id
            ren = lambda k: new + k[len(old):] if k == old or k.startswith(old + ".") else k   # noqa: E731
            for k in [k for k in review.reviewed if ren(k) != k]:
                review.reviewed.pop(k)
            renamed = [k for k in doc.node_ids() if k == new or k.startswith(new + ".")]
            review.mark(doc.to_plain(), [k for k in renamed if old + k[len(new):] not in was_stale])
            mine = {os.path.realpath(p) for p in (path, self.path, self.files.review, prefs_file)}
            self.writing |= mine
            try:
                atomic_write(path, intent_text)
                atomic_write(self.path, py_text)
                review.save()
                if migrated:
                    prefs.save()
            finally:
                for p in mine:
                    self.own_writes[p] = _sha(p)
                self.writing -= mine
        self.load()
        return {"renamed_literals": n, "old": old, "new": new, "migrated_preferences": migrated,
                "renamed_features": rename_features}

    # ------------------------------------------------------------------ iteration 3 actions
    def _write_intent_ops(self, base_hash: str | None, ops: list) -> dict:
        """Apply intent ops for an accept action (the designer's click), with the base-hash check."""
        return self.patch_intent(base_hash if base_hash is not None else file_sha256(self.intent_path), ops)

    def context_action(self, base_hash: str | None, action: str, values: dict | None) -> dict:
        """accept: write the assumed context into the intent file; set: write changed values
        (the picker).  Only ever on the designer's request (3E.6)."""
        from ..resolution import CONTEXT_KEYS, accept_context_ops, context_items
        if self.intent_doc is None:
            raise intent_store.IntentOpError("this design has no intent file to write the context into")
        items = context_items(self.intent_doc.to_plain().get("context"))
        vals = {k: v for k, v in (values or {}).items() if k in CONTEXT_KEYS}
        if action not in ("accept", "set"):
            raise intent_store.IntentOpError(f"unknown context action {action!r}")
        return self._write_intent_ops(base_hash, accept_context_ops(items, vals))

    def orientation_action(self, base_hash: str | None, action: str) -> dict:
        from ..resolution import accept_orientation_ops, accepted_orientation
        if action == "infer":
            if self.intent_doc is not None and accepted_orientation(self.intent_doc.to_plain()):
                return {"note": "an accepted orientation is in the intent file; inference never replaces it"}
            self.force_orientation = True
            return {"note": "re-inferred"}
        if action != "accept":
            raise intent_store.IntentOpError(f"unknown orientation action {action!r}")
        if self.intent_doc is None:
            raise intent_store.IntentOpError("this design has no intent file to write the orientation into")
        if accepted_orientation(self.intent_doc.to_plain()):
            raise intent_store.IntentOpError("an orientation is already accepted in the intent file")
        o = (self.record.data.get("orientation") if self.record else None)
        if not o:
            raise intent_store.IntentOpError("no inferred orientation to accept yet")
        root = self.intent_doc.nodes()[0][0]
        return self._write_intent_ops(base_hash, accept_orientation_ops(o, root))

    def review_action(self, base_hash: str | None, action: str, key: str = "", value=None) -> dict:
        """First-open prompt (#48): `all` marks every node reviewed; `one_by_one` writes an empty
        record so the prompt does not return.  `accept_item`: a model-made item that does not live
        in the intent file (an interpretation reading `slot:<id>`)."""
        if action == "all":
            return self.patch_intent(base_hash if base_hash is not None else file_sha256(self.intent_path),
                                     [{"op": "mark_reviewed", "all": True}])
        rp = os.path.realpath(self.files.review)
        if action == "one_by_one":
            rec = ReviewRecord.load(self.files.review)
        elif action == "accept_item":
            if not key.startswith("slot:"):
                raise intent_store.IntentOpError("accept_item takes slot:<id>; assumptions, context and the "
                                                 "orientation are accepted into the intent file")
            rec = ReviewRecord.load(self.files.review)
            rec.accept_item(key, value)
        else:
            raise intent_store.IntentOpError(f"unknown review action {action!r}")
        self.writing.add(rp)
        try:
            rec.save()
        finally:
            self.own_writes[rp] = _sha(rp)
            self.writing.discard(rp)
        self.load_intent()
        return {"ok": True}

    def refresh_payload(self) -> dict | None:
        """Re-serialize the last build with the current intent state (no rebuild)."""
        if self.last_build is None:
            return None
        design, b, mesh_id, notes = self.last_build
        with self.build_lock:
            payload = self.payload(design, b, mesh_id, notes)
        return self._decorate(payload)

    def _decorate(self, payload: dict) -> dict:
        payload["file"] = self.path
        payload["generation"] = self.generation
        payload["resolving"] = bool(self.needs_resolve or self.resolving)
        payload["last_good_mesh_id"] = self.last_good_mesh
        payload["intent"] = {k: v for k, v in self.intent_info().items() if k != "doc"}
        self.last_payload = payload
        return payload

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
        self.load_intent()
        self.key_build = self._defaults_build(design)

    def _defaults_build(self, design):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                if design.interpretation is None and design.lock is not None:
                    return design.build(on_fail="record", interpretations={}, prefs=design.prefs)
                return design.build(on_fail="record")
            except Exception:   # noqa: BLE001 - only the orientation key depends on it
                return None

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
            if b.ok and mesh_id:
                self.last_good_mesh = mesh_id
            self.last_build = (design, b, mesh_id, notes)
            payload = self.payload(design, b, mesh_id, notes)
            return self._decorate(payload)

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
        kb = self._defaults_build(design)
        if gen == self.generation:
            self.key_build = kb

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
        """Watcher callback: reload (design file) and rebuild, keeping the current parameters;
        re-read the intent file / review record; announce proposal changes."""
        real = {os.path.realpath(p) for p in paths}
        if {os.path.dirname(p) for p in real} & self.proposal_dirs():
            self.publish({"type": "proposals-changed"})
        paths = real & self.watched()
        paths = {p for p in paths if p not in self.writing and not self.is_own_write(p)}
        if not paths:
            return
        if not (paths & self.design_paths()):
            # only the intent file and/or the review record changed: no rebuild needed
            await asyncio.to_thread(self.load_intent)
            payload = await asyncio.to_thread(self.refresh_payload)
            self.publish({"type": "intent-changed", "intent": self.intent_info(),
                          "changed": sorted(os.path.relpath(p) for p in paths)})
            if payload is not None:
                self.publish({"type": "rebuilt", "reason": "intent-changed", "build": payload})
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
    session.files.ensure_dirs()
    dirs = sorted({os.path.dirname(p) for p in session.watched()} | session.proposal_dirs())
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

    async def body_json(request: Request) -> dict:
        raw = await request.body()
        if not raw:
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise json.JSONDecodeError("body must be an object", "", 0)
        return data

    def err(msg, status=400, **extra):
        return JSONResponse({"error": msg, **extra}, status_code=status)

    async def api_intent(request: Request):
        if request.method == "GET":
            await asyncio.to_thread(session.load_intent) if session.intent_doc is None else None
            return JSONResponse(session.intent_info())
        try:
            body = await body_json(request)
        except json.JSONDecodeError:
            return err("body must be a JSON object")
        ops = body.get("ops") or []
        if not isinstance(ops, list) or not all(isinstance(o, dict) for o in ops):
            return err("ops must be a list of objects")
        try:
            res = await asyncio.to_thread(session.patch_intent, body.get("base_hash"), ops)
        except intent_store.IntentConflict as e:
            await asyncio.to_thread(session.load_intent)
            return err(str(e), 409, conflict=True, current=session.intent_info())
        except intent_store.IntentSchemaError as e:
            return err(str(e), 400, errors=e.errors)
        except intent_store.IntentOpError as e:
            return err(str(e), 400)
        payload = await asyncio.to_thread(session.refresh_payload)
        info = session.intent_info()
        session.publish({"type": "intent-changed", "intent": info, "changed": [os.path.relpath(session.intent_path)]})
        if payload is not None:
            session.publish({"type": "rebuilt", "reason": "intent-edit", "build": payload})
        return JSONResponse({"intent": info, "build": payload, **res})

    async def api_rename(request: Request):
        try:
            body = await body_json(request)
        except json.JSONDecodeError:
            return err("body must be a JSON object")
        old, new = str(body.get("old") or ""), str(body.get("new") or "").strip()
        try:
            res = await asyncio.to_thread(session.rename_id, body.get("base_hash"), body.get("design_hash"), old, new,
                                          bool(body.get("rename_features")))
        except intent_store.IntentConflict as e:
            return err(str(e), 409, conflict=True, current=session.intent_info())
        except (intent_store.IntentOpError, intent_store.IntentSchemaError) as e:
            return err(str(e))
        payload = await asyncio.to_thread(session.build)
        session.publish({"type": "design-changed", "design": design_info(session.design, session.path), "changed": []})
        session.publish({"type": "rebuilt", "reason": "rename-id", "build": payload})
        session.publish({"type": "intent-changed", "intent": session.intent_info(), "changed": []})
        session.resolve_in_background()
        return JSONResponse({**res, "intent": session.intent_info(), "build": payload})

    def strip(p: dict) -> dict:
        p = dict(p)
        if p.get("evaluation"):
            p["evaluation"] = {k: v for k, v in p["evaluation"].items() if k != "lock"}
        return p

    def evaluate_bg(pid: str) -> None:
        if pid in session.evaluating:
            return
        session.evaluating.add(pid)

        def run():
            try:
                session.store.evaluate(pid, view_params=dict(session.params))
            finally:
                session.evaluating.discard(pid)
                session.publish({"type": "proposals-changed", "id": pid})

        threading.Thread(target=run, name=f"dipm-eval-{pid}", daemon=True).start()

    async def api_proposals(request: Request):
        if request.method == "GET":
            ps = await asyncio.to_thread(session.store.list)
            rs = await asyncio.to_thread(session.store.requests)
            return JSONResponse({"proposals": [strip(p) for p in ps], "requests": rs,
                                 "waiting": sum(1 for r in rs if r.get("status") == "open"),
                                 "prompt": session.store.claude_prompt()})
        try:
            body = await body_json(request)
            p = await asyncio.to_thread(session.store.create, body.get("summary", ""), body.get("rationale", ""),
                                        body.get("files") or {}, body.get("base_hashes") or {},
                                        body.get("addresses_nodes") or [], body.get("revises"), "api")
        except json.JSONDecodeError:
            return err("body must be a JSON object")
        except ProposalError as e:
            return err(str(e))
        if p["status"] == "pending":
            evaluate_bg(p["id"])
        session.publish({"type": "proposals-changed", "id": p["id"]})
        return JSONResponse(strip(p), status_code=201)

    async def api_proposal(request: Request):
        try:
            p = await asyncio.to_thread(lambda: session.store.refresh(session.store.get(request.path_params["id"])))
        except ProposalError as e:
            return err(str(e), 404)
        return JSONResponse(strip(p))

    async def api_proposal_mesh(request: Request):
        try:
            path = session.store.mesh_path(request.path_params["id"], request.path_params["which"])
        except ProposalError as e:
            return err(str(e), 404)
        if not os.path.exists(path):
            return err("no mesh for this proposal (not evaluated, or no geometry)", 404)
        with open(path, "rb") as fh:
            return Response(fh.read(), media_type="application/octet-stream", headers={"Cache-Control": "no-cache"})

    def accept_and_reload(pid: str, comment: str, override_reason: str | None = None) -> tuple:
        mine = session.design_paths() | session.intent_paths()
        session.writing |= mine
        try:
            p = session.store.accept(pid, comment, override_reason)
        finally:
            for x in mine:
                session.own_writes[x] = _sha(x)
            session.writing -= mine
        session.load()
        payload = session.build()
        return p, payload

    async def api_proposal_action(request: Request):
        pid, action = request.path_params["id"], request.path_params["action"]
        try:
            body = await body_json(request)
        except json.JSONDecodeError:
            return err("body must be a JSON object")
        comment = str(body.get("comment") or "")
        try:
            if action == "accept":
                p, payload = await asyncio.to_thread(accept_and_reload, pid, comment, body.get("override_reason"))
                session.publish({"type": "design-changed", "design": design_info(session.design, session.path),
                                 "changed": list(p.get("accepted", {}).get("written", []))})
                session.publish({"type": "rebuilt", "reason": "proposal-accepted", "build": payload})
                session.publish({"type": "intent-changed", "intent": session.intent_info(), "changed": []})
                session.publish({"type": "proposals-changed", "id": pid})
                session.resolve_in_background()
                return JSONResponse({"proposal": strip(p), "build": payload})
            if action == "reject":
                p = await asyncio.to_thread(session.store.reject, pid, comment)
                session.publish({"type": "proposals-changed", "id": pid})
                return JSONResponse({"proposal": strip(p)})
            if action == "evaluate":
                evaluate_bg(pid)
                return JSONResponse({"ok": True})
            if action == "view":
                params = body.get("params") or session.params
                p = await asyncio.to_thread(session.store.view, pid, params)
                return JSONResponse(strip(p))
        except ProposalError as e:
            p = None
            try:
                p = strip(session.store.get(pid))
            except ProposalError:
                pass
            return err(str(e), 409, proposal=p)
        return err(f"unknown action {action}", 404)

    async def api_requests(request: Request):
        if request.method == "GET":
            rs = await asyncio.to_thread(session.store.requests)
            return JSONResponse({"requests": rs, "waiting": sum(1 for r in rs if r.get("status") == "open"),
                                 "prompt": session.store.claude_prompt()})
        try:
            body = await body_json(request)
        except json.JSONDecodeError:
            return err("body must be a JSON object")
        node = str(body.get("node") or "")
        if session.intent_doc is None or node not in session.intent_doc.node_ids():
            return err(f"no intent node {node!r}")
        plain = session.intent_doc.to_plain()
        change = (session.review.stale(plain) if session.review else {}).get(node)
        r = await asyncio.to_thread(session.store.create_request, node, str(body.get("note") or ""), jsonable(change))
        session.publish({"type": "proposals-changed"})
        return JSONResponse(r, status_code=201)

    async def api_display(request: Request):
        from .. import display
        info = await asyncio.to_thread(display.displays)
        q = request.query_params
        if q.get("width"):
            scr = {"width": q.get("width"), "height": q.get("height"), "dpr": q.get("dpr"),
                   "label": q.get("label") or "", "left": q.get("left"), "top": q.get("top"),
                   "internal": (q.get("internal") == "true") if q.get("internal") in ("true", "false") else None}
            info["match"] = display.match(info, scr)
        return JSONResponse(info)

    async def intent_action(request: Request, fn):
        try:
            body = await body_json(request)
        except json.JSONDecodeError:
            return err("body must be a JSON object")
        try:
            res = await asyncio.to_thread(fn, body)
        except intent_store.IntentConflict as e:
            await asyncio.to_thread(session.load_intent)
            return err(str(e), 409, conflict=True, current=session.intent_info())
        except (intent_store.IntentOpError, intent_store.IntentSchemaError) as e:
            return err(str(e))
        payload = await asyncio.to_thread(session.refresh_payload)
        info = session.intent_info()
        session.publish({"type": "intent-changed", "intent": info, "changed": []})
        if payload is not None:
            session.publish({"type": "rebuilt", "reason": "review", "build": payload})
        return JSONResponse({"intent": info, "build": payload, **(res if isinstance(res, dict) else {})})

    async def api_context(request: Request):
        return await intent_action(request, lambda b: session.context_action(b.get("base_hash"), b.get("action", "accept"),
                                                                             b.get("values")))

    async def api_orientation(request: Request):
        return await intent_action(request, lambda b: session.orientation_action(b.get("base_hash"),
                                                                                 b.get("action", "accept")))

    async def api_review(request: Request):
        return await intent_action(request, lambda b: session.review_action(b.get("base_hash"), b.get("action", ""),
                                                                            str(b.get("key") or ""), b.get("value")))

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
              Route("/api/intent", api_intent, methods=["GET", "PATCH"]),
              Route("/api/intent/rename", api_rename, methods=["POST"]),
              Route("/api/proposals", api_proposals, methods=["GET", "POST"]),
              Route("/api/proposals/{id}", api_proposal),
              Route("/api/proposals/{id}/mesh/{which}", api_proposal_mesh),
              Route("/api/proposals/{id}/{action}", api_proposal_action, methods=["POST"]),
              Route("/api/requests", api_requests, methods=["GET", "POST"]),
              Route("/api/display", api_display),
              Route("/api/context", api_context, methods=["POST"]),
              Route("/api/orientation", api_orientation, methods=["POST"]),
              Route("/api/review", api_review, methods=["POST"]),
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

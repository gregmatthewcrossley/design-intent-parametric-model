"""Automatic pickup (docs/purpose-loop.md §7, iteration 4b): dipm starts Claude Code itself.

MCP is pull-based: Claude Code calls dipm, dipm cannot wake Claude.  So for a queued request the
GUI server launches **headless Claude Code** (`claude -p`) with a generated MCP config that runs
this design's `dipm mcp` server, and only that server's tools allowed:

    claude -p <prompt> --output-format stream-json --verbose
           --mcp-config <.dipm/runs/<run>.mcp.json> --strict-mcp-config
           --tools "" --allowedTools mcp__dipm__get_design,… --disallowedTools Bash,Edit,…
           --permission-mode dontAsk [--model <settings.model>]

run from the repository root.  `--tools ""` removes every built-in tool (no shell, no file
reading or editing, no web); the allow list names exactly the dipm MCP tools; `dontAsk` denies
anything else instead of prompting.  Even so Claude can only *propose*: `dipm mcp` never writes
design files.  The binary is `claude` on PATH, or `DIPM_CLAUDE_BIN`.

Runs: one at a time per design (more requests queue behind it), cancellable, stopped by a
timeout (default 20 min; settings or `DIPM_CLAUDE_TIMEOUT` in seconds).  Each run keeps

    .dipm/runs/<run>.json        state: requests, status, plain-language steps, usage, proposals
    .dipm/runs/<run>.jsonl       the stream-json transcript, verbatim
    .dipm/runs/<run>.stderr.log  Claude Code's stderr
    .dipm/runs/<run>.mcp.json    the generated MCP config
    .dipm/runs/<design>.settings.json   auto-run (default on), model override, timeout

A request moves open → running → proposed (linked to its proposals when they are submitted) or
failed (with the reason).  `DIPM_CLAUDE_AUTORUN=0` makes auto-run default to off (the tests use
it so nothing ever starts the real `claude`).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

from .fileio import atomic_write
from .mcp_server import INSTRUCTIONS, TOOL_NAMES
from .proposals import OPEN_STATUSES, ProposalError, ProposalStore

ENV_BIN = "DIPM_CLAUDE_BIN"
ENV_TIMEOUT = "DIPM_CLAUDE_TIMEOUT"
ENV_AUTORUN = "DIPM_CLAUDE_AUTORUN"
SERVER = "dipm"
DEFAULT_TIMEOUT_S = 20 * 60
KILL_GRACE_S = 3.0
MAX_STEPS = 400
#: built-in tools denied by name as well (belt and braces: `--tools ""` already removes them)
DENIED_TOOLS = ("Bash", "Edit", "MultiEdit", "Write", "Read", "NotebookEdit", "Glob", "Grep", "LS", "WebFetch",
                "WebSearch", "Task", "Agent", "TodoWrite", "KillShell", "BashOutput")
#: strings in a result or stderr that mean Claude Code is not logged in
AUTH_PATTERNS = re.compile(r"not logged in|please run /login|/login|invalid api key|authentication[_ ]error|"
                           r"oauth token (has )?expired|credit balance is too low", re.I)
#: environment variables of an enclosing Claude Code session that a child must not inherit
NESTED_ENV = ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")


class RunError(Exception):
    """A run cannot start: `code` is busy | unavailable | nothing | bad."""

    def __init__(self, message: str, code: str = "bad"):
        super().__init__(message)
        self.code = code


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- the command line

def allowed_tools() -> list:
    return [f"mcp__{SERVER}__{n}" for n in TOOL_NAMES]


def find_claude() -> dict:
    """Where the `claude` binary is: {ok, bin, source, reason}.  Never runs it."""
    env = os.environ.get(ENV_BIN)
    if env:
        path = env if os.path.sep in env else shutil.which(env)
        ok = bool(path) and os.path.isfile(path) and os.access(path, os.X_OK)
        return {"ok": ok, "bin": path or env, "source": ENV_BIN,
                "reason": "" if ok else f"{ENV_BIN}={env} is not an executable file"}
    path = shutil.which("claude")
    if path:
        return {"ok": True, "bin": path, "source": "PATH", "reason": ""}
    return {"ok": False, "bin": "claude", "source": "PATH",
            "reason": "Claude Code (`claude`) is not on PATH: install it, or set DIPM_CLAUDE_BIN"}


def repo_root(design_path: str) -> str:
    """The repository holding the design (the nearest parent with .git), else its directory."""
    d = os.path.dirname(os.path.abspath(design_path))
    cur = d
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        up = os.path.dirname(cur)
        if up == cur:
            return d
        cur = up


def mcp_config(design_path: str, run_id: str, request_ids: list) -> dict:
    """The generated MCP config: this design's `dipm mcp` server, run by this Python."""
    return {"mcpServers": {SERVER: {
        "type": "stdio", "command": sys.executable,
        "args": ["-m", "dipm", "mcp", os.path.abspath(design_path)],
        "env": {"DIPM_RUN": run_id, "DIPM_REQUESTS": ",".join(request_ids), "PYTHONWARNINGS": "ignore"}}}}


def command(bin_path: str, prompt: str, config_path: str, model: str | None = None) -> list:
    """argv for one run.  The prompt comes right after -p, and every variadic option
    (--mcp-config, --tools, --allowedTools, --disallowedTools) is followed by another option,
    so none of them can swallow the prompt."""
    cmd = [bin_path, "-p", prompt,
           "--output-format", "stream-json", "--verbose",
           "--mcp-config", config_path, "--strict-mcp-config",
           "--tools", "",
           "--allowedTools", ",".join(allowed_tools()),
           "--disallowedTools", ",".join(DENIED_TOOLS),
           "--permission-mode", "dontAsk"]
    if model:
        cmd += ["--model", model]
    return cmd


def child_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in NESTED_ENV}
    env.setdefault("PYTHONWARNINGS", "ignore")
    return env


def _short(text, n: int = 160) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def build_prompt(store: ProposalStore, reqs: list) -> str:
    """The prompt for one run: the requests (node, note, change) plus the loop instructions."""
    F = store.files
    lines = [f"dipm started this headless Claude Code session to handle design requests for "
             f"{F.stem} ({F.design}).",
             "You can use only the dipm MCP tools (mcp__dipm__*): you cannot run commands, read or edit files, "
             "or browse.  You never write files: you propose, dipm evaluates, the designer decides in the dipm GUI.",
             "", f"Requests ({', '.join(r['id'] for r in reqs)}):"]
    for r in reqs:
        ch = r.get("change") or {}
        lines.append(f"- {r['id']} · node {r.get('node')} · {r.get('kind') or 'queue'} · queued {r.get('created', '')}")
        was = ((ch.get("reviewed") or {}).get("statement"))
        now = ((ch.get("current") or {}).get("statement"))
        if ch.get("new"):
            lines.append(f"  New purpose: \"{now}\" (no solution has been reviewed for it yet).")
        elif was is not None and now is not None and was != now:
            lines.append(f"  The purpose changed: was \"{was}\", now \"{now}\".")
        if ch.get("changed"):
            lines.append(f"  Changed since its solution was reviewed: {', '.join(ch['changed'])}.")
        if r.get("note"):
            lines.append(f"  Designer's note: \"{r['note']}\"")
        if r.get("status_detail"):
            lines.append(f"  History: {r['status_detail']}")
    lines += ["", INSTRUCTIONS.strip(), "",
              "Proposals you submit are linked to these requests automatically.  Read the designer's feedback on "
              "earlier proposals with get_proposal_feedback.  If a request needs no change (the solution still "
              "fits), say so and submit nothing.  Finish with a short plain-language summary of what you proposed "
              "and what you could not check."]
    return "\n".join(lines)


# ---------------------------------------------------------------- reading the stream

TOOL_STEPS = {
    "get_requests": "reading the requests", "get_stale_nodes": "checking which purposes are stale",
    "get_impact": "reading the impact report", "get_source": "reading the design's source",
    "get_design": "reading the design", "get_intent": "reading the purpose tree",
    "get_check_vocabulary": "reading the check vocabulary", "get_components": "looking up component envelopes",
    "build": "building the current design", "list_proposals": "listing proposals",
    "get_proposal_feedback": "reading the designer's feedback", "propose_purposes": "proposing revised purposes",
    "propose_patch": "submitting a patch",
}


def _tool_text(content) -> str:
    """A tool_result's content as text (a string, or a list of {type: text, text} blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _json_or_none(text: str):
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else None
    except (TypeError, ValueError):
        return None


class StreamParser:
    """Turns Claude Code's stream-json events into plain-language steps.  Defensive: unknown
    or malformed events are ignored; nothing here can fail a run."""

    def __init__(self, attempts: dict | None = None):
        self.steps: list = []
        self.calls: dict = {}                      # tool_use id -> (short name, input)
        self.attempts = dict(attempts or {})       # alternative label -> attempts so far
        self.result: dict | None = None
        self.session_id = None
        self.model = None
        self.mcp_status = None
        self.auth_error = False
        self.proposals: list = []
        self.denied: list = []
        self._new: list = []

    def _step(self, kind: str, text: str, **extra) -> dict:
        s = {"at": _now(), "kind": kind, "text": _short(text, 200), **extra}
        self.steps.append(s)
        self._new.append(s)
        if len(self.steps) > MAX_STEPS:
            del self.steps[: len(self.steps) - MAX_STEPS]
        return s

    def feed_line(self, line: str) -> list:
        line = line.strip()
        if not line:
            return []
        try:
            ev = json.loads(line)
        except ValueError:
            return []
        return self.feed(ev) if isinstance(ev, dict) else []

    def feed(self, ev: dict) -> list:
        """One event -> the steps it added."""
        self._new = []
        try:
            t = ev.get("type")
            if t == "system" and ev.get("subtype") == "init":
                self._init(ev)
            elif t == "assistant":
                for b in self._blocks(ev):
                    if b.get("type") == "tool_use":
                        self._call(b)
                    elif b.get("type") == "text" and str(b.get("text") or "").strip():
                        self._step("say", "Claude: " + str(b["text"]))
            elif t == "user":
                for b in self._blocks(ev):
                    if b.get("type") == "tool_result":
                        self._result(b)
            elif t == "result":
                self._final(ev)
        except Exception:   # noqa: BLE001 - a malformed event never breaks a run
            pass
        return list(self._new)

    @staticmethod
    def _blocks(ev: dict) -> list:
        msg = ev.get("message") or {}
        content = msg.get("content") if isinstance(msg, dict) else None
        return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []

    def _init(self, ev: dict) -> None:
        self.session_id = ev.get("session_id") or self.session_id
        self.model = ev.get("model") or self.model
        servers = ev.get("mcp_servers") or []
        st = next((s.get("status") for s in servers if isinstance(s, dict) and s.get("name") == SERVER), None)
        self.mcp_status = st
        if st not in (None, "connected"):
            self._step("error", f"the dipm MCP server did not start ({st})")
        else:
            self._step("start", "Claude started" + (f" ({self.model})" if self.model else ""))

    def _call(self, b: dict) -> None:
        name = str(b.get("name") or "")
        inp = b.get("input") if isinstance(b.get("input"), dict) else {}
        prefix = f"mcp__{SERVER}__"
        if not name.startswith(prefix):
            self.denied.append(name)
            self._step("warn", f"tried {name or 'a tool'} (not allowed)", tool=name)
            return
        short = name[len(prefix):]
        self.calls[str(b.get("id"))] = (short, inp)
        if short == "evaluate":
            label = str(inp.get("label") or "").strip()
            if label:
                self.attempts[label] = self.attempts.get(label, 0) + 1
                text = f"evaluating attempt {self.attempts[label]} of '{label}'"
            else:
                text = "evaluating a candidate"
        elif short == "propose_alternatives":
            alts = inp.get("alternatives")
            n = len(alts) if isinstance(alts, list) else 0
            text = f"submitting {n} alternative{'s' if n != 1 else ''}" if n else "submitting alternatives"
        elif short == "why":
            text = f"asking why face {inp.get('face_id', '?')} is there"
        else:
            text = TOOL_STEPS.get(short, f"calling {short}")
        self._step("tool", text, tool=short)

    def _result(self, b: dict) -> None:
        short, inp = self.calls.get(str(b.get("tool_use_id")), (None, {}))
        text = _tool_text(b.get("content"))
        if b.get("is_error"):
            self._step("error", f"{short or 'a tool'} refused: {text.splitlines()[0] if text else 'error'}",
                       tool=short)
            return
        data = _json_or_none(text)
        if data is None or short is None:
            return
        if short == "propose_alternatives":
            ids = [a.get("id") for a in data.get("alternatives") or [] if isinstance(a, dict) and a.get("id")]
            self.proposals += ids
            self._step("proposed", f"submitted {len(ids)} alternative{'s' if len(ids) != 1 else ''}"
                                   + (f" ({', '.join(ids)})" if ids else ""), tool=short, proposals=ids)
        elif short in ("propose_purposes", "propose_patch") and data.get("id"):
            self.proposals.append(data["id"])
            what = "purpose proposal" if short == "propose_purposes" else "patch"
            self._step("proposed", f"submitted {what} {data['id']}", tool=short, proposals=[data["id"]])
        elif short == "evaluate":
            label = str(inp.get("label") or "")
            head = ((data.get("status") or {}).get("headline")) or ("does not load" if data.get("loaded") is False else "")
            if label and data.get("attempt"):
                self.attempts[label] = int(data["attempt"])
            which = f"attempt {data.get('attempt')} of '{label}'" if label and data.get("attempt") else "candidate"
            if head:
                self._step("result", f"{which}: {head}", tool=short)

    def _final(self, ev: dict) -> None:
        self.result = {k: ev.get(k) for k in ("subtype", "is_error", "result", "total_cost_usd", "usage",
                                              "num_turns", "duration_ms", "duration_api_ms", "session_id")
                       if k in ev}
        self.session_id = ev.get("session_id") or self.session_id
        if ev.get("is_error") or str(ev.get("subtype") or "").startswith("error"):
            msg = str(ev.get("result") or ev.get("subtype") or "error")
            if AUTH_PATTERNS.search(msg):
                self.auth_error = True
            self._step("error", f"Claude stopped: {msg}")
        else:
            text = "finished" + (f": {_short(ev.get('result'), 140)}" if ev.get("result") else "")
            last = self.steps[-1] if self.steps else None
            if last and last["kind"] == "say" and ev.get("result") and \
                    " ".join(str(ev["result"]).split()).startswith(last["text"][len("Claude: "):].rstrip("…")):
                self.steps.pop()         # the closing message repeats Claude's last words: show it once
            self._step("done", text)

    def usage_line(self) -> str:
        r = self.result or {}
        return usage_line(r)


def usage_line(r: dict) -> str:
    """'$0.42 · 12,345 in / 2,100 out tokens · 9 turns · 3 min 5 s', from whatever the stream reported."""
    parts = []
    if isinstance(r.get("total_cost_usd"), (int, float)):
        parts.append(f"${r['total_cost_usd']:.2f}")
    u = r.get("usage") if isinstance(r.get("usage"), dict) else {}
    tin = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
              if isinstance(u.get(k), (int, float)))
    tout = u.get("output_tokens")
    if tin or tout:
        parts.append(f"{tin:,} in / {int(tout or 0):,} out tokens")
    if isinstance(r.get("num_turns"), int):
        parts.append(f"{r['num_turns']} turn{'s' if r['num_turns'] != 1 else ''}")
    if isinstance(r.get("duration_ms"), (int, float)):
        s = int(r["duration_ms"] / 1000)
        parts.append(f"{s // 60} min {s % 60} s" if s >= 60 else f"{s} s")
    return " · ".join(parts)


# ---------------------------------------------------------------- runs

def _pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


class Runner:
    """Headless Claude runs for one design (owned by the `dipm serve` session)."""

    def __init__(self, store: ProposalStore, publish=None):
        self.store = store
        self.files = store.files
        self.dir = os.path.join(self.files.dipm_dir, "runs")
        self.publish = publish or (lambda msg: None)
        self._lock = threading.RLock()
        self.current: dict | None = None
        self.proc: subprocess.Popen | None = None
        self._stop_reason: str | None = None
        self.auth_failed = False
        self._recover()

    # ------------------------------------------------------------ files and settings
    def _path(self, rid: str, ext: str = ".json") -> str:
        if not re.fullmatch(r"run\d+", rid or ""):
            raise RunError(f"bad run id {rid!r}")
        return os.path.join(self.dir, rid + ext)

    def _settings_path(self) -> str:
        return os.path.join(self.dir, self.files.stem + ".settings.json")

    def settings(self) -> dict:
        env_auto = os.environ.get(ENV_AUTORUN)
        st = {"auto_run": env_auto not in ("0", "false", "no", "off") if env_auto is not None else True,
              "model": None, "timeout_s": DEFAULT_TIMEOUT_S}
        try:
            with open(self._settings_path(), encoding="utf-8") as fh:
                saved = json.load(fh)
            if isinstance(saved, dict):
                st.update({k: saved[k] for k in ("auto_run", "model", "timeout_s") if k in saved})
        except (OSError, ValueError):
            pass
        env_t = os.environ.get(ENV_TIMEOUT)
        if env_t:
            try:
                st["timeout_s"] = float(env_t)
            except ValueError:
                pass
        return st

    def update_settings(self, **kw) -> dict:
        cur = {}
        try:
            with open(self._settings_path(), encoding="utf-8") as fh:
                cur = json.load(fh) or {}
        except (OSError, ValueError):
            pass
        if "auto_run" in kw and kw["auto_run"] is not None:
            cur["auto_run"] = bool(kw["auto_run"])
        if "model" in kw:
            m = str(kw["model"] or "").strip()
            if m and not re.fullmatch(r"[A-Za-z0-9._\-\[\]:]+", m):
                raise RunError(f"bad model name {m!r}")
            cur["model"] = m or None
        if kw.get("timeout_s") is not None:
            t = float(kw["timeout_s"])
            if not 10 <= t <= 6 * 3600:
                raise RunError("timeout must be between 10 s and 6 h")
            cur["timeout_s"] = t
        os.makedirs(self.dir, exist_ok=True)
        atomic_write(self._settings_path(), json.dumps(cur, indent=2) + "\n")
        self.publish({"type": "claude-run", "status": self.status()})
        return self.settings()

    def _save(self, run: dict) -> None:
        atomic_write(self._path(run["id"]), json.dumps(run, indent=2, ensure_ascii=False) + "\n")

    def _alloc(self) -> str:
        os.makedirs(self.dir, exist_ok=True)
        gi = os.path.join(self.files.dipm_dir, ".gitignore")
        if not os.path.exists(gi):
            atomic_write(gi, "*\n")
        nums = [int(m.group(1)) for f in os.listdir(self.dir) if (m := re.fullmatch(r"run(\d+)\.json", f))]
        n = max(nums, default=0) + 1
        while True:
            rid = f"run{n}"
            try:
                fd = os.open(self._path(rid), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                return rid
            except FileExistsError:
                n += 1

    def runs(self) -> list:
        """This design's runs, newest first."""
        if not os.path.isdir(self.dir):
            return []
        out = []
        for f in os.listdir(self.dir):
            m = re.fullmatch(r"(run\d+)\.json", f)
            if not m:
                continue
            try:
                with open(os.path.join(self.dir, f), encoding="utf-8") as fh:
                    r = json.load(fh)
            except (OSError, ValueError):
                continue
            if r.get("design") == self.files.stem:
                out.append(r)
        return sorted(out, key=lambda r: int(r["id"][3:]), reverse=True)

    def get(self, rid: str) -> dict:
        with self._lock:
            if self.current and self.current["id"] == rid:
                return self.current
        try:
            with open(self._path(rid), encoding="utf-8") as fh:
                r = json.load(fh)
        except (OSError, ValueError):
            raise RunError(f"no run {rid}") from None
        if r.get("design") != self.files.stem:
            raise RunError(f"no run {rid} for {self.files.stem}")
        return r

    def transcript_path(self, rid: str) -> str:
        self.get(rid)
        return self._path(rid, ".jsonl")

    def _recover(self) -> None:
        """A run left `running` by a dipm that stopped: kill what is left of it, mark it failed."""
        for r in self.runs():
            if r.get("status") != "running":
                continue
            pid = r.get("pid")
            if pid and _pid_alive(pid):
                try:
                    os.killpg(int(pid), signal.SIGKILL)
                except (OSError, ValueError):
                    pass
            r.update(status="failed", ended=_now(), reason="interrupted: dipm serve stopped during the run")
            self._save(r)
            self._finish_requests(r, r["reason"], revert=False)

    # ------------------------------------------------------------ status
    def summary(self, run: dict | None) -> dict | None:
        if run is None:
            return None
        return {k: run.get(k) for k in ("id", "design", "requests", "status", "trigger", "started", "ended",
                                        "reason", "proposals", "usage", "usage_line", "model", "session_id",
                                        "steps", "auth_error", "timeout_s")}

    def status(self) -> dict:
        reqs = self.store.requests()
        with self._lock:
            cur = self.current
        last = cur or next(iter(self.runs()), None)
        avail = find_claude()
        if avail["ok"] and self.auth_failed:
            avail = {**avail, "login": "failed",
                     "reason": "Claude Code is not logged in: run `claude` in a terminal and log in (/login)"}
        return {"available": avail, "settings": self.settings(), "running": cur is not None,
                "run": self.summary(last), "runs": [{k: r.get(k) for k in ("id", "status", "requests", "started",
                                                                            "ended", "reason", "proposals")}
                                                    for r in self.runs()[:8]],
                "waiting": sum(1 for r in reqs if r.get("status") == "open"),
                "runnable": [r["id"] for r in reqs if r.get("status") == "open"],
                "prompt": self.store.claude_prompt()}

    # ------------------------------------------------------------ starting
    def runnable(self, ids=None, include_failed: bool = False) -> list:
        """Requests a run may take: open (and, when asked explicitly, failed) ones.  A request
        already answered by a pending proposal is `proposed`, never runnable."""
        ok = ("open", "failed") if include_failed else ("open",)
        reqs = [r for r in self.store.requests() if r.get("status") in ok]
        if ids:
            want = set(ids)
            reqs = [r for r in reqs if r["id"] in want]
        out = []
        for r in reqs:          # belt and braces: never re-run a request a pending proposal answers
            open_links = []
            for pid in r.get("proposals") or []:
                try:
                    q = self.store.get(pid)
                except ProposalError:
                    continue
                if q.get("status") in OPEN_STATUSES and not (q.get("kind") == "purpose" and q["status"] == "trying"):
                    open_links.append(pid)
            if not open_links:
                out.append(r)
        return out

    def auto(self, trigger: str = "queue") -> tuple:
        """Auto-run (on by default, per design): start a run for the open requests if none is
        running.  Returns (run summary | None, why not)."""
        if not self.settings()["auto_run"]:
            return None, "auto-run is off"
        if self.auth_failed:
            return None, "Claude Code is not logged in"
        try:
            return self.summary(self.start(trigger=trigger)), ""
        except RunError as e:
            return None, str(e)

    def start(self, request_ids=None, trigger: str = "button") -> dict:
        """Start one headless run for the given (default: all open) requests."""
        with self._lock:
            if self.current is not None:
                raise RunError(f"Claude is already working on {', '.join(self.current['requests'])} ({self.current['id']}); "
                               "the request is queued behind it", "busy")
            other = next((r for r in self.runs() if r.get("status") == "running" and _pid_alive(r.get("pid"))), None)
            if other is not None:
                raise RunError(f"another dipm process is running {other['id']} for this design", "busy")
            avail = find_claude()
            if not avail["ok"]:
                raise RunError(avail["reason"], "unavailable")
            explicit = trigger == "button"
            reqs = self.runnable(request_ids, include_failed=explicit)
            if not reqs:
                raise RunError("no open requests to run (a request answered by a pending proposal is not re-run)",
                               "nothing")
            if explicit:
                self.auth_failed = False
            st = self.settings()
            rid = self._alloc()
            ids = [r["id"] for r in reqs]
            cfg_path = self._path(rid, ".mcp.json")
            atomic_write(cfg_path, json.dumps(mcp_config(self.files.design, rid, ids), indent=2) + "\n")
            prompt = build_prompt(self.store, reqs)
            cmd = command(avail["bin"], prompt, cfg_path, st.get("model"))
            cwd = repo_root(self.files.design)
            before = {r["id"]: list(r.get("proposals") or []) for r in reqs}
            run = {"id": rid, "design": self.files.stem, "requests": ids, "status": "running", "trigger": trigger,
                   "started": _now(), "ended": None, "reason": "", "proposals": [], "usage": None, "usage_line": "",
                   "model": st.get("model"), "session_id": None, "steps": [], "auth_error": False,
                   "timeout_s": st["timeout_s"], "cwd": cwd, "bin": avail["bin"],
                   "argv": [a if a != prompt else "<prompt>" for a in cmd], "prompt": prompt,
                   "transcript": os.path.relpath(self._path(rid, ".jsonl"), self.files.dir),
                   "before": before, "pid": None}
            for r in reqs:
                self.store.update_request(r["id"], status="running", status_detail=f"Claude is working on it ({rid})",
                                          runs=list(dict.fromkeys((r.get("runs") or []) + [rid])))
            try:
                proc = subprocess.Popen(cmd, cwd=cwd, env=child_env(), stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=open(self._path(rid, ".stderr.log"), "wb"),
                                        start_new_session=True)
            except OSError as e:
                run.update(status="failed", ended=_now(), reason=f"could not start {avail['bin']}: {e}")
                self._save(run)
                self._finish_requests(run, run["reason"], revert=True)
                raise RunError(run["reason"], "unavailable") from None
            run["pid"] = proc.pid
            self._save(run)
            self.current, self.proc, self._stop_reason = run, proc, None
            threading.Thread(target=self._pump, args=(run, proc, float(st["timeout_s"])), name=f"dipm-{rid}",
                             daemon=True).start()
        self._announce(run)
        self.publish({"type": "proposals-changed"})
        return run

    def cancel(self, rid: str | None = None, reason: str = "cancel") -> dict:
        with self._lock:
            run, proc = self.current, self.proc
            if run is None or (rid and run["id"] != rid):
                raise RunError(f"{rid or 'no run'} is not running", "nothing")
            self._stop_reason = reason
        self._kill(proc)
        return run

    def shutdown(self) -> None:
        """dipm serve is stopping: stop the run (its requests fail as interrupted)."""
        try:
            self.cancel(reason="shutdown")
        except RunError:
            pass

    @staticmethod
    def _kill(proc: subprocess.Popen | None) -> None:
        if proc is None or proc.poll() is not None:
            return
        for sig, wait in ((signal.SIGTERM, KILL_GRACE_S), (signal.SIGKILL, 2.0)):
            try:
                os.killpg(proc.pid, sig)
            except (ProcessLookupError, PermissionError, OSError):
                return
            try:
                proc.wait(wait)
                return
            except subprocess.TimeoutExpired:
                continue

    # ------------------------------------------------------------ the run thread
    def _announce(self, run: dict) -> None:
        self.publish({"type": "claude-run", "status": self.status()})

    def _pump(self, run: dict, proc: subprocess.Popen, timeout_s: float) -> None:
        def on_timeout():
            with self._lock:
                if self.current is run:
                    self._stop_reason = "timeout"
            self._kill(proc)

        timer = threading.Timer(timeout_s, on_timeout)
        timer.daemon = True
        timer.start()
        attempts = {k: len(v) for k, v in (self.store.loop_state().get("attempts") or {}).items()}
        parser = StreamParser(attempts)
        last_pub = 0.0
        try:
            with open(self._path(run["id"], ".jsonl"), "ab") as tx:
                for raw in proc.stdout:
                    tx.write(raw if raw.endswith(b"\n") else raw + b"\n")
                    tx.flush()
                    new = parser.feed_line(raw.decode("utf-8", "replace"))
                    if not new:
                        continue
                    with self._lock:
                        run["steps"] = list(parser.steps)
                        run["session_id"] = parser.session_id
                        run["model"] = parser.model or run.get("model")
                        run["proposals"] = list(dict.fromkeys(run["proposals"] + parser.proposals))
                        self._save(run)
                    now = time.monotonic()
                    if now - last_pub > 0.15 or any(s["kind"] in ("proposed", "done", "error") for s in new):
                        self._announce(run)
                        last_pub = now
                    if any(s["kind"] == "proposed" for s in new):
                        self.publish({"type": "proposals-changed"})
            proc.wait()
        except Exception as e:   # noqa: BLE001
            parser._step("error", f"dipm lost the stream: {type(e).__name__}: {e}")
            self._kill(proc)
        finally:
            timer.cancel()
        self._finalize(run, proc, parser)

    def _finalize(self, run: dict, proc: subprocess.Popen, parser: StreamParser) -> None:
        rc = proc.returncode
        stop = self._stop_reason
        stderr = ""
        try:
            with open(self._path(run["id"], ".stderr.log"), encoding="utf-8", errors="replace") as fh:
                stderr = fh.read()[-4000:]
        except OSError:
            pass
        auth = parser.auth_error or bool(AUTH_PATTERNS.search(stderr) and rc not in (0, None) and parser.result is None)
        res = parser.result or {}
        if stop == "cancel":
            status, reason = "cancelled", "cancelled by the designer"
        elif stop == "timeout":
            status, reason = "timeout", f"stopped after the {run['timeout_s'] / 60:g} min timeout"
        elif stop == "shutdown":
            status, reason = "failed", "interrupted: dipm serve stopped during the run"
        elif auth:
            status, reason = "failed", "Claude Code is not logged in: run `claude` in a terminal and log in (/login)"
        elif rc == 0 and res and not res.get("is_error"):
            status, reason = "done", ""
        else:
            msg = res.get("result") or res.get("subtype") or (stderr.strip().splitlines() or [""])[-1]
            status, reason = "failed", f"Claude Code exited with {rc}" + (f": {_short(msg, 200)}" if msg else "")
        with self._lock:
            run["steps"] = list(parser.steps)
            if stop in ("cancel", "timeout"):
                run["steps"].append({"at": _now(), "kind": "error", "text": reason})
            run.update(status=status, ended=_now(), reason=reason, exit_code=rc, auth_error=auth,
                       usage=res.get("usage"), usage_line=usage_line(res), session_id=parser.session_id,
                       denied_tools=parser.denied)
            self.auth_failed = auth
        linked = self._finish_requests(run, reason or "Claude finished without submitting a proposal", revert=auth)
        with self._lock:
            run["proposals"] = list(dict.fromkeys(run["proposals"] + linked))
            self._save(run)
            self.current, self.proc = None, None
        self._announce(run)
        self.publish({"type": "proposals-changed"})
        # requests queued while this run was going start the next one (never the ones it just had)
        if status != "cancelled" and stop != "shutdown" and not auth:
            pending = [r["id"] for r in self.runnable() if r["id"] not in run["requests"]]
            if pending and self.settings()["auto_run"]:
                try:
                    self.start(pending, trigger="queue")
                except RunError:
                    pass

    def _finish_requests(self, run: dict, reason: str, revert: bool) -> list:
        """open → running → proposed (it has new proposals) | failed (reason); `revert` (Claude
        never started: not logged in) puts requests back to open."""
        linked = []
        before = run.get("before") or {}
        for rid in run.get("requests") or []:
            try:
                r = self.store.request(rid)
            except ProposalError:
                continue
            if r.get("status") != "running":
                continue
            new = [p for p in (r.get("proposals") or []) if p not in (before.get(rid) or [])]
            if new:
                linked += new
                self.store.update_request(rid, status="proposed",
                                          status_detail=f"answered by pending proposal{'s' if len(new) > 1 else ''} "
                                                        f"{', '.join(new)} ({run['id']})")
            elif revert:
                self.store.update_request(rid, status="open", status_detail=f"{run['id']} could not run: {reason}")
            else:
                self.store.update_request(rid, status="failed", status_detail=f"{run['id']}: {reason}")
        return linked

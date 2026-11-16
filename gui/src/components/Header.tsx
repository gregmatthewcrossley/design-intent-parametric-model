// Header strip (docs/gui.md §3, §8.3 items 1, 4, 8): design name, the honest tiered status (no bare
// PASS), the assumed-context chip, the View menu, requests waiting for Claude and the headless
// Claude run working on them (iteration 4b), live/theme.

import { useEffect, useRef, useState } from "preact/hooks";
import { impactOf } from "../loop";
import { build, building, design, designError, focusCheck, focusImpact, roundTripMs, theme, wsUp, persist } from "../store";
import {
  canRunNow, cancelClaude, claude, claudeBusy, claudeError, dismissedRun, dismissRun, headerState, requestText,
  runClaudeNow, runHeadline, setAutoRun,
} from "../claude";
import { claudePrompt, requests, selectedProposal } from "../intent";
import type { RunJ } from "../types";
import { Mono } from "./common";
import { ContextChip } from "./ContextChip";
import { ViewMenu } from "./ViewMenu";

export function Header() {
  const d = design.value, b = build.value;
  return (
    <header class="header">
      <div class="brand" title="design-intent parametric model">dipm</div>
      <div class="title">
        <h1>{d?.name ?? "…"}</h1>
        <span class="path mono" title={d?.file ?? ""}>{shortPath(d?.file ?? "")}</span>
      </div>
      <div class="header-status">
        {b && <StatusTiers />}
        {b && <ContextChip />}
        <ViewMenu />
        {impactOf(b) && (
          <button class="badge badge-impact" data-testid="impact-chip" onClick={() => (focusImpact.value = Date.now())}
                  title="a purpose changed since its solution was reviewed: see what it invalidated">
            purpose changed · {impactOf(b)!.summary.nodes.invalidated + impactOf(b)!.summary.checks.invalidated +
              impactOf(b)!.summary.assumptions.invalidated} invalidated</button>
        )}
        <ClaudeStatus />
        {b && (
          <span class="mono num" title="engine build time · round trip">
            {b.ms.toFixed(0)} ms{roundTripMs.value !== null ? ` · ${roundTripMs.value.toFixed(0)} ms` : ""}
          </span>
        )}
        {building.value && <span class="busy" aria-live="polite">building…</span>}
        {b?.resolving && <span class="busy" title="interpretations are being re-resolved">re-resolving…</span>}
        {designError.value && <span class="badge badge-fail" title={designError.value}>design error</span>}
        <span class={`ws ${wsUp.value ? "up" : "down"}`} title={wsUp.value ? "live: watching the design file" : "not connected"}>
          {wsUp.value ? "live" : "offline"}
        </span>
        <button class="theme-toggle" onClick={() => { theme.value = theme.value === "dark" ? "light" : "dark"; persist("theme", theme.value); }}
                aria-label="toggle light/dark theme" title="toggle light/dark theme">
          {theme.value === "dark" ? "☀" : "☾"}
        </button>
      </div>
    </header>
  );
}

/** "Kernel ✓ · Intent checks 3 of 11 run · 2 failing · 1 thin margin".  Green only for tiers that
 *  ran and passed; each tier opens the checks panel at the relevant row. */
function StatusTiers() {
  const b = build.value!;
  const st = b.status;
  const k = st.kernel, it = st.intent;
  const go = (id: string | undefined) => { if (id) focusCheck.value = { id, at: Date.now() }; };
  return (
    <span class="tiers" data-testid="build-status" role="status" aria-label={st.headline} title={st.text}>
      <button class={`tier ${k.state === "pass" ? "tier-ok" : "tier-fail"}`} data-testid="tier-kernel"
              onClick={() => go(k.state === "pass" ? "kernel" : (b.failing[0] ? `feature:${b.failing[0]}` : "kernel"))}
              title="kernel invariants: validity, Euler, ΔH, ΔS, volume sign, references">
        Kernel {k.state === "pass" ? "✓" : `✗ ${k.failures}`}
      </button>
      <span class="tier-sep">·</span>
      <button class="tier tier-neutral" data-testid="tier-intent" onClick={() => go(it.not_run_ids[0] ?? it.ample_ids[0])}
              title={`${it.not_run} intent check(s) have no computable form yet`}>
        {it.total ? `Intent checks ${it.run} of ${it.total} run` : "Intent checks: none stated"}
      </button>
      {it.failing > 0 && <>
        <span class="tier-sep">·</span>
        <button class="tier tier-fail" data-testid="tier-failing" onClick={() => go(it.failing_ids[0])}
                title={`failing: ${it.failing_ids.join(", ")}`}>{it.failing} failing</button>
      </>}
      {it.thin > 0 && <>
        <span class="tier-sep">·</span>
        <button class="tier tier-warn" data-testid="tier-thin" onClick={() => go(it.thin_ids[0])}
                title={`thin: ${it.thin_ids.join(", ")}`}>{it.thin} thin margin{it.thin === 1 ? "" : "s"}</button>
      </>}
      {(st.guesses ?? 0) > 0 && <>
        <span class="tier-sep">·</span>
        <span class="tier guess" data-testid="tier-guesses" title="model-made items nobody has reviewed yet">
          {st.guesses} guess{st.guesses === 1 ? "" : "es"} unreviewed</span>
      </>}
    </span>
  );
}

/** Requests and Claude (iteration 4b): "Claude is working on r3…" with the live step while a
 *  headless run goes; "N requests waiting" otherwise; the last run until dismissed.  Without a
 *  usable `claude` the popover is the copyable prompt, as before. */
function ClaudeStatus() {
  const s = claude.value;
  const reqs = requests.value;
  const [open, setOpen] = useState(false);
  const st = headerState(s, reqs, dismissedRun.value);
  const unavailable = !s || !s.available.ok || s.available.login === "failed";
  if (st.kind === "none" && !open) return null;
  const cls = st.kind === "running" ? "badge badge-claude running" : st.kind === "last" && st.tone === "ok" ?
    "badge badge-ok claude-last" : st.kind === "last" ? "badge badge-warn claude-last" : "badge badge-warn";
  const full = st.kind === "running" ? `${st.text}${st.step ? ` · ${st.step}` : ""}` : st.kind === "none" ? "" : st.text;
  return (
    <span class="waiting">
      {st.kind !== "none" && (
        <button class={cls} data-testid={st.kind === "waiting" ? "requests-waiting" : "claude-status"}
                data-state={st.kind} onClick={() => setOpen(!open)} aria-expanded={open}
                title={st.kind === "running" ? `${full}\nClaude Code is running headless with dipm's tools only: it can propose, never write`
                  : unavailable ? "requests queued for Claude: copy the prompt into your Claude Code session"
                  : `${full}\nrequests and Claude runs`}>
          {st.kind === "running" && <span class="spinner" aria-hidden="true" />}
          {st.text}
          {st.kind === "running" && st.step && <span class="claude-step" data-testid="claude-step"> · {st.step}</span>}
        </button>
      )}
      {open && <ClaudePopover onClose={() => setOpen(false)} />}
    </span>
  );
}

function ClaudePopover({ onClose }: { onClose: () => void }) {
  const s = claude.value;
  const reqs = requests.value;
  const [copied, setCopied] = useState(false);
  const unavailable = !s || !s.available.ok || s.available.login === "failed";
  const run = s?.run ?? null;
  const copy = async () => {
    try { await navigator.clipboard.writeText(claudePrompt.value); setCopied(true); } catch {
      const t = document.getElementById("claude-prompt") as HTMLTextAreaElement | null;
      t?.select();
    }
  };
  const prompt = (
    <>
      <textarea id="claude-prompt" rows={4} readOnly value={claudePrompt.value} data-testid="claude-prompt" />
      <div class="confirm-actions">
        <button class="btn primary" onClick={copy} data-testid="copy-prompt">{copied ? "copied" : "copy prompt"}</button>
        <button class="btn" onClick={onClose}>close</button>
      </div>
    </>
  );
  if (unavailable) {
    return (
      <div class="popover claude-pop" role="dialog" aria-label="prompt for Claude" data-testid="claude-popover">
        {s && <div class="small warn-text" data-testid="claude-unavailable">{s.available.reason}</div>}
        <div class="small">Paste this into your Claude Code session (the dipm MCP server must be registered):</div>
        {prompt}
      </div>
    );
  }
  const waiting = reqs.filter((r) => r.status === "open" || r.status === "failed");
  return (
    <div class="popover claude-pop" role="dialog" aria-label="Claude runs" data-testid="claude-popover">
      {run && <RunView run={run} />}
      {waiting.length > 0 && (
        <div class="small claude-waiting">
          {waiting.map((r) => (
            <div key={r.id}><Mono>{r.id}</Mono> {r.node} · <span class={`rq rq-${r.status}`}>{requestText(r)}</span></div>
          ))}
        </div>
      )}
      <div class="confirm-actions">
        <button class="btn primary" data-testid="claude-run-now" disabled={!canRunNow(s, reqs) || claudeBusy.value}
                onClick={() => void runClaudeNow()}
                title={s?.running ? "a run is going: new requests queue behind it" : "start Claude Code now for the open (and failed) requests"}>
          Run Claude now</button>
        {run && run.status !== "running" && (
          <button class="btn" onClick={() => { dismissRun(run.id); onClose(); }} data-testid="claude-dismiss">dismiss</button>
        )}
        <button class="btn" onClick={onClose}>close</button>
      </div>
      <label class="small claude-auto">
        <input type="checkbox" data-testid="claude-autorun" checked={!!s?.settings.auto_run} disabled={claudeBusy.value}
               onChange={(e) => void setAutoRun((e.target as HTMLInputElement).checked)} />
        start Claude automatically when a request is queued (this design)
      </label>
      {claudeError.value && <div class="small warn-text" data-testid="claude-error">{claudeError.value}</div>}
      <details class="small">
        <summary>or copy the prompt for your own Claude Code session</summary>
        {prompt}
      </details>
    </div>
  );
}

function RunView({ run }: { run: RunJ }) {
  const steps = run.steps.slice(-40);
  const list = useRef<HTMLOListElement>(null);
  useEffect(() => {      // keep the latest step in view
    if (list.current) list.current.scrollTop = list.current.scrollHeight;
  }, [run.steps.length, run.status]);
  return (
    <div class="claude-run" data-testid="claude-run" data-status={run.status}>
      <div class="claude-run-head">
        <b>{runHeadline(run)}</b>
        <span class="small muted mono"> {run.id}{run.model ? ` · ${run.model}` : ""}</span>
      </div>
      <ol class="claude-steps" data-testid="claude-steps" ref={list}>
        {steps.map((x, i) => (
          <li key={i} class={`step step-${x.kind}`}>{x.text}</li>
        ))}
        {run.status === "running" && <li class="step step-live" aria-live="polite">…</li>}
      </ol>
      {run.reason && run.status !== "done" && <div class="small warn-text" data-testid="claude-reason">{run.reason}</div>}
      {run.usage_line && <div class="small muted mono" data-testid="claude-usage">{run.usage_line}</div>}
      <div class="claude-run-actions">
        {run.status === "running" && (
          <button class="btn danger-outline" data-testid="claude-cancel" disabled={claudeBusy.value}
                  onClick={() => void cancelClaude(run.id)}>Cancel</button>
        )}
        <a class="link small" href={`/api/claude/runs/${run.id}/transcript`} target="_blank" rel="noopener"
           data-testid="claude-transcript">open transcript</a>
        {run.proposals.length > 0 && (
          <span class="small">proposals: {run.proposals.map((p) => (
            <button key={p} class="link mono" onClick={() => { selectedProposal.value = p; }}>{p}</button>
          ))}</span>
        )}
      </div>
    </div>
  );
}

function shortPath(p: string): string {
  const parts = p.split("/");
  return parts.length > 3 ? "…/" + parts.slice(-3).join("/") : p;
}

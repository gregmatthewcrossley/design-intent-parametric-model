// Header strip (docs/gui.md §3, §8.3 items 1, 4, 8): design name, the honest tiered status (no bare
// PASS), the assumed-context chip, the View menu, requests waiting for Claude, live/theme.

import { useState } from "preact/hooks";
import { build, building, design, designError, focusCheck, roundTripMs, theme, wsUp, persist } from "../store";
import { claudePrompt, requests } from "../intent";
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
        <RequestsWaiting />
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

function RequestsWaiting() {
  const n = requests.value.filter((r) => r.status === "open").length;
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  if (!n) return null;
  const copy = async () => {
    try { await navigator.clipboard.writeText(claudePrompt.value); setCopied(true); } catch {
      const t = document.getElementById("claude-prompt") as HTMLTextAreaElement | null;
      t?.select();
    }
  };
  return (
    <span class="waiting">
      <button class="badge badge-warn" data-testid="requests-waiting" onClick={() => setOpen(!open)}
              title="requests queued for Claude: nothing is sent automatically">
        {n} request{n === 1 ? "" : "s"} waiting
      </button>
      {open && (
        <div class="popover" role="dialog" aria-label="prompt for Claude">
          <div class="small">Paste this into your Claude Code session (the dipm MCP server must be registered):</div>
          <textarea id="claude-prompt" rows={4} readOnly value={claudePrompt.value} data-testid="claude-prompt" />
          <div class="confirm-actions">
            <button class="btn primary" onClick={copy} data-testid="copy-prompt">{copied ? "copied" : "copy prompt"}</button>
            <button class="btn" onClick={() => setOpen(false)}>close</button>
          </div>
        </div>
      )}
    </span>
  );
}

function shortPath(p: string): string {
  const parts = p.split("/");
  return parts.length > 3 ? "…/" + parts.slice(-3).join("/") : p;
}

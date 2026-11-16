// Iteration 4b (docs/purpose-loop.md §7): dipm starts headless Claude Code for queued requests.
// State of the runs (pushed over the websocket as "claude-run" events) and the plain-language
// texts the header and the proposals panel show.  The texts are pure functions (gui/tests).

import { signal } from "@preact/signals";
import { api, HttpError } from "./api";
import { loadProposals } from "./intent";
import { persist } from "./store";
import type { ClaudeStatusJ, RequestJ, RunJ } from "./types";

export const claude = signal<ClaudeStatusJ | null>(null);
export const claudeError = signal<string | null>(null);
export const claudeBusy = signal(false);
/** The last finished run the designer dismissed from the header (per browser). */
export const dismissedRun = signal<string | null>((() => {
  try { return JSON.parse(localStorage.getItem("dipm.claudeDismissed") ?? "null"); } catch { return null; }
})());

export async function loadClaude(): Promise<void> {
  try {
    claude.value = await api.claude();
  } catch {
    /* older server or gone: no automatic pickup, the prompt fallback stays */
  }
}

export function applyClaude(s: ClaudeStatusJ): void {
  claude.value = s;
}

async function act(fn: () => Promise<{ status?: ClaudeStatusJ } | unknown>): Promise<boolean> {
  claudeBusy.value = true;
  claudeError.value = null;
  try {
    const r = (await fn()) as { status?: ClaudeStatusJ };
    if (r && r.status) claude.value = r.status;
    else await loadClaude();
    await loadProposals();
    return true;
  } catch (e) {
    const body = e instanceof HttpError ? e.body : {};
    claudeError.value = (e as Error).message;
    if (body.claude) claude.value = body.claude as ClaudeStatusJ;
    return false;
  } finally {
    claudeBusy.value = false;
  }
}

export const runClaudeNow = (ids?: string[]) => act(() => api.claudeRun(ids));
export const cancelClaude = (run?: string) => act(() => api.claudeCancel(run));
export const setAutoRun = (on: boolean) => act(() => api.claudeSettings({ auto_run: on }));
export const setModel = (model: string) => act(() => api.claudeSettings({ model: model.trim() || null }));

export function dismissRun(id: string): void {
  dismissedRun.value = id;
  persist("claudeDismissed", id);
}

// ------------------------------------------------------------------ texts (pure)

export function idList(ids: string[]): string {
  return ids.length <= 3 ? ids.join(", ") : `${ids.slice(0, 2).join(", ")} and ${ids.length - 2} more`;
}

/** The step to show next to "Claude is working…": the latest one that is not Claude talking. */
export function currentStep(run: RunJ | null): string {
  if (!run || !run.steps.length) return run?.status === "running" ? "starting…" : "";
  const s = [...run.steps].reverse().find((x) => x.kind !== "say") ?? run.steps[run.steps.length - 1];
  return s.text;
}

export function runHeadline(run: RunJ): string {
  const who = idList(run.requests);
  const made = run.proposals.length ? ` · proposed ${idList(run.proposals)}` : "";
  switch (run.status) {
    case "running": return `Claude is working on ${who}…`;
    case "done": return run.proposals.length ? `Claude finished ${who}${made}` : `Claude finished ${who}: nothing proposed`;
    case "cancelled": return `Claude stopped on ${who}: cancelled${made}`;
    case "timeout": return `Claude stopped on ${who}: timed out${made}`;
    default: return `Claude could not finish ${who}${made}`;
  }
}

export type HeaderState =
  | { kind: "running"; text: string; step: string }
  | { kind: "waiting"; text: string }
  | { kind: "last"; text: string; tone: "ok" | "warn" }
  | { kind: "none" };

/** What the header shows for Claude: a run in progress, requests waiting, or the last run. */
export function headerState(s: ClaudeStatusJ | null, reqs: RequestJ[], dismissed: string | null): HeaderState {
  const waiting = reqs.filter((r) => r.status === "open").length;
  const run = s?.run ?? null;
  if (s?.running && run) return { kind: "running", text: runHeadline(run), step: currentStep(run) };
  if (waiting) return { kind: "waiting", text: `${waiting} request${waiting === 1 ? "" : "s"} waiting` };
  if (run && run.status !== "running" && run.id !== dismissed) {
    return { kind: "last", text: runHeadline(run), tone: run.status === "done" && run.proposals.length ? "ok" : "warn" };
  }
  return { kind: "none" };
}

/** A request's state in words (open → running → proposed / failed → answered). */
export function requestText(r: RequestJ): string {
  switch (r.status) {
    case "open": return "waiting for Claude";
    case "running": return "Claude is working on it";
    case "proposed": return r.proposals.length ? `proposed: ${idList(r.proposals)}` : "proposed";
    case "failed": return `failed${r.status_detail ? `: ${r.status_detail.replace(/^run\d+: /, "")}` : ""}`;
    case "answered": return "answered";
    default: return r.status;
  }
}

export function canRunNow(s: ClaudeStatusJ | null, reqs: RequestJ[]): boolean {
  return !!s?.available.ok && !s.running && reqs.some((r) => r.status === "open" || r.status === "failed");
}

// Iteration 2 state and actions (docs/gui.md §7): the intent file (edit with a base hash,
// 409 → conflict banner), staleness review, "Ask Claude" requests, and proposals.

import { signal } from "@preact/signals";
import { api, HttpError } from "./api";
import { applyBuild, buildError } from "./store";
import type { BuildJ, IntentInfo, IntentOp, ProposalJ, RequestJ } from "./types";

export const intentInfo = signal<IntentInfo | null>(null);
export const intentBusy = signal(false);

/** An inline statement edit in progress.  `base` is the intent file hash when editing began:
 *  if the file changes on disk meanwhile, committing produces a conflict, not an overwrite. */
export const editing = signal<{ id: string; draft: string; base: string | null; where: "row" | "inspector" } | null>(null);

/** A rejected (409) write, kept so the designer can reload or re-apply it. */
export const conflict = signal<{ ops: IntentOp[]; message: string; current: IntentInfo | null } | null>(null);
export const intentError = signal<string | null>(null);

/** Node waiting for an in-page delete confirmation. */
export const confirmDelete = signal<{ id: string; where: "row" | "inspector" } | null>(null);
export const dragging = signal<string | null>(null);
export const dropTarget = signal<string | null>(null);

export async function loadIntent(): Promise<void> {
  try {
    intentInfo.value = await api.intent();
  } catch {
    intentInfo.value = null;
  }
}

/** Send edit ops against `base` (default: the hash we last saw).  Returns true on success. */
export async function patchIntent(ops: IntentOp[], base?: string | null): Promise<boolean> {
  const h = base === undefined ? intentInfo.value?.hash ?? null : base;
  intentBusy.value = true;
  intentError.value = null;
  try {
    const r = await api.patchIntent(h, ops);
    intentInfo.value = r.intent;
    if (r.build) applyBuild(r.build);
    conflict.value = null;
    return true;
  } catch (e) {
    if (e instanceof HttpError && e.status === 409) {
      const current = (e.body.current as IntentInfo | undefined) ?? null;
      if (current) intentInfo.value = current;
      conflict.value = { ops, message: String(e.body.error ?? "conflict"), current };
    } else {
      intentError.value = (e as Error).message;
    }
    return false;
  } finally {
    intentBusy.value = false;
  }
}

export function startEdit(id: string, statement: string, where: "row" | "inspector" = "row"): void {
  editing.value = { id, draft: statement, base: intentInfo.value?.hash ?? null, where };
}

export async function commitEdit(): Promise<void> {
  const e = editing.value;
  if (!e) return;
  const st = e.draft.trim();
  editing.value = null;
  if (!st) return;
  await patchIntent([{ op: "edit_statement", id: e.id, statement: st }], e.base);
}

/** Conflict banner: drop my edit and show what is on disk now. */
export async function reloadAfterConflict(): Promise<void> {
  conflict.value = null;
  await loadIntent();
}

/** Conflict banner: apply my edit again on top of the current file. */
export async function reapplyAfterConflict(): Promise<void> {
  const c = conflict.value;
  if (!c) return;
  await loadIntent();
  await patchIntent(c.ops, intentInfo.value?.hash ?? null);
}

export const markReviewed = (ids: string[]) => patchIntent([{ op: "mark_reviewed", ids }]);

/** Rename an intent id in the intent file and the DSL (server-side LibCST codemod); saved
 *  preferences move with it (#49), and `renameFeatures` also renames matching feature ids. */
export async function renameId(old: string, next: string, renameFeatures = false): Promise<boolean> {
  const info = intentInfo.value;
  intentBusy.value = true;
  intentError.value = null;
  try {
    const r = await api.rename(info?.hash ?? null, info?.design_hash ?? null, old, next, renameFeatures);
    intentInfo.value = r.intent;
    applyBuild(r.build);
    return true;
  } catch (e) {
    if (e instanceof HttpError && e.status === 409) {
      const current = (e.body.current as IntentInfo | undefined) ?? null;
      if (current) intentInfo.value = current;
      conflict.value = { ops: [], message: String(e.body.error ?? "conflict"), current };
    } else {
      intentError.value = (e as Error).message;
    }
    return false;
  } finally {
    intentBusy.value = false;
  }
}

// ------------------------------------------------------------------ proposals and requests

export const proposals = signal<ProposalJ[]>([]);
export const requests = signal<RequestJ[]>([]);
/** "Queue for Claude" (#55): open requests waiting and the prompt to paste into Claude Code. */
export const claudePrompt = signal<string>("");
export const selectedProposal = signal<string | null>(null);
/** Geometry comparison shown in the viewport (null: the live build). */
export const compare = signal<{ id: string; mode: "before" | "after" | "overlay" } | null>(null);
export const proposalBusy = signal<string | null>(null);

let reloadTimer: ReturnType<typeof setTimeout> | null = null;

export async function loadProposals(): Promise<void> {
  try {
    const r = await api.proposals();
    proposals.value = r.proposals;
    requests.value = r.requests;
    claudePrompt.value = r.prompt ?? "";
    if (compare.value && !r.proposals.some((p) => p.id === compare.value!.id && p.evaluation?.meshes)) compare.value = null;
  } catch {
    /* server gone: keep the list */
  }
}

export function reloadProposalsSoon(): void {
  if (reloadTimer) clearTimeout(reloadTimer);
  reloadTimer = setTimeout(() => void loadProposals(), 120);
}

export async function acceptProposal(id: string, overrideReason?: string): Promise<void> {
  proposalBusy.value = id;
  try {
    const r = await api.accept(id, "", overrideReason);
    applyBuild(r.build);
    compare.value = null;
    await Promise.all([loadProposals(), loadIntent()]);
  } catch (e) {
    buildError.value = (e as Error).message;
    await loadProposals();
  } finally {
    proposalBusy.value = null;
  }
}

export async function rejectProposal(id: string, comment: string): Promise<void> {
  proposalBusy.value = id;
  try {
    await api.reject(id, comment);
    if (compare.value?.id === id) compare.value = null;
    await loadProposals();
  } catch (e) {
    buildError.value = (e as Error).message;
  } finally {
    proposalBusy.value = null;
  }
}

export async function askClaude(node: string, note: string): Promise<RequestJ | null> {
  try {
    const r = await api.ask(node, note);
    await loadProposals();
    return r;
  } catch (e) {
    intentError.value = (e as Error).message;
    return null;
  }
}

/** Before/after at the GUI's current parameters (NOTES #53 change). */
export async function viewProposalAt(id: string, params: Record<string, unknown>): Promise<void> {
  try {
    const p = await api.view(id, params);
    proposals.value = proposals.value.map((x) => (x.id === id ? p : x));
  } catch {
    /* keep the verdict geometry */
  }
}

// ------------------------------------------------------------------ iteration 3: confirming guesses

async function intentAction(fn: (base: string | null) => Promise<{ intent: IntentInfo; build: BuildJ | null }>): Promise<boolean> {
  intentBusy.value = true;
  intentError.value = null;
  try {
    const r = await fn(intentInfo.value?.hash ?? null);
    intentInfo.value = r.intent;
    if (r.build) applyBuild(r.build);
    return true;
  } catch (e) {
    if (e instanceof HttpError && e.status === 409) {
      const current = (e.body.current as IntentInfo | undefined) ?? null;
      if (current) intentInfo.value = current;
      conflict.value = { ops: [], message: String(e.body.error ?? "conflict"), current };
    } else {
      intentError.value = (e as Error).message;
    }
    return false;
  } finally {
    intentBusy.value = false;
  }
}

/** Accept a model-made item.  Keys are the payload's provenance keys (B5): readings go to the
 *  review record; assumptions, context and the orientation go into the intent file. */
export async function acceptGuess(key: string, b: BuildJ | null): Promise<boolean> {
  const pv = b?.provenance?.[key];
  if (key.startsWith("slot:")) return intentAction((h) => api.review(h, "accept_item", key, pv?.value));
  if (key.startsWith("assumption:")) {
    const id = key.slice("assumption:".length);
    if (!pv?.node) return false;
    return patchIntent([{ op: "edit_assumption", id: pv.node, assumption_id: id, fields: { status: "accepted" } }]);
  }
  if (key.startsWith("context:")) return intentAction((h) => api.context(h, "accept"));
  if (key === "orientation") return intentAction((h) => api.orientation(h, "accept"));
  if (key.startsWith("check:")) {
    if (!pv?.node) return false;
    return markReviewed([pv.node]);
  }
  return false;
}

export const setContext = (values: Record<string, string>) => intentAction((h) => api.context(h, "set", values));
export const reinferOrientation = () => intentAction((h) => api.orientation(h, "infer"));
export const reviewAll = () => intentAction((h) => api.review(h, "all"));
export const reviewOneByOne = () => intentAction((h) => api.review(h, "one_by_one"));

// ------------------------------------------------------------------ iteration 4: purpose proposals

/** "Accept to try": geometry alternatives may be built against the purpose proposal; nothing is
 *  written until an alternative is accepted. */
export async function tryPurpose(id: string): Promise<void> {
  proposalBusy.value = id;
  try {
    await api.tryPurpose(id);
    await loadProposals();
  } catch (e) {
    buildError.value = (e as Error).message;
  } finally {
    proposalBusy.value = null;
  }
}

/** The designer edits a purpose proposal while reviewing it: a revised proposal (designer-made
 *  for what was edited) replaces it and is selected. */
export async function editPurpose(id: string, ops: IntentOp[], comment = ""): Promise<string | null> {
  proposalBusy.value = id;
  try {
    const r = await api.editPurpose(id, ops, comment);
    await loadProposals();
    selectedProposal.value = r.proposal.id;
    return r.proposal.id;
  } catch (e) {
    buildError.value = (e as Error).message;
    return null;
  } finally {
    proposalBusy.value = null;
  }
}

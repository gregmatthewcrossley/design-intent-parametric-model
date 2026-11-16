// Iteration 2 state and actions (docs/gui.md §7): the intent file (edit with a base hash,
// 409 → conflict banner), staleness review, "Ask Claude" requests, and proposals.

import { signal } from "@preact/signals";
import { api, HttpError } from "./api";
import { applyBuild, buildError } from "./store";
import type { IntentInfo, IntentOp, ProposalJ, RequestJ } from "./types";

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

/** Rename an intent id in the intent file and the DSL (server-side LibCST codemod). */
export async function renameId(old: string, next: string): Promise<boolean> {
  const info = intentInfo.value;
  intentBusy.value = true;
  intentError.value = null;
  try {
    const r = await api.rename(info?.hash ?? null, info?.design_hash ?? null, old, next);
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
    if (compare.value && !r.proposals.some((p) => p.id === compare.value!.id && p.evaluation?.meshes)) compare.value = null;
  } catch {
    /* server gone: keep the list */
  }
}

export function reloadProposalsSoon(): void {
  if (reloadTimer) clearTimeout(reloadTimer);
  reloadTimer = setTimeout(() => void loadProposals(), 120);
}

export async function acceptProposal(id: string): Promise<void> {
  proposalBusy.value = id;
  try {
    const r = await api.accept(id);
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

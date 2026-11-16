// Pure helpers for iteration 2 (docs/gui.md §7): intent editing, staleness, proposals.

import type { BuildJ, EvaluationJ, ProposalJ, ProposalStatus } from "./types";

/** Every node at or beneath `id` (tree order). */
export function subtree(b: BuildJ, id: string): string[] {
  const out: string[] = [];
  const walk = (n: string) => {
    out.push(n);
    for (const c of b.tree.nodes[n]?.children ?? []) walk(c);
  };
  if (b.tree.nodes[id]) walk(id);
  return out;
}

/** Can `drag` be reparented under `target`?  Only nodes declared in the intent file, never a
 *  root, never into its own subtree, and not onto its current parent (a no-op). */
export function canDrop(b: BuildJ, drag: string, target: string): boolean {
  const d = b.tree.nodes[drag], t = b.tree.nodes[target];
  if (!b.tree.from_file || !d || !t || !d.in_file || !t.in_file) return false;
  if (d.parent === null || d.parent === target) return false;
  return !subtree(b, drag).includes(target);
}

/** Parents a node may be moved to (for the keyboard-accessible "move to" control). */
export function moveTargets(b: BuildJ, id: string): string[] {
  return b.tree.order.filter((t) => canDrop(b, id, t));
}

/** Features whose intent changed since their solution was reviewed (they serve a stale node). */
export function staleFeatures(b: BuildJ | null): Map<string, string[]> {
  const m = new Map<string, string[]>();
  for (const f of b?.features ?? []) if (f.stale && f.stale.length) m.set(f.id, f.stale);
  return m;
}

export function staleNodes(b: BuildJ | null): string[] {
  return b ? b.tree.order.filter((id) => b.tree.nodes[id]?.stale) : [];
}

/** How many features reference a node (or anything beneath it): deleting it leaves them with "no intent". */
export function featuresUnder(b: BuildJ, id: string): string[] {
  const ids = new Set(subtree(b, id));
  return b.features.filter((f) => f.nodes.some((n) => ids.has(n)) ||
    Object.values(f.instances).some((ts) => ts.some((t) => ids.has(t.node)))).map((f) => f.id);
}

export type DiffLine = { cls: "add" | "del" | "hunk" | "meta" | "ctx"; text: string };

export function diffLines(diff: string): DiffLine[] {
  return diff.split("\n").filter((l, i, a) => !(i === a.length - 1 && l === "")).map((text) => ({
    text,
    cls: text.startsWith("+++") || text.startsWith("---") ? "meta" : text.startsWith("@@") ? "hunk" :
      text.startsWith("+") ? "add" : text.startsWith("-") ? "del" : "ctx",
  }));
}

export const OPEN: ProposalStatus[] = ["pending", "evaluating", "ready", "failed"];

export function isOpen(p: ProposalJ): boolean {
  return OPEN.includes(p.status);
}

export function canAccept(p: ProposalJ): boolean {
  return p.status === "ready";
}

/** Per-face display states for a proposal mesh: changed faces highlighted, the rest plain. */
export function compareStates(nFaces: number, changed: number[]): ("base" | "selected")[] {
  const set = new Set(changed);
  return Array.from({ length: nFaces }, (_, i) => (set.has(i) ? "selected" : "base"));
}

/** One-line summaries of a proposal's semantic diff, for the panel and tests. */
export function semanticSummary(ev: EvaluationJ | null): string[] {
  const sd = ev?.semantic_diff;
  if (!sd) return [];
  const out: string[] = [];
  for (const c of sd.intent.changed) {
    if (c.statement) out.push(`intent ${c.id}: “${c.statement.before}” → “${c.statement.after}”`);
    for (const k of ["checks", "assumptions"]) if (c[k]) out.push(`intent ${c.id}: ${k} changed`);
  }
  for (const a of sd.intent.added) out.push(`intent + ${a.id} “${a.statement}”`);
  for (const r of sd.intent.removed) out.push(`intent − ${r.id}`);
  for (const m of sd.intent.moved) out.push(`intent ${m.id} moved ${m.from} → ${m.to}`);
  for (const f of sd.features.added) out.push(`feature + ${f}`);
  for (const f of sd.features.removed) out.push(`feature − ${f}`);
  for (const f of sd.features.changed) {
    const keys = Object.keys(f).filter((k) => k !== "id");
    out.push(`feature ${f.id}: ${keys.join(", ")} changed`);
  }
  for (const s of sd.interpretations.removed) out.push(`interpretation − ${s.id} (was ${s.chosen})`);
  for (const s of sd.interpretations.added) out.push(`interpretation + ${s.id} → ${s.chosen}`);
  for (const s of sd.interpretations.changed) out.push(`interpretation ${s.id}: ${s.before} → ${s.after}`);
  return out;
}

/** Hole centres before → after for a feature, if its detail carries them ("where did it move?"). */
export function centreMove(ev: EvaluationJ | null, fid: string): { before: number[][]; after: number[][] } | null {
  const f = ev?.semantic_diff?.features.changed.find((x) => x.id === fid);
  const d = f?.detail as { before: { centres?: number[][] }; after: { centres?: number[][] } } | undefined;
  if (!d?.before?.centres || !d?.after?.centres) return null;
  return { before: d.before.centres, after: d.after.centres };
}

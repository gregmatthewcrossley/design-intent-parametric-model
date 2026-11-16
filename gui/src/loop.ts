// Pure helpers for the purpose -> geometry loop (iteration 4, docs/purpose-loop.md §4 GUI):
// impact marks, purpose proposals as a tree diff, alternatives grouped for comparison, and the
// geometry of component ghosts.  No DOM, no three.js; tests/loop.test.ts.

import type {
  BuildJ, GhostJ, ImpactClass, ImpactJ, IntentDocJ, IntentDocNode, ProposalJ, PurposeCheckJ, SummaryCheckJ,
  SummaryTermJ,
} from "./types";

// ------------------------------------------------------------------ impact

export function impactOf(b: BuildJ | null): ImpactJ | null {
  return b?.impact && b.impact.any_change ? b.impact : null;
}

/** The impact class of an intent node (null when there is no change to show). */
export function nodeImpact(b: BuildJ | null, id: string): ImpactClass | null {
  return impactOf(b)?.nodes[id]?.class ?? null;
}

export const IMPACT_TEXT: Record<ImpactClass, string> = {
  changed: "changed", invalidated: "invalidated", survives: "survives",
};

/** Rows for the impact panel: changed first, then invalidated, each kind in a fixed order. */
export function impactRows(im: ImpactJ): { kind: string; id: string; cls: ImpactClass; text: string; reasons: string[] }[] {
  const out: { kind: string; id: string; cls: ImpactClass; text: string; reasons: string[] }[] = [];
  const kinds: [string, Record<string, { class: ImpactClass; reasons: string[]; statement?: string }>][] = [
    ["node", im.nodes], ["check", im.checks], ["assumption", im.assumptions], ["feature", im.features]];
  for (const cls of ["changed", "invalidated"] as ImpactClass[]) {
    for (const [kind, items] of kinds) {
      for (const [id, v] of Object.entries(items)) {
        if (v.class === cls) out.push({ kind, id, cls, text: v.statement ?? "", reasons: v.reasons });
      }
    }
  }
  return out;
}

// ------------------------------------------------------------------ purpose proposal as a tree diff

export type DiffStatus = "added" | "removed" | "changed" | "same";

export interface DiffRow {
  id: string;
  depth: number;
  parent: string | null;
  status: DiffStatus;
  statement: string;
  before: string | null;       // the old statement when it changed or the node was removed
  moved: boolean;
  checks: (PurposeCheckJ & { change: DiffStatus })[];
  removedChecks: string[];
}

interface Flat { node: IntentDocNode; parent: string | null; depth: number }

function flatten(doc: IntentDocJ | null): Map<string, Flat> {
  const m = new Map<string, Flat>();
  const walk = (ns: IntentDocNode[] | undefined, parent: string | null, depth: number) => {
    for (const n of ns ?? []) {
      m.set(n.id, { node: n, parent, depth });
      walk(n.children, n.id, depth + 1);
    }
  };
  walk(doc?.intents, null, 0);
  return m;
}

function sameJson(a: unknown, b: unknown): boolean {
  return JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
}

/** The proposed tree in its own order, each node marked added/changed/same, removed nodes
 *  listed after their old parent's subtree, and each check with its binding row. */
export function treeDiff(before: IntentDocJ | null, after: IntentDocJ, checks: PurposeCheckJ[] = []): DiffRow[] {
  const A = flatten(before), B = flatten(after);
  const byId = new Map(checks.map((c) => [c.id, c]));
  const rows: DiffRow[] = [];
  const emitRemoved = (parent: string, depth: number) => {
    for (const [id, f] of A) {
      if (f.parent === parent && !B.has(id)) {
        rows.push({ id, depth, parent, status: "removed", statement: f.node.statement, before: f.node.statement,
                    moved: false, checks: [], removedChecks: (f.node.checks ?? []).map((c) => c.id) });
        emitRemoved(id, depth + 1);
      }
    }
  };
  const walk = (ns: IntentDocNode[] | undefined, parent: string | null, depth: number) => {
    for (const n of ns ?? []) {
      const old = A.get(n.id);
      const own = (x: IntentDocNode | undefined) => x && { s: x.statement, c: x.checks ?? [], a: x.assumptions ?? [] };
      const status: DiffStatus = !old ? "added" : sameJson(own(old.node), own(n)) ? "same" : "changed";
      const oldChecks = new Map((old?.node.checks ?? []).map((c) => [c.id, c]));
      const cs = (n.checks ?? []).map((c) => {
        const pc = byId.get(c.id) ?? { id: c.id, node: n.id, statement: c.statement, form: null, binding: null,
                                       reads_as: "", made_by: null, reviewed: false, state: "not run", reason: "" };
        const o = oldChecks.get(c.id);
        return { ...pc, change: (!o ? "added" : sameJson(o, c) ? "same" : "changed") as DiffStatus };
      });
      const newIds = new Set((n.checks ?? []).map((c) => c.id));
      rows.push({ id: n.id, depth, parent, status, statement: n.statement,
                  before: old && old.node.statement !== n.statement ? old.node.statement : null,
                  moved: !!old && old.parent !== parent, checks: cs,
                  removedChecks: [...oldChecks.keys()].filter((k) => !newIds.has(k)) });
      walk(n.children, n.id, depth + 1);
      emitRemoved(n.id, depth + 1);
    }
  };
  walk(after.intents, null, 0);
  // removed roots
  for (const [id, f] of A) if (f.parent === null && !B.has(id)) {
    rows.push({ id, depth: 0, parent: null, status: "removed", statement: f.node.statement, before: f.node.statement,
                moved: false, checks: [], removedChecks: [] });
  }
  return rows;
}

export function diffCounts(rows: DiffRow[]): Record<DiffStatus, number> {
  const out: Record<DiffStatus, number> = { added: 0, removed: 0, changed: 0, same: 0 };
  for (const r of rows) out[r.status]++;
  return out;
}

// ------------------------------------------------------------------ geometry alternatives

/** Geometry proposals grouped by their alternatives group, alternatives in label order. */
export function alternativeGroups(ps: ProposalJ[]): Map<string, ProposalJ[]> {
  const m = new Map<string, ProposalJ[]>();
  for (const p of ps) {
    if (p.kind !== "geometry" || !p.group) continue;
    const g = m.get(p.group) ?? [];
    g.push(p);
    m.set(p.group, g);
  }
  for (const g of m.values()) g.sort((a, b) => (a.alternative ?? a.id).localeCompare(b.alternative ?? b.id));
  return m;
}

/** A summary term as the MarginBar component wants it (margin relative to |limit|). */
export function asTerm(t: SummaryTermJ | (Omit<SummaryTermJ, "sense" | "state"> & Partial<SummaryTermJ>), state?: string) {
  const lim = Math.abs(t.limit_worst ?? t.limit);
  const st = (t.state ?? (state === "failing" || state === "thin" ? state : "ample")) as SummaryTermJ["state"];
  return { ...t, sense: t.sense ?? "<=", state: st, plain: "", inputs: [], method: "", formula: "",
           margin_rel: lim > 1e-12 ? t.margin_worst / lim : null } as const;
}

/** Counts per check state for one alternative's verdict (ran, failing, thin, not run). */
export function checkCounts(cs: SummaryCheckJ[]): { run: number; failing: number; thin: number; ample: number; notRun: number } {
  const out = { run: 0, failing: 0, thin: 0, ample: 0, notRun: 0 };
  for (const c of cs) {
    if (c.state === "not run") out.notRun++;
    else {
      out.run++;
      if (c.state === "failing") out.failing++;
      else if (c.state === "thin") out.thin++;
      else out.ample++;
    }
  }
  return out;
}

/** Union of check ids across alternatives, in first-seen order (the compare view's rows). */
export function checkRows(alts: ProposalJ[]): string[] {
  const seen: string[] = [];
  for (const p of alts) for (const c of p.evaluation?.after?.intent_checks ?? []) if (!seen.includes(c.id)) seen.push(c.id);
  return seen;
}

// ------------------------------------------------------------------ component ghosts

export interface GhostPose {
  shape: "cylinder" | "box";
  position: [number, number, number];
  /** Columns of the rotation: local x, y, z in world (cylinder: y = its axis). */
  basis: [number[], number[], number[]];
  /** Cylinder: [radius, length]; box: [along, across, down] sizes. */
  size: number[];
  dashed: boolean;
}

function unit(v: number[]): number[] {
  const n = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / n, v[1] / n, v[2] / n];
}

function cross(a: number[], b: number[]): number[] {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}

/** Where and how to draw a ghost: unreviewed (model-made) ghosts are dashed, reviewed solid. */
export function ghostPose(g: GhostJ): GhostPose {
  const pos = [g.center[0], g.center[1], g.center[2]] as [number, number, number];
  if (g.shape === "cylinder") {
    const y = unit(g.axis ?? [1, 0, 0]);
    const ref = Math.abs(y[2]) < 0.9 ? [0, 0, 1] : [1, 0, 0];
    const x = unit(cross(y, ref));
    const z = cross(x, y);
    return { shape: "cylinder", position: pos, basis: [x, y, z], size: [(g.diameter ?? 0) / 2, g.length ?? 0],
             dashed: !g.reviewed };
  }
  const ax = (g.axes ?? [[1, 0, 0], [0, 1, 0], [0, 0, 1]]).map(unit);
  return { shape: "box", position: pos, basis: [ax[0], ax[1], ax[2]], size: g.size ?? [0, 0, 0], dashed: !g.reviewed };
}

/** One ghost per component: the first one listed (the nominal pose its checks computed). */
export function ghostsToShow(b: BuildJ | null): GhostJ[] {
  const out: GhostJ[] = [];
  const seen = new Set<string>();
  for (const g of b?.ghosts ?? []) {
    if (seen.has(g.component)) continue;
    seen.add(g.component);
    out.push(g);
  }
  return out;
}

/** A not-run reason without the long list of what exists ("'cradle_seat' is not an export (…)"):
 *  the full text stays in the tooltip. */
export function shortReason(r: string): string {
  const i = r.indexOf(" (");
  return i > 20 ? r.slice(0, i) : r;
}

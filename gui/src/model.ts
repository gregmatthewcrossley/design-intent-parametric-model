// Pure view-model logic: row layouts for WHY / HOW, the shared-element mapping for the
// WHY <-> HOW transition, and "what is connected to this selection" (docs/gui.md §2 item 9, §3).

import type { BuildJ, FeatureJ, Selection, Status } from "./types";

export type View = "why" | "how";

export interface Chip {
  key: string; // flip key, e.g. "feat:A.P.holes" or "node:A.P"
  kind: "feature" | "node" | "instance";
  id: string; // feature id or node id
  label: string;
  status: Status;
}

export interface Row {
  key: string;
  kind: "node" | "feature" | "group";
  id: string;
  depth: number;
  index?: number; // build order (features)
  label: string; // id shown in mono
  sub: string; // description
  status: Status;
  chips: Chip[];
  uses: string[]; // feature ids this row's feature (or chips) use
  implicit?: boolean;
}

export const STATUS_RANK: Record<Status, number> = { ok: 0, not_built: 1, warn: 2, fail: 3 };

export function worst(statuses: Status[]): Status {
  return statuses.reduce<Status>((a, b) => (STATUS_RANK[b] > STATUS_RANK[a] ? b : a), "ok");
}

export function featureMap(b: BuildJ): Map<string, FeatureJ> {
  return new Map(b.features.map((f) => [f.id, f]));
}

export function nodeDepth(b: BuildJ, id: string): number {
  let d = 0;
  let p = b.tree.nodes[id]?.parent ?? null;
  while (p !== null && b.tree.nodes[p]) {
    d++;
    p = b.tree.nodes[p].parent;
  }
  return d;
}

/** True if `n` is `anc` or lies beneath it in the intent tree.  The conventional root "R"
 *  parents every top-level id (src/dipm/connections.py), so everything lies beneath R. */
export function isUnder(n: string, anc: string): boolean {
  return n === anc || n.startsWith(anc + ".") || anc === "R";
}

export function shortOp(f: FeatureJ): string {
  if (f.lowered_from) {
    const m = /^(\w+)\(/.exec(f.lowered_from);
    const word = m ? m[1] : f.lowered_from;
    const n = Object.keys(f.instances).length;
    return n > 1 ? `${word} ×${n}` : word;
  }
  return f.op;
}

/** WHY: the intent tree is primary; each node shows the features that realize it as callouts. */
export function whyRows(b: BuildJ): Row[] {
  const fm = featureMap(b);
  const rows: Row[] = [];
  for (const id of b.tree.order) {
    const n = b.tree.nodes[id];
    const chips: Chip[] = n.realized_by.map((fid) => ({
      key: `feat:${fid}`, kind: "feature", id: fid, label: fid, status: fm.get(fid)?.status ?? "not_built",
    }));
    for (const [fid, k] of n.instances) {
      chips.push({ key: `inst:${fid}:${k}`, kind: "instance", id: fid, label: `${fid}[${k}]`,
                   status: fm.get(fid)?.status ?? "not_built" });
    }
    const uses = Array.from(new Set(n.realized_by.flatMap((fid) => fm.get(fid)?.uses ?? [])));
    rows.push({ key: `node:${id}`, kind: "node", id, depth: nodeDepth(b, id), label: id, sub: n.label,
                status: n.status, chips, uses, implicit: n.implicit });
  }
  const orphans = b.features.filter((f) => f.serves.length === 0);
  if (orphans.length) {
    rows.push({
      key: "group:no-intent", kind: "group", id: "(no intent)", depth: 0, label: "—", sub: "no intent",
      status: worst(orphans.map((f) => f.status)),
      chips: orphans.map((f) => ({ key: `feat:${f.id}`, kind: "feature", id: f.id, label: f.id, status: f.status })),
      uses: Array.from(new Set(orphans.flatMap((f) => f.uses))),
    });
  }
  return rows;
}

/** HOW: the ordered feature list is primary; each feature shows the intents it serves. */
export function howRows(b: BuildJ): Row[] {
  return [...b.features].sort((a, c) => a.index - c.index).map((f) => {
    const nodes: string[] = [...f.serves];
    for (const k of Object.keys(f.instances).sort((a, c) => Number(a) - Number(c))) {
      for (const t of f.instances[k]) if (!nodes.includes(t.node)) nodes.push(t.node);
    }
    return {
      key: `feat:${f.id}`, kind: "feature", id: f.id, depth: 0, index: f.index, label: f.id, sub: shortOp(f),
      status: f.status, uses: f.uses,
      chips: nodes.map((n) => ({ key: `node:${n}`, kind: "node", id: n, label: n,
                                 status: b.tree.nodes[n]?.status ?? "ok" })),
    } as Row;
  });
}

export function rowsFor(b: BuildJ, view: View): Row[] {
  return view === "why" ? whyRows(b) : howRows(b);
}

/** Flip keys of a layout in document order: each row, then its chips. */
export function layoutKeys(rows: Row[]): string[] {
  const out: string[] = [];
  for (const r of rows) {
    out.push(r.key);
    for (const c of r.chips) out.push(c.key);
  }
  return out;
}

/** Shared elements of a WHY <-> HOW transition: keys present in both layouts (first occurrence
 *  of each), split by whether the element changes role (row <-> callout) or keeps it. */
export function transitionMap(from: Row[], to: Row[]): { shared: string[]; morph: string[]; enter: string[]; exit: string[] } {
  const role = (rows: Row[]) => {
    const m = new Map<string, "row" | "chip">();
    for (const r of rows) {
      if (!m.has(r.key)) m.set(r.key, "row");
      for (const c of r.chips) if (!m.has(c.key)) m.set(c.key, "chip");
    }
    return m;
  };
  const a = role(from), b = role(to);
  const shared = [...b.keys()].filter((k) => a.has(k));
  return {
    shared,
    morph: shared.filter((k) => a.get(k) !== b.get(k)),
    enter: [...b.keys()].filter((k) => !a.has(k)),
    exit: [...a.keys()].filter((k) => !b.has(k)),
  };
}

export interface Lit {
  nodes: Set<string>;
  features: Set<string>;
  params: Set<string>;
  faces: Set<number>;
  primaryNode: string | null;
  primaryFeature: string | null;
  indirectFeatures: Set<string>; // e.g. driven by a parameter only through `uses`
}

export function emptyLit(): Lit {
  return { nodes: new Set(), features: new Set(), params: new Set(), faces: new Set(), primaryNode: null,
           primaryFeature: null, indirectFeatures: new Set() };
}

function featureNodes(f: FeatureJ): string[] {
  const out = [...f.nodes];
  for (const ts of Object.values(f.instances)) for (const t of ts) if (!out.includes(t.node)) out.push(t.node);
  return out;
}

/** Everything connected to a selection, in every view (docs/gui.md §2 item 9). */
export function connected(sel: Selection | null, b: BuildJ | null): Lit {
  const lit = emptyLit();
  if (!sel || !b) return lit;
  const fm = featureMap(b);
  const addFeature = (fid: string) => {
    const f = fm.get(fid);
    if (!f) return;
    lit.features.add(fid);
    for (const n of f.nodes) lit.nodes.add(n);
    for (const p of f.params) lit.params.add(p);
  };
  const facesOfFeatures = (fids: Set<string>) => {
    for (const face of b.faces) if (face.features.some((x) => fids.has(x))) lit.faces.add(face.id);
  };
  switch (sel.kind) {
    case "face": {
      const face = b.faces[sel.id];
      if (!face) break;
      lit.faces.add(face.id);
      for (const n of face.nodes) lit.nodes.add(n);
      for (const fid of face.features) {
        lit.features.add(fid);
        for (const p of fm.get(fid)?.params ?? []) lit.params.add(p);
      }
      lit.primaryNode = face.nodes[0] ?? null;
      lit.primaryFeature = face.features[0] ?? null;
      break;
    }
    case "edge": {
      const e = b.edges[sel.id];
      if (!e) break;
      for (const n of e.nodes) lit.nodes.add(n);
      for (const fid of e.features) lit.features.add(fid);
      for (const fi of e.derived_from) lit.faces.add(fi);
      lit.primaryNode = e.nodes[0] ?? null;
      break;
    }
    case "node": {
      lit.primaryNode = sel.id;
      for (const id of Object.keys(b.tree.nodes)) if (isUnder(id, sel.id)) lit.nodes.add(id);
      for (const face of b.faces) if (face.nodes.some((n) => isUnder(n, sel.id))) lit.faces.add(face.id);
      for (const f of b.features) {
        if (featureNodes(f).some((n) => isUnder(n, sel.id))) {
          lit.features.add(f.id);
          for (const p of f.params) lit.params.add(p);
        }
      }
      break;
    }
    case "feature": {
      lit.primaryFeature = sel.id;
      addFeature(sel.id);
      const f = fm.get(sel.id);
      for (const n of f ? featureNodes(f) : []) lit.nodes.add(n);
      for (const u of f?.uses ?? []) lit.indirectFeatures.add(u);
      facesOfFeatures(new Set([sel.id]));
      break;
    }
    case "param": {
      lit.params.add(sel.id);
      for (const f of b.features) {
        if (f.params.includes(sel.id)) {
          lit.features.add(f.id);
          for (const n of f.nodes) lit.nodes.add(n);
        } else if (f.params_all.includes(sel.id)) {
          lit.indirectFeatures.add(f.id);
        }
      }
      facesOfFeatures(lit.features);
      break;
    }
  }
  return lit;
}

/** "feature · role" for the viewport tooltip. */
export function faceLabel(b: BuildJ, faceId: number): string {
  const f = b.faces[faceId];
  if (!f) return "";
  const e = f.entries[0];
  if (!e) return `${f.descriptor} (untracked)`;
  const role = e.source !== null ? `${e.role}(${e.source})` : e.role;
  return `${e.feature} · ${role}`;
}

export function fmtNumber(x: unknown, digits = 4): string {
  if (typeof x !== "number") return String(x);
  if (Number.isInteger(x)) return String(x);
  return Number(x.toPrecision(digits)).toString();
}

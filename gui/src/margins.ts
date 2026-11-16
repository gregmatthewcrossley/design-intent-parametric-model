// Margins and the margin heatmap (docs/gui.md §8.3 items 2 and 9; tolerance-uncertainty §3):
// faces are coloured by the smallest margin among the intent checks they take part in, green
// ample → amber thin → red failing, grey where no check applies.  Pure; tests/margins.test.ts.

import type { BuildJ, IntentCheckJ } from "./types";

export type MarginState = "ample" | "thin" | "failing" | "none";

const RANK: Record<MarginState, number> = { failing: 0, thin: 1, ample: 2, none: 3 };

export interface FaceMargin {
  state: MarginState;
  rel: number | null; // worst-case margin / |limit| of the deciding check
  checks: string[]; // every check the face takes part in
  by: string | null; // the deciding check
}

/** The smaller (worse) of two margins: state first, then relative margin. */
export function worse(a: FaceMargin, b: FaceMargin): FaceMargin {
  if (RANK[a.state] !== RANK[b.state]) return RANK[a.state] < RANK[b.state] ? a : b;
  const ra = a.rel ?? Infinity, rb = b.rel ?? Infinity;
  return ra <= rb ? a : b;
}

export function checkMargin(c: IntentCheckJ): FaceMargin {
  const st = (c.state === "not run" ? "none" : c.state) as MarginState;
  return { state: st, rel: c.headline?.margin_rel ?? null, checks: [c.id], by: c.id };
}

/** Per face: the smallest margin among the checks that ran and involve it. */
export function faceMargins(b: BuildJ): FaceMargin[] {
  const out: FaceMargin[] = b.faces.map(() => ({ state: "none", rel: null, checks: [], by: null }));
  for (const c of b.intent_checks ?? []) {
    if (c.state === "not run") continue;
    const m = checkMargin(c);
    for (const f of c.faces ?? []) {
      if (f < 0 || f >= out.length) continue;
      const cur = out[f];
      const w = cur.state === "none" ? m : worse(cur, m);
      out[f] = { ...w, checks: [...cur.checks, c.id] };
    }
  }
  return out;
}

/** Heatmap colour for a margin: a palette token name plus how strongly to apply it. */
export function heatColor(m: FaceMargin): { token: "ok" | "warn" | "fail" | "none"; strength: number } {
  switch (m.state) {
    case "failing": return { token: "fail", strength: 1 };
    case "thin": return { token: "warn", strength: 1 };
    case "ample": {
      // deeper green for larger margins (rel ≥ 1 is full strength)
      const r = m.rel === null ? 1 : Math.max(0, Math.min(1, m.rel));
      return { token: "ok", strength: 0.55 + 0.45 * r };
    }
    default: return { token: "none", strength: 1 };
  }
}

/** Where to draw the marks of a margin bar (0..1 across the bar, zero margin in the middle). */
export function marginBar(nominalRel: number | null, worstRel: number | null, span = 1):
  { zero: number; nominal: number; worst: number; offLeft: boolean; offRight: boolean; negative: boolean } {
  const pos = (r: number | null) => r === null ? 0.5 : 0.5 + Math.max(-1, Math.min(1, r / span)) * 0.5;
  const w = worstRel ?? nominalRel ?? 0;
  return {
    zero: 0.5, nominal: pos(nominalRel), worst: pos(worstRel),
    offLeft: (worstRel ?? 0) < -span || (nominalRel ?? 0) < -span,
    offRight: (nominalRel ?? 0) > span,
    negative: w < 0,
  };
}

export const STATE_TEXT: Record<string, string> = {
  ample: "ample margin", thin: "thin margin", failing: "failing", "not run": "not run", none: "no check",
};

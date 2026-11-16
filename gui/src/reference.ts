// Reference objects (docs/gui.md §8.3 item 14): one at a time, chosen by context.  A screw
// generated from the hole's spec when a screw hole is under the cursor; a fingertip next to small
// controls; a hand or an ID-1 card for the part as a whole.  Pure choice logic, tested in
// tests/reference.test.ts; the geometry is built in viewer.ts.

import type { BuildJ } from "./types";

export type RefKind = "screw" | "fingertip" | "hand" | "card";

export interface RefChoice {
  kind: RefKind;
  label: string;
  screw?: string; // e.g. "#8"
  face?: number;
  feature?: string;
  centre?: [number, number, number];
  axis?: [number, number, number];
}

/** Largest overall dimension (mm) for which the card, rather than a hand, is the whole-part reference. */
export const CARD_MAX_PART_MM = 120;
/** Features at most this size (mm) without a screw read as "small controls" -> fingertip. */
export const FINGERTIP_MAX_MM = 20;

export function partSize(bounds: { min: number[]; max: number[] }): number {
  return Math.max(...bounds.max.map((x, i) => x - bounds.min[i]));
}

/** Choose the reference object for the hovered face (or the whole part). */
export function chooseReference(b: BuildJ, face: number | null, part: { min: number[]; max: number[] }): RefChoice {
  if (face !== null && b.faces[face]) {
    const f = b.faces[face];
    const e = f.entries[0];
    if (e && ["wall", "countersink", "floor"].includes(e.role)) {
      const feat = b.features.find((x) => x.id === e.feature);
      const d = (feat?.detail ?? {}) as Record<string, unknown>;
      const k = Number(e.source ?? 0);
      const centres = d.centres as number[][] | undefined;
      const screw = d.screw as string | null | undefined;
      const centre = centres?.[k] as [number, number, number] | undefined;
      const axis = d.normal as [number, number, number] | undefined;
      if (screw && b.references?.screws?.[screw]) {
        return { kind: "screw", label: `${screw} screw`, screw, face, feature: e.feature, centre, axis };
      }
      const dia = Number(d.diameter ?? 0);
      if (dia > 0 && dia <= FINGERTIP_MAX_MM) {
        return { kind: "fingertip", label: "fingertip", face, feature: e.feature, centre, axis };
      }
    }
  }
  return partSize(part) <= CARD_MAX_PART_MM ? { kind: "card", label: "ID-1 card (85.6 × 54 mm)" } :
    { kind: "hand", label: "hand" };
}

/** Where to put a ghost of half-width `halfW` beside the part, never overlapping it: from
 *  `anchor` (the hovered feature, or the part's centre) along `dir` (the camera's screen-right,
 *  perpendicular to the view, so the ghost stays at the anchor's depth and in focus) until it
 *  clears every corner of the part's bounding box by `gap`. */
export function besidePart(part: { min: number[]; max: number[] }, anchor: number[], dir: number[], halfW: number,
                           gap = 12): [number, number, number] {
  const n = Math.hypot(dir[0], dir[1], dir[2]) || 1;
  const d = dir.map((x) => x / n);
  let ext = 0;
  for (const x of [part.min[0], part.max[0]]) for (const y of [part.min[1], part.max[1]]) for (const z of [part.min[2], part.max[2]]) {
    ext = Math.max(ext, (x - anchor[0]) * d[0] + (y - anchor[1]) * d[1] + (z - anchor[2]) * d[2]);
  }
  const k = ext + gap + halfW;
  return [anchor[0] + d[0] * k, anchor[1] + d[1] * k, anchor[2] + d[2] * k];
}

// Pure scale logic (docs/gui.md §8.3 items 12 and 15): the adaptive scale bar, 1:1 real-size
// math, the nearest standard view, and ID-1 card calibration.  Unit-tested in tests/scale.test.ts.

export interface DisplayJ {
  id: number | string;
  name: string;
  builtin?: boolean;
  main?: boolean;
  mm: [number, number];
  px: [number, number]; // points (= CSS px at 100 % zoom on macOS)
  origin?: [number, number];
  scale?: number | null; // backing pixels per point (2 on a Retina panel)
  plausible: boolean;
  implausible_reason?: string;
}

export interface DisplayInfo {
  source: string;
  displays: DisplayJ[];
  match?: { index: number | null; display: DisplayJ | null; reason: string };
}

/** ID-1 card (ISO/IEC 7810), the calibration object and the familiar-size reference (§8.6.1). */
export const ID1 = { width: 85.6, height: 53.98, radius: 3.18 };
/** Coins for the optional calibration check (diameters in mm). */
export const COINS: Record<string, number> = { "€1": 23.25, "US quarter": 24.26 };

/** Scale bar: the longest 1 / 2 / 5 × 10ⁿ mm step whose length is at most `maxPx` CSS px
 *  (and at least maxPx / 2.5, which a 1-2-5 series always allows). */
export function scaleBarStep(pxPerMm: number, maxPx = 120): { mm: number; px: number; label: string } {
  if (!(pxPerMm > 0) || !isFinite(pxPerMm)) return { mm: 0, px: 0, label: "" };
  const maxMm = maxPx / pxPerMm;
  const e = Math.floor(Math.log10(maxMm));
  let best = Math.pow(10, e);
  for (const m of [1, 2, 5, 10]) {
    const v = m * Math.pow(10, e);
    if (v <= maxMm * (1 + 1e-9)) best = v;
  }
  const mm = +best.toPrecision(6);
  return { mm, px: mm * pxPerMm, label: formatMm(mm) };
}

export function formatMm(mm: number): string {
  if (mm >= 1000) return `${+(mm / 1000).toPrecision(3)} m`;
  if (mm >= 10) return `${+(mm / 10).toPrecision(3)} cm`;
  if (mm >= 1) return `${+mm.toPrecision(3)} mm`;
  return `${+(mm * 1000).toPrecision(3)} µm`;
}

/** CSS px per physical mm for a display, given the browser's screen width in CSS px and
 *  devicePixelRatio.  Browser zoom: if the reported screen width already reflects the zoom
 *  (it differs from the display's point width) it is used directly (tolerance §4: screen width
 *  in CSS px ÷ width in mm); otherwise the zoom is recovered from dpr ÷ backing scale. */
export function cssPxPerMm(d: DisplayJ, screenCssWidth: number, dpr: number): number {
  const ptsPerMm = d.px[0] / d.mm[0];
  if (screenCssWidth > 0 && Math.abs(screenCssWidth - d.px[0]) > 1.5) return screenCssWidth / d.mm[0];
  const zoom = d.scale && d.scale > 0 && dpr > 0 ? dpr / d.scale : 1;
  return ptsPerMm / zoom;
}

/** Is a px/mm value believable for a real screen (some TVs report nonsense)? */
export function plausiblePxPerMm(v: number): boolean {
  return isFinite(v) && v >= 1 && v <= 40;
}

/** World height (mm) an orthographic camera must show so 1 mm on the model is 1 mm on the glass. */
export function orthoHeightMm(canvasCssHeight: number, pxPerMm: number): number {
  return canvasCssHeight / pxPerMm;
}

export type StdView = "front" | "back" | "right" | "left" | "top" | "bottom";

/** Standard view directions (from the target towards the camera; Z up, the engine's convention). */
export const STD_DIRS: Record<StdView, [number, number, number]> = {
  front: [0, 1, 0], back: [0, -1, 0], right: [1, 0, 0], left: [-1, 0, 0], top: [0, 0, 1], bottom: [0, 0, -1],
};

/** The standard view nearest a camera direction (target -> camera). */
export function nearestStdView(dir: [number, number, number]): StdView {
  let best: StdView = "front", bd = -Infinity;
  for (const [k, v] of Object.entries(STD_DIRS) as [StdView, [number, number, number]][]) {
    const d = v[0] * dir[0] + v[1] * dir[1] + v[2] * dir[2];
    if (d > bd + 1e-9) { bd = d; best = k; }
  }
  return best;
}

/** px/mm from an on-screen card the user matched to a real ID-1 card (its width in CSS px). */
export function calibrate(cardCssWidth: number): number {
  return cardCssWidth / ID1.width;
}

/** A key for the screen a calibration belongs to. */
export function screenKey(w: number, h: number, dpr: number): string {
  return `${Math.round(w)}x${Math.round(h)}@${+dpr.toFixed(3)}`;
}

/** Pixels per mm of a perspective camera at distance `dist` (the orbit target). */
export function perspectivePxPerMm(canvasCssHeight: number, fovDeg: number, dist: number): number {
  return canvasCssHeight / (2 * dist * Math.tan((fovDeg * Math.PI) / 360));
}

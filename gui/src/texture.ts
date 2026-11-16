// Process texture (docs/gui.md §8.3 item 13): FDM layer lines at the real pitch along the build
// direction, and top-surface extrusion lines.  Shading only (normal and roughness), never colour.
// Detail fades in once its real pitch spans about 2 screen pixels and is fully in by 4, so it
// disappears before it can alias (Nyquist: a period needs at least 2 pixels).  The shader in
// viewer.ts uses the same constants with fwidth(); tests/texture.test.ts checks this mapping.

export const FADE_START_PX = 2;
export const FADE_FULL_PX = 4;

export function smoothstep(e0: number, e1: number, x: number): number {
  const t = Math.max(0, Math.min(1, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
}

/** Strength (0..1) of a periodic detail whose period spans `pitchPx` screen pixels. */
export function textureFade(pitchPx: number): number {
  return smoothstep(FADE_START_PX, FADE_FULL_PX, pitchPx);
}

/** Screen pixels spanned by a pitch (mm) at a given scale (CSS px per mm × device pixel ratio). */
export function pitchPx(pitchMm: number, cssPxPerMm: number, dpr = 1): number {
  return pitchMm * cssPxPerMm * dpr;
}

/** Zoom (CSS px per mm) at which a pitch becomes visible / fully drawn. */
export function visibleFrom(pitchMm: number, dpr = 1): { start: number; full: number } {
  return { start: FADE_START_PX / (pitchMm * dpr), full: FADE_FULL_PX / (pitchMm * dpr) };
}

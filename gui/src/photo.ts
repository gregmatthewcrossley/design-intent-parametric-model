// Photo view optics (docs/gui.md §8.3 item 11; tolerance-uncertainty.md §4.1): a thin-lens camera
// whose depth of field narrows as magnification rises, with the blur capped so the focused
// feature and labels stay readable.  Pure functions, unit-tested in tests/photo.test.ts; the
// DOF shader in viewer.ts computes the same circle of confusion per pixel.

/** Sensor height of the simulated camera (mm): full frame, 36 × 24 mm. */
export const SENSOR_H = 24;
/** Aperture (f-number).  f/4 gives tabletop-photo depth of field at the part's scale. */
export const F_NUMBER = 4;
/** Largest blur radius in CSS px: blur beyond this would hide shapes rather than suggest scale. */
export const BLUR_CAP_PX = 12;
/** Focus easing time constant (ms); 0 under prefers-reduced-motion. */
export const FOCUS_TAU_MS = 140;

/** Focal length (mm) of a lens whose vertical field of view is `fovDeg` on the sensor. */
export function focalLength(fovDeg: number, sensorH = SENSOR_H): number {
  return sensorH / 2 / Math.tan((fovDeg * Math.PI) / 360);
}

/** Thin-lens magnification at focus distance s (mm). */
export function magnification(f: number, s: number): number {
  return s > f ? f / (s - f) : Infinity;
}

/** Diameter of the circle of confusion on the sensor (mm) for an object at distance d when
 *  focused at s (thin lens: c = f² / (N (s − f)) · |d − s| / d). */
export function cocMm(f: number, N: number, s: number, d: number): number {
  if (d <= 0 || s <= f) return 0;
  return ((f * f) / (N * (s - f))) * (Math.abs(d - s) / d);
}

/** Blur radius on screen (CSS px), uncapped. */
export function cocPx(f: number, N: number, s: number, d: number, viewportCssH: number, sensorH = SENSOR_H): number {
  return (cocMm(f, N, s, d) / sensorH) * viewportCssH * 0.5;
}

/** The capped blur radius the shader applies. */
export function cappedBlur(px: number, cap = BLUR_CAP_PX): number {
  return Math.max(0, Math.min(cap, px));
}

/** One easing step of the focus distance towards its target (exponential, frame-rate independent). */
export function easeFocus(current: number, target: number, dtMs: number, tauMs = FOCUS_TAU_MS): number {
  if (tauMs <= 0 || !isFinite(current)) return target;
  const k = 1 - Math.exp(-Math.max(0, dtMs) / tauMs);
  return current + (target - current) * k;
}

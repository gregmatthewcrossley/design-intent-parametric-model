// 1:1 real size (docs/gui.md §8.3 item 12; tolerance-uncertainty §4 item 2).  The browser reports
// its screen (CSS-px size, devicePixelRatio, and on Chromium the Window Management API's details
// when permission was already granted); the engine (`GET /api/display`) reports physical sizes
// from the OS and picks the display; px/mm = screen width (CSS px) ÷ width (mm), recomputed when
// the window moves to another screen or the browser zoom changes.  If the size is missing or
// implausible, a one-time ID-1 card calibration (stored per screen) is used instead.

import { signal } from "@preact/signals";
import { calibrate, cssPxPerMm, plausiblePxPerMm, screenKey, type DisplayInfo, type DisplayJ } from "./scale";

export interface RealSize {
  pxPerMm: number | null;
  source: "os" | "calibration" | "none";
  display: DisplayJ | null;
  name: string;
  reason: string;
}

export const realSize = signal<RealSize>({ pxPerMm: null, source: "none", display: null, name: "", reason: "" });
export const needCalibration = signal(false);
export const lastDisplays = signal<DisplayInfo | null>(null);

function stored(): Record<string, number> {
  try { return JSON.parse(localStorage.getItem("dipm.calibration") ?? "{}"); } catch { return {}; }
}

export function currentScreen(): { width: number; height: number; dpr: number; label?: string; internal?: boolean;
                                   left?: number; top?: number } {
  const s = window.screen as Screen & { label?: string; isInternal?: boolean; availLeft?: number; availTop?: number };
  return { width: s.width, height: s.height, dpr: window.devicePixelRatio || 1,
           label: s.label, internal: s.isInternal, left: s.availLeft, top: s.availTop };
}

async function windowManagementDetails(): Promise<{ label?: string; internal?: boolean } | null> {
  // Only when permission is already granted: never prompt just to measure.
  try {
    const perm = await navigator.permissions?.query({ name: "window-management" as PermissionName });
    if (perm?.state !== "granted") return null;
    const w = window as unknown as { getScreenDetails?: () => Promise<{ currentScreen: { label: string; isInternal: boolean } }> };
    if (!w.getScreenDetails) return null;
    const d = await w.getScreenDetails();
    return { label: d.currentScreen.label, internal: d.currentScreen.isInternal };
  } catch {
    return null;
  }
}

/** Ask the engine and compute px/mm for the screen this window is on. */
export async function measure(override?: Partial<ReturnType<typeof currentScreen>>): Promise<RealSize> {
  const scr = { ...currentScreen(), ...(await windowManagementDetails()), ...(override ?? {}) };
  const q = new URLSearchParams({ width: String(scr.width), height: String(scr.height), dpr: String(scr.dpr) });
  if (scr.label) q.set("label", scr.label);
  if (scr.internal !== undefined) q.set("internal", String(scr.internal));
  if (scr.left !== undefined) q.set("left", String(scr.left));
  if (scr.top !== undefined) q.set("top", String(scr.top));
  let info: DisplayInfo | null = null;
  try {
    const r = await fetch(`/api/display?${q}`);
    info = r.ok ? ((await r.json()) as DisplayInfo) : null;
  } catch {
    info = null;
  }
  lastDisplays.value = info;
  const d = info?.match?.display ?? null;
  let out: RealSize;
  if (d && d.plausible) {
    const v = cssPxPerMm(d, scr.width, scr.dpr);
    out = plausiblePxPerMm(v) ? { pxPerMm: v, source: "os", display: d, name: d.name, reason: info?.match?.reason ?? "" } :
      { pxPerMm: null, source: "none", display: d, name: d.name, reason: `${v.toFixed(2)} px/mm is implausible` };
  } else {
    out = { pxPerMm: null, source: "none", display: d, name: d?.name ?? "",
            reason: d ? (d.implausible_reason || "implausible size") : (info?.source === "unknown" ?
              "this OS does not report the screen's physical size" : "no display information") };
  }
  if (out.pxPerMm === null) {
    const cal = stored()[screenKey(scr.width, scr.height, scr.dpr)];
    if (cal && plausiblePxPerMm(cal)) {
      out = { pxPerMm: cal, source: "calibration", display: d, name: d?.name || "this screen", reason: "calibrated with a card" };
    }
  }
  realSize.value = out;
  needCalibration.value = out.pxPerMm === null;
  return out;
}

export function saveCalibration(cardCssWidth: number): number {
  const v = calibrate(cardCssWidth);
  const s = currentScreen();
  const all = stored();
  all[screenKey(s.width, s.height, s.dpr)] = v;
  try { localStorage.setItem("dipm.calibration", JSON.stringify(all)); } catch { /* private mode */ }
  realSize.value = { pxPerMm: v, source: "calibration", display: realSize.value.display,
                     name: realSize.value.name || "this screen", reason: "calibrated with a card" };
  needCalibration.value = false;
  return v;
}

/** Recompute on screen change (window moved), browser zoom (devicePixelRatio) and resize. */
export function watchScreen(onChange: () => void): () => void {
  let mq: MediaQueryList | null = null;
  const arm = () => {
    mq?.removeEventListener("change", fire);
    mq = matchMedia(`(resolution: ${window.devicePixelRatio}dppx)`);
    mq.addEventListener("change", fire);
  };
  const fire = () => { arm(); onChange(); };
  arm();
  let last = `${screen.width}x${screen.height}@${window.devicePixelRatio}:${(screen as Screen & { availLeft?: number }).availLeft ?? 0}`;
  const poll = () => {
    const k = `${screen.width}x${screen.height}@${window.devicePixelRatio}:${(screen as Screen & { availLeft?: number }).availLeft ?? 0}`;
    if (k !== last) { last = k; onChange(); }
  };
  const t = setInterval(poll, 1000);
  const sc = window.screen as Screen & { addEventListener?: (t: string, f: () => void) => void;
                                         removeEventListener?: (t: string, f: () => void) => void };
  sc.addEventListener?.("change", onChange);
  window.addEventListener("resize", poll);
  return () => {
    mq?.removeEventListener("change", fire);
    clearInterval(t);
    sc.removeEventListener?.("change", onChange);
    window.removeEventListener("resize", poll);
  };
}

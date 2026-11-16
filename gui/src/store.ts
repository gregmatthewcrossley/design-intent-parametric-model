// Application state (Preact signals) and the actions that talk to the server.

import { computed, signal } from "@preact/signals";
import { api } from "./api";
import { connected, type View } from "./model";
import type { BuildJ, DesignInfo, Selection } from "./types";

export type Theme = "light" | "dark";
export type Tab = "viewport" | "tree" | "inspector" | "checks" | "interpretations";

function stored<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(`dipm.${key}`);
    return v === null ? fallback : (JSON.parse(v) as T);
  } catch {
    return fallback;
  }
}

export function persist(key: string, value: unknown): void {
  try {
    localStorage.setItem(`dipm.${key}`, JSON.stringify(value));
  } catch {
    /* private mode: ignore */
  }
}

const prefersDark = typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches;

export const design = signal<DesignInfo | null>(null);
export const build = signal<BuildJ | null>(null); // latest build (may have failed)
export const goodBuild = signal<BuildJ | null>(null); // last PASS build
export const params = signal<Record<string, number | string>>({});
export const building = signal(false);
export const buildError = signal<string | null>(null);
export const roundTripMs = signal<number | null>(null);
export const designError = signal<string | null>(null);
export const wsUp = signal(false);
export const lastEvent = signal<string>("");

export const view = signal<View>(stored<View>("view", "why"));
export const showLinks = signal<boolean>(stored("showLinks", true));
export const expanded = signal(false);
export const theme = signal<Theme>(stored<Theme>("theme", prefersDark ? "dark" : "light"));
export const tab = signal<Tab>("viewport");
export const showGhost = signal(true);

export const hover = signal<Selection | null>(null);
export const selection = signal<Selection | null>(null);
/** What is lit: the hovered thing if any, else the pinned selection. */
export const active = computed<Selection | null>(() => hover.value ?? selection.value);
export const lit = computed(() => connected(active.value, build.value));
export const pinnedLit = computed(() => connected(selection.value, build.value));

export function sameSel(a: Selection | null, b: Selection | null): boolean {
  return !!a && !!b && a.kind === b.kind && a.id === b.id;
}

export function select(s: Selection | null): void {
  selection.value = s && sameSel(s, selection.value) ? null : s;
}

export function applyBuild(b: BuildJ): void {
  build.value = b;
  if (b.ok) goodBuild.value = b;
  params.value = { ...params.value, ...b.params };
  buildError.value = null;
  // drop a selection that no longer exists
  const s = selection.value;
  if (s?.kind === "face" && s.id >= b.faces.length) selection.value = null;
  if (s?.kind === "feature" && !b.features.some((f) => f.id === s.id)) selection.value = null;
  if (s?.kind === "node" && !b.tree.nodes[s.id]) selection.value = null;
}

let seq = 0;
let timer: ReturnType<typeof setTimeout> | null = null;
export const DEBOUNCE_MS = 140;

/** Rebuild with the current parameters (debounced; only the latest response is applied). */
export function requestBuild(immediate = false): void {
  if (timer) clearTimeout(timer);
  const run = async () => {
    const my = ++seq;
    building.value = true;
    const t0 = performance.now();
    try {
      const b = await api.build(params.value);
      if (my === seq) {
        roundTripMs.value = performance.now() - t0;
        applyBuild(b);
      }
    } catch (e) {
      if (my === seq) buildError.value = (e as Error).message;
    } finally {
      if (my === seq) building.value = false;
    }
  };
  if (immediate) void run();
  else timer = setTimeout(run, DEBOUNCE_MS);
}

export function setParam(name: string, value: number | string): void {
  params.value = { ...params.value, [name]: value };
  requestBuild();
}

export const answering = signal<string | null>(null);

export async function answer(assumptionId: string, reading: string): Promise<void> {
  answering.value = assumptionId;
  try {
    applyBuild(await api.answer(assumptionId, reading));
  } catch (e) {
    buildError.value = (e as Error).message;
  } finally {
    answering.value = null;
  }
}

// Classic CAD layout (docs/gui.md §3): header strip; left WHY⇄HOW panel | viewport | right
// panel (inspector, checks, interpretations); parameter bar.  Side panels resize and collapse;
// below 1024 px the panels become tabs over the viewport.

import { signal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { api, connectEvents } from "./api";
import { Connections } from "./components/Connections";
import { Header } from "./components/Header";
import { IntentPanel, useEscapeToClear } from "./components/IntentPanel";
import { ParamBar } from "./components/ParamBar";
import { RightPanel, Inspector, Checks, Interpretations } from "./components/RightPanel";
import { Viewport, useViewKeys } from "./components/Viewport";
import {
  applyBuild, build, design, designError, expanded, lastEvent, params, persist, requestBuild, tab, theme, wsUp,
  type Tab,
} from "./store";

function stored(key: string, fallback: number): number {
  try { return Number(localStorage.getItem(`dipm.${key}`) ?? fallback) || fallback; } catch { return fallback; }
}

const leftW = signal(stored("leftW", 340));
const rightW = signal(stored("rightW", 360));
const leftOpen = signal(true);
const rightOpen = signal(true);
const narrow = signal(typeof matchMedia !== "undefined" && matchMedia("(max-width: 1023px)").matches);

function Resizer({ side }: { side: "left" | "right" }) {
  const onDown = (e: PointerEvent) => {
    e.preventDefault();
    const x0 = e.clientX, w0 = side === "left" ? leftW.value : rightW.value;
    const move = (m: PointerEvent) => {
      const dx = m.clientX - x0;
      const w = Math.max(220, Math.min(720, side === "left" ? w0 + dx : w0 - dx));
      if (side === "left") leftW.value = w; else rightW.value = w;
    };
    const up = () => {
      removeEventListener("pointermove", move);
      removeEventListener("pointerup", up);
      persist(side === "left" ? "leftW" : "rightW", side === "left" ? leftW.value : rightW.value);
    };
    addEventListener("pointermove", move);
    addEventListener("pointerup", up);
  };
  return <div class={`resizer resizer-${side}`} onPointerDown={onDown} role="separator" aria-orientation="vertical"
              aria-label={`resize ${side} panel`} />;
}

const TABS: [Tab, string][] = [["viewport", "Model"], ["tree", "WHY ⇄ HOW"], ["inspector", "Inspector"],
                               ["checks", "Checks"], ["interpretations", "Interpretations"]];

export function App() {
  useEscapeToClear();
  useViewKeys();

  useEffect(() => {
    document.documentElement.dataset.theme = theme.value;
  }, [theme.value]);

  useEffect(() => {
    const mq = matchMedia("(max-width: 1023px)");
    const h = () => (narrow.value = mq.matches);
    mq.addEventListener("change", h);
    return () => mq.removeEventListener("change", h);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const d = await api.design();
        design.value = d;
        const p: Record<string, number | string> = {};
        for (const x of d.params) p[x.name] = x.default;
        params.value = { ...p, ...(d.current_params ?? {}) };
        requestBuild(true);
      } catch (e) {
        designError.value = (e as Error).message;
      }
    })();
    return connectEvents((ev) => {
      lastEvent.value = ev.type;
      if (ev.type === "design-changed") {
        design.value = ev.design;
        designError.value = null;
        const known = new Set(ev.design.params.map((p) => p.name));
        const p: Record<string, number | string> = {};
        for (const x of ev.design.params) p[x.name] = params.value[x.name] ?? x.default;
        for (const k of Object.keys(params.value)) if (!known.has(k)) delete p[k];
        params.value = p;
      } else if (ev.type === "rebuilt") {
        applyBuild(ev.build);
      } else if (ev.type === "design-error") {
        designError.value = ev.message;
      } else if (ev.type === "hello" && build.value) {
        requestBuild(true); // reconnected: catch up
      }
    }, (up) => (wsUp.value = up));
  }, []);

  const n = narrow.value;
  const cols = n ? "1fr" :
    `${leftOpen.value ? `${leftW.value}px` : "30px"} 1fr ${rightOpen.value ? `${rightW.value}px` : "30px"}`;
  return (
    <div class={`app ${n ? "narrow" : "wide"} ${expanded.value ? "expanded" : ""}`}>
      <Header />
      {n && (
        <nav class="tabs" role="tablist">
          {TABS.map(([t, label]) => (
            <button key={t} role="tab" aria-selected={tab.value === t} class={tab.value === t ? "on" : ""}
                    onClick={() => (tab.value = t)}>{label}</button>
          ))}
        </nav>
      )}
      <main class="main" style={{ gridTemplateColumns: cols }}>
        {!n && (
          <aside class={`panel left ${leftOpen.value ? "" : "collapsed"}`} aria-label="intent and features">
            {leftOpen.value ? <IntentPanel /> : null}
            <button class="collapse-btn" onClick={() => (leftOpen.value = !leftOpen.value)}
                    title={leftOpen.value ? "collapse" : "expand"} aria-label="collapse left panel">
              {leftOpen.value ? "‹" : "›"}
            </button>
            {leftOpen.value && <Resizer side="left" />}
          </aside>
        )}
        <section class="center" aria-label="3D viewport">
          <Viewport />
          {n && tab.value !== "viewport" && (
            <div class="tab-sheet">
              {tab.value === "tree" && <IntentPanel />}
              {tab.value === "inspector" && <Inspector />}
              {tab.value === "checks" && <Checks />}
              {tab.value === "interpretations" && <Interpretations />}
            </div>
          )}
        </section>
        {!n && (
          <aside class={`panel right ${rightOpen.value ? "" : "collapsed"}`} aria-label="inspector, checks, interpretations">
            {rightOpen.value && <Resizer side="right" />}
            {rightOpen.value ? <RightPanel /> : null}
            <button class="collapse-btn" onClick={() => (rightOpen.value = !rightOpen.value)}
                    title={rightOpen.value ? "collapse" : "expand"} aria-label="collapse right panel">
              {rightOpen.value ? "›" : "‹"}
            </button>
          </aside>
        )}
        {expanded.value && (
          <div class="connections-overlay" style={n ? {} : { right: `${rightOpen.value ? rightW.value : 30}px` }}>
            <Connections />
          </div>
        )}
      </main>
      <ParamBar />
    </div>
  );
}

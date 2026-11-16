// Expanded connections view: intents ⇄ features ⇄ parameters, widened over the viewport
// (docs/gui.md §2 item 9, §3 "expanded").

import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { active, build, design, expanded, hover, lit, select, selection } from "../store";
import type { Selection } from "../types";
import { Dot } from "./common";
import { DiagnosticsSummary } from "./IntentPanel";
import { nodeDepth } from "../model";

interface Line { d: string; cls: string }

export function Connections() {
  const b = build.value, d = design.value;
  const host = useRef<HTMLDivElement>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const L = lit.value;
  const isAct = active.value !== null;

  useLayoutEffect(() => {
    const root = host.current;
    if (!root || !b) return;
    const measure = () => {
      const base = root.getBoundingClientRect();
      const box = (sel: string) => {
        const el = root.querySelector<HTMLElement>(sel);
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { l: r.left - base.left, r: r.right - base.left, cy: (r.top + r.bottom) / 2 - base.top };
      };
      const out: Line[] = [];
      const cls = (hot: boolean, kind: string) => `${kind} ${hot ? "hot" : ""} ${isAct && !hot ? "dim" : ""}`;
      for (const f of b.features) {
        const F = box(`[data-c-feat="${CSS.escape(f.id)}"]`);
        if (!F) continue;
        // feature -> the intents it serves (instances dashed)
        const inst = new Set<string>();
        for (const ts of Object.values(f.instances)) for (const t of ts) inst.add(t.node);
        for (const n of [...f.serves, ...inst]) {
          const N = box(`[data-c-node="${CSS.escape(n)}"]`);
          if (!N) continue;
          const hot = L.features.has(f.id) && L.nodes.has(n);
          const mx = (N.r + F.l) / 2;
          out.push({ d: `M${N.r},${N.cy} C${mx},${N.cy} ${mx},${F.cy} ${F.l},${F.cy}`,
                     cls: cls(hot, inst.has(n) && !f.serves.includes(n) ? "serve instance" : "serve") });
        }
        // feature -> parameters it reads directly
        for (const p of f.params) {
          const P = box(`[data-c-param="${CSS.escape(p)}"]`);
          if (!P) continue;
          const hot = L.params.has(p) && L.features.has(f.id);
          const mx = (F.r + P.l) / 2;
          out.push({ d: `M${F.r},${F.cy} C${mx},${F.cy} ${mx},${P.cy} ${P.l},${P.cy}`, cls: cls(hot, "param-link") });
        }
        // feature -> features it uses (arcs left of the feature column)
        let lane = 0;
        for (const g of f.uses) {
          const G = box(`[data-c-feat="${CSS.escape(g)}"]`);
          if (!G) continue;
          lane++;
          const x = F.l - 14 - lane * 6;
          const hot = L.features.has(f.id) && (L.features.has(g) || L.indirectFeatures.has(g));
          out.push({ d: `M${F.l},${F.cy - 3} C${x},${F.cy - 3} ${x},${G.cy + 3} ${G.l},${G.cy + 3}`,
                     cls: cls(hot, "uses-link") });
        }
      }
      setLines(out);
      setSize({ w: root.scrollWidth, h: root.scrollHeight });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    return () => ro.disconnect();
  }, [b, L, isAct]);

  if (!b || !d) return null;
  const on = (s: Selection) => ({
    onMouseEnter: () => (hover.value = s), onMouseLeave: () => (hover.value = null), onClick: () => select(s),
  });
  const isSel = (s: Selection) => selection.value?.kind === s.kind && selection.value?.id === s.id;
  const state = (litHere: boolean, s: Selection, indirect = false) =>
    `${litHere ? "lit" : ""} ${indirect ? "indirect" : ""} ${isSel(s) ? "selected" : ""} ${isAct && !litHere && !indirect ? "dim" : ""}`;
  return (
    <div class="connections" data-testid="connections">
      <div class="connections-head">
        <h2>Connections</h2>
        <span class="muted">intents ⇄ features ⇄ parameters · hover or click anything to light up what it touches</span>
        <span class="legend">
          <span class="lg serve" /> serves <span class="lg instance" /> instance <span class="lg uses-link" /> uses
          <span class="lg param-link" /> reads parameter
        </span>
        <button class="icon-btn" onClick={() => (expanded.value = false)} title="close (Esc)">✕</button>
      </div>
      <div class="connections-body" ref={host}>
        <svg class="links" width={size.w} height={size.h} aria-hidden="true">
          <defs>
            <marker id="carrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
              <path d="M0,0 L6,3 L0,6 z" class="arrowhead" />
            </marker>
          </defs>
          {lines.map((l, i) => <path key={i} d={l.d} class={l.cls} marker-end={l.cls.startsWith("uses") ? "url(#carrow)" : undefined} />)}
        </svg>
        <div class="c-col c-nodes">
          <div class="c-col-title">INTENTS</div>
          {b.tree.order.map((id) => {
            const n = b.tree.nodes[id];
            const s: Selection = { kind: "node", id };
            return (
              <div key={id} class={`c-item ${state(L.nodes.has(id), s)} ${b.diagnostics.no_feature.includes(id) ? "flag" : ""}`}
                   data-c-node={id} style={{ "--depth": nodeDepth(b, id) } as never} {...on(s)}>
                <Dot status={n.status} /> <span class="mono">{id}</span> <span class="c-label">{n.label}</span>
                {b.diagnostics.no_feature.includes(id) && <span class="flag-text">no feature</span>}
              </div>
            );
          })}
        </div>
        <div class="c-col c-feats">
          <div class="c-col-title">FEATURES (build order)</div>
          {b.features.map((f) => {
            const s: Selection = { kind: "feature", id: f.id };
            const flags = [b.diagnostics.no_intent.includes(f.id) ? "no intent" : "",
                           b.diagnostics.multi_intent.some((m) => m.feature === f.id) ? "several intents" : ""]
              .filter(Boolean);
            return (
              <div key={f.id} class={`c-item ${state(L.features.has(f.id), s, L.indirectFeatures.has(f.id))} ${flags.length ? "flag" : ""}`}
                   data-c-feat={f.id} {...on(s)}>
                <span class="idx mono num">{f.index + 1}</span> <Dot status={f.status} />
                <span class="mono">{f.id}</span> <span class="c-label">{f.lowered_from ?? f.op}</span>
                {flags.map((x) => <span class="flag-text" key={x}>{x}</span>)}
              </div>
            );
          })}
        </div>
        <div class="c-col c-params">
          <div class="c-col-title">PARAMETERS</div>
          {d.params.map((p) => {
            const s: Selection = { kind: "param", id: p.name };
            return (
              <div key={p.name} class={`c-item ${state(L.params.has(p.name), s)}`} data-c-param={p.name} {...on(s)}>
                <span class="mono">{p.name}</span>
                <span class="c-label mono num">{String(b.params[p.name] ?? p.default)}{p.unit && p.kind === "range" ? ` ${p.unit}` : ""}</span>
              </div>
            );
          })}
        </div>
      </div>
      <DiagnosticsSummary />
    </div>
  );
}

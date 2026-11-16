// Left panel: WHY ⇄ HOW in one window (docs/gui.md §3), with the shared-element transition,
// "show links" connector lines, and selection sync with the viewport and other panels.

import { Fragment } from "preact";
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { canDrop, staleFeatures } from "../edit";
import { confirmDelete, dragging, dropTarget, editing, patchIntent, startEdit } from "../intent";
import { rowsFor, type Chip, type Row, type View } from "../model";
import { active, build, expanded, hover, lit, persist, select, selection, showLinks, view } from "../store";
import type { Selection } from "../types";
import { Dot } from "./common";
import { ConfirmDelete, editable, RowActions, rowKeys, StaleTag, StatementInput } from "./IntentEditor";

export const FLIP_MS = 300;

export function reducedMotion(): boolean {
  return typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Bounding rects of the first element per flip key inside `root`. */
function snapshot(root: HTMLElement): Map<string, DOMRect> {
  const m = new Map<string, DOMRect>();
  root.querySelectorAll<HTMLElement>("[data-flip]").forEach((el) => {
    const k = el.dataset.flip!;
    if (!m.has(k)) m.set(k, el.getBoundingClientRect());
  });
  return m;
}

/** FLIP: shared elements glide from their old rect to the new one; new ones fade in. */
function play(root: HTMLElement, before: Map<string, DOMRect>): void {
  const seen = new Set<string>();
  root.querySelectorAll<HTMLElement>("[data-flip]").forEach((el) => {
    const k = el.dataset.flip!;
    const first = !seen.has(k);
    seen.add(k);
    const prev = first ? before.get(k) : undefined;
    if (prev) {
      const now = el.getBoundingClientRect();
      const dx = prev.left - now.left, dy = prev.top - now.top;
      if (Math.abs(dx) < 0.5 && Math.abs(dy) < 0.5) return;
      el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: "translate(0, 0)" }],
                 { duration: FLIP_MS, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" });
    } else {
      el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: FLIP_MS * 0.7, delay: FLIP_MS * 0.3, easing: "ease-out",
                                                     fill: "backwards" });
    }
  });
}

function selOf(kind: "node" | "feature", id: string): Selection {
  return { kind, id } as Selection;
}

export function IntentPanel() {
  const b = build.value;
  const listRef = useRef<HTMLDivElement>(null);
  const snap = useRef<Map<string, DOMRect> | null>(null);
  const [animating, setAnimating] = useState(false);

  const toggle = (to?: View) => {
    const next: View = to ?? (view.value === "why" ? "how" : "why");
    if (next === view.value) return;
    if (listRef.current && !reducedMotion()) snap.current = snapshot(listRef.current);
    view.value = next;
    persist("view", next);
  };

  useLayoutEffect(() => {
    const root = listRef.current;
    const before = snap.current;
    snap.current = null;
    if (!root) return;
    if (before) {
      setAnimating(true);
      play(root, before);
      setTimeout(() => setAnimating(false), FLIP_MS + 40);
    }
    // scroll anchor: keep the selected / primary item in view
    const key = anchorKey(selection.value, lit.value.primaryNode, view.value);
    const el = key ? root.querySelector<HTMLElement>(`[data-flip="${CSS.escape(key)}"]`) : null;
    el?.scrollIntoView?.({ block: "nearest" });
  }, [view.value]);

  if (!b) return <aside class="panel left"><div class="empty">loading…</div></aside>;
  const rows = rowsFor(b, view.value);
  const d = b.diagnostics;
  const nDiag = d.no_intent.length + d.no_feature.length + d.multi_intent.length + d.cross_intent.length +
    (d.missing_in_file?.length ?? 0);
  return (
    <div class="intent-panel" data-view={view.value}>
      <div class="panel-toolbar">
        <div class="whyhow" role="radiogroup" aria-label="WHY or HOW first">
          <button role="radio" aria-checked={view.value === "why"} class={view.value === "why" ? "on" : ""}
                  onClick={() => toggle("why")} data-testid="view-why">WHY</button>
          <button class="whyhow-track" onClick={() => toggle()} aria-label="toggle WHY / HOW" title="WHY ⇄ HOW">
            <span class="knob" />
          </button>
          <button role="radio" aria-checked={view.value === "how"} class={view.value === "how" ? "on" : ""}
                  onClick={() => toggle("how")} data-testid="view-how">HOW</button>
        </div>
        <label class="links-toggle" title="draw connector lines">
          <input type="checkbox" checked={showLinks.value}
                 onChange={(e) => { showLinks.value = (e.target as HTMLInputElement).checked; persist("showLinks", showLinks.value); }} />
          links
        </label>
        <button class="icon-btn" onClick={() => (expanded.value = !expanded.value)} aria-pressed={expanded.value}
                title="expanded connections view (intents ⇄ features ⇄ parameters)" data-testid="expand">
          {expanded.value ? "⤡" : "⤢"}
        </button>
      </div>
      <div class="caption">
        {view.value === "why" ? "intent tree · realized by" : "features in build order · serves"}
      </div>
      <div class="rows-scroll" ref={listRef}>
        <div class="rows" role="tree" aria-label={view.value === "why" ? "intent tree" : "features in build order"}>
          {rows.map((r) => (
            <Fragment key={r.key}>
              <RowView r={r} />
              {r.kind === "node" && confirmDelete.value?.id === r.id && <ConfirmDelete b={b} id={r.id} where="row" />}
            </Fragment>
          ))}
          {showLinks.value && !animating && <Links rows={rows} root={listRef} v={view.value} />}
        </div>
      </div>
      {nDiag > 0 && <DiagnosticsSummary />}
    </div>
  );
}

function anchorKey(sel: Selection | null, primaryNode: string | null, _v: View): string | null {
  if (sel?.kind === "node") return `node:${sel.id}`;
  if (sel?.kind === "feature") return `feat:${sel.id}`;
  if (primaryNode) return `node:${primaryNode}`;
  return null;
}

function RowView({ r }: { r: Row }) {
  const L = lit.value;
  const isAct = active.value !== null;
  const kind = r.kind === "node" ? "node" : "feature";
  const isLit = r.kind === "node" ? L.nodes.has(r.id) : r.kind === "feature" ? L.features.has(r.id) : false;
  const indirect = r.kind === "feature" && L.indirectFeatures.has(r.id);
  const primary = (r.kind === "node" && L.primaryNode === r.id) || (r.kind === "feature" && L.primaryFeature === r.id);
  const sel = selection.value;
  const isSel = !!sel && sel.kind === kind && sel.id === r.id;
  const b = build.value!;
  const n = r.kind === "node" ? b.tree.nodes[r.id] : undefined;
  const canEdit = !!n && editable(b) && !!n.in_file;
  const fStale = r.kind === "feature" ? staleFeatures(b).get(r.id) : undefined;
  const isDrop = r.kind === "node" && dropTarget.value === r.id;
  const cls = ["row", `row-${r.kind}`, isLit ? "lit" : "", indirect ? "indirect" : "", primary ? "primary" : "",
               isSel ? "selected" : "", isAct && !isLit && !indirect ? "dim" : "", r.implicit ? "implicit" : "",
               n?.stale ? "stale" : "", fStale ? "stale" : "", isDrop ? "drop-target" : "",
               dragging.value === r.id ? "dragging" : ""].join(" ");
  const interactive = r.kind !== "group";
  const isEditing = editing.value?.id === r.id && editing.value.where === "row" && r.kind === "node";
  return (
    <div class={cls} data-row={r.key} style={{ "--depth": r.depth } as never}
         tabIndex={interactive ? 0 : undefined} role={interactive ? "treeitem" : undefined}
         aria-selected={interactive ? isSel : undefined}
         aria-label={interactive ? `${r.label} ${r.sub}${n?.stale || fStale ? " (intent changed, solution not reviewed)" : ""}` : undefined}
         onMouseEnter={interactive ? () => (hover.value = selOf(kind, r.id)) : undefined}
         onMouseLeave={interactive ? () => (hover.value = null) : undefined}
         onClick={interactive ? () => select(selOf(kind, r.id)) : undefined}
         onKeyDown={interactive ? (e) => {
           if (e.target !== e.currentTarget) return;
           if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(selOf(kind, r.id)); return; }
           if (n && rowKeys(e, n)) e.preventDefault();
         } : undefined}
         draggable={canEdit && n!.parent !== null && !isEditing}
         onDragStart={canEdit ? (e) => {
           e.dataTransfer?.setData("text/plain", r.id);
           if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
           dragging.value = r.id;
         } : undefined}
         onDragEnd={() => { dragging.value = null; dropTarget.value = null; }}
         onDragOver={r.kind === "node" ? (e) => {
           const d = dragging.value;
           if (d && canDrop(b, d, r.id)) { e.preventDefault(); dropTarget.value = r.id; }
         } : undefined}
         onDragLeave={r.kind === "node" ? () => { if (dropTarget.value === r.id) dropTarget.value = null; } : undefined}
         onDrop={r.kind === "node" ? (e) => {
           e.preventDefault();
           const d = dragging.value ?? e.dataTransfer?.getData("text/plain");
           dragging.value = null;
           dropTarget.value = null;
           if (d && canDrop(b, d, r.id)) void patchIntent([{ op: "move", id: d, parent: r.id }]);
         } : undefined}>
      <span class="row-main">
        {r.kind === "feature" && <span class="idx mono num">{(r.index ?? 0) + 1}</span>}
        <span class="row-id mono" data-flip={r.kind === "group" ? undefined : r.key} data-status={r.status}>
          {r.kind === "node" && <Dot status={r.status} />}
          {r.label}
        </span>
        {isEditing ? <StatementInput id={r.id} /> : (
          <span class="row-sub" onDblClick={canEdit ? (e) => { e.stopPropagation(); startEdit(r.id, n!.statement ?? ""); } : undefined}>
            {r.sub}
          </span>
        )}
        {n?.stale && <StaleTag id={r.id} compact />}
        {fStale && <StaleTag id={`feat-${r.id}`} compact />}
        {r.kind === "feature" && <Dot status={r.status} />}
        {canEdit && !isEditing && <RowActions n={n!} />}
      </span>
      <span class="callouts">
        {r.chips.map((c) => <ChipView key={c.key} c={c} />)}
        {r.kind === "feature" && r.uses.length > 0 && (
          <span class="uses mono" title={`uses ${r.uses.join(", ")}`}>uses {r.uses.map(shortIdx).join(",")}</span>
        )}
      </span>
    </div>
  );
}

function shortIdx(fid: string): string {
  const b = build.value;
  const f = b?.features.find((x) => x.id === fid);
  return f ? String(f.index + 1) : fid;
}

function ChipView({ c }: { c: Chip }) {
  const L = lit.value;
  const kind = c.kind === "node" ? "node" : "feature";
  const isLit = kind === "node" ? L.nodes.has(c.id) : L.features.has(c.id);
  const isAct = active.value !== null;
  const s = selOf(kind, c.id);
  const b = build.value;
  const stale = kind === "feature" ? staleFeatures(b).has(c.id) : !!b?.tree.nodes[c.id]?.stale;
  return (
    <span class={`chip chip-${c.kind} ${isLit ? "lit" : ""} ${isAct && !isLit ? "dim" : ""} ${stale ? "chip-stale" : ""}`}
          data-flip={c.kind === "instance" ? undefined : c.key} data-chip={c.key}
          onMouseEnter={(e) => { e.stopPropagation(); hover.value = s; }}
          onMouseLeave={(e) => { e.stopPropagation(); hover.value = null; }}
          onClick={(e) => { e.stopPropagation(); select(s); }}
          title={c.kind === "instance" ? `instance ${c.label}` : c.id}>
      {c.kind === "feature" && <Dot status={c.status} />}
      {c.label}
    </span>
  );
}

// ------------------------------------------------------------------ connector lines

interface Seg { d: string; cls: string }

function Links({ rows, root, v }: { rows: Row[]; root: { current: HTMLDivElement | null }; v: View }) {
  const [segs, setSegs] = useState<Seg[]>([]);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const L = lit.value;
  const isAct = active.value !== null;

  useLayoutEffect(() => {
    const scroller = root.current;
    const host = scroller?.querySelector<HTMLElement>(".rows");
    if (!scroller || !host) return;
    const measure = () => {
      const base = host.getBoundingClientRect();
      const rel = (r: DOMRect) => ({ l: r.left - base.left, r: r.right - base.left, t: r.top - base.top,
                                     b: r.bottom - base.top, cy: (r.top + r.bottom) / 2 - base.top });
      const first = (key: string) => host.querySelector<HTMLElement>(`[data-flip="${CSS.escape(key)}"]`);
      const out: Seg[] = [];
      // leader lines: main row label -> each callout
      for (const r of rows) {
        const rowEl = host.querySelector<HTMLElement>(`[data-row="${CSS.escape(r.key)}"]`);
        const sub = rowEl?.querySelector<HTMLElement>(".row-sub");
        if (!rowEl || !sub) continue;
        const a = rel(sub.getBoundingClientRect());
        for (const c of r.chips) {
          const ce = rowEl.querySelector<HTMLElement>(`[data-chip="${CSS.escape(c.key)}"]`);
          if (!ce) continue;
          const k = rel(ce.getBoundingClientRect());
          const x0 = Math.min(a.r + 4, k.l - 2);
          const hot = (c.kind === "node" ? L.nodes.has(c.id) : L.features.has(c.id)) &&
            (r.kind === "node" ? L.nodes.has(r.id) : L.features.has(r.id));
          out.push({ d: `M${x0},${a.cy} L${k.l - 2},${k.cy}`, cls: `leader ${hot ? "hot" : ""} ${isAct && !hot ? "dim" : ""}` });
        }
      }
      // uses arrows between features
      const fUses = new Map<string, string[]>();
      const b = build.value;
      for (const f of b?.features ?? []) fUses.set(f.id, f.uses);
      const gutter = v === "how";
      let lane = 0;
      for (const [fid, uses] of fUses) {
        const fe = first(`feat:${fid}`);
        if (!fe) continue;
        const A = rel(fe.getBoundingClientRect());
        for (const g of uses) {
          const ge = first(`feat:${g}`);
          if (!ge) continue;
          const B = rel(ge.getBoundingClientRect());
          const hot = L.features.has(fid) && (L.features.has(g) || L.indirectFeatures.has(g));
          lane = (lane % 4) + 1;
          if (gutter) {
            // anchor at the row's left edge, before the build-order index
            const ra = fe.closest<HTMLElement>("[data-row]"), rb = ge.closest<HTMLElement>("[data-row]");
            const xa = ra ? rel(ra.getBoundingClientRect()).l + 17 : A.l - 2;
            const xb = rb ? rel(rb.getBoundingClientRect()).l + 17 : B.l - 2;
            const x = 2 + lane * 3;
            out.push({ d: `M${xa},${A.cy} C${x},${A.cy} ${x},${B.cy} ${xb},${B.cy}`,
                       cls: `uses-link ${hot ? "hot" : ""} ${isAct && !hot ? "dim" : ""}` });
          } else {
            const x = Math.max(A.r, B.r) + 4 + lane * 5;
            out.push({ d: `M${A.r + 2},${A.cy} C${x},${A.cy} ${x},${B.cy} ${B.r + 2},${B.cy}`,
                       cls: `uses-link ${hot ? "hot" : ""} ${isAct && !hot ? "dim" : ""}` });
          }
        }
      }
      setSegs(out);
      setSize({ w: host.scrollWidth, h: host.scrollHeight });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(host);
    return () => ro.disconnect();
  }, [rows, v, L, isAct]);

  return (
    <svg class="links" width={size.w} height={size.h} aria-hidden="true">
      <defs>
        <marker id="arrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="5" markerHeight="5" orient="auto-start-reverse">
          <path d="M0,0 L6,3 L0,6 z" class="arrowhead" />
        </marker>
      </defs>
      {segs.map((s, i) => <path key={i} d={s.d} class={s.cls} marker-end={s.cls.startsWith("uses") ? "url(#arrow)" : undefined} />)}
    </svg>
  );
}

// ------------------------------------------------------------------ diagnostics

export function DiagnosticsSummary() {
  const d = build.value!.diagnostics;
  return (
    <div class="diagnostics" data-testid="diagnostics">
      <div class="diag-title">DIAGNOSTICS</div>
      {d.no_intent.map((f) => (
        <div class="diag diag-warn" key={`ni-${f}`} onClick={() => select({ kind: "feature", id: f })}>
          <span class="mono">{f}</span> no intent
        </div>
      ))}
      {(d.missing_in_file ?? []).map((n) => (
        <div class="diag diag-warn" key={`mf-${n}`} onClick={() => select({ kind: "node", id: n })}>
          <span class="mono">{n}</span> used in the DSL but missing from the intent file
        </div>
      ))}
      {d.no_feature.map((n) => (
        <div class="diag diag-warn" key={`nf-${n}`} onClick={() => select({ kind: "node", id: n })}>
          <span class="mono">{n}</span> intent with no feature
        </div>
      ))}
      {d.multi_intent.map((m) => (
        <div class="diag diag-warn" key={`mi-${m.feature}`} onClick={() => select({ kind: "feature", id: m.feature })}>
          <span class="mono">{m.feature}</span> serves several intents: <span class="mono">{m.nodes.join(" · ")}</span>
        </div>
      ))}
      {d.cross_intent.map((c) => (
        <div class="diag diag-info" key={`ci-${c.from}-${c.to}`} onClick={() => select({ kind: "feature", id: c.from })}
             title="a dependency between features of unrelated intents: shared purpose, or false coupling? (architecture §5.1)">
          <span class="mono">{c.from}</span> uses <span class="mono">{c.to}</span>
          <span class="muted"> · crosses intents {c.from_nodes.join(", ")} → {c.to_nodes.join(", ")}</span>
        </div>
      ))}
    </div>
  );
}

export function useEscapeToClear() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (confirmDelete.value) confirmDelete.value = null;
        else if (editing.value) editing.value = null;
        else if (expanded.value) expanded.value = false;
        else selection.value = null;
      }
    };
    addEventListener("keydown", h);
    return () => removeEventListener("keydown", h);
  }, []);
}

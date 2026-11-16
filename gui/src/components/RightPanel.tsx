// Right panel: inspector ("why is this here?"), checks, interpretations (docs/gui.md §2 items 5–7).

import { useEffect, useRef } from "preact/hooks";
import { answer, answering, build, design, focusCheck, hover, persist, select, selection, showDetails } from "../store";
import type { BuildJ, CheckTermJ, FaceJ, FeatureJ, IntentCheckJ, IntentTagJ, Selection, WhyEntryJ } from "../types";
import { faceLabel, featureMap, fmtNumber } from "../model";
import { Dot, Guess, Mono, Section } from "./common";
import { acceptGuess } from "../intent";
import { marginBar, STATE_TEXT } from "../margins";
import { staleFeatures } from "../edit";
import { NodeEditor, StaleTag, editable } from "./IntentEditor";
import { ProposalsPanel, proposalBadge } from "./Proposals";
import { ImpactPanel } from "./Loop";
import { impactOf } from "../loop";
import { focusImpact } from "../store";

export function RightPanel() {
  const b = build.value;
  const it = b?.interpretations;
  const nAttn = (it?.questions.length ?? 0) + (it?.notices.length ?? 0);
  const nFail = b?.failing.length ?? 0;
  return (
    <div class="right-stack">
      {impactOf(b) && (
        <Section id="impact" title="IMPACT" attention forceOpen={focusImpact.value}
                 badge={<span class="count attn" data-testid="impact-badge">
                   {impactOf(b)!.summary.nodes.invalidated + impactOf(b)!.summary.checks.invalidated +
                    impactOf(b)!.summary.assumptions.invalidated} invalidated</span>}>
          <ImpactPanel />
        </Section>
      )}
      <Section id="inspector" title="INSPECTOR" badge={<span class="muted">why is this here?</span>}>
        <Inspector />
      </Section>
      <Section id="checks" title="CHECKS" attention={nFail > 0 || (b?.status.intent.failing ?? 0) > 0}
               forceOpen={focusCheck.value?.at}
               badge={b ? <span class={`count ${nFail || b.status.intent.failing ? "fail" : "neutral"}`} data-testid="checks-badge">
                 {b.status.intent.failing ? `${b.status.intent.failing} failing · ` : ""}{nFail ? `kernel ✗${nFail}` : "kernel ✓"} · {b.status.intent.run}/{b.status.intent.total} run</span> : null}>
        <Checks />
      </Section>
      <Section id="interpretations" title="INTERPRETATIONS" attention={nAttn > 0}
               badge={it ? <span class={`count ${nAttn ? "attn" : "ok"}`}>
                 {it.slots.length} slots · {it.questions.length} q · {it.notices.length} notices</span> : null}>
        <Interpretations />
      </Section>
      <Section id="proposals" title="PROPOSALS" attention={proposalBadge().open > 0}
               badge={<span class={`count ${proposalBadge().open ? "attn" : "ok"}`} data-testid="proposals-badge">
                 {proposalBadge().open} open · {proposalBadge().total}</span>}>
        <ProposalsPanel />
      </Section>
    </div>
  );
}

// ------------------------------------------------------------------ inspector

export function Inspector() {
  const b = build.value;
  const s = selection.value;
  if (!b) return <div class="empty">no build yet</div>;
  if (!s) {
    const h = hover.value;
    return (
      <div class="empty">
        {h?.kind === "face" ? <>hovering <Mono>{faceLabel(b, h.id)}</Mono>. Click to pin.</> :
          "Hover a face to see what made it; click to pin its genealogy here. Click a tree node, feature or parameter to see what it drives."}
      </div>
    );
  }
  switch (s.kind) {
    case "face": return b.faces[s.id] ? <FaceInspector b={b} f={b.faces[s.id]} /> : null;
    case "edge": return <EdgeInspector b={b} id={s.id} />;
    case "node": return <NodeInspector b={b} id={s.id} />;
    case "feature": return <FeatureInspector f={featureMap(b).get(s.id)} />;
    case "param": return <ParamInspector b={b} name={s.id} />;
  }
}

function TagChips({ tags, instance }: { tags: IntentTagJ[]; instance?: boolean }) {
  return (
    <>
      {tags.map((t) => (
        <button class={`tag ${instance ? "tag-instance" : ""}`} key={t.text} onClick={() => select({ kind: "node", id: t.node })}
                title={`intent node ${t.node}`}>
          <span class="mono">{t.word}@{t.node}</span>{t.note && <span class="tag-note"> ({t.note})</span>}
        </button>
      ))}
    </>
  );
}

function Entry({ e }: { e: WhyEntryJ }) {
  const summary = [e.tag, ...e.instance_intent.map((t) => t.text), ...e.intent.filter((t) => t.note).map((t) => t.text)];
  return (
    <div class="why-entry">
      <div class="why-summary mono" data-testid="why-summary">{summary.join(" · ")}</div>
      <dl class="kv">
        <dt>created as</dt>
        <dd><button class="link mono" onClick={() => select({ kind: "feature", id: e.feature })}>{e.tag}</button></dd>
        <dt>op</dt>
        <dd><Mono>{e.op}</Mono>{e.lowered_from && <> ← <Mono>{e.lowered_from}</Mono></>}</dd>
        <dt>intent</dt>
        <dd class="tags"><TagChips tags={e.instance_intent} instance /><TagChips tags={e.intent} /></dd>
        <dt>history</dt>
        <dd class="mono">{e.events.length ? e.events.map(([f, ev]) => `${f}:${ev}`).join(" → ") : "(unchanged)"}</dd>
      </dl>
    </div>
  );
}

function FaceInspector({ b, f }: { b: BuildJ; f: FaceJ }) {
  return (
    <div class="inspector" data-testid="inspector-face">
      <div class="insp-head"><span class="kind">face</span> <Mono>f{f.id}</Mono> <span class="muted">{f.descriptor}</span></div>
      {f.size && <div class="small" data-testid="face-size">{f.size}</div>}
      {f.failing && <div class="callout fail">touched by a failing feature</div>}
      {f.entries.length === 0 && <div class="muted">no genealogy (untracked)</div>}
      {f.entries.map((e, i) => <Entry key={i} e={e} />)}
      {f.touched_by.length > 1 && (
        <div class="muted small">touched by {f.touched_by.map((x, i) => (
          <span key={x}>{i ? ", " : ""}<button class="link mono" onClick={() => select({ kind: "feature", id: x })}>{x}</button></span>
        ))}</div>
      )}
      <NodesLine b={b} nodes={f.nodes} />
    </div>
  );
}

function EdgeInspector({ b, id }: { b: BuildJ; id: number }) {
  const e = b.edges[id];
  if (!e) return null;
  return (
    <div class="inspector">
      <div class="insp-head"><span class="kind">edge</span> <Mono>e{e.id}</Mono> <span class="muted">{e.descriptor}</span></div>
      {e.entries.map((x, i) => <Entry key={i} e={x} />)}
      {e.derived_from.length > 0 && (
        <div class="muted">untracked edge: edges_between faces {e.derived_from.map((fi) => (
          <button key={fi} class="link mono" onClick={() => select({ kind: "face", id: fi })}>f{fi}</button>))}</div>
      )}
      <NodesLine b={b} nodes={e.nodes} />
    </div>
  );
}

function NodesLine({ b, nodes }: { b: BuildJ; nodes: string[] }) {
  if (!nodes.length) return null;
  return (
    <div class="nodes-line">
      serves{" "}
      {nodes.map((n) => (
        <button key={n} class="node-chip" onClick={() => select({ kind: "node", id: n })}>
          <Dot status={b.tree.nodes[n]?.status ?? "ok"} /> <Mono>{n}</Mono>
        </button>
      ))}
    </div>
  );
}

function NodeInspector({ b, id }: { b: BuildJ; id: string }) {
  const n = b.tree.nodes[id];
  if (!n) return null;
  const nFaces = b.faces.filter((f) => f.nodes.some((x) => x === id || x.startsWith(id + "."))).length;
  const fileTree = editable(b) && !!n.in_file;
  return (
    <div class="inspector" data-testid="inspector-node">
      <div class="insp-head"><span class="kind">intent</span> <Mono>{id}</Mono> <Dot status={n.status} />
        {n.stale && <StaleTag compact />}
        {n.review_state === "reviewed_failing" && <span class="pill fail-pill" data-testid="reviewed-failing">reviewed with failing checks</span>}
        {n.review_state === "unreviewed" && <span class="guess-chip guess">not reviewed</span>}</div>
      <NodeChecks b={b} id={id} />
      {fileTree ? <NodeEditor b={b} n={n} /> :
        <div class="insp-label">{n.label || <span class="muted">(no label)</span>}</div>}
      <dl class="kv">
        {n.words.length > 0 && <><dt>words</dt><dd class="mono">{n.words.join(", ")}</dd></>}
        {n.notes.length > 1 && <><dt>notes</dt><dd>{n.notes.join(" · ")}</dd></>}
        <dt>realized by</dt>
        <dd>{n.realized_by.length ? n.realized_by.map((f) => <FeatLink key={f} id={f} />) :
             n.features.length ? n.features.map((f) => <FeatLink key={f} id={f} />) : <span class="muted">—</span>}</dd>
        {n.instances.length > 0 && <><dt>instances</dt><dd class="mono">{n.instances.map(([f, k]) => `${f}[${k}]`).join(", ")}</dd></>}
        {n.children.length > 0 && <><dt>children</dt><dd>{n.children.map((c) => (
          <button key={c} class="link mono" onClick={() => select({ kind: "node", id: c })}>{c}</button>))}</dd></>}
        <dt>faces</dt><dd class="mono num">{nFaces}</dd>
      </dl>
      {n.implicit && <div class="muted small">implicit node (only an ancestor of tagged nodes)</div>}
    </div>
  );
}

function FeatLink({ id }: { id: string }) {
  return <button class="link mono" onClick={() => select({ kind: "feature", id })}>{id}</button>;
}

function FeatureInspector({ f }: { f: FeatureJ | undefined }) {
  if (!f) return null;
  const indirect = f.params_all.filter((p) => !f.params.includes(p));
  return (
    <div class="inspector" data-testid="inspector-feature">
      <div class="insp-head"><span class="kind">feature {f.index + 1}</span> <Mono>{f.id}</Mono> <Dot status={f.status} /></div>
      {staleFeatures(build.value).has(f.id) && (
        <div class="stale-box small" data-testid="feature-stale">
          <StaleTag /> serves {f.stale!.map((x) => <button key={x} class="link mono" onClick={() => select({ kind: "node", id: x })}>{x}</button>)}
        </div>
      )}
      <dl class="kv">
        <dt>op</dt><dd><Mono>{f.op}</Mono>{f.lowered_from && <> ← <Mono>{f.lowered_from}</Mono></>}</dd>
        <dt>intent</dt><dd class="tags">{f.tags.length ? <TagChips tags={f.tags} /> : <span class="warn-text">no intent</span>}</dd>
        {Object.keys(f.instances).length > 0 && <><dt>instances</dt><dd class="tags">
          {Object.entries(f.instances).map(([k, ts]) => <span key={k}><Mono>k={k}</Mono> <TagChips tags={ts} instance /></span>)}</dd></>}
        <dt>uses</dt>
        <dd>{f.uses.length ? f.uses.map((u) => <FeatLink key={u} id={u} />) : <span class="muted">—</span>}
          {f.reads.map((r, i) => <div key={i} class="muted small">{r.what} {r.features.join(", ")}</div>)}</dd>
        <dt>parameters</dt>
        <dd>{f.params.map((p) => <ParamLink key={p} name={p} />)}
          {indirect.length > 0 && <span class="muted small"> via uses: {indirect.join(", ")}</span>}
          {!f.params_all.length && <span class="muted">—</span>}</dd>
        {f.ms !== null && <><dt>time</dt><dd class="mono num">{f.ms.toFixed(1)} ms</dd></>}
      </dl>
      {f.error && <ErrorBox e={f.error} />}
      {f.slots.length > 0 && <div class="muted small">interpreted slots: {f.slots.join(", ")}</div>}
    </div>
  );
}

function ParamLink({ name }: { name: string }) {
  return <button class="link mono" onClick={() => select({ kind: "param", id: name })}>{name}</button>;
}

function ParamInspector({ b, name }: { b: BuildJ; name: string }) {
  const p = design.value?.params.find((x) => x.name === name);
  const direct = b.features.filter((f) => f.params.includes(name));
  const via = b.features.filter((f) => !f.params.includes(name) && f.params_all.includes(name));
  return (
    <div class="inspector" data-testid="inspector-param">
      <div class="insp-head"><span class="kind">parameter</span> <Mono>{name}</Mono> = <Mono>{String(b.params[name])}</Mono></div>
      {p?.doc && <div class="insp-label">{p.doc}</div>}
      <dl class="kv">
        <dt>declared</dt><dd class="mono">{p?.range ? `[${p.range[0]}, ${p.range[1]}] ${p.unit}` : p?.choices?.join(" | ")}</dd>
        <dt>drives</dt><dd>{direct.map((f) => <FeatLink key={f.id} id={f.id} />)}</dd>
        {via.length > 0 && <><dt>through uses</dt><dd>{via.map((f) => <FeatLink key={f.id} id={f.id} />)}</dd></>}
      </dl>
    </div>
  );
}

function ErrorBox({ e }: { e: NonNullable<FeatureJ["error"]> }) {
  return (
    <div class="callout fail" data-testid="error-box">
      <div><b>{e.kind}</b>{e.invariant && <> · <Mono>{e.invariant}</Mono></>}</div>
      <div>{e.message}</div>
      {(e.expected !== null || e.got !== null) && <div class="mono small">expected {e.expected} · got {e.got}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ checks

const CHECK_COLS: [string, string][] = [["validity", "valid"], ["euler", "Euler"], ["delta_H", "ΔH"], ["delta_S", "ΔS"],
                                         ["volume_sign", "vol"]];

/** Checks grouped by tier (docs/gui.md §8.3 item 2): the kernel tier in plain words (engine terms
 *  behind Details), then every intent check, run or not, each with a margin bar and a state. */
export function Checks() {
  const b = build.value;
  const ref = useRef<HTMLDivElement>(null);
  const fc = focusCheck.value;
  useEffect(() => {
    if (!fc || !ref.current) return;
    const el = ref.current.querySelector(`[data-check-id="${CSS.escape(fc.id)}"]`) as HTMLElement | null;
    if (el) {
      el.scrollIntoView({ block: "nearest" });
      el.classList.add("flash");
      setTimeout(() => el.classList.remove("flash"), 1200);
    }
  }, [fc?.at]);
  if (!b) return null;
  const det = showDetails.value;
  const k = b.status.kernel;
  const ics = b.intent_checks ?? [];
  return (
    <div class="checks" ref={ref}>
      <div class="checks-tools">
        <label class="small"><input type="checkbox" checked={det} data-testid="details-toggle"
               onChange={(e) => { showDetails.value = (e.target as HTMLInputElement).checked; persist("showDetails", showDetails.value); }} />
          Details (engine terms)</label>
      </div>
      <div class="tier-group" data-testid="tier-kernel-group">
        <div class="tier-head">Kernel <span class={k.state === "pass" ? "pass-text" : "fail-text"}>
          {k.state === "pass" ? "✓ every feature passed" : `✗ ${k.failures} failure(s)`}</span></div>
        <div class={`check-plain ${k.state === "pass" ? "ok" : "fail"}`} data-check-id="kernel">
          {k.state === "pass" ? `The geometry is a valid solid and each of its ${k.features} features did what it says ` +
            "(made the holes it should, removed or added material, split nothing)." :
            "A feature did not do what it says: see the red rows."}
        </div>
        {(det || k.state !== "pass") && <KernelTable b={b} />}
      </div>
      <div class="tier-group" data-testid="tier-intent-group">
        <div class="tier-head">Intent checks <span class="muted">{b.status.intent.run} of {b.status.intent.total} run · worst case over
          the input ranges</span></div>
        {ics.map((c) => <IntentCheckRow key={c.id} c={c} det={det} />)}
        {ics.length === 0 && <div class="small muted">No intent checks stated for this design.</div>}
      </div>
      {b.signature && det && (
        <div class="sig mono small muted">
          (V,E,F,R,S,H) = ({b.signature.VEFRSH.join(", ")}) · vol {fmtNumber(b.signature.volume, 7)} mm³ ·
          {" "}{b.coverage.with_genealogy}/{b.coverage.faces} faces explained
        </div>
      )}
    </div>
  );
}

function KernelTable({ b }: { b: BuildJ }) {
  return (
    <>
      <table class="checks-table">
        <thead>
          <tr><th>#</th><th>feature</th>{CHECK_COLS.map(([, h]) => <th key={h} class="c">{h}</th>)}<th class="c">refs</th></tr>
        </thead>
        <tbody>
          {b.features.map((f) => {
            const by = new Map(f.checks.map((c) => [c.name, c]));
            const s: Selection = { kind: "feature", id: f.id };
            const sel = selection.value?.kind === "feature" && selection.value.id === f.id;
            return (
              <tr key={f.id} class={`${f.status} ${sel ? "selected" : ""}`} onClick={() => select(s)}
                  onMouseEnter={() => (hover.value = s)} onMouseLeave={() => (hover.value = null)} data-check-row={f.id}
                  data-check-id={`feature:${f.id}`}>
                <td class="mono num muted">{f.index + 1}</td>
                <td class="mono">{f.id}</td>
                {CHECK_COLS.map(([k]) => {
                  const c = by.get(k);
                  if (!c) return <td key={k} class="c muted">{f.status === "not_built" ? "·" : "–"}</td>;
                  const val = k === "delta_H" || k === "delta_S" ? fmtNumber(c.got) : c.ok ? "✓" : "✗";
                  return (
                    <td key={k} class={`c ${c.ok ? "pass" : "fail"}`}
                        title={`${c.name}: expected ${String(c.expected)}, got ${String(c.got)}${c.note ? ` — ${c.note}` : ""}`}>
                      {c.ok ? val : <b>{val}</b>}
                    </td>
                  );
                })}
                <td class={`c ${f.refs_ok ? "pass" : "fail"}`} title={f.refs.map((r) => `${r.ref} → ${r.count}`).join("\n") || "no references"}>
                  {f.status === "not_built" ? "·" : f.refs_ok ? (f.refs.length ? `✓${f.refs.length}` : "–") : <b>✗</b>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {b.errors.map((e, i) => (
        <div key={i} class="callout fail check-error" data-testid="check-error">
          <div><b>{e.feature ?? "build"}</b> · {e.kind}{e.invariant && <> · <Mono>{e.invariant}</Mono></>}</div>
          <div class="small">{e.message}</div>
          {(e.expected !== null || e.got !== null) && <div class="mono small">expected {e.expected} · got {e.got}</div>}
        </div>
      ))}
    </>
  );
}

function num(x: number, unit = ""): string {
  if (x === null || x === undefined || !isFinite(x)) return String(x);
  const a = Math.abs(x);
  const t = a >= 100 ? x.toLocaleString("en-US", { maximumFractionDigits: 0 }) : a >= 1 ? x.toFixed(2) : x.toPrecision(2);
  return unit ? `${t} ${unit}` : t;
}

export function MarginBar({ t }: { t: CheckTermJ }) {
  const lim = Math.abs(t.limit) > 1e-12 ? Math.abs(t.limit) : null;
  const relN = lim ? t.margin / lim : (t.margin < 0 ? -1 : t.margin > 0 ? 1 : 0);
  const relW = t.margin_rel ?? (t.margin_worst < 0 ? -1 : t.margin_worst > 0 ? 1 : 0);
  const m = marginBar(relN, relW);
  return (
    <div class={`margin-bar ${m.negative ? "neg" : "pos"} st-${t.state}`} data-testid="margin-bar"
         data-sign={m.negative ? "negative" : "positive"}
         title={`margin ${num(t.margin, t.unit)} nominal, ${num(t.margin_worst, t.unit)} worst case`}>
      <div class="mb-track">
        <div class="mb-neg" />
        <div class="mb-zero" style={{ left: `${m.zero * 100}%` }} />
        <div class="mb-span" style={{ left: `${Math.min(m.zero, m.worst) * 100}%`, width: `${Math.abs(m.worst - m.zero) * 100}%` }} />
        <div class="mb-nom" style={{ left: `${m.nominal * 100}%` }} title="nominal" />
        <div class="mb-worst" style={{ left: `${m.worst * 100}%` }} title="worst case" />
        {m.offLeft && <span class="mb-off left">◀</span>}
      </div>
      <div class="mb-labels small mono">
        <span>{t.sense === "<=" ? "value" : "value"} {num(t.nominal, t.unit)} <span class="muted">(worst {num(t.worst, t.unit)})</span></span>
        <span>limit {t.sense === "<=" ? "≤" : "≥"} {num(t.limit, t.unit)}{t.limit_worst !== t.limit ? <span class="muted"> (worst {num(t.limit_worst, t.unit)})</span> : null}</span>
        <span class={t.margin_worst < 0 ? "fail-text" : t.state === "thin" ? "warn-text" : "pass-text"}>
          margin {num(t.margin, t.unit)} · worst {num(t.margin_worst, t.unit)}</span>
      </div>
    </div>
  );
}

function IntentCheckRow({ c, det }: { c: IntentCheckJ; det: boolean }) {
  const b = build.value;
  const h = c.headline;
  return (
    <div class={`ic-row st-${c.state.replace(" ", "-")}`} data-check-id={c.id} data-testid={`check-${c.id}`}>
      <div class="ic-head">
        <Mono class="cid">{c.id}</Mono>
        <span class={`state-chip st-${c.state.replace(" ", "-")}`} data-testid="check-state">{STATE_TEXT[c.state] ?? c.state}</span>
        <Guess pkey={`check:${c.id}`} label={<span class="small">{c.priority || c.kind}</span>}
               onAccept={() => void acceptGuess(`check:${c.id}`, b)} />
      </div>
      <div class="ic-plain">{c.plain || c.statement}</div>
      {c.state === "not run" && <div class="small muted">not run: {c.reason}</div>}
      {h && <MarginBar t={h} />}
      {c.terms.length > 1 && !det && <div class="small muted">governed by {c.governing}; {c.terms.length - 1} more term(s) under Details</div>}
      {c.assumptions.length > 0 && (
        <div class="small ic-asm">relies on {c.assumptions.map((a) => (
          <Guess key={a.id} pkey={a.id === "print_orientation" ? "orientation" : `assumption:${a.id}`}
                 label={<span>{a.id === "print_orientation" ? "print orientation" : a.id}</span>} title={a.statement}
                 onAccept={() => void acceptGuess(a.id === "print_orientation" ? "orientation" : `assumption:${a.id}`, b)} />))}</div>
      )}
      {det && (
        <div class="ic-details small" data-testid="check-details">
          {c.terms.map((t) => (
            <div key={t.name} class="ic-term">
              <div><b>{t.name}</b>{t.name === c.governing && c.terms.length > 1 ? " (governs)" : ""} · <Mono>{t.formula}</Mono></div>
              {t !== h && <MarginBar t={t} />}
              <div class="muted">{t.method}</div>
              <ul class="ic-inputs">{t.inputs.map((q) => (
                <li key={q.name}><Mono>{q.label || q.name}</Mono> {num(q.nominal, q.unit)}{q.lo !== q.hi ? ` [${num(q.lo)}, ${num(q.hi)}]` : ""}
                  <span class="muted"> · {q.source}{q.placeholder ? " (placeholder)" : ""}</span></li>))}</ul>
            </div>
          ))}
          {c.method_assumptions.length > 0 && <ul class="ic-model">{c.method_assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>}
          <div class="muted">{c.kind} (rung {c.rung}){c.source ? ` · ${c.source}` : ""} · node {c.node}</div>
        </div>
      )}
    </div>
  );
}

function NodeChecks({ b, id }: { b: BuildJ; id: string }) {
  const cs = (b.intent_checks ?? []).filter((c) => c.node === id);
  if (!cs.length) return null;
  return (
    <div class="node-checks" data-testid="node-checks">
      {cs.map((c) => (
        <button key={c.id} class={`ic-mini st-${c.state.replace(" ", "-")}`} onClick={() => (focusCheck.value = { id: c.id, at: Date.now() })}
                title={c.plain || c.statement}>
          <Mono>{c.id}</Mono> {STATE_TEXT[c.state]}
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ interpretations

export function Interpretations() {
  const b = build.value;
  if (!b) return null;
  const it = b.interpretations;
  return (
    <div class="interp">
      <div class="muted small">source: <Mono>{it.source}</Mono>{it.unchecked && " · unchecked defaults"}</div>
      {it.questions.map((q) => (
        <div class="question" key={q.id} data-testid="question">
          <div class="q-head"><span class="q-label">QUESTION</span> <Mono>{q.id}</Mono></div>
          <div class="q-text">{q.text}</div>
          <div class="q-options">
            {q.options.map((o) => (
              <button key={o.reading} class={`answer ${o.reading === q.default ? "default" : ""}`}
                      disabled={answering.value !== null} onClick={() => answer(q.id, o.reading)}
                      title={`${o.rationale}\n${o.effect}`} data-reading={o.reading}>
                <span class="mono">{o.reading}</span>
                <span class="a-effect">{o.reading === q.default ? "current default" : o.effect}</span>
              </button>
            ))}
          </div>
          {answering.value === q.id && <div class="muted small">recording the answer and re-resolving…</div>}
        </div>
      ))}
      {it.notices.map((n, i) => (
        <div class="notice" key={i} data-testid="notice">
          <div class="q-head"><span class="n-label">NOTICE</span> <Mono>{n.kind.replace(/_/g, " ")}</Mono> · <Mono>{n.id}</Mono></div>
          <div class="small">{n.text}</div>
        </div>
      ))}
      {it.slots.map((s) => (
        <div class={`slot ${selection.value?.kind === "feature" && selection.value.id === s.feature ? "selected" : ""}`}
             key={s.id} data-slot={s.id}>
          <div class="slot-head">
            <button class="link mono" onClick={() => select({ kind: "feature", id: s.feature })}>{s.id}</button>
          </div>
          <div class="slot-chosen">
            <Guess pkey={`slot:${s.id}`} label={<span class="reading chosen mono">{s.chosen}</span>}
                   onAccept={() => void acceptGuess(`slot:${s.id}`, b)} testid="slot-guess" />
            <span class={`sens sens-${s.sensitivity}`} title={s.sensitivity_detail}>
              {s.sensitivity === "forced" ? "forced" : s.sensitivity === "insensitive" ? "insensitive" : `sensitivity ${s.sensitivity}`}</span>
            <span class="made-by">{s.made_by}</span>
          </div>
          {s.resolution && s.resolution !== "author" && (
            <div class={`small resolution res-${s.resolution}`} data-testid="slot-resolution">
              {s.resolution === "confirmed" ? <>meant: confirmed by {s.confirmed_by?.join(", ")}</> :
                <>feasible ({(s.feasible ?? []).join(", ")}), not confirmed as meant: no intent check at {s.node} has run</>}
            </div>
          )}
          <div class="small">{s.rationale}</div>
          {s.alternatives.length > 0 && (
            <div class="small muted">also survive: {s.alternatives.map((a) => <span class="reading mono" key={a}>{a}</span>)}
              {s.sensitivity_detail && <> — {s.sensitivity_detail}</>}</div>
          )}
          {s.eliminated.map((e) => (
            <div class="small elim" key={e.reading}>
              <span class="reading struck mono">{e.reading}</span> eliminated: <Mono>{e.check}</Mono> at <Mono>{e.feature}</Mono>
              {" "}({e.failed_points}/{e.of_points} points)
            </div>
          ))}
          {s.mismatch && <div class="small warn-text">this build used <Mono>{s.used ?? "?"}</Mono></div>}
        </div>
      ))}
      {it.slots.length === 0 && <div class="muted small">no ambiguous intent words in this design</div>}
    </div>
  );
}

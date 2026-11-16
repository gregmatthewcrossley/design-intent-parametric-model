// The purpose -> geometry loop in the GUI (iteration 4, docs/purpose-loop.md §4):
//   * ImpactPanel: what a purpose change invalidated, with reasons (stage 1);
//   * PurposeReview: a purpose proposal reviewed as a tree diff, each binding in plain language;
//   * AlternativesCompare: 2–3 geometry alternatives side by side with margins and thumbnails.
// Model-made items keep the hatched/dashed guess style until the designer accepts them.

import { useEffect, useState } from "preact/hooks";
import { api } from "../api";
import { canAccept, isOpen, needsOverride } from "../edit";
import {
  acceptProposal, compare, editPurpose, proposalBusy, proposals, rejectProposal, selectedProposal, tryPurpose,
} from "../intent";
import {
  alternativeGroups, asTerm, shortReason, checkCounts, checkRows, diffCounts, IMPACT_TEXT, impactOf, impactRows, treeDiff,
  type DiffRow,
} from "../loop";
import { decodeMesh } from "../mesh";
import { STATE_TEXT } from "../margins";
import { altGroup, build, impactMarks, select, setView, theme } from "../store";
import { thumbnail } from "../thumb";
import type { PurposeCheckJ, ProposalJ, SummaryCheckJ } from "../types";
import { Mono } from "./common";
import { MarginBar } from "./RightPanel";

// ------------------------------------------------------------------ impact (stage 1)

export function ImpactPanel() {
  const b = build.value;
  const im = impactOf(b);
  if (!b) return null;
  if (!im) {
    return <div class="small muted" data-testid="impact-none">
      {b.impact === null || b.impact === undefined
        ? "No review baseline: impact needs a review record (mark the design reviewed first)."
        : "No purpose changed since the solution was last reviewed."}</div>;
  }
  const rows = impactRows(im);
  const s = im.summary;
  return (
    <div class="impact" data-testid="impact-panel">
      <div class="small">
        <span class="imp-chip imp-changed">{s.nodes.changed} changed</span>{" "}
        <span class="imp-chip imp-invalidated">{s.nodes.invalidated + s.checks.invalidated + s.assumptions.invalidated} invalidated</span>{" "}
        <span class="muted">· {s.nodes.survives} nodes, {s.checks.survives} checks survive · {s.features.invalidated} feature(s) to revisit</span>
      </div>
      {(im.terms.removed.length > 0 || im.terms.added.length > 0) && (
        <div class="small imp-terms" data-testid="impact-terms">
          {im.terms.removed.length > 0 && <>removed <span class="del-text mono">{im.terms.removed.join(", ")}</span></>}
          {im.terms.added.length > 0 && <> · added <span class="add-text mono">{im.terms.added.join(", ")}</span></>}
        </div>
      )}
      {im.changes.filter((c) => c.before && c.fields.includes("statement")).map((c) => (
        <div key={c.id} class="small imp-change" data-testid="impact-change">
          <Mono>{c.id}</Mono> “<span class="del-text">{c.before!.statement}</span>” → “<span class="add-text">{c.after.statement}</span>”
        </div>
      ))}
      <label class="small"><input type="checkbox" checked={impactMarks.value} data-testid="toggle-impact-marks"
             onChange={(e) => setView(impactMarks, "impactMarks", (e.target as HTMLInputElement).checked)} />
        mark the tree (changed · invalidated)</label>
      <ul class="imp-rows">
        {rows.map((r) => (
          <li key={`${r.kind}:${r.id}`} class={`imp-row imp-${r.cls}`} data-impact={r.id} data-impact-class={r.cls}>
            <span class={`imp-chip imp-${r.cls}`}>{IMPACT_TEXT[r.cls]}</span>{" "}
            <span class="muted small">{r.kind}</span>{" "}
            {r.kind === "node" || r.kind === "feature"
              ? <button class="link mono" onClick={() => select({ kind: r.kind as "node" | "feature", id: r.id })}>{r.id}</button>
              : <Mono>{r.id}</Mono>}
            {r.text && <span class="small"> {r.text}</span>}
            <div class="small muted imp-why">{r.reasons.join("; ")}</div>
          </li>
        ))}
      </ul>
      <div class="small muted">{im.method}</div>
    </div>
  );
}

// ------------------------------------------------------------------ purpose proposals as a tree diff

const DIFF_TEXT: Record<string, string> = { added: "+", removed: "−", changed: "~", same: "" };

export function PurposeReview({ p }: { p: ProposalJ }) {
  const pr = p.evaluation?.purpose;
  const [editing, setEditing] = useState<{ id: string; draft: string } | null>(null);
  const [comment, setComment] = useState("");
  const busy = proposalBusy.value === p.id;
  if (!pr) return <div class="small muted">evaluating the purpose proposal…</div>;
  const rows = treeDiff(pr.before, pr.after, pr.checks);
  const n = diffCounts(rows);
  const open = isOpen(p);
  const commitEdit = async () => {
    if (!editing) return;
    const st = editing.draft.trim();
    setEditing(null);
    if (st) await editPurpose(p.id, [{ op: "edit_statement", id: editing.id, statement: st }], "edited while reviewing");
  };
  return (
    <div class="p-block purpose-review" data-testid="purpose-diff">
      <div class="field-label">purposes · tree diff</div>
      <div class="small muted">{n.added} added · {n.changed} changed · {n.removed} removed · purposes only: no geometry is
        written; their solution stays unreviewed until an alternative is accepted</div>
      <ul class="pd-tree" role="tree" aria-label="proposed purpose tree">
        {rows.map((r) => (
          <PdRow key={r.id} r={r} edit={open && r.status !== "removed" ? () => setEditing({ id: r.id, draft: r.statement }) : null}
                 editing={editing?.id === r.id ? editing.draft : null}
                 onDraft={(d) => setEditing({ id: r.id, draft: d })} onCommit={() => void commitEdit()}
                 onCancel={() => setEditing(null)} />
        ))}
      </ul>
      {pr.components.length > 0 && (
        <div class="pd-comps" data-testid="purpose-components">
          <div class="field-label">components it must fit</div>
          {pr.components.map((c) => (
            <div key={c.id} class={`small pd-comp guess-chip ${c.reviewed ? "confirmed" : "guess"}`}>
              <Mono>{c.id}</Mono> {c.shape} {Object.entries(c.dims).map(([k, q]) =>
                `${k} ${q.lo !== q.hi ? `${q.lo}–${q.hi}` : q.nominal} ${q.unit}`).join(" · ")}
              {c.mass && ` · mass ${c.mass.lo}–${c.mass.hi} kg`}
              <span class="muted"> · {c.source || "no source stated"}{c.placeholder ? " (placeholder)" : ""}</span>
            </div>
          ))}
        </div>
      )}
      {(pr.validation.unbound_unchanged ?? []).length > 0 && (
        <div class="small muted">unchanged checks still without a computable form (not run):{" "}
          <Mono>{pr.validation.unbound_unchanged.join(" ")}</Mono></div>
      )}
      {open && (
        <div class="p-actions">
          <button class="btn primary" disabled={!canAccept(p) || busy} data-testid="accept-purpose"
                  onClick={() => void acceptProposal(p.id)} title="write the revised purposes into the intent file">
            Accept purposes</button>
          {p.status !== "trying" && (
            <button class="btn" disabled={busy || !["ready", "pending", "failed"].includes(p.status)} data-testid="try-purpose"
                    onClick={() => void tryPurpose(p.id)}
                    title="let geometry alternatives be built against these purposes; nothing is written yet">Accept to try</button>
          )}
          <textarea rows={2} placeholder="what should change in these purposes? (sent to Claude)" value={comment}
                    aria-label="rejection comment" data-testid="reject-comment"
                    onInput={(e) => setComment((e.target as HTMLTextAreaElement).value)} />
          <button class="btn danger-outline" disabled={busy || !comment.trim()} data-testid="reject-proposal"
                  onClick={() => { void rejectProposal(p.id, comment); setComment(""); }}>Reject with comment</button>
        </div>
      )}
      {(p.designer_edits ?? []).length > 0 && (
        <div class="small muted" data-testid="designer-edits">{p.designer_edits!.length} designer edit(s): edited items are
          designer-made</div>
      )}
    </div>
  );
}

function PdRow({ r, edit, editing, onDraft, onCommit, onCancel }: {
  r: DiffRow; edit: (() => void) | null; editing: string | null; onDraft: (d: string) => void; onCommit: () => void;
  onCancel: () => void;
}) {
  return (
    <li class={`pd-row pd-${r.status}`} style={{ "--depth": r.depth } as never} data-pd={r.id} data-pd-status={r.status}
        role="treeitem">
      <div class="pd-head">
        <span class="pd-mark mono" aria-label={r.status}>{DIFF_TEXT[r.status]}</span>
        <Mono class="pd-id">{r.id}</Mono>
        {editing !== null ? (
          <input class="pd-edit" value={editing} data-testid="pd-edit-input" aria-label={`statement of ${r.id}`}
                 ref={(el) => el?.focus()}
                 onInput={(e) => onDraft((e.target as HTMLInputElement).value)}
                 onKeyDown={(e) => { if (e.key === "Enter") onCommit(); if (e.key === "Escape") onCancel(); }} />
        ) : (
          <span class="pd-statement">{r.statement}
            {r.before && r.status === "changed" && <span class="small muted"> (was “<span class="del-text">{r.before}</span>”)</span>}
            {r.moved && <span class="small muted"> (moved)</span>}</span>
        )}
        {edit && editing === null && (
          <button class="link small" onClick={edit} data-testid="pd-edit" title="edit this statement (becomes a revised, designer-made proposal)">edit</button>
        )}
        {editing !== null && <button class="link small" onClick={onCommit} data-testid="pd-edit-save">save</button>}
      </div>
      {r.checks.map((c) => <PdCheck key={c.id} c={c} />)}
      {r.removedChecks.map((id) => <div key={id} class="pd-check pd-removed small"><span class="pd-mark mono">−</span> <Mono>{id}</Mono></div>)}
    </li>
  );
}

function PdCheck({ c }: { c: PurposeCheckJ & { change: string } }) {
  const descriptive = c.form === "descriptive" || (!c.form && c.state === "not run");
  const guess = !!c.form && !c.reviewed;
  return (
    <div class={`pd-check pd-${c.change}`} data-pd-check={c.id} data-form={c.form ?? ""}>
      <div>
        <span class="pd-mark mono">{DIFF_TEXT[c.change]}</span> <Mono>{c.id}</Mono> <span class="small">{c.statement}</span>
        {" "}<span class={`state-chip st-${c.state.replace(" ", "-")}`} data-testid="pd-check-state"
                   title="on the current geometry">{descriptive ? "descriptive, not run" : STATE_TEXT[c.state] ?? c.state}</span>
      </div>
      <div class={`small pd-binding ${c.form ? `guess-chip ${guess ? "guess" : "confirmed"}` : ""}`}
           data-guess={guess ? "1" : "0"} title={c.form ? `${c.made_by ?? "model"}-made binding${c.reviewed ? ", accepted" : ", not reviewed"}` : ""}>
        {c.form && c.form !== "descriptive" && <Mono class="pd-form">{c.form}</Mono>} {c.reads_as}
      </div>
      {c.state === "not run" && c.reason && !c.reason.startsWith("descriptive") && (
        <div class="small muted" title={c.reason}>not run on the current geometry: {shortReason(c.reason)}</div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ alternatives compare

export function AlternativesButton({ p }: { p: ProposalJ }) {
  if (p.kind !== "geometry" || !p.group) return null;
  const n = alternativeGroups(proposals.value).get(p.group)?.length ?? 0;
  return (
    <button class="btn" data-testid="open-alternatives" onClick={() => (altGroup.value = p.group!)}>
      Compare {n} alternatives</button>
  );
}

export function AlternativesCompare() {
  const g = altGroup.value;
  const alts = g ? alternativeGroups(proposals.value).get(g) ?? [] : [];
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") altGroup.value = null; };
    addEventListener("keydown", h);
    return () => removeEventListener("keydown", h);
  }, []);
  if (!g) return null;
  const rows = checkRows(alts);
  const purpose = alts.find((a) => a.purpose)?.purpose;
  return (
    <div class="alt-overlay" data-testid="alternatives" role="dialog" aria-label="compare alternatives">
      <div class="alt-head">
        <b>Alternatives</b> <span class="muted small">group {g} · {alts.length} geometry proposals
          {purpose && <> · built against purpose proposal <Mono>{purpose}</Mono></>}</span>
        <button class="btn" onClick={() => (altGroup.value = null)} data-testid="close-alternatives">close</button>
      </div>
      <div class="alt-grid" style={{ gridTemplateColumns: `repeat(${Math.max(1, alts.length)}, minmax(0, 1fr))` }}>
        {alts.map((p) => <AltColumn key={p.id} p={p} rows={rows} />)}
      </div>
    </div>
  );
}

function AltThumb({ p }: { p: ProposalJ }) {
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const mid = p.evaluation?.meshes?.after;
  useEffect(() => {
    if (!mid) return;
    let alive = true;
    (async () => {
      try {
        const m = decodeMesh(await api.proposalMesh(p.id, "after"));
        const s = getComputedStyle(document.documentElement);
        const v = (n: string) => s.getPropertyValue(n).trim() || "#888";
        if (alive) setUrl(thumbnail(`${p.id}:${mid}`, m, { bg: v("--viewport-bg"), model: v("--model"), edge: v("--model-edge") }));
      } catch (e) {
        if (alive) setErr((e as Error).message);
      }
    })();
    return () => { alive = false; };
  }, [mid, theme.value]);
  return (
    <button class="alt-thumb" data-testid="alt-thumb" title="show this alternative in the viewport"
            onClick={() => { compare.value = { id: p.id, mode: "after" }; altGroup.value = null; selectedProposal.value = p.id; }}>
      {url ? <img src={url} alt={`alternative ${p.alternative} geometry`} data-loaded="1" /> :
        <span class="muted small">{err ?? (mid ? "rendering…" : "no geometry")}</span>}
    </button>
  );
}

function AltColumn({ p, rows }: { p: ProposalJ; rows: string[] }) {
  const ev = p.evaluation;
  const after = ev?.after;
  const cs = after?.intent_checks ?? [];
  const byId = new Map(cs.map((c) => [c.id, c]));
  const cnt = checkCounts(cs);
  const override = needsOverride(p);
  const [anyway, setAnyway] = useState(false);
  const [reason, setReason] = useState("");
  const busy = proposalBusy.value === p.id;
  return (
    <div class={`alt-col st-${p.status}`} data-alt={p.alternative} data-proposal={p.id}>
      <div class="alt-label"><span class="alt-letter">{p.alternative}</span> <Mono>{p.id}</Mono>
        <span class={`p-status st-${p.status} small`}>{p.status}</span></div>
      <AltThumb p={p} />
      <div class="alt-summary"><b>{p.summary}</b></div>
      {p.rationale && <div class="small muted alt-rationale">{p.rationale}</div>}
      {ev?.error && <div class="callout fail small">{ev.error}</div>}
      {after && (
        <div class={`small alt-status ${cnt.failing ? "fail-text" : cnt.thin ? "warn-text" : ""}`} data-testid="alt-status">
          {after.status.headline}
          {ev?.sweep && <span class="muted"> · {ev.sweep.points - ev.sweep.failing.length}/{ev.sweep.points} sample points</span>}
        </div>
      )}
      <div class="alt-checks">
        {rows.map((id) => <AltCheck key={id} id={id} c={byId.get(id)} />)}
      </div>
      {(ev?.assumed ?? []).length > 0 && (
        <details class="alt-block" data-testid="alt-assumed">
          <summary class="small">assumes {ev!.assumed!.length} unreviewed item(s)</summary>
          {ev!.assumed!.map((a) => (
            <div key={`${a.kind}:${a.id}`} class="small guess-chip guess alt-assumed">{a.kind} <Mono>{a.id}</Mono> {a.text}</div>
          ))}
        </details>
      )}
      <details class="alt-block" data-testid="alt-attempts">
        <summary class="small">attempt log: {(p.attempts ?? []).length} build(s){p.budget ? ` of ${p.budget}` : ""}</summary>
        {(p.attempts ?? []).map((a) => (
          <div key={a.n} class="small alt-attempt"><Mono>#{a.n}</Mono> {a.summary || "—"}
            <span class={a.failing.length || a.error ? "fail-text" : "muted"}> · {a.error ?? a.headline}</span></div>
        ))}
      </details>
      {isOpen(p) && (
        <div class="p-actions">
          {!override ? (
            <button class="btn primary" disabled={!canAccept(p) || busy} data-testid="accept-alternative"
                    onClick={() => void acceptProposal(p.id).then(() => (altGroup.value = null))}>Accept {p.alternative}</button>
          ) : !anyway ? (
            <button class="btn danger-outline" disabled={!canAccept(p) || busy} data-testid="accept-anyway"
                    onClick={() => setAnyway(true)}>Accept anyway…</button>
          ) : (
            <div class="anyway" data-testid="accept-anyway-form">
              <label class="field-label">why accept with failing checks? (recorded in the review record)</label>
              <textarea rows={2} value={reason} data-testid="override-reason"
                        onInput={(e) => setReason((e.target as HTMLTextAreaElement).value)} />
              <div class="confirm-actions">
                <button class="btn danger" disabled={!reason.trim() || busy} data-testid="confirm-accept-anyway"
                        onClick={() => void acceptProposal(p.id, reason.trim()).then(() => (altGroup.value = null))}>
                  Accept with failing checks</button>
                <button class="btn" onClick={() => { setAnyway(false); setReason(""); }}>Cancel</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function AltCheck({ id, c }: { id: string; c: SummaryCheckJ | undefined }) {
  if (!c) return <div class="alt-check small muted" data-alt-check={id}><Mono>{id}</Mono> —</div>;
  const st = c.state.replace(" ", "-");
  const guess = !!c.form && !c.binding_reviewed;
  return (
    <div class={`alt-check st-${st}`} data-alt-check={id} data-state={c.state}>
      <div class="small"><Mono>{id}</Mono> <span class={`state-chip st-${st}`}>{STATE_TEXT[c.state] ?? c.state}</span>
        {c.form && <span class={`guess-chip tiny ${guess ? "guess" : "confirmed"}`} title={c.binding_text}>{c.form}</span>}</div>
      <div class="small alt-plain">{c.plain}</div>
      {c.state === "not run" ? <div class="small muted" title={c.reason}>{shortReason(c.reason ?? "")}</div> :
        c.headline ? <MarginBar t={asTerm(c.terms?.find((t) => t.name === c.headline!.name) ?? c.headline, c.state) as never} />
          : null}
    </div>
  );
}

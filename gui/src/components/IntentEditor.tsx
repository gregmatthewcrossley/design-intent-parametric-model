// Intent editing (docs/gui.md §7.2): inline statement edit, add child, delete with an in-page
// confirmation, reparent (drag in WHY, or "move to" here), checks and assumptions editors,
// stale status with "Mark reviewed" and "Ask Claude", and the conflict banner.

import { useEffect, useRef, useState } from "preact/hooks";
import { featuresUnder, moveTargets, subtree } from "../edit";
import {
  askClaude, commitEdit, confirmDelete, conflict, editing, intentBusy, intentError, intentInfo, markReviewed,
  acceptGuess, patchIntent, reapplyAfterConflict, reloadAfterConflict, renameId, requests, startEdit,
} from "../intent";
import { build, select } from "../store";
import type { AssumptionSpec, BuildJ, CheckSpec, IntentNodeJ } from "../types";
import { claude, requestText } from "../claude";
import { Mono } from "./common";

export const CHECK_KINDS = ["relation", "rule", "analysis", "learned score", "live judgment"];
export const PRIORITIES = ["must", "should", "nice to have"];
export const ASSUMPTION_STATUS = ["proposed", "accepted", "challenged", "replaced"];

export function editable(b: BuildJ | null): boolean {
  return !!b?.tree.from_file && !!b.intent?.exists;
}

/** "intent changed · solution not reviewed" */
export function StaleTag({ id, compact }: { id?: string; compact?: boolean }) {
  return (
    <span class="stale-tag" data-testid={id ? `stale-${id}` : "stale"}
          title="the intent changed since its solution was last reviewed: mark it reviewed, edit the DSL, or ask Claude">
      {compact ? "intent changed" : "intent changed · solution not reviewed"}
    </span>
  );
}

/** Inline statement editor used in WHY rows and the inspector. */
export function StatementInput({ id, where = "row" }: { id: string; where?: "row" | "inspector" }) {
  const e = editing.value;
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => { ref.current?.focus(); ref.current?.select(); }, []);
  if (!e || e.id !== id || e.where !== where) return null;
  return (
    <input ref={ref} class="stmt-input" value={e.draft} aria-label={`statement of ${id}`} data-testid="statement-input"
           onClick={(ev) => ev.stopPropagation()}
           onInput={(ev) => (editing.value = { ...e, draft: (ev.target as HTMLInputElement).value })}
           onKeyDown={(ev) => {
             ev.stopPropagation();
             if (ev.key === "Enter") { ev.preventDefault(); void commitEdit(); }
             if (ev.key === "Escape") { ev.preventDefault(); editing.value = null; }
           }}
           onBlur={() => { if (editing.value?.id === id) void commitEdit(); }} />
  );
}

/** In-page delete confirmation (never `confirm()`). */
export function ConfirmDelete({ b, id, where }: { b: BuildJ; id: string; where: "row" | "inspector" }) {
  const btn = useRef<HTMLButtonElement>(null);
  useEffect(() => { btn.current?.focus(); }, []);
  const c = confirmDelete.value;
  if (!c || c.id !== id || c.where !== where) return null;
  const sub = subtree(b, id);
  const feats = featuresUnder(b, id);
  const cancel = () => (confirmDelete.value = null);
  return (
    <div class="confirm" role="alertdialog" aria-label={`delete ${id}?`} data-testid="confirm-delete"
         onClick={(e) => e.stopPropagation()}
         onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); cancel(); } }}>
      <div>
        Delete <Mono>{id}</Mono>{sub.length > 1 && <> and its {sub.length - 1} child intent{sub.length > 2 ? "s" : ""}</>}?
        {feats.length > 0 && <> <Mono>{feats.join(", ")}</Mono> will show “no intent”.</>}
      </div>
      <div class="confirm-actions">
        <button ref={btn} class="btn danger" data-testid="confirm-delete-yes" onClick={async () => {
          confirmDelete.value = null;
          await patchIntent([{ op: "delete", id }]);
        }}>Delete</button>
        <button class="btn" onClick={cancel}>Cancel</button>
      </div>
    </div>
  );
}

export async function addChild(parent: string): Promise<void> {
  const before = new Set(Object.keys(build.value?.tree.nodes ?? {}));
  const ok = await patchIntent([{ op: "add_child", parent, statement: "New intent" }]);
  if (!ok) return;
  const b = build.value;
  const added = b?.tree.order.find((id) => !before.has(id));
  if (added && b) {
    select({ kind: "node", id: added });
    startEdit(added, b.tree.nodes[added].statement ?? "");
  }
}

/** Row action buttons (WHY view): edit, add child, delete.  Keyboard: F2 / + / Delete on a focused row. */
export function RowActions({ n }: { n: IntentNodeJ }) {
  if (!n.in_file) return null;
  const stop = (f: () => void) => (e: Event) => { e.stopPropagation(); f(); };
  return (
    <span class="row-actions">
      <button class="ra" title="edit statement (F2)" aria-label={`edit ${n.id}`} data-testid={`edit-${n.id}`}
              onClick={stop(() => startEdit(n.id, n.statement ?? n.label))}>✎</button>
      <button class="ra" title="add a child intent (+)" aria-label={`add child under ${n.id}`} data-testid={`add-${n.id}`}
              onClick={stop(() => void addChild(n.id))}>+</button>
      {n.parent !== null && (
        <button class="ra" title="delete (Del)" aria-label={`delete ${n.id}`} data-testid={`delete-${n.id}`}
                onClick={stop(() => (confirmDelete.value = { id: n.id, where: "row" }))}>×</button>
      )}
    </span>
  );
}

export function rowKeys(e: KeyboardEvent, n: IntentNodeJ): boolean {
  if (!n.in_file || !editable(build.value)) return false;
  if (e.key === "F2") { startEdit(n.id, n.statement ?? n.label); return true; }
  if (e.key === "+") { void addChild(n.id); return true; }
  if ((e.key === "Delete" || e.key === "Backspace") && n.parent !== null) {
    confirmDelete.value = { id: n.id, where: "row" };
    return true;
  }
  return false;
}

// ------------------------------------------------------------------ inspector: the node editor

export function NodeEditor({ b, n }: { b: BuildJ; n: IntentNodeJ }) {
  const st = b.stale?.[n.id];
  return (
    <div class="node-editor">
      {n.in_file && (
        <div class="stmt-block">
          <div class="field-label">statement</div>
          {editing.value?.id === n.id && editing.value.where === "inspector" ? <StatementInput id={n.id} where="inspector" /> : (
            <div class="stmt" onDblClick={() => startEdit(n.id, n.statement ?? "", "inspector")}>
              {n.statement}
              <button class="link small" onClick={() => startEdit(n.id, n.statement ?? "", "inspector")}
                      data-testid="inspector-edit">edit</button>
            </div>
          )}
        </div>
      )}
      {n.stale && st && <StaleBox b={b} n={n} />}
      {n.in_file && <Structure b={b} n={n} />}
      {n.in_file && <ChecksEditor n={n} />}
      {n.in_file && <AssumptionsEditor n={n} />}
      {n.in_file && n.parent === null && <OrientationRow b={b} />}
      {intentError.value && <div class="callout fail small">{intentError.value}</div>}
    </div>
  );
}

function StaleBox({ b, n }: { b: BuildJ; n: IntentNodeJ }) {
  const st = b.stale![n.id];
  const [note, setNote] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const open = requests.value.filter((r) => r.node === n.id && r.status !== "answered");
  const mine = (asked ? requests.value.find((r) => r.id === asked) : null) ?? open[open.length - 1] ?? null;
  const cs = claude.value;
  const canRun = !!cs?.available.ok && cs.available.login !== "failed";
  const auto = canRun && !!cs?.settings.auto_run;
  const feats = b.features.filter((f) => f.stale?.includes(n.id)).map((f) => f.id);
  return (
    <div class="stale-box" data-testid="stale-box">
      <StaleTag />
      {st.reviewed && st.changed.includes("statement") && (
        <div class="small stmt-change">
          was <span class="was">“{st.reviewed.statement}”</span>
        </div>
      )}
      {st.new && <div class="small muted">new intent: no solution has been reviewed for it yet</div>}
      {!st.new && st.changed.length > 0 && <div class="small muted">changed: {st.changed.join(", ")}</div>}
      {feats.length > 0 && <div class="small">realized by {feats.map((f) => <Mono key={f}>{f} </Mono>)}</div>}
      <div class="stale-actions">
        <button class="btn" data-testid="mark-reviewed" disabled={intentBusy.value}
                onClick={() => void markReviewed([n.id])} title="the current solution still fits this intent">
          Mark reviewed
        </button>
      </div>
      <div class="ask">
        <label class="field-label" for={`ask-${n.id}`}>note for Claude (optional)</label>
        <textarea id={`ask-${n.id}`} rows={2} value={note} data-testid="ask-note"
                  onInput={(e) => setNote((e.target as HTMLTextAreaElement).value)} />
        <button class="btn primary" data-testid="ask-claude" onClick={async () => {
          const r = await askClaude(n.id, note);
          if (r) { setAsked(r.id); setNote(""); }
        }} title={auto ? "queue a request: dipm starts Claude Code for it (auto-run is on)"
                  : "queue a request; nothing is sent until you ask Claude to handle the queue"}>Queue for Claude</button>
        {mine && (
          <div class="small muted" data-testid="request-pending" data-status={mine.status}>
            {mine.status === "open" && (auto ? <>request {mine.id} queued: Claude starts when the current run ends</> :
              canRun ? <>request {mine.id} waiting: <b>Run Claude now</b> from “requests waiting” in the header</> :
              <>request {mine.id} waiting: copy the prompt from “requests waiting” in the header into
                your Claude Code session (MCP tools <Mono>get_requests</Mono>, <Mono>propose_patch</Mono>)</>)}
            {mine.status !== "open" && <>request {mine.id}: {requestText(mine)}</>}
          </div>
        )}
      </div>
    </div>
  );
}

function Structure({ b, n }: { b: BuildJ; n: IntentNodeJ }) {
  const targets = n.parent !== null ? moveTargets(b, n.id) : [];
  return (
    <div class="structure">
      <button class="btn" onClick={() => void addChild(n.id)} data-testid="inspector-add-child">Add child</button>
      {n.parent !== null && (
        <button class="btn danger-outline" onClick={() => (confirmDelete.value = { id: n.id, where: "inspector" })} data-testid="inspector-delete">Delete…</button>
      )}
      {targets.length > 0 && (
        <label class="move-to small">
          move under{" "}
          <select aria-label={`move ${n.id} under`} value="" data-testid="move-to"
                  onChange={(e) => {
                    const v = (e.target as HTMLSelectElement).value;
                    if (v) void patchIntent([{ op: "move", id: n.id, parent: v }]);
                  }}>
            <option value="">…</option>
            {targets.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
      )}
      <RenameId id={n.id} />
      <ConfirmDelete b={b} id={n.id} where="inspector" />
    </div>
  );
}

function RenameId({ id }: { id: string }) {
  const [open, setOpen] = useState(false);
  const [v, setV] = useState(id);
  const [feats, setFeats] = useState(false);
  if (!open) {
    return <button class="link small" onClick={() => { setV(id); setOpen(true); }} data-testid="rename-id"
                   title="rename this id in the intent file and in the DSL's intent(...) / instance_tags literals">rename id…</button>;
  }
  const go = async () => {
    if (v.trim() && v.trim() !== id && await renameId(id, v.trim(), feats)) {
      setOpen(false);
      select({ kind: "node", id: v.trim() });
    }
  };
  return (
    <span class="rename" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); setOpen(false); } }}>
      <input class="stmt-input mono" value={v} aria-label={`new id for ${id}`} data-testid="rename-input"
             onInput={(e) => setV((e.target as HTMLInputElement).value)} onKeyDown={(e) => { if (e.key === "Enter") void go(); }} />
      <button class="btn" onClick={go} data-testid="rename-go">Rename</button>
      <button class="btn" onClick={() => setOpen(false)}>Cancel</button>
      <label class="small rename-opt"><input type="checkbox" checked={feats} data-testid="rename-features"
             onChange={(e) => setFeats((e.target as HTMLInputElement).checked)} />
        also rename matching feature ids (e.g. <Mono>{id}.cable</Mono> → <Mono>{v || "…"}.cable</Mono>)</label>
      <span class="small muted">Saved answers to interpretation questions move with the id.</span>
    </span>
  );
}

function ChecksEditor({ n }: { n: IntentNodeJ }) {
  const [adding, setAdding] = useState(false);
  const checks = n.checks ?? [];
  return (
    <div class="sub-editor" data-testid="checks-editor">
      <div class="field-label">checks <span class="muted">(descriptive in 2a)</span></div>
      {checks.map((c) => <CheckRow key={c.id} node={n.id} c={c} />)}
      {checks.length === 0 && !adding && <div class="small muted">none</div>}
      {adding ? <CheckForm node={n.id} onDone={() => setAdding(false)} /> :
        <button class="link small" onClick={() => setAdding(true)} data-testid="add-check">+ add check</button>}
    </div>
  );
}

function CheckRow({ node, c }: { node: string; c: CheckSpec }) {
  const [open, setOpen] = useState(false);
  if (open) return <CheckForm node={node} c={c} onDone={() => setOpen(false)} />;
  return (
    <div class="check-row" data-check={c.id}>
      <Mono class="cid">{c.id}</Mono>
      {c.kind && <span class="pill">{c.kind}</span>}
      {c.priority && <span class={`pill pr-${c.priority.replace(/ /g, "-")}`}>{c.priority}</span>}
      <span class="check-st">{c.statement}</span>
      <button class="link small" onClick={() => setOpen(true)} aria-label={`edit check ${c.id}`}>edit</button>
    </div>
  );
}

function CheckForm({ node, c, onDone }: { node: string; c?: CheckSpec; onDone: () => void }) {
  const [f, setF] = useState<Partial<CheckSpec>>(c ? { ...c } : { kind: "relation", priority: "should", statement: "", source: "" });
  const set = (k: keyof CheckSpec) => (e: Event) => setF({ ...f, [k]: (e.target as HTMLInputElement).value });
  const save = async () => {
    const fields = { kind: f.kind, source: f.source ?? "", priority: f.priority, statement: f.statement ?? "" };
    const ok = c ? await patchIntent([{ op: "edit_check", id: node, check_id: c.id, fields }]) :
      await patchIntent([{ op: "add_check", id: node, check: fields }]);
    if (ok) onDone();
  };
  return (
    <div class="check-form" data-testid="check-form" onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); onDone(); } }}>
      {c && <Mono>{c.id}</Mono>}
      <label>kind <select value={f.kind} onChange={set("kind")}>{CHECK_KINDS.map((k) => <option key={k}>{k}</option>)}</select></label>
      <label>priority <select value={f.priority} onChange={set("priority")}>{PRIORITIES.map((k) => <option key={k}>{k}</option>)}</select></label>
      <label>source <input value={f.source ?? ""} onInput={set("source")} placeholder="world, pack:…, human:…" /></label>
      <label class="wide">statement <input value={f.statement ?? ""} onInput={set("statement")} data-testid="check-statement"
                                           onKeyDown={(e) => { if (e.key === "Enter") void save(); }} /></label>
      <div class="confirm-actions">
        <button class="btn primary" onClick={save} disabled={!String(f.statement ?? "").trim()} data-testid="save-check">Save</button>
        {c && <button class="btn danger-outline" onClick={async () => {
          if (await patchIntent([{ op: "remove_check", id: node, check_id: c.id }])) onDone();
        }} data-testid="remove-check">Remove</button>}
        <button class="btn" onClick={onDone}>Cancel</button>
      </div>
    </div>
  );
}

function AssumptionsEditor({ n }: { n: IntentNodeJ }) {
  const as = n.assumptions ?? [];
  if (!as.length) return null;
  return (
    <div class="sub-editor" data-testid="assumptions-editor">
      <div class="field-label">assumptions</div>
      {as.map((a) => <AssumptionRow key={a.id} node={n.id} a={a} />)}
    </div>
  );
}

function AssumptionRow({ node, a }: { node: string; a: AssumptionSpec }) {
  const guess = (a.status ?? "proposed") !== "accepted";
  const [rat, setRat] = useState(a.rationale ?? "");
  useEffect(() => setRat(a.rationale ?? ""), [a.rationale]);
  const edit = (fields: Partial<AssumptionSpec>) =>
    patchIntent([{ op: "edit_assumption", id: node, assumption_id: a.id, fields }]);
  return (
    <div class={`assumption st-${a.status ?? "proposed"} ${guess ? "guess" : "confirmed"}`} data-assumption={a.id}
         data-guess={guess ? "1" : "0"}>
      <div class="a-head">
        <Mono>{a.id}</Mono>
        <select aria-label={`status of ${a.id}`} value={a.status ?? "proposed"} data-testid={`status-${a.id}`}
                onChange={(e) => void edit({ status: (e.target as HTMLSelectElement).value })}>
          {ASSUMPTION_STATUS.map((s) => <option key={s}>{s}</option>)}
        </select>
        {a.made_by && <span class="made-by">{a.made_by}</span>}
        {a.sensitivity && <span class={`sens sens-${a.sensitivity}`}>sensitivity {a.sensitivity}</span>}
      </div>
      <div class="small">{a.statement}</div>
      <label class="small rat">rationale
        <input value={rat} onInput={(e) => setRat((e.target as HTMLInputElement).value)} aria-label={`rationale of ${a.id}`}
               onKeyDown={(e) => { if (e.key === "Enter") void edit({ rationale: rat }); }}
               onBlur={() => { if (rat !== (a.rationale ?? "")) void edit({ rationale: rat }); }} />
      </label>
    </div>
  );
}

// ------------------------------------------------------------------ banners

export function IntentBanners() {
  const c = conflict.value;
  const info = intentInfo.value;
  const b = build.value;
  const err = info?.error ?? b?.intent?.error;
  if (!c && !err) return null;
  return (
    <div class="banner-stack">
      {c && (
        <div class="banner conflict" role="alert" data-testid="conflict-banner">
          <span class="b-label">CONFLICT</span>
          <span>The intent file changed on disk since you started this edit; nothing was overwritten.
            {c.ops.length > 0 && <> Your change: <Mono>{describeOps(c.ops)}</Mono>.</>}</span>
          <span class="b-actions">
            <button class="btn" onClick={() => void reloadAfterConflict()} data-testid="conflict-reload">Reload (drop my edit)</button>
            <button class="btn primary" onClick={() => void reapplyAfterConflict()} data-testid="conflict-reapply">Re-apply my edit</button>
          </span>
        </div>
      )}
      {err && (
        <div class="banner conflict" role="alert" data-testid="intent-error-banner">
          <span class="b-label">INTENT FILE</span>
          <span>{info?.file?.split("/").pop()} is invalid; showing the last good version. {err.slice(0, 3).join("; ")}</span>
        </div>
      )}
    </div>
  );
}

export function describeOps(ops: { op: string; [k: string]: unknown }[]): string {
  return ops.map((o) => o.op === "edit_statement" ? `${o.id}: “${o.statement}”` : `${o.op} ${o.id ?? o.parent ?? ""}`).join("; ");
}

/** The print orientation at the root (3E.10): a model guess from the resolution record until the
 *  designer accepts it into the intent file. */
function OrientationRow({ b }: { b: BuildJ }) {
  const o = b.orientation;
  if (!o) return null;
  return (
    <div class={`sub-editor orient ${o.reviewed ? "confirmed" : "guess"}`} data-testid="orientation-row">
      <div class="field-label">print orientation <span class="muted">({o.reviewed ? "accepted, in the intent file" :
        "model guess, in the resolution record"})</span></div>
      <div class="small"><b>{o.label}</b></div>
      {o.rationale && <div class="small muted">{o.rationale}</div>}
      {!o.reviewed && <button class="btn" onClick={() => void acceptGuess("orientation", b)} data-testid="accept-orientation-inspector">
        Accept orientation</button>}
    </div>
  );
}

// Proposals panel (docs/gui.md §7.3): what Claude (via `dipm mcp`) proposed, evaluated in a temp
// copy: semantic diff, DSL text diff, check results, geometry before/after.  Accept applies the
// patch atomically; reject stores a comment that Claude reads with get_proposal_feedback.

import { useState } from "preact/hooks";
import { canAccept, centreMove, diffLines, isOpen, needsOverride, semanticSummary } from "../edit";
import {
  acceptProposal, compare, proposalBusy, proposals, rejectProposal, requests, selectedProposal,
} from "../intent";
import { select } from "../store";
import type { ProposalJ } from "../types";
import { Mono } from "./common";

const STATUS_TEXT: Record<string, string> = {
  pending: "evaluating…", evaluating: "evaluating…", ready: "ready for review", failed: "evaluation failed",
  accepted: "accepted", rejected: "rejected", stale: "stale",
};

export function proposalBadge(): { open: number; total: number } {
  const ps = proposals.value;
  return { open: ps.filter(isOpen).length, total: ps.length };
}

export function ProposalsPanel() {
  const ps = proposals.value;
  const sel = ps.find((p) => p.id === selectedProposal.value) ?? null;
  const reqs = requests.value.filter((r) => r.status === "open");
  return (
    <div class="proposals" data-testid="proposals">
      {ps.length === 0 && (
        <div class="muted small">
          No proposals yet. Proposals come from Claude through <Mono>dipm mcp</Mono> (see gui/README.md); use
          <b> Queue for Claude</b> on a stale intent node to request one.
        </div>
      )}
      <ul class="p-list" role="listbox" aria-label="proposals">
        {[...ps].reverse().map((p) => (
          <li key={p.id} role="option" aria-selected={p.id === sel?.id} tabIndex={0} data-proposal={p.id}
              class={`p-item st-${p.status} ${p.id === sel?.id ? "on" : ""}`}
              onClick={() => (selectedProposal.value = p.id === sel?.id ? null : p.id)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectedProposal.value = p.id === sel?.id ? null : p.id; }
              }}>
            <Mono class="pid">{p.id}</Mono>
            <span class={`p-status st-${p.status}`} data-testid="proposal-status">{STATUS_TEXT[p.status] ?? p.status}</span>
            {p.evaluation && p.status !== "failed" && (
              <span class={`p-checks ${needsOverride(p) ? "fail" : "ok"}`}>
                {needsOverride(p) ? `fails ${(p.evaluation.failing_checks ?? []).join(", ") || "checks"}` : "no failing checks here"}</span>
            )}
            <span class="p-summary">{p.summary}</span>
            {p.addresses_nodes.length > 0 && <span class="p-nodes mono">{p.addresses_nodes.join(" ")}</span>}
          </li>
        ))}
      </ul>
      {sel && <ProposalDetail p={sel} />}
      {reqs.length > 0 && (
        <div class="requests" data-testid="requests">
          <div class="field-label">{reqs.length} request{reqs.length === 1 ? "" : "s"} waiting for Claude</div>
          {reqs.map((r) => (
            <div key={r.id} class="small req">
              <Mono>{r.id}</Mono> waiting · <button class="link mono" onClick={() => select({ kind: "node", id: r.node })}>{r.node}</button>
              {r.note && <> · “{r.note}”</>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ProposalDetail({ p }: { p: ProposalJ }) {
  const ev = p.evaluation;
  const [comment, setComment] = useState("");
  const [anyway, setAnyway] = useState(false);
  const [reason, setReason] = useState("");
  const override = needsOverride(p);
  const busy = proposalBusy.value === p.id;
  const cmp = compare.value?.id === p.id ? compare.value.mode : null;
  const lines = semanticSummary(ev);
  const after = ev?.after;
  const nChanged = ev?.changed_faces?.after.length ?? 0;
  const moves = (ev?.semantic_diff?.features.changed ?? []).map((f) => [f.id, centreMove(ev, f.id)] as const)
    .filter(([, m]) => m !== null);
  return (
    <div class="p-detail" data-testid="proposal-detail">
      <div class="p-head"><Mono>{p.id}</Mono> <b>{p.summary}</b></div>
      {p.revises && <div class="small muted">revises <Mono>{p.revises}</Mono></div>}
      {p.rationale && <div class="small p-rationale">{p.rationale}</div>}
      {p.status_detail && <div class={`small ${p.status === "stale" || p.status === "failed" ? "warn-text" : "muted"}`}>{p.status_detail}</div>}
      {ev && ev.error && <div class="callout fail small">{ev.error}</div>}

      {after && (
        <div class="p-block" data-testid="proposal-checks">
          <div class="field-label">checks</div>
          <div class="small">
            proposed build <span class={after.ok ? "pass-text" : "fail-text"} data-testid="proposal-check-status">
              {after.status.headline}</span>
            {ev?.sweep && <> · <span class={ev.sweep.failing.length ? "fail-text" : "pass-text"}>
              {ev.sweep.points - ev.sweep.failing.length}/{ev.sweep.points}</span> parameter sample points pass</>}
            {" "}· before <span class="muted">{ev?.before?.status.headline}</span>
          </div>
          {(ev?.failing_checks ?? []).length > 0 && (
            <div class="small fail-text" data-testid="proposal-failing">failing at the addressed intent: {ev!.failing_checks!.join(", ")}</div>
          )}
          <div class="small muted">verdict at the design's defaults plus {ev?.sweep?.points ?? 0} sample points; geometry
            shown at {Object.entries(ev?.view_params ?? ev?.params ?? {}).map(([k, v]) => `${k}=${v}`).join(", ")}</div>
          {after.errors.map((e, i) => <div key={i} class="small fail-text">{e.feature}: {e.message}</div>)}
          {(after.stale_nodes ?? []).length > 0 && (
            <div class="small warn-text">still stale after accepting: {after.stale_nodes.join(", ")}</div>
          )}
        </div>
      )}

      {ev?.meshes && (
        <div class="p-block">
          <div class="field-label">geometry</div>
          <div class="seg" role="group" aria-label="geometry before or after">
            {(["before", "after", "overlay"] as const).map((m) => (
              <button key={m} aria-pressed={cmp === m} class={cmp === m ? "on" : ""} data-testid={`compare-${m}`}
                      onClick={() => (compare.value = cmp === m ? null : { id: p.id, mode: m })}>{m}</button>
            ))}
            {cmp && <button onClick={() => (compare.value = null)} data-testid="compare-exit">live model</button>}
          </div>
          <div class="small muted">{nChanged} changed face{nChanged === 1 ? "" : "s"} highlighted in the viewport</div>
          {moves.map(([fid, m]) => (
            <div key={fid} class="small mono" data-testid="centre-move">
              {fid}: {m!.before.map((c) => `(${c.map((x) => +x.toFixed(2)).join(", ")})`).join(" ")} →{" "}
              {m!.after.map((c) => `(${c.map((x) => +x.toFixed(2)).join(", ")})`).join(" ")}
            </div>
          ))}
        </div>
      )}

      {lines.length > 0 && (
        <div class="p-block" data-testid="semantic-diff">
          <div class="field-label">semantic diff</div>
          <ul class="sem">{lines.map((l, i) => <li key={i} class="small">{l}</li>)}</ul>
        </div>
      )}

      {ev?.text_diff && Object.entries(ev.text_diff).map(([name, diff]) => (
        <div class="p-block" key={name}>
          <div class="field-label">{name}</div>
          <pre class="diff" data-testid="text-diff">
            {diffLines(diff).map((l, i) => <div key={i} class={`dl ${l.cls}`}>{l.text || " "}</div>)}
          </pre>
        </div>
      ))}

      {isOpen(p) && (
        <div class="p-actions">
          {!override ? (
            <button class="btn primary" disabled={!canAccept(p) || busy} onClick={() => void acceptProposal(p.id)}
                    data-testid="accept-proposal" title="apply the patch to the design files (atomic), record review, rebuild">
              Accept
            </button>
          ) : !anyway ? (
            <button class="btn danger-outline" disabled={!canAccept(p) || busy} onClick={() => setAnyway(true)}
                    data-testid="accept-anyway" title="this proposal fails checks: accepting records an override">
              Accept anyway…
            </button>
          ) : (
            <div class="anyway" data-testid="accept-anyway-form">
              <label class="field-label" for={`why-${p.id}`}>why accept with failing checks? (recorded in the review record)</label>
              <textarea id={`why-${p.id}`} rows={2} value={reason} data-testid="override-reason"
                        onInput={(e) => setReason((e.target as HTMLTextAreaElement).value)} />
              <div class="confirm-actions">
                <button class="btn danger" disabled={!reason.trim() || busy} data-testid="confirm-accept-anyway"
                        onClick={() => void acceptProposal(p.id, reason.trim())}>Accept with failing checks</button>
                <button class="btn" onClick={() => { setAnyway(false); setReason(""); }}>Cancel</button>
              </div>
            </div>
          )}
          <textarea rows={2} placeholder="what should change? (sent to Claude)" value={comment} aria-label="rejection comment"
                    onInput={(e) => setComment((e.target as HTMLTextAreaElement).value)} data-testid="reject-comment" />
          <button class="btn danger-outline" disabled={busy || !comment.trim()} data-testid="reject-proposal"
                  onClick={() => { void rejectProposal(p.id, comment); setComment(""); }}>Reject with comment</button>
        </div>
      )}
      {p.status === "stale" && (
        <div class="small warn-text">A file changed since this proposal was made. Ask Claude to regenerate it.</div>
      )}
      {p.feedback.length > 0 && (
        <div class="p-block" data-testid="proposal-feedback">
          <div class="field-label">history</div>
          {p.feedback.map((f, i) => (
            <div key={i} class="small"><span class="muted mono">{f.at.replace("T", " ").replace("Z", "")}</span> {f.kind}
              {f.comment && <> · “{f.comment}”</>}</div>
          ))}
        </div>
      )}
    </div>
  );
}

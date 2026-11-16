// "Assumed: PLA · FDM 0.2 mm · change" (docs/gui.md §8.3 item 4; 3E.6, 3E.10).  Hatched while any
// part of the context or the print orientation is a model-made, unreviewed assumption; the
// picker writes the designer's choice into the intent file, which makes the chip solid.

import { useState } from "preact/hooks";
import { acceptGuess, intentBusy, reinferOrientation, setContext } from "../intent";
import { build } from "../store";

const MATERIALS = ["PLA", "PETG", "ABS"];
const LAYERS = ["0.1 mm", "0.15 mm", "0.2 mm", "0.28 mm"];
const NOZZLES = ["0.25 mm", "0.4 mm", "0.6 mm"];

export function ContextChip() {
  const b = build.value;
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<Record<string, string>>({});
  const ctx = b?.context;
  if (!ctx) return null;
  const o = b?.orientation ?? null;
  const assumed = ctx.assumed;
  const oGuess = !!o && !o.reviewed;
  const guess = assumed || oGuess;
  const items = ctx.items;
  const val = (k: string) => f[k] ?? items[k]?.value ?? "";
  return (
    <span class="ctx-wrap">
      <button class={`ctx-chip ${guess ? "guess" : "confirmed"}`} data-testid="context-chip" data-guess={guess ? "1" : "0"}
              onClick={() => { setF({}); setOpen(!open); }}
              title={guess ? "model-made assumptions, not reviewed: click to review or change" : "context (reviewed)"}>
        {assumed ? "Assumed: " : ""}{ctx.summary}{o ? <span class="ctx-orient"> · {shortOrient(o.label)}</span> : null}
        <span class="ctx-change"> · change</span>
      </button>
      {open && (
        <div class="popover ctx-pop" role="dialog" aria-label="material and process" data-testid="context-picker">
          <div class="field-label">material and process</div>
          <div class="ctx-grid">
            <label>process <select value={val("process")} disabled>
              <option value="fdm_printing">FDM printing</option></select></label>
            <label>material <select value={val("material")} data-testid="ctx-material"
                                    onChange={(e) => setF({ ...f, material: (e.target as HTMLSelectElement).value })}>
              {MATERIALS.map((m) => <option key={m}>{m}</option>)}</select></label>
            <label>layer height <select value={val("layer_height")} data-testid="ctx-layer"
                                        onChange={(e) => setF({ ...f, layer_height: (e.target as HTMLSelectElement).value })}>
              {LAYERS.map((m) => <option key={m}>{m}</option>)}</select></label>
            <label>nozzle <select value={val("nozzle")}
                                  onChange={(e) => setF({ ...f, nozzle: (e.target as HTMLSelectElement).value })}>
              {NOZZLES.map((m) => <option key={m}>{m}</option>)}</select></label>
          </div>
          <div class="small muted">
            {Object.entries(items).map(([k, v]) => (
              <span key={k} class={`ctx-item ${v.reviewed ? "confirmed" : "guess"}`} data-ctx={k}>{k}: {v.value}</span>))}
          </div>
          <div class="confirm-actions">
            <button class="btn primary" disabled={intentBusy.value} data-testid="context-confirm"
                    onClick={async () => { if (await setContext(Object.fromEntries(
                      ["process", "material", "layer_height", "nozzle"].map((k) => [k, val(k)])))) setOpen(false); }}>
              Confirm</button>
            <button class="btn" onClick={() => setOpen(false)}>Close</button>
          </div>
          {o && (
            <div class={`orient ${o.reviewed ? "confirmed" : "guess"}`} data-testid="orientation">
              <div class="field-label">print orientation {o.reviewed ? "(accepted)" : "(model guess, unreviewed)"}</div>
              <div class="small"><b>{o.label}</b></div>
              {o.rationale && <div class="small muted">{o.rationale}</div>}
              {!o.reviewed && (
                <div class="confirm-actions">
                  <button class="btn primary" data-testid="accept-orientation" disabled={intentBusy.value}
                          onClick={() => void acceptGuess("orientation", b)}>Accept orientation</button>
                  <button class="btn" data-testid="reinfer-orientation" onClick={() => void reinferOrientation()}>Re-infer</button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </span>
  );
}

function shortOrient(label: string): string {
  return label.replace(/^Print with the /i, "").replace(/ down$/, " down");
}

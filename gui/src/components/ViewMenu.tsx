// View menu in the header strip (docs/gui.md §8.3 item 8; tolerance-uncertainty §4.1): Work /
// Photo view; 1:1 real size; process texture; reference objects; scale bar; uncertainty mode.

import { useState } from "preact/hooks";
import { oneToOneOn, refsOn, scaleBarOn, setView, textureOn, uncertainty, viewMode, type Uncertainty, type ViewMode } from "../store";

export function ViewMenu() {
  const [open, setOpen] = useState(false);
  const m = viewMode.value;
  return (
    <span class="view-menu">
      <button class="btn view-btn" aria-haspopup="menu" aria-expanded={open} data-testid="view-menu"
              onClick={() => setOpen(!open)}>
        View ▾ <span class="muted small">{m === "photo" ? "photo" : "work"}{oneToOneOn.value ? " · 1:1" : ""}
          {uncertainty.value === "heatmap" ? " · margins" : ""}</span>
      </button>
      {open && (
        <div class="popover menu" role="menu" onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}>
          <div class="field-label">view</div>
          {(["work", "photo"] as ViewMode[]).map((v) => (
            <label key={v} class="menu-row" role="menuitemradio" aria-checked={m === v}>
              <input type="radio" name="viewmode" checked={m === v} data-testid={`view-${v}`}
                     onChange={() => setView(viewMode, "viewMode", v)} />
              {v === "work" ? "Work view (crisp)" : "Photo view (depth of field)"}
            </label>
          ))}
          <label class="menu-row" role="menuitemcheckbox" aria-checked={oneToOneOn.value}>
            <input type="checkbox" checked={oneToOneOn.value} data-testid="toggle-1to1"
                   onChange={(e) => (oneToOneOn.value = (e.target as HTMLInputElement).checked)} /> 1:1 real size
          </label>
          <div class="field-label">scale cues</div>
          <label class="menu-row"><input type="checkbox" checked={textureOn.value} data-testid="toggle-texture"
                 onChange={(e) => setView(textureOn, "textureOn", (e.target as HTMLInputElement).checked)} /> Process texture</label>
          <label class="menu-row"><input type="checkbox" checked={refsOn.value[m]} data-testid="toggle-refs"
                 onChange={(e) => setView(refsOn, "refsOn", { ...refsOn.value, [m]: (e.target as HTMLInputElement).checked })} />
            Reference objects <span class="muted small">({m} view)</span></label>
          <label class="menu-row"><input type="checkbox" checked={scaleBarOn.value} data-testid="toggle-scalebar"
                 onChange={(e) => setView(scaleBarOn, "scaleBarOn", (e.target as HTMLInputElement).checked)} /> Scale bar</label>
          <div class="field-label">uncertainty (one at a time)</div>
          {([["none", "None"], ["heatmap", "Margin heatmap"]] as [Uncertainty, string][]).map(([v, l]) => (
            <label key={v} class="menu-row" role="menuitemradio" aria-checked={uncertainty.value === v}>
              <input type="radio" name="uncertainty" checked={uncertainty.value === v} data-testid={`uncertainty-${v}`}
                     onChange={() => setView(uncertainty, "uncertainty", v)} /> {l}
            </label>
          ))}
          <div class="muted small">Variation ghost and animated samples wait for opt-in sampling.</div>
        </div>
      )}
    </span>
  );
}

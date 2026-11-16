// One-time 1:1 calibration (docs/gui.md §8.3 item 12): when the OS reports no plausible physical
// size, hold a real ID-1 card (85.60 × 53.98 mm: a bank card, an ID card) against the screen and
// resize the on-screen card to match.  An optional coin check confirms it.  Stored per screen.

import { useState } from "preact/hooks";
import { needCalibration, realSize, saveCalibration } from "../realsize";
import { oneToOneOn } from "../store";
import { COINS, ID1 } from "../scale";

export function Calibration() {
  const [w, setW] = useState(323); // CSS px: 96 px/in, the CSS convention, as a starting guess
  const [coin, setCoin] = useState<string>("");
  const [done, setDone] = useState<number | null>(null);
  const ppm = w / ID1.width;
  return (
    <div class="calibration" role="dialog" aria-label="calibrate real size" data-testid="calibration">
      <div class="field-label">calibrate 1:1</div>
      <div class="small">{realSize.value.reason ? `${realSize.value.reason}. ` : ""}
        Hold a real bank or ID card (ID-1, 85.60 × 53.98 mm) against the screen and drag the slider until the outline
        matches it.</div>
      <div class="cal-card" style={{ width: `${w}px`, height: `${(w * ID1.height) / ID1.width}px` }} data-testid="cal-card" />
      <input type="range" min={150} max={700} step={0.5} value={w} aria-label="card width" data-testid="cal-slider"
             onInput={(e) => setW(Number((e.target as HTMLInputElement).value))} />
      <div class="small mono">{ppm.toFixed(3)} px/mm</div>
      <div class="small">Optional check with a coin:{" "}
        <select value={coin} onChange={(e) => setCoin((e.target as HTMLSelectElement).value)} aria-label="coin">
          <option value="">—</option>
          {Object.keys(COINS).map((c) => <option key={c} value={c}>{c} ({COINS[c]} mm)</option>)}
        </select>
        {coin && <span class="cal-coin" style={{ width: `${COINS[coin] * ppm}px`, height: `${COINS[coin] * ppm}px` }} />}
      </div>
      <div class="confirm-actions">
        <button class="btn primary" data-testid="cal-save" onClick={() => setDone(saveCalibration(w))}>It matches</button>
        <button class="btn" onClick={() => { oneToOneOn.value = false; needCalibration.value = false; }}>Cancel</button>
      </div>
      {done && <div class="small">saved: {done.toFixed(3)} px/mm for this screen</div>}
    </div>
  );
}

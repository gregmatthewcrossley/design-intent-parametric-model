// First-open review prompt (docs/gui.md §8.3 item 5; NOTES #48 change): a design with no review
// record starts unreviewed.  Nothing is marked reviewed automatically: the designer chooses.

import { intentBusy, intentInfo, reviewAll, reviewOneByOne } from "../intent";
import { firstOpenDismissed } from "../store";

export function FirstOpen() {
  const info = intentInfo.value;
  if (!info || !info.exists || info.review_exists || firstOpenDismissed.value) return null;
  return (
    <div class="modal-backdrop">
      <div class="modal" role="dialog" aria-modal="true" aria-labelledby="first-open-title" data-testid="first-open">
        <h2 id="first-open-title">This design hasn't been reviewed</h2>
        <p class="small">Nobody has confirmed that the solution fits its intent yet, so every intent node shows as
          not reviewed. You can mark everything reviewed now, or go through the nodes one by one (each has a
          <b> Mark reviewed</b> button in the inspector).</p>
        <div class="confirm-actions">
          <button class="btn primary" disabled={intentBusy.value} data-testid="review-all"
                  onClick={async () => { if (await reviewAll()) firstOpenDismissed.value = true; }}>Mark all reviewed</button>
          <button class="btn" disabled={intentBusy.value} data-testid="review-one-by-one"
                  onClick={async () => { if (await reviewOneByOne()) firstOpenDismissed.value = true; }}>Review one by one</button>
        </div>
      </div>
    </div>
  );
}

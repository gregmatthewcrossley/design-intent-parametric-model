import type { ComponentChildren } from "preact";
import { useEffect, useState } from "preact/hooks";
import { build, persist } from "../store";
import type { Status } from "../types";

const STATUS_TEXT: Record<Status, string> = { ok: "pass", warn: "needs review", fail: "failing", not_built: "not built" };

export function Dot({ status, title }: { status: Status; title?: string }) {
  return <span class={`dot dot-${status}`} title={title ?? STATUS_TEXT[status]} aria-label={STATUS_TEXT[status]} />;
}

export function Section(props: { id: string; title: string; badge?: ComponentChildren; children: ComponentChildren;
                                  attention?: boolean; forceOpen?: unknown }) {
  const key = `section.${props.id}`;
  const [open, setOpen] = useState<boolean>(() => {
    try { return JSON.parse(localStorage.getItem(`dipm.${key}`) ?? "true"); } catch { return true; }
  });
  useEffect(() => { if (props.forceOpen) setOpen(true); }, [props.forceOpen]);
  const toggle = () => { setOpen(!open); persist(key, !open); };
  return (
    <section class={`section ${open ? "open" : "closed"} ${props.attention ? "attention" : ""}`} data-section={props.id}>
      <button class="section-head" onClick={toggle} aria-expanded={open}>
        <span class="chev" aria-hidden="true">{open ? "▾" : "▸"}</span>
        <span class="section-title">{props.title}</span>
        {props.badge !== undefined && <span class="section-badge">{props.badge}</span>}
      </button>
      {open && <div class="section-body">{props.children}</div>}
    </section>
  );
}

export function Mono({ children, class: cls }: { children: ComponentChildren; class?: string }) {
  return <span class={`mono ${cls ?? ""}`}>{children}</span>;
}

/** The one style for guesses vs. confirmed items (B5, PAIN-12): model-made or unreviewed items
 *  are a hatched chip with a dashed outline; reviewed or designer-made items are solid.  Driven
 *  by the payload's provenance map, so accepting one item restyles it everywhere at once. */
export function Guess({ pkey, label, title, onAccept, testid }: {
  pkey: string; label: ComponentChildren; title?: string; onAccept?: () => void; testid?: string;
}) {
  const pv = build.value?.provenance?.[pkey];
  const guess = pv ? pv.guess : true;
  return (
    <span class={`guess-chip ${guess ? "guess" : "confirmed"}`} data-guess={guess ? "1" : "0"} data-pkey={pkey}
          data-testid={testid} title={title ?? (guess ? `${pv?.made_by ?? "model"}-made, not reviewed yet` : "reviewed")}>
      {label}
      {guess && onAccept && (
        <button class="link small accept-guess" onClick={(e) => { e.stopPropagation(); onAccept(); }}
                title="I reviewed this: keep it" data-testid={`accept-${pkey}`}>accept</button>
      )}
    </span>
  );
}

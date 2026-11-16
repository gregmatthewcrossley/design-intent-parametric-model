import type { ComponentChildren } from "preact";
import { useState } from "preact/hooks";
import { persist } from "../store";
import type { Status } from "../types";

const STATUS_TEXT: Record<Status, string> = { ok: "pass", warn: "needs review", fail: "failing", not_built: "not built" };

export function Dot({ status, title }: { status: Status; title?: string }) {
  return <span class={`dot dot-${status}`} title={title ?? STATUS_TEXT[status]} aria-label={STATUS_TEXT[status]} />;
}

export function Section(props: { id: string; title: string; badge?: ComponentChildren; children: ComponentChildren;
                                  attention?: boolean }) {
  const key = `section.${props.id}`;
  const [open, setOpen] = useState<boolean>(() => {
    try { return JSON.parse(localStorage.getItem(`dipm.${key}`) ?? "true"); } catch { return true; }
  });
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

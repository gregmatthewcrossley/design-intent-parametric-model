import { build, building, design, designError, roundTripMs, theme, wsUp, persist } from "../store";

export function Header() {
  const d = design.value, b = build.value;
  const status = b?.status;
  return (
    <header class="header">
      <div class="brand" title="design-intent parametric model">dipm</div>
      <div class="title">
        <h1>{d?.name ?? "…"}</h1>
        <span class="path mono" title={d?.file ?? ""}>{shortPath(d?.file ?? "")}</span>
      </div>
      <div class="header-status">
        {status && (
          <span class={`badge ${status === "PASS" ? "badge-ok" : "badge-fail"}`} data-testid="build-status">
            {status === "PASS" ? "PASS" : `FAIL · ${b!.error_count}`}
          </span>
        )}
        {b && (
          <span class="mono num" title="engine build time · round trip">
            {b.ms.toFixed(0)} ms{roundTripMs.value !== null ? ` · ${roundTripMs.value.toFixed(0)} ms` : ""}
          </span>
        )}
        {building.value && <span class="busy" aria-live="polite">building…</span>}
        {b?.resolving && <span class="busy" title="interpretations are being re-resolved">re-resolving…</span>}
        {designError.value && <span class="badge badge-fail" title={designError.value}>design error</span>}
        <span class={`ws ${wsUp.value ? "up" : "down"}`} title={wsUp.value ? "live: watching the design file" : "not connected"}>
          {wsUp.value ? "live" : "offline"}
        </span>
        <button class="theme-toggle" onClick={() => { theme.value = theme.value === "dark" ? "light" : "dark"; persist("theme", theme.value); }}
                aria-label="toggle light/dark theme" title="toggle light/dark theme">
          {theme.value === "dark" ? "☀" : "☾"}
        </button>
      </div>
    </header>
  );
}

function shortPath(p: string): string {
  const parts = p.split("/");
  return parts.length > 3 ? "…/" + parts.slice(-3).join("/") : p;
}

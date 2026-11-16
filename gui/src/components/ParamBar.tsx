import { useState } from "preact/hooks";
import { build, building, design, lit, params, select, selection, setParam, hover, sameSel } from "../store";
import type { ParamInfo } from "../types";
import { fmtNumber } from "../model";

export function ParamBar() {
  const d = design.value;
  if (!d) return <footer class="parambar" />;
  return (
    <footer class="parambar" aria-label="parameters">
      <span class="parambar-title">PARAMETERS</span>
      <div class="params">
        {d.params.map((p) => <ParamControl key={p.name} p={p} />)}
      </div>
      <div class="parambar-status mono num">
        {building.value ? "building…" : build.value ? `${build.value.ms.toFixed(0)} ms` : ""}
      </div>
    </footer>
  );
}

function step(p: ParamInfo): number {
  if (!p.range) return 1;
  const span = p.range[1] - p.range[0];
  return span >= 50 ? 1 : span >= 5 ? 0.1 : 0.01;
}

function ParamControl({ p }: { p: ParamInfo }) {
  const v = params.value[p.name] ?? p.default;
  const sel = { kind: "param" as const, id: p.name };
  const isSel = sameSel(selection.value, sel);
  const isLit = lit.value.params.has(p.name);
  const [draft, setDraft] = useState<string | null>(null);
  const commit = (s: string) => {
    setDraft(null);
    const x = Number(s);
    if (!Number.isFinite(x) || !p.range) return;
    setParam(p.name, Math.min(p.range[1], Math.max(p.range[0], x)));
  };
  return (
    <div class={`param ${isSel ? "selected" : ""} ${isLit ? "lit" : ""}`} data-param={p.name}>
      <button class="param-name mono" title={`${p.doc}\nclick: highlight what this drives`}
              onClick={() => select(sel)} onMouseEnter={() => (hover.value = sel)} onMouseLeave={() => (hover.value = null)}
              aria-pressed={isSel}>
        {p.name}
      </button>
      {p.kind === "choice" && (
        <select value={String(v)} onChange={(e) => setParam(p.name, (e.target as HTMLSelectElement).value)}
                aria-label={p.name}>
          {p.choices!.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      )}
      {p.kind === "range" && (
        <>
          <input type="range" min={p.range![0]} max={p.range![1]} step={step(p)} value={Number(v)}
                 aria-label={p.name}
                 onInput={(e) => setParam(p.name, Number((e.target as HTMLInputElement).value))} />
          <input class="num-input mono num" type="number" min={p.range![0]} max={p.range![1]} step={step(p)}
                 value={draft ?? fmtNumber(Number(v), 6)} aria-label={`${p.name} value`}
                 onInput={(e) => setDraft((e.target as HTMLInputElement).value)}
                 onBlur={(e) => commit((e.target as HTMLInputElement).value)}
                 onKeyDown={(e) => { if (e.key === "Enter") commit((e.target as HTMLInputElement).value); }} />
          {p.unit && <span class="unit">{p.unit}</span>}
        </>
      )}
    </div>
  );
}

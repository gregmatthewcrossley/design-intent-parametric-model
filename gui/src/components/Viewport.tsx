import { useEffect, useRef, useState } from "preact/hooks";
import { api } from "../api";
import { decodeMesh, bounds, type DecodedMesh } from "../mesh";
import { faceLabel } from "../model";
import {
  build, goodBuild, hover, lit, oneToOneOn, params, pinnedLit, refsOn, scaleBarOn, select, selection, showGhost, textureOn,
  theme, uncertainty, viewMode,
} from "../store";
import { Viewer, type FaceState, type Palette, type ViewName } from "../viewer";
import { compareStates } from "../edit";
import { compare, proposals, viewProposalAt } from "../intent";
import { faceMargins, heatColor, STATE_TEXT } from "../margins";
import { chooseReference } from "../reference";
import { scaleBarStep } from "../scale";
import { measure, needCalibration, realSize, watchScreen } from "../realsize";
import { Calibration } from "./Calibration";

const cache = new Map<string, DecodedMesh>();

/** A proposal's before/after mesh, cached by its content id. */
async function getProposalMesh(pid: string, which: "before" | "after", meshId: string): Promise<DecodedMesh> {
  const key = `p:${meshId}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const m = decodeMesh(await api.proposalMesh(pid, which));
  cache.set(key, m);
  return m;
}

async function getMesh(id: string): Promise<DecodedMesh> {
  const hit = cache.get(id);
  if (hit) return hit;
  const m = decodeMesh(await api.mesh(id));
  cache.set(id, m);
  if (cache.size > 24) cache.delete(cache.keys().next().value!);
  return m;
}

function cssPalette(): Palette {
  const s = getComputedStyle(document.documentElement);
  const v = (n: string) => s.getPropertyValue(n).trim() || "#888";
  return {
    background: v("--viewport-bg"), model: v("--model"), modelHover: v("--model-hover"), modelLit: v("--model-lit"),
    modelSelected: v("--model-selected"), modelDim: v("--model-dim"), fail: v("--model-fail"), edge: v("--model-edge"),
    ghost: v("--model-ghost"), triad: v("--ink-2"), heatOk: v("--heat-ok"), heatThin: v("--heat-thin"),
    heatFail: v("--heat-fail"), heatNone: v("--heat-none"), outline: v("--model-outline"), refGhost: v("--ref-ghost"),
  };
}

export function Viewport() {
  const host = useRef<HTMLDivElement>(null);
  const triad = useRef<HTMLCanvasElement>(null);
  const viewer = useRef<Viewer | null>(null);
  const [tip, setTip] = useState<{ face: number; x: number; y: number } | null>(null);
  const [size, setSize] = useState<string>("");
  const [meshErr, setMeshErr] = useState<string | null>(null);
  const [bar, setBar] = useState<{ px: number; label: string } | null>(null);
  const [meshKey, setMeshKey] = useState(0);

  useEffect(() => {
    const v = new Viewer(host.current!, cssPalette(), {
      onHover: (face, x, y) => {
        setTip(face === null ? null : { face, x, y });
        if (compare.value) return; // proposal geometry: face ids are not the live build's
        const cur = hover.value;
        if (face === null) {
          if (cur?.kind === "face") hover.value = null;
        } else if (cur?.kind !== "face" || cur.id !== face) {
          hover.value = { kind: "face", id: face };
        }
      },
      onClick: (face) => { if (!compare.value) select(face === null ? null : { kind: "face", id: face }); },
      onView: () => {
        const ppm = v.pxPerMm();
        const s = scaleBarStep(ppm, 120);
        setBar((old) => (old && Math.abs(old.px - s.px) < 0.5 && old.label === s.label ? old : { px: s.px, label: s.label }));
      },
    }, triad.current!);
    viewer.current = v;
    // test hook (e2e and screenshots): the viewer and the current build
    (window as unknown as { __dipm: unknown }).__dipm = { viewer: v, build, compare, proposals, realSize, measure };
    return () => v.dispose();
  }, []);

  // geometry: the current build; while it fails, the last good model as a grey ghost
  const b = build.value;
  const good = goodBuild.value;
  const failing = !!b && !b.ok;
  const ghostId = failing ? (b?.last_good_mesh_id ?? good?.mesh_id ?? null) : null;
  const cmp = compare.value;
  const cp = cmp ? proposals.value.find((p) => p.id === cmp.id) ?? null : null;
  const cev = cp?.evaluation ?? null;
  const cmpKey = cmp && cev?.meshes ? `${cmp.id}:${cmp.mode}:${cev.meshes.before}:${cev.meshes.after}` : null;
  const cmpShow = cmpKey ? cmp!.mode : null;   // what is actually loaded into the viewer
  // NOTES #53 change: show the comparison at the designer's current parameters
  useEffect(() => {
    if (!cmp || !cev || cev.error) return;
    const vp = cev.view_params ?? cev.params ?? {};
    const cur = params.value;
    const differs = Object.keys(cur).some((k) => String(vp[k]) !== String(cur[k]));
    if (differs) void viewProposalAt(cmp.id, cur);
  }, [cmp?.id, cev?.view_params ? JSON.stringify(cev.view_params) : null]);
  // proposal comparison: before / after / overlay (after solid, before as a ghost)
  useEffect(() => {
    const v = viewer.current;
    if (!v || !cmp || !cev?.meshes) return;
    let cancelled = false;
    (async () => {
      try {
        const ms = cev.meshes!;
        const after = ms.after ? await getProposalMesh(cmp.id, "after", ms.after) : null;
        const before = ms.before ? await getProposalMesh(cmp.id, "before", ms.before) : null;
        if (cancelled) return;
        const main = cmp.mode === "before" ? before : after;
        if (main) v.setMesh(main); else v.clearMesh();
        v.setGhost(cmp.mode === "overlay" ? before : null);
        const cf = cev.changed_faces;
        const changed = (cmp.mode === "before" ? cf?.before : cf?.after) ?? [];
        const outline = (cmp.mode === "before" ? cf?.outline_before : cf?.outline_after) ?? [];
        v.setFaceStates(compareStates(main?.nFaces ?? 0, changed, outline));
        setMeshErr(null);
      } catch (e) {
        if (!cancelled) setMeshErr((e as Error).message);
      }
    })();
    return () => { cancelled = true; };
  }, [cmpKey]);

  useEffect(() => {
    const v = viewer.current;
    if (!v || !b || cmpKey) return;
    let cancelled = false;
    (async () => {
      try {
        if (b.mesh_id) {
          const m = await getMesh(b.mesh_id);
          if (cancelled) return;
          v.setMesh(m);
          const bb = bounds(m.positions);
          setSize(bb.max.map((x, i) => (x - bb.min[i]).toFixed(1)).join(" × ") + " mm");
          setMeshKey((k) => k + 1);
        } else {
          v.clearMesh();
        }
        const g = ghostId && ghostId !== b.mesh_id && showGhost.value ? await getMesh(ghostId) : null;
        if (!cancelled) v.setGhost(g);
        setMeshErr(null);
      } catch (e) {
        if (!cancelled) setMeshErr((e as Error).message);
      }
    })();
    return () => { cancelled = true; };
  }, [b?.mesh_id, ghostId, showGhost.value, cmpKey]);

  // face colours: failure tint, pinned selection, hover, lit/dim; or the margin heatmap
  const L = lit.value, P = pinnedLit.value, h = hover.value, s = selection.value;
  const heat = uncertainty.value === "heatmap";
  useEffect(() => {
    const v = viewer.current;
    if (!v || !b || cmpKey) return;
    const n = b.faces.length;
    const st: FaceState[] = new Array(n).fill("base");
    if (heat) {
      const fm = faceMargins(b);
      for (let i = 0; i < n; i++) {
        const t = heatColor(fm[i]).token;
        st[i] = t === "fail" ? "heatFail" : t === "warn" ? "heatThin" : t === "ok" ? "heatOk" : "heatNone";
      }
      if (h?.kind === "face" && h.id < n) st[h.id] = "hover";
      if (s?.kind === "face" && s.id < n) st[s.id] = "selected";
      v.setFaceStates(st);
      return;
    }
    const panelHover = h && h.kind !== "face";
    const ref = panelHover ? L : P;
    const refSel = panelHover ? h : s;
    if (refSel && refSel.kind !== "face") {
      for (let i = 0; i < n; i++) st[i] = ref.faces.has(i) ? "lit" : "dim";
    }
    if (s?.kind === "face" && s.id < n) st[s.id] = "selected";
    if (h?.kind === "face" && h.id < n && st[h.id] !== "selected") st[h.id] = "hover";
    for (let i = 0; i < n; i++) {
      const f = b.faces[i];
      if (f.failing) st[i] = st[i] === "lit" || st[i] === "selected" ? "failLit" : "fail";
      else if (f.failing_touched && (st[i] === "base" || st[i] === "dim")) st[i] = "failTouched";
    }
    v.setFaceStates(st);
  }, [b, L, P, h, s, cmpKey, heat]);

  // work / photo view
  const mode = viewMode.value;
  useEffect(() => { viewer.current?.setMode(mode); }, [mode]);

  // process texture from the process pack (same source as the checks): FDM layer lines along the
  // build direction of the inferred / accepted print orientation
  const app = b?.appearance;
  const texKey = app ? `${app.layer_pitch}:${app.extrusion_width}:${(app.build_direction ?? []).join(",")}:${meshKey}` : "";
  useEffect(() => {
    const v = viewer.current;
    if (!v) return;
    v.setTexture(app && app.build_direction ? {
      pitch: app.layer_pitch, width: app.extrusion_width, up: app.build_direction, topAngleDeg: app.top_line_angle_deg,
      roughness: app.roughness,
    } : null, textureOn.value && !cmpKey);
  }, [texKey, textureOn.value, cmpKey]);

  // reference objects: one at a time, by what is under the cursor, else the part as a whole
  const refOn = refsOn.value[mode];
  const hoveredFace = h?.kind === "face" ? h.id : null;
  useEffect(() => {
    const v = viewer.current;
    if (!v || !b || cmpKey || !refOn || !b.references) { v?.setReference(null, null); return; }
    v.setReference(chooseReference(b, hoveredFace, v.partBounds()), b.references);
  }, [b?.mesh_id, hoveredFace, refOn, cmpKey, meshKey, mode]);

  // 1:1 real size: px/mm from the OS display size (or a card calibration), recomputed on screen change
  const on11 = oneToOneOn.value;
  useEffect(() => {
    if (!on11) { viewer.current?.setOneToOne(null); return; }
    let alive = true;
    const run = async () => {
      const r = await measure();
      if (alive) viewer.current?.setOneToOne(r.pxPerMm);
    };
    void run();
    const stop = watchScreen(() => void run());
    return () => { alive = false; stop(); };
  }, [on11]);
  const rs = realSize.value;
  useEffect(() => { if (on11 && rs.pxPerMm) viewer.current?.setOneToOne(rs.pxPerMm); }, [rs.pxPerMm]);

  useEffect(() => {
    // theme tokens change after the attribute flips; read them on the next frame
    requestAnimationFrame(() => viewer.current?.setPalette(cssPalette()));
  }, [theme.value]);

  const go = (name: ViewName | "fit") => viewer.current?.setView(name);
  const tipFace = tip && b && !cmpShow ? b.faces[tip.face] : null;
  const fm = heat && b ? faceMargins(b) : null;
  return (
    <div class={`viewport mode-${mode}`}>
      <div class="viewport-host" ref={host} data-testid="viewport" />
      <canvas class="triad" ref={triad} aria-hidden="true" />
      <div class="viewport-tools" role="toolbar" aria-label="views">
        <button onClick={() => go("fit")} title="fit (F)">fit</button>
        <button onClick={() => go("iso")}>iso</button>
        <button onClick={() => go("front")}>front</button>
        <button onClick={() => go("side")}>side</button>
        <button onClick={() => go("top")}>top</button>
        {failing && ghostId && (
          <label class="ghost-toggle" title="show the last good model, greyed">
            <input type="checkbox" checked={showGhost.value}
                   onChange={(e) => (showGhost.value = (e.target as HTMLInputElement).checked)} /> last good
          </label>
        )}
      </div>
      <div class="viewport-info mono num">{size}</div>
      {scaleBarOn.value && bar && bar.px > 0 && (
        <div class="scale-bar" data-testid="scale-bar" aria-label={`scale bar ${bar.label}`}>
          <div class="sb-line" style={{ width: `${bar.px}px` }} />
          <span class="sb-label mono">{bar.label}</span>
        </div>
      )}
      {on11 && rs.pxPerMm && (
        <div class="one-to-one" data-testid="one-to-one" title={`${rs.pxPerMm.toFixed(3)} CSS px per mm · ${rs.reason}`}>
          1:1 on {rs.name || "this screen"}{rs.source === "calibration" ? " (calibrated)" : ""}
        </div>
      )}
      {on11 && needCalibration.value && <Calibration />}
      {mode === "photo" && !on11 && <div class="photo-tag" data-testid="photo-tag">photo view · focus follows the cursor</div>}
      {heat && b && <HeatLegend />}
      {cmpShow && cp && (
        <div class="viewport-banner compare-banner" data-testid="compare-banner">
          <span class="b-label">COMPARING PROPOSAL {cp.id}</span> · inspection paused ·{" "}
          {cmpShow === "overlay" ? "after, with before as a ghost" : cmpShow}
          {" · "}{((cmpShow === "before" ? cev?.changed_faces?.before : cev?.changed_faces?.after) ?? []).length} changed
          face(s) highlighted{((cmpShow === "before" ? cev?.changed_faces?.outline_before : cev?.changed_faces?.outline_after) ?? []).length
            ? ", outline changes lighter" : ""}
          {cev?.view_params && <span class="muted"> · at {Object.entries(cev.view_params).map(([k, v]) => `${k}=${v}`).join(", ")}</span>}
          <button class="btn" onClick={() => (compare.value = null)}>live model</button>
        </div>
      )}
      {failing && !cmpShow && (
        <div class="viewport-banner" data-testid="fail-banner">
          build failed: {b!.failing.join(", ")} · {b!.mesh_id ? "faces it made in red, faces it changed tinted" : "no geometry"}
          {ghostId && " · last good model in grey"}
        </div>
      )}
      {meshErr && <div class="viewport-banner">{meshErr}</div>}
      {tip && b && (
        <div class="tooltip mono" style={{ left: `${tip.x + 14}px`, top: `${tip.y + 12}px` }} role="tooltip" data-testid="face-tip">
          {cmpShow ? (cev?.face_tags?.[cmpShow === "before" ? "before" : "after"]?.[tip.face] ?? "") : faceLabel(b, tip.face)}
          {tipFace?.size && <div class="tip-size" data-testid="size-callout">{tipFace.size}</div>}
          {fm && fm[tip.face] && <div class="tip-size">{STATE_TEXT[fm[tip.face].state]}{fm[tip.face].by ? ` (${fm[tip.face].by})` : ""}</div>}
        </div>
      )}
    </div>
  );
}

function HeatLegend() {
  return (
    <div class="heat-legend" data-testid="heat-legend" aria-label="margin heatmap legend">
      <span class="field-label">smallest margin</span>
      <span><i class="sw sw-ok" /> ample</span>
      <span><i class="sw sw-thin" /> thin</span>
      <span><i class="sw sw-fail" /> failing</span>
      <span><i class="sw sw-none" /> no check</span>
    </div>
  );
}

export function useViewKeys() {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t && (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA")) return;
      const v = (window as unknown as { __dipm?: { viewer: Viewer } }).__dipm?.viewer;
      if (!v) return;
      if (e.key === "f") v.setView("fit");
      if (e.key === "1") v.setView("front");
      if (e.key === "3") v.setView("side");
      if (e.key === "7") v.setView("top");
      if (e.key === "0") v.setView("iso");
    };
    addEventListener("keydown", h);
    return () => removeEventListener("keydown", h);
  }, []);
}

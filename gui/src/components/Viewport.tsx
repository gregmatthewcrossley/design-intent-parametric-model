import { useEffect, useRef, useState } from "preact/hooks";
import { api } from "../api";
import { decodeMesh, bounds, type DecodedMesh } from "../mesh";
import { faceLabel } from "../model";
import { build, goodBuild, hover, lit, pinnedLit, select, selection, showGhost, theme } from "../store";
import { Viewer, type FaceState, type Palette, type ViewName } from "../viewer";
import { compareStates } from "../edit";
import { compare, proposals } from "../intent";

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
    ghost: v("--model-ghost"), triad: v("--ink-2"),
  };
}

export function Viewport() {
  const host = useRef<HTMLDivElement>(null);
  const triad = useRef<HTMLCanvasElement>(null);
  const viewer = useRef<Viewer | null>(null);
  const [tip, setTip] = useState<{ face: number; x: number; y: number } | null>(null);
  const [size, setSize] = useState<string>("");
  const [meshErr, setMeshErr] = useState<string | null>(null);

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
    }, triad.current!);
    viewer.current = v;
    // test hook (e2e and screenshots): the viewer and the current build
    (window as unknown as { __dipm: unknown }).__dipm = { viewer: v, build, compare, proposals };
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
        const changed = (cmp.mode === "before" ? cev.changed_faces?.before : cev.changed_faces?.after) ?? [];
        v.setFaceStates(compareStates(main?.nFaces ?? 0, changed));
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

  // face colours: failure tint, pinned selection, hover, lit/dim
  const L = lit.value, P = pinnedLit.value, h = hover.value, s = selection.value;
  useEffect(() => {
    const v = viewer.current;
    if (!v || !b || cmpKey) return;
    const n = b.faces.length;
    const st: FaceState[] = new Array(n).fill("base");
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
  }, [b, L, P, h, s, cmpKey]);

  useEffect(() => {
    // theme tokens change after the attribute flips; read them on the next frame
    requestAnimationFrame(() => viewer.current?.setPalette(cssPalette()));
  }, [theme.value]);

  const go = (name: ViewName | "fit") => viewer.current?.setView(name);
  return (
    <div class="viewport">
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
      {cmpShow && cp && (
        <div class="viewport-banner compare-banner" data-testid="compare-banner">
          <span class="b-label">PROPOSAL {cp.id}</span> {cmpShow === "overlay" ? "after, with before as a ghost" : cmpShow}
          {" · "}{((cmpShow === "before" ? cev?.changed_faces?.before : cev?.changed_faces?.after) ?? []).length} changed
          face(s) highlighted
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
        <div class="tooltip mono" style={{ left: `${tip.x + 14}px`, top: `${tip.y + 12}px` }} role="tooltip">
          {cmpShow ? (cev?.face_tags?.[cmpShow === "before" ? "before" : "after"]?.[tip.face] ?? "") : faceLabel(b, tip.face)}
        </div>
      )}
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

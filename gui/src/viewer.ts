// Imperative three.js viewport: shaded model with visible edges, face picking, standard views,
// an axis triad, and a greyed "last good" ghost (docs/gui.md §2 item 2, §4).
//
// Iteration 3 (docs/gui.md §8.3):
//   * work view (crisp) and photo view: a thin-lens camera with depth of field (photo.ts), blur
//     capped, focus following the cursor (raycast, eased), soft procedural image-based lighting
//     (three.js RoomEnvironment through PMREM: no third-party HDRI);
//   * 1:1 real size: an orthographic camera snapped to the nearest standard view, zoomed so
//     1 mm on the model is 1 mm on the glass (scale.ts);
//   * FDM process texture: layer lines at the real pitch along the build direction and top
//     surface extrusion lines, as normal/roughness detail only, fading in above ~2 px (texture.ts);
//   * margin heatmap face states; ghosted reference objects beside the part (reference.ts).

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { bounds, edgeSegments, faceOfTriangle, type DecodedMesh } from "./mesh";
import { BLUR_CAP_PX, F_NUMBER, SENSOR_H, cappedBlur, cocPx, easeFocus, focalLength, magnification } from "./photo";
import { STD_DIRS, nearestStdView, orthoHeightMm, perspectivePxPerMm, type StdView } from "./scale";
import { FADE_FULL_PX, FADE_START_PX, textureFade } from "./texture";
import { besidePart, type RefChoice } from "./reference";
import type { ReferencesJ } from "./types";
import type { GhostPose } from "./loop";

export type ViewName = "iso" | "front" | "side" | "top";

export interface Palette {
  background: string;
  model: string;
  modelHover: string;
  modelLit: string;
  modelSelected: string;
  modelDim: string;
  fail: string;
  edge: string;
  ghost: string;
  triad: string;
  heatOk: string;
  heatThin: string;
  heatFail: string;
  heatNone: string;
  outline: string;
  refGhost: string;
  compGhost: string;
}

export type FaceState = "base" | "hover" | "lit" | "selected" | "dim" | "fail" | "failLit" | "failTouched"
  | "heatOk" | "heatThin" | "heatFail" | "heatNone" | "outline";

export interface TextureSpec {
  pitch: number; // layer height (mm)
  width: number; // extrusion width (mm)
  up: number[]; // build direction (part coordinates)
  topAngleDeg: number; // top-surface line direction
  roughness: number;
}

interface Callbacks {
  onHover: (face: number | null, x: number, y: number) => void;
  onClick: (face: number | null) => void;
  onView?: () => void;
}

const VIEW_DIRS: Record<ViewName, [number, number, number]> = {
  // Z up (the engine's convention); front looks along -Y (from +Y), side along -X (from +X)
  iso: [1.25, 1.0, 0.85],
  front: [0, 1, 0],
  side: [1, 0, 0],
  top: [0, 0, 1],
};

const reducedMotion = () => typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

// ------------------------------------------------------------------ depth of field (photo view)

const DOF_VERT = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`;

// Thin lens, per pixel: c = f² / (N (s − f)) · |d − s| / d on the sensor, in device px, capped.
// Gather with a golden-angle disc; a sample counts if its own circle of confusion reaches the
// centre (scatter-as-gather), so a sharp foreground does not bleed into a blurred background.
const DOF_FRAG = /* glsl */ `
#include <packing>
varying vec2 vUv;
uniform sampler2D tColor;
uniform sampler2D tDepth;
uniform float uNear, uFar, uFocus, uF, uN, uSensorH, uViewH, uCap;
uniform vec2 uRes;
float distAt(vec2 uv) {
  float d = texture2D(tDepth, uv).x;
  return -perspectiveDepthToViewZ(d, uNear, uFar);
}
float cocAt(float dist) {
  if (uFocus <= uF) return 0.0;
  float c = (uF * uF / (uN * (uFocus - uF))) * abs(dist - uFocus) / max(dist, 1e-3);
  return min(uCap, c / uSensorH * uViewH * 0.5);
}
void main() {
  float d0 = distAt(vUv);
  float c0 = cocAt(d0);
  vec4 acc = texture2D(tColor, vUv);
  float wsum = 1.0;
  if (c0 > 0.5) {
    const int N = 48;
    for (int i = 0; i < N; i++) {
      float r = sqrt((float(i) + 0.5) / float(N));
      float a = float(i) * 2.39996323;
      vec2 o = vec2(cos(a), sin(a)) * r * c0;
      vec2 uv = vUv + o / uRes;
      float ds = distAt(uv);
      float cs = cocAt(ds);
      float w = clamp(cs - r * c0 + 1.0, 0.0, 1.0);
      if (ds > d0) w = max(w, clamp(c0 - r * c0 + 1.0, 0.0, 1.0));
      acc += texture2D(tColor, uv) * w;
      wsum += w;
    }
  }
  gl_FragColor = acc / wsum;
}`;

// ------------------------------------------------------------------ the viewer

export class Viewer {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private persp: THREE.PerspectiveCamera;
  private ortho: THREE.OrthographicCamera;
  private camera: THREE.PerspectiveCamera | THREE.OrthographicCamera;
  private controls: OrbitControls;
  private model = new THREE.Group();
  private mesh: THREE.Mesh | null = null;
  private edges: THREE.LineSegments | null = null;
  private ghost = new THREE.Group();
  private refGroup = new THREE.Group();
  private compGroup = new THREE.Group();      // iteration 4: component envelopes (ghosts)
  private comps: (GhostPose & { component: string })[] = [];
  private data: DecodedMesh | null = null;
  private faceStates: FaceState[] = [];
  private palette: Palette;
  private raycaster = new THREE.Raycaster();
  private pointer = new THREE.Vector2();
  private down: { x: number; y: number } | null = null;
  private frame = 0;
  private pendingPick: { x: number; y: number } | null = null;
  private resizeObs: ResizeObserver;
  private triad: HTMLCanvasElement;
  private light = new THREE.DirectionalLight(0xffffff, 1.6);
  private hemi = new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.25);
  private fitted = false;
  private radius = 100;
  // photo view
  private mode: "work" | "photo" = "work";
  private envTex: THREE.Texture | null = null;
  private rt: THREE.WebGLRenderTarget | null = null;
  private dofScene = new THREE.Scene();
  private dofCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  private dofMat: THREE.ShaderMaterial;
  private focus = 600; // mm along the view axis
  private focusTarget = 600;
  private lastT = 0;
  // 1:1
  private oneToOne: number | null = null; // CSS px per mm
  private oneToOneView: StdView | null = null;
  // process texture
  private texture: TextureSpec | null = null;
  private textureOn = false;
  private texUniforms = {
    uTexOn: { value: 0 }, uBuild: { value: new THREE.Vector3(0, 0, 1) }, uBed: { value: 0 },
    uPitch: { value: 0.2 }, uWidth: { value: 0.45 }, uTopPerp: { value: new THREE.Vector3(1, -1, 0).normalize() },
    uAmp: { value: 0.35 },
  };
  private reference: RefChoice | null = null;
  private refs: ReferencesJ | null = null;

  constructor(private host: HTMLElement, palette: Palette, private cb: Callbacks, triad: HTMLCanvasElement) {
    this.palette = palette;
    this.triad = triad;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    host.appendChild(this.renderer.domElement);
    this.renderer.domElement.className = "viewport-canvas";
    this.persp = new THREE.PerspectiveCamera(30, 1, 0.1, 100000);
    this.persp.up.set(0, 0, 1);
    this.persp.position.set(300, -360, 270);
    this.ortho = new THREE.OrthographicCamera(-100, 100, 100, -100, -100000, 100000);
    this.ortho.up.set(0, 0, 1);
    this.camera = this.persp;
    this.persp.add(this.light);
    this.light.position.set(0.4, 1, 0.6);
    this.scene.add(this.persp, this.ortho, this.hemi, this.model, this.ghost, this.refGroup, this.compGroup);
    this.controls = new OrbitControls(this.persp, this.renderer.domElement);
    this.controls.enableDamping = false;
    this.controls.screenSpacePanning = true;
    this.controls.addEventListener("change", () => this.render());
    // after an orbit, put the reference object beside the part again as seen from the new view
    this.controls.addEventListener("end", () => { if (this.reference) this.setReference(this.reference, this.refs); });
    this.dofMat = new THREE.ShaderMaterial({
      vertexShader: DOF_VERT, fragmentShader: DOF_FRAG, depthTest: false, depthWrite: false,
      uniforms: {
        tColor: { value: null }, tDepth: { value: null }, uNear: { value: 1 }, uFar: { value: 1000 },
        uFocus: { value: 600 }, uF: { value: 45 }, uN: { value: F_NUMBER }, uSensorH: { value: SENSOR_H },
        uViewH: { value: 900 }, uCap: { value: BLUR_CAP_PX }, uRes: { value: new THREE.Vector2(1, 1) },
      },
    });
    this.dofScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2), this.dofMat));
    const el = this.renderer.domElement;
    el.addEventListener("pointermove", this.onMove);
    el.addEventListener("pointerdown", this.onDown);
    el.addEventListener("pointerup", this.onUp);
    el.addEventListener("pointerleave", () => this.cb.onHover(null, 0, 0));
    this.resizeObs = new ResizeObserver(() => this.resize());
    this.resizeObs.observe(host);
    this.setPalette(palette);
    this.resize();
  }

  dispose(): void {
    this.resizeObs.disconnect();
    this.controls.dispose();
    this.rt?.dispose();
    this.envTex?.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  // ------------------------------------------------------------------ geometry
  private modelMaterial(): THREE.MeshStandardMaterial {
    const mat = new THREE.MeshStandardMaterial({
      vertexColors: true, roughness: 0.82, metalness: 0.08, polygonOffset: true, polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    });
    const U = this.texUniforms;
    mat.onBeforeCompile = (sh) => {
      Object.assign(sh.uniforms, U);
      sh.vertexShader = sh.vertexShader
        .replace("#include <common>", "#include <common>\nvarying vec3 vWPos;\nvarying vec3 vWNor;")
        .replace("#include <begin_vertex>",
                 "#include <begin_vertex>\nvWPos = (modelMatrix * vec4(position, 1.0)).xyz;\nvWNor = normalize(mat3(modelMatrix) * normal);");
      sh.fragmentShader = sh.fragmentShader
        .replace("#include <common>", `#include <common>
varying vec3 vWPos;
varying vec3 vWNor;
uniform float uTexOn, uBed, uPitch, uWidth, uAmp;
uniform vec3 uBuild, uTopPerp;`)
        .replace("#include <roughnessmap_fragment>", `#include <roughnessmap_fragment>
float dSide = 0.0, dSlope = 0.0, dTop = 0.0, dSlope2 = 0.0;
if (uTexOn > 0.5) {
  vec3 bw = normalize(uBuild);
  float h = dot(vWPos, bw) - uBed;
  float pp = uPitch / max(fwidth(h), 1e-6);
  dSide = smoothstep(${FADE_START_PX.toFixed(1)}, ${FADE_FULL_PX.toFixed(1)}, pp) * (1.0 - abs(dot(normalize(vWNor), bw)));
  dSlope = (fract(h / uPitch) - 0.5) * 2.0;
  float s = dot(vWPos, normalize(uTopPerp));
  float pp2 = uWidth / max(fwidth(s), 1e-6);
  dTop = smoothstep(${FADE_START_PX.toFixed(1)}, ${FADE_FULL_PX.toFixed(1)}, pp2) * smoothstep(0.92, 0.99, dot(normalize(vWNor), bw));
  dSlope2 = (fract(s / uWidth) - 0.5) * 2.0;
  roughnessFactor = clamp(roughnessFactor + 0.12 * (dSide * (dSlope * dSlope - 0.33) + dTop * (dSlope2 * dSlope2 - 0.33)), 0.04, 1.0);
}`)
        .replace("#include <normal_fragment_maps>", `#include <normal_fragment_maps>
if (uTexOn > 0.5) {
  vec3 bView = normalize((viewMatrix * vec4(normalize(uBuild), 0.0)).xyz);
  vec3 tView = normalize((viewMatrix * vec4(normalize(uTopPerp), 0.0)).xyz);
  normal = normalize(normal + bView * dSlope * uAmp * dSide + tView * dSlope2 * uAmp * dTop);
}`);
    };
    return mat;
  }

  setMesh(m: DecodedMesh): void {
    this.data = m;
    this.disposeGroup(this.model);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(m.positions, 3));
    g.setAttribute("normal", new THREE.BufferAttribute(m.normals, 3));
    g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(m.positions.length), 3));
    g.setIndex(new THREE.BufferAttribute(m.indices, 1));
    this.mesh = new THREE.Mesh(g, this.modelMaterial());
    const es = edgeSegments(m);
    const eg = new THREE.BufferGeometry();
    eg.setAttribute("position", new THREE.BufferAttribute(es.positions, 3));
    this.edges = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ color: this.palette.edge }));
    this.model.add(this.mesh, this.edges);
    if (this.faceStates.length !== m.nFaces) this.faceStates = new Array(m.nFaces).fill("base");
    this.paint();
    this.applyTexture();
    this.applyMode();
    if (!this.fitted) {
      this.setView("iso");
      this.fitted = true;
    } else if (this.oneToOne) {
      this.setOneToOne(this.oneToOne);
    }
    this.render();
  }

  clearMesh(): void {
    this.disposeGroup(this.model);
    this.mesh = null;
    this.edges = null;
    this.data = null;
    this.render();
  }

  /** The last good model, greyed and translucent, shown while the current build fails. */
  setGhost(m: DecodedMesh | null): void {
    this.disposeGroup(this.ghost);
    if (m) {
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(m.positions, 3));
      g.setAttribute("normal", new THREE.BufferAttribute(m.normals, 3));
      g.setIndex(new THREE.BufferAttribute(m.indices, 1));
      const mat = new THREE.MeshStandardMaterial({ color: this.palette.ghost, transparent: true, opacity: 0.32,
                                                   depthWrite: false, roughness: 1, metalness: 0 });
      const es = edgeSegments(m);
      const eg = new THREE.BufferGeometry();
      eg.setAttribute("position", new THREE.BufferAttribute(es.positions, 3));
      const lm = new THREE.LineBasicMaterial({ color: this.palette.ghost, transparent: true, opacity: 0.7 });
      this.ghost.add(new THREE.Mesh(g, mat), new THREE.LineSegments(eg, lm));
      if (!this.fitted) {
        this.data = this.data ?? m;
        this.setView("iso");
        this.fitted = true;
      }
    }
    this.render();
  }

  private disposeGroup(g: THREE.Group): void {
    for (const c of [...g.children]) {
      g.remove(c);
      c.traverse((o) => {
        const mm = o as THREE.Mesh;
        mm.geometry?.dispose();
        const mat = mm.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(mat)) mat.forEach((x) => x.dispose());
        else mat?.dispose();
      });
    }
  }

  // ------------------------------------------------------------------ colours
  setPalette(p: Palette): void {
    this.palette = p;
    this.scene.background = new THREE.Color(p.background);
    if (this.edges) (this.edges.material as THREE.LineBasicMaterial).color.set(p.edge);
    for (const c of this.ghost.children) {
      const m = (c as THREE.Mesh).material as THREE.MeshStandardMaterial;
      m.color.set(p.ghost);
    }
    if (this.comps.length) {
      this.disposeGroup(this.compGroup);
      for (const g of this.comps) this.compGroup.add(buildComponentGhost(g, p));
    }
    this.paint();
    this.render();
  }

  setFaceStates(states: FaceState[]): void {
    this.faceStates = states;
    this.paint();
    this.render();
  }

  private paint(): void {
    const m = this.data;
    if (!m || !this.mesh) return;
    const attr = this.mesh.geometry.getAttribute("color") as THREE.BufferAttribute;
    const col = attr.array as Float32Array;
    const p = this.palette;
    const colors: Record<FaceState, THREE.Color> = {
      base: new THREE.Color(p.model), hover: new THREE.Color(p.modelHover), lit: new THREE.Color(p.modelLit),
      selected: new THREE.Color(p.modelSelected), dim: new THREE.Color(p.modelDim), fail: new THREE.Color(p.fail),
      failLit: new THREE.Color(p.fail).lerp(new THREE.Color(p.modelSelected), 0.35),
      failTouched: new THREE.Color(p.model).lerp(new THREE.Color(p.fail), 0.28),
      heatOk: new THREE.Color(p.heatOk), heatThin: new THREE.Color(p.heatThin), heatFail: new THREE.Color(p.heatFail),
      heatNone: new THREE.Color(p.heatNone), outline: new THREE.Color(p.outline),
    };
    for (let f = 0; f < m.nFaces; f++) {
      const c = colors[this.faceStates[f] ?? "base"];
      const s = m.faceRanges[f * 2], n = m.faceRanges[f * 2 + 1];
      for (let i = s * 3; i < (s + n) * 3; i++) {
        const v = m.indices[i] * 3;
        col[v] = c.r;
        col[v + 1] = c.g;
        col[v + 2] = c.b;
      }
    }
    attr.needsUpdate = true;
  }

  // ------------------------------------------------------------------ work / photo view
  setMode(mode: "work" | "photo"): void {
    this.mode = mode;
    this.applyMode();
    this.render();
  }

  getMode(): "work" | "photo" {
    return this.mode;
  }

  private applyMode(): void {
    const photo = this.mode === "photo";
    if (photo && !this.envTex) {
      // soft image-based lighting from a procedural room (no third-party HDRI)
      const pm = new THREE.PMREMGenerator(this.renderer);
      this.envTex = pm.fromScene(new RoomEnvironment(), 0.04).texture;
      pm.dispose();
    }
    this.scene.environment = photo ? this.envTex : null;
    this.light.intensity = photo ? 0.55 : 1.6;
    this.hemi.intensity = photo ? 0.35 : 1.25;
    if (this.mesh) {
      const mat = this.mesh.material as THREE.MeshStandardMaterial;
      mat.envMapIntensity = photo ? 0.9 : 0;
      mat.roughness = photo ? (this.texture?.roughness ?? 0.6) : 0.82;
      mat.needsUpdate = true;
    }
  }

  // ------------------------------------------------------------------ process texture
  setTexture(spec: TextureSpec | null, on: boolean): void {
    this.texture = spec;
    this.textureOn = on && !!spec;
    this.applyTexture();
    this.render();
  }

  private applyTexture(): void {
    const U = this.texUniforms, t = this.texture;
    U.uTexOn.value = this.textureOn && t ? 1 : 0;
    if (!t) return;
    const up = new THREE.Vector3(...(t.up as [number, number, number])).normalize();
    U.uBuild.value.copy(up);
    U.uPitch.value = t.pitch;
    U.uWidth.value = t.width;
    // the bed: the lowest point of the part along the build direction
    let bed = 0;
    if (this.data) {
      const P = this.data.positions;
      bed = Infinity;
      for (let i = 0; i < P.length; i += 3) bed = Math.min(bed, P[i] * up.x + P[i + 1] * up.y + P[i + 2] * up.z);
    }
    U.uBed.value = isFinite(bed) ? bed : 0;
    // top-surface lines: perpendicular to a direction at `topAngleDeg` in the bed plane
    const ref = Math.abs(up.z) < 0.9 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1, 0, 0);
    const a = ref.clone().sub(up.clone().multiplyScalar(ref.dot(up))).normalize();
    const b = up.clone().cross(a).normalize();
    const th = (t.topAngleDeg * Math.PI) / 180;
    U.uTopPerp.value.copy(a.multiplyScalar(Math.cos(th)).add(b.multiplyScalar(Math.sin(th)))).normalize();
  }

  /** Texture visibility at the orbit target (tests; the shader decides per pixel with fwidth). */
  textureState(): { on: boolean; pitch: number; pitchPx: number; fade: number } {
    const t = this.texture;
    const dpr = this.renderer.getPixelRatio();
    const ppm = this.pxPerMm();
    const pitchPx = t ? t.pitch * ppm * dpr : 0;
    return { on: this.textureOn && !!t, pitch: t?.pitch ?? 0, pitchPx, fade: this.textureOn && t ? textureFade(pitchPx) : 0 };
  }

  // ------------------------------------------------------------------ reference objects
  setReference(choice: RefChoice | null, refs: ReferencesJ | null): void {
    this.disposeGroup(this.refGroup);
    this.reference = choice;
    this.refs = refs;
    if (choice && refs && this.data) {
      this.camera.updateMatrixWorld();
      const right = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 0).normalize();
      const up = new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 1).normalize();
      const obj = buildReference(choice, refs, this.palette, this.partBounds(), right, up);
      if (obj) this.refGroup.add(obj);
    }
    this.render();
  }

  // ------------------------------------------------------------------ component envelopes (iteration 4)
  /** Ghost the components a design must fit (a rod, a reel) where their checks posed them:
   *  translucent, outlined dashed while unreviewed (model-made) and solid once accepted. */
  setComponents(poses: (GhostPose & { component: string })[]): void {
    this.disposeGroup(this.compGroup);
    this.comps = poses;
    for (const g of poses) this.compGroup.add(buildComponentGhost(g, this.palette));
    this.render();
  }

  /** What is ghosted (tests): component, shape, dashed, world bounding box. */
  componentState(): { component: string; shape: string; dashed: boolean; box: number[] }[] {
    return this.compGroup.children.map((o, i) => {
      const bb = new THREE.Box3().setFromObject(o);
      return { component: this.comps[i]?.component ?? o.name, shape: this.comps[i]?.shape ?? "?",
               dashed: !!this.comps[i]?.dashed, box: [bb.min.x, bb.min.y, bb.min.z, bb.max.x, bb.max.y, bb.max.z] };
    });
  }

  referenceState(): { kind: string; label: string; box: number[] | null } | null {
    if (!this.reference) return null;
    const bb = new THREE.Box3().setFromObject(this.refGroup);
    return { kind: this.reference.kind, label: this.reference.label,
             box: bb.isEmpty() ? null : [bb.min.x, bb.min.y, bb.min.z, bb.max.x, bb.max.y, bb.max.z] };
  }

  partBounds(): { min: number[]; max: number[] } {
    if (!this.data) return { min: [0, 0, 0], max: [0, 0, 0] };
    const b = bounds(this.data.positions);
    return { min: b.min, max: b.max };
  }

  // ------------------------------------------------------------------ camera
  private size(): { w: number; h: number } {
    return { w: Math.max(1, this.host.clientWidth), h: Math.max(1, this.host.clientHeight) };
  }

  setView(name: ViewName | "fit"): void {
    if (this.oneToOne) {
      // 1:1 keeps its scale; a view button snaps to that standard view instead
      const dir = name === "fit" ? STD_DIRS[this.oneToOneView ?? "front"] : VIEW_DIRS[name];
      this.oneToOneView = nearestStdView(dir);
      this.setOneToOne(this.oneToOne);
      return;
    }
    const src = this.data?.positions;
    let center = new THREE.Vector3();
    let radius = this.radius;
    if (src && src.length) {
      const b = bounds(src);
      const min = new THREE.Vector3(...b.min), max = new THREE.Vector3(...b.max);
      center = min.clone().add(max).multiplyScalar(0.5);
      radius = Math.max(1, max.clone().sub(min).length() / 2);
      this.radius = radius;
    }
    const cam = this.persp;
    const dir = name === "fit"
      ? cam.position.clone().sub(this.controls.target).normalize()
      : new THREE.Vector3(...VIEW_DIRS[name]).normalize();
    const fov = (cam.fov * Math.PI) / 180;
    const aspect = Math.max(0.2, cam.aspect);
    const dist = (radius * 1.15) / Math.sin(Math.min(fov, fov * aspect) / 2);
    cam.up.set(0, 0, 1);
    if (name === "top") cam.up.set(0, 1, 0);
    this.controls.target.copy(center);
    cam.position.copy(center).add(dir.multiplyScalar(dist));
    cam.near = dist / 100;
    cam.far = dist * 100;
    cam.updateProjectionMatrix();
    this.controls.update();
    this.focus = this.focusTarget = dist;
    this.render();
  }

  /** Move the perspective camera towards (k < 1) or away from the target (tests, photo view). */
  dolly(k: number): void {
    const cam = this.persp;
    const t = this.controls.target;
    const off = cam.position.clone().sub(t).multiplyScalar(k);
    cam.position.copy(t).add(off);
    this.controls.update();
    if (this.reference) this.setReference(this.reference, this.refs);
    this.render();
  }

  /** Look at a model point from `dist` mm along `dir` (tests and screenshots: close-ups). */
  lookAt(point: number[], dist: number, dir: number[] = [0.35, 1, 0.25]): void {
    const cam = this.persp;
    const t = new THREE.Vector3(...(point as [number, number, number]));
    const d = new THREE.Vector3(...(dir as [number, number, number])).normalize();
    this.controls.target.copy(t);
    cam.up.set(0, 0, 1);
    cam.position.copy(t).add(d.multiplyScalar(dist));
    cam.near = Math.max(0.01, dist / 100);
    cam.far = dist * 1000;
    cam.updateProjectionMatrix();
    this.controls.update();
    this.focus = this.focusTarget = dist;
    if (this.reference) this.setReference(this.reference, this.refs);
    this.render();
  }

  /** 1:1 real size (CSS px per mm), or null to leave it.  Snaps to the nearest standard view. */
  setOneToOne(pxPerMm: number | null): void {
    if (!pxPerMm) {
      if (this.oneToOne) {
        this.oneToOne = null;
        this.oneToOneView = null;
        this.camera = this.persp;
        this.controls.object = this.persp;
        this.controls.enableRotate = true;
        this.controls.enableZoom = true;
        const d = this.ortho.position.clone().sub(this.controls.target).normalize();
        const dist = this.persp.position.distanceTo(this.controls.target) || this.radius * 4;
        this.persp.position.copy(this.controls.target).add(d.multiplyScalar(dist));
        this.persp.up.copy(this.ortho.up);
        this.controls.update();
      }
      this.render();
      return;
    }
    const wasOn = !!this.oneToOne;
    this.oneToOne = pxPerMm;
    if (!this.oneToOneView || !wasOn) {
      const cur = this.camera.position.clone().sub(this.controls.target).normalize();
      this.oneToOneView = nearestStdView([cur.x, cur.y, cur.z]);
    }
    const b = this.partBounds();
    const center = new THREE.Vector3((b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2, (b.min[2] + b.max[2]) / 2);
    const dir = new THREE.Vector3(...STD_DIRS[this.oneToOneView]);
    const { w, h } = this.size();
    const hh = orthoHeightMm(h, pxPerMm) / 2, hw = orthoHeightMm(w, pxPerMm) / 2;
    const o = this.ortho;
    o.left = -hw; o.right = hw; o.top = hh; o.bottom = -hh; o.zoom = 1;
    o.up.set(0, 0, 1);
    if (this.oneToOneView === "top" || this.oneToOneView === "bottom") o.up.set(0, 1, 0);
    const keepPan = wasOn ? this.controls.target.clone() : center;
    o.position.copy(keepPan).add(dir.multiplyScalar(this.radius * 6 + 1000));
    o.near = -100000; o.far = 100000;
    o.updateProjectionMatrix();
    this.camera = o;
    this.controls.object = o;
    this.controls.target.copy(keepPan);
    this.controls.enableRotate = false;
    this.controls.enableZoom = false; // zooming would break 1:1; pan stays
    this.controls.update();
    this.render();
  }

  oneToOneState(): { pxPerMm: number | null; view: StdView | null } {
    return { pxPerMm: this.oneToOne, view: this.oneToOneView };
  }

  /** CSS px per mm at the orbit target (scale bar). */
  pxPerMm(): number {
    const { h } = this.size();
    if (this.camera instanceof THREE.OrthographicCamera) {
      const o = this.camera;
      return (h * o.zoom) / (o.top - o.bottom);
    }
    const dist = this.persp.position.distanceTo(this.controls.target);
    return perspectivePxPerMm(h, this.persp.fov, dist);
  }

  /** Distance in CSS px between two model points as drawn (tests: 1:1 must give 1 mm per mm). */
  measureCssPx(a: number[], b: number[]): number {
    const { w, h } = this.size();
    this.camera.updateMatrixWorld();
    const pa = new THREE.Vector3(...(a as [number, number, number])).project(this.camera);
    const pb = new THREE.Vector3(...(b as [number, number, number])).project(this.camera);
    return Math.hypot(((pa.x - pb.x) / 2) * w, ((pa.y - pb.y) / 2) * h);
  }

  // ------------------------------------------------------------------ photo view: lens and focus
  private lens(): { f: number; N: number; viewH: number } {
    const { h } = this.size();
    return { f: focalLength(this.persp.fov), N: F_NUMBER, viewH: h };
  }

  private viewDistance(p: THREE.Vector3): number {
    const cam = this.persp;
    const fwd = new THREE.Vector3();
    cam.getWorldDirection(fwd);
    return p.clone().sub(cam.position).dot(fwd);
  }

  /** Focus on the surface under the cursor (eased; instant with prefers-reduced-motion). */
  private focusAt(clientX: number, clientY: number): void {
    if (this.mode !== "photo" || !this.mesh || this.camera !== this.persp) return;
    const hit = this.hit(clientX, clientY);
    if (!hit) return;
    this.focusTarget = Math.max(this.lens().f * 1.05, this.viewDistance(hit.point));
    if (reducedMotion()) this.focus = this.focusTarget;
    this.lastT = performance.now();
    this.render();
  }

  photoState(points: number[][] = []): { focus: number; target: number; f: number; N: number; magnification: number;
                                          cap: number; blur: { raw: number; capped: number }[] } {
    const { f, N, viewH } = this.lens();
    const blur = points.map((p) => {
      const d = this.viewDistance(new THREE.Vector3(...(p as [number, number, number])));
      const raw = cocPx(f, N, this.focus, d, viewH);
      return { raw, capped: cappedBlur(raw) };
    });
    return { focus: this.focus, target: this.focusTarget, f, N, magnification: magnification(f, this.focus),
             cap: BLUR_CAP_PX, blur };
  }

  // ------------------------------------------------------------------ picking
  private onMove = (e: PointerEvent) => {
    this.pendingPick = { x: e.clientX, y: e.clientY };
    if (this.down) return; // dragging: no hover updates
    requestAnimationFrame(() => {
      const p = this.pendingPick;
      if (!p) return;
      this.pendingPick = null;
      this.cb.onHover(this.pick(p.x, p.y), p.x, p.y);
      this.focusAt(p.x, p.y);
    });
  };

  private onDown = (e: PointerEvent) => {
    this.down = { x: e.clientX, y: e.clientY };
  };

  private onUp = (e: PointerEvent) => {
    const d = this.down;
    this.down = null;
    if (d && Math.hypot(e.clientX - d.x, e.clientY - d.y) < 4 && e.button === 0) {
      this.cb.onClick(this.pick(e.clientX, e.clientY));
    }
  };

  private hit(clientX: number, clientY: number): THREE.Intersection | null {
    if (!this.mesh) return null;
    this.camera.updateMatrixWorld();   // the camera may have moved since the last frame
    const r = this.renderer.domElement.getBoundingClientRect();
    this.pointer.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
    this.raycaster.setFromCamera(this.pointer, this.camera);
    return this.raycaster.intersectObject(this.mesh, false)[0] ?? null;
  }

  pick(clientX: number, clientY: number): number | null {
    if (!this.mesh || !this.data) return null;
    const hit = this.hit(clientX, clientY);
    if (!hit || hit.faceIndex === undefined || hit.faceIndex === null) return null;
    const f = faceOfTriangle(this.data.faceRanges, hit.faceIndex);
    return f >= 0 ? f : null;
  }

  /** Screen position of a face's centre (for tests and tooltips). */
  faceScreenPoint(face: number): { x: number; y: number } | null {
    const m = this.data;
    if (!m) return null;
    const s = m.faceRanges[face * 2], n = m.faceRanges[face * 2 + 1];
    if (!n) return null;
    let best = -1, bi = s;
    const v = (i: number) => new THREE.Vector3(m.positions[i * 3], m.positions[i * 3 + 1], m.positions[i * 3 + 2]);
    for (let t = s; t < s + n; t++) {
      const a = v(m.indices[t * 3]), b = v(m.indices[t * 3 + 1]), c = v(m.indices[t * 3 + 2]);
      const area = b.clone().sub(a).cross(c.clone().sub(a)).length();
      if (area > best) { best = area; bi = t; }
    }
    const a = v(m.indices[bi * 3]), b = v(m.indices[bi * 3 + 1]), c = v(m.indices[bi * 3 + 2]);
    this.camera.updateMatrixWorld();
    const p = a.add(b).add(c).multiplyScalar(1 / 3).project(this.camera);
    const r = this.renderer.domElement.getBoundingClientRect();
    return { x: r.left + ((p.x + 1) / 2) * r.width, y: r.top + ((1 - p.y) / 2) * r.height };
  }

  /** Mean vertex position of a face in the displayed mesh (tests: where did a hole move?). */
  faceCentroid(face: number): number[] | null {
    const m = this.data;
    if (!m || face < 0 || face >= m.nFaces) return null;
    const s = m.faceRanges[face * 2], n = m.faceRanges[face * 2 + 1];
    const acc = [0, 0, 0];
    let k = 0;
    for (let t = s * 3; t < (s + n) * 3; t++) {
      const v = m.indices[t] * 3;
      acc[0] += m.positions[v]; acc[1] += m.positions[v + 1]; acc[2] += m.positions[v + 2];
      k++;
    }
    return k ? acc.map((x) => x / k) : null;
  }

  /** Current per-face display states (tests). */
  states(): FaceState[] {
    return [...this.faceStates];
  }

  /** Whether a ghost (last good model) is shown (tests). */
  hasGhost(): boolean {
    return this.ghost.children.length > 0;
  }

  /** Camera position and target (tests: the camera survives a rebuild). */
  cameraState(): number[] {
    const c = this.camera.position, t = this.controls.target;
    return [c.x, c.y, c.z, t.x, t.y, t.z];
  }

  /** A screen point where picking returns `face` (it is visible there), or null. */
  visiblePoint(face: number): { x: number; y: number } | null {
    const m = this.data;
    if (!m) return null;
    const s = m.faceRanges[face * 2], n = m.faceRanges[face * 2 + 1];
    const r = this.renderer.domElement.getBoundingClientRect();
    const v = new THREE.Vector3();
    this.camera.updateMatrixWorld();
    for (let t = s; t < s + n; t++) {
      v.set(0, 0, 0);
      for (let j = 0; j < 3; j++) {
        const i = m.indices[t * 3 + j] * 3;
        v.x += m.positions[i] / 3; v.y += m.positions[i + 1] / 3; v.z += m.positions[i + 2] / 3;
      }
      const p = v.clone().project(this.camera);
      const x = r.left + ((p.x + 1) / 2) * r.width, y = r.top + ((1 - p.y) / 2) * r.height;
      if (x > r.left && x < r.right && y > r.top && y < r.bottom && this.pick(x, y) === face) return { x, y };
    }
    return null;
  }

  // ------------------------------------------------------------------ rendering
  private resize(): void {
    const { w, h } = this.size();
    this.renderer.setSize(w, h, false);
    this.persp.aspect = w / h;
    this.persp.updateProjectionMatrix();
    if (this.oneToOne) this.setOneToOne(this.oneToOne);
    this.rt?.dispose();
    this.rt = null;
    this.render();
  }

  private ensureTarget(): THREE.WebGLRenderTarget {
    const dpr = this.renderer.getPixelRatio();
    const { w, h } = this.size();
    const W = Math.max(1, Math.round(w * dpr)), H = Math.max(1, Math.round(h * dpr));
    if (!this.rt || this.rt.width !== W || this.rt.height !== H) {
      this.rt?.dispose();
      const dt = new THREE.DepthTexture(W, H);
      dt.type = THREE.UnsignedIntType;
      this.rt = new THREE.WebGLRenderTarget(W, H, { depthTexture: dt, depthBuffer: true });
    }
    return this.rt;
  }

  render(): void {
    if (this.frame) return;
    this.frame = requestAnimationFrame(() => {
      this.frame = 0;
      const photo = this.mode === "photo" && this.camera === this.persp;
      if (photo) {
        const now = performance.now();
        const dt = this.lastT ? now - this.lastT : 16;
        this.lastT = now;
        this.focus = reducedMotion() ? this.focusTarget : easeFocus(this.focus, this.focusTarget, dt);
        const rt = this.ensureTarget();
        this.renderer.setRenderTarget(rt);
        this.renderer.render(this.scene, this.camera);
        this.renderer.setRenderTarget(null);
        const { f, N, viewH } = this.lens();
        const dpr = this.renderer.getPixelRatio();
        const u = this.dofMat.uniforms;
        u.tColor.value = rt.texture;
        u.tDepth.value = rt.depthTexture;
        u.uNear.value = this.persp.near;
        u.uFar.value = this.persp.far;
        u.uFocus.value = this.focus;
        u.uF.value = f;
        u.uN.value = N;
        u.uViewH.value = viewH * dpr;
        u.uCap.value = BLUR_CAP_PX * dpr;
        u.uRes.value.set(rt.width, rt.height);
        this.renderer.render(this.dofScene, this.dofCam);
        if (Math.abs(this.focus - this.focusTarget) > 0.05 * Math.max(1, this.focusTarget / 100)) this.render();
        else this.lastT = 0;
      } else {
        this.renderer.render(this.scene, this.camera);
      }
      this.drawTriad();
      this.cb.onView?.();
    });
  }

  private drawTriad(): void {
    const c = this.triad;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const dpr = Math.min(window.devicePixelRatio, 2);
    const size = 76;
    if (c.width !== size * dpr) {
      c.width = c.height = size * dpr;
      c.style.width = c.style.height = `${size}px`;
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);
    const q = this.camera.quaternion.clone().invert();
    const axes: [string, THREE.Vector3][] = [["X", new THREE.Vector3(1, 0, 0)], ["Y", new THREE.Vector3(0, 1, 0)],
                                             ["Z", new THREE.Vector3(0, 0, 1)]];
    const o = size / 2, L = 24;
    const proj = axes.map(([n, v]) => [n, v.applyQuaternion(q)] as [string, THREE.Vector3])
      .sort((a, b) => a[1].z - b[1].z);
    ctx.lineCap = "round";
    for (const [n, v] of proj) {
      const x = o + v.x * L, y = o - v.y * L;
      ctx.strokeStyle = this.palette.triad;
      ctx.globalAlpha = 0.45 + 0.55 * (v.z + 1) / 2;
      ctx.lineWidth = n === "Z" ? 2 : 1.5;
      ctx.beginPath();
      ctx.moveTo(o, o);
      ctx.lineTo(x, y);
      ctx.stroke();
      ctx.fillStyle = this.palette.triad;
      ctx.font = "500 10px 'IBM Plex Mono', monospace";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(n, o + v.x * (L + 9), o - v.y * (L + 9));
    }
    ctx.globalAlpha = 1;
  }
}

// ------------------------------------------------------------------ reference object geometry

function ghostMaterial(p: Palette): THREE.MeshStandardMaterial {
  // depthWrite: the photo view's depth of field reads the depth buffer, so the ghost must write
  // its own depth or it would be blurred as if it were the background (nothing is behind it: it
  // is placed beside the part)
  return new THREE.MeshStandardMaterial({ color: p.refGhost, transparent: true, opacity: 0.55, depthWrite: true,
                                          roughness: 0.6, metalness: 0.1 });
}

function orient(obj: THREE.Object3D, from: THREE.Vector3, to: THREE.Vector3): void {
  obj.quaternion.setFromUnitVectors(from.clone().normalize(), to.clone().normalize());
}

/** Build the ghosted reference object beside the part (never overlapping it), offset along the
 *  camera's screen-right `right` from the hovered feature (or the part's centre), so it sits at
 *  the same depth as what it explains. */
export function buildReference(choice: RefChoice, refs: ReferencesJ, p: Palette, part: { min: number[]; max: number[] },
                               right: THREE.Vector3, up: THREE.Vector3): THREE.Object3D | null {
  const mat = ghostMaterial(p);
  const g = new THREE.Group();
  g.name = `reference:${choice.kind}`;
  const centre = [(part.min[0] + part.max[0]) / 2, (part.min[1] + part.max[1]) / 2, (part.min[2] + part.max[2]) / 2];
  const R = [right.x, right.y, right.z];
  const facing = right.clone().cross(up).normalize();      // towards the camera
  if (choice.kind === "screw" && choice.screw && refs.screws[choice.screw]) {
    const s = refs.screws[choice.screw];
    const r = s.major / 2, rh = s.head / 2, L = s.length;
    const headDepth = rh - r; // 90° countersunk head
    // lathe profile along +Y: head at y = 0 (the face), shank to y = -L, a sawtooth for the thread
    const pts: THREE.Vector2[] = [new THREE.Vector2(0, 0), new THREE.Vector2(rh, 0), new THREE.Vector2(r, -headDepth)];
    const pitch = 0.8; // visual thread pitch only
    for (let y = -headDepth - pitch; y > -L + pitch; y -= pitch) {
      pts.push(new THREE.Vector2(r * 0.82, y + pitch / 2), new THREE.Vector2(r, y));
    }
    pts.push(new THREE.Vector2(r * 0.4, -L), new THREE.Vector2(0, -L));
    const screw = new THREE.Mesh(new THREE.LatheGeometry(pts, 32), mat);
    const axis = new THREE.Vector3(...(choice.axis ?? [0, 1, 0]));
    orient(screw, new THREE.Vector3(0, 1, 0), axis);
    const at = besidePart(part, choice.centre ?? centre, R, rh);
    screw.position.set(at[0], at[1], at[2]);
    g.add(screw);
    return g;
  }
  if (choice.kind === "card") {
    const { width: W, height: H, corner_radius: Rc, thickness: T } = refs.card;
    const sh = new THREE.Shape();
    sh.moveTo(Rc, 0); sh.lineTo(W - Rc, 0); sh.quadraticCurveTo(W, 0, W, Rc); sh.lineTo(W, H - Rc);
    sh.quadraticCurveTo(W, H, W - Rc, H); sh.lineTo(Rc, H); sh.quadraticCurveTo(0, H, 0, H - Rc); sh.lineTo(0, Rc);
    sh.quadraticCurveTo(0, 0, Rc, 0);
    const geo = new THREE.ExtrudeGeometry(sh, { depth: T, bevelEnabled: false });
    geo.translate(-W / 2, -H / 2, 0);
    const card = new THREE.Mesh(geo, mat);
    // facing the camera, upright on screen
    card.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(right, up, facing));
    const at = besidePart(part, centre, R, W / 2);
    card.position.set(at[0], at[1], at[2]);
    g.add(card);
    return g;
  }
  if (choice.kind === "fingertip") {
    const b = refs.fingertip.breadth, L = refs.fingertip.length * 2.4;
    const finger = new THREE.Mesh(new THREE.CapsuleGeometry(b / 2, L - b, 8, 20), mat);
    const axis = new THREE.Vector3(...(choice.axis ?? [0, 1, 0]));
    orient(finger, new THREE.Vector3(0, 1, 0), axis);
    const at = besidePart(part, choice.centre ?? centre, R, b / 2);
    finger.position.set(at[0], at[1], at[2]);
    g.add(finger);
    return g;
  }
  // a stylised hand: palm and five capsule fingers, sized from the (placeholder) hand length,
  // upright on screen and facing the camera
  const L = refs.hand.length, B = refs.hand.breadth;
  const palmH = L * 0.53, fingerL = L * 0.47;
  const hand = new THREE.Group();
  const palm = new THREE.Mesh(new THREE.BoxGeometry(B, palmH, B * 0.3), mat);
  palm.position.set(0, palmH / 2 - L / 2, 0);
  hand.add(palm);
  const fr = B / 8.5;
  for (let i = 0; i < 4; i++) {
    const len = fingerL * [0.88, 1, 0.95, 0.75][i];
    const f = new THREE.Mesh(new THREE.CapsuleGeometry(fr, len - 2 * fr, 6, 14), mat);
    f.position.set(-B / 2 + fr + i * (B - 2 * fr) / 3, palmH - L / 2 + len / 2, 0);
    hand.add(f);
  }
  const th = new THREE.Mesh(new THREE.CapsuleGeometry(fr * 1.1, fingerL * 0.6, 6, 14), mat);
  th.rotation.set(0, 0, -0.7);
  th.position.set(B / 2 + fr, palmH * 0.45 - L / 2, 0);
  hand.add(th);
  hand.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(right, up, facing));
  const at = besidePart(part, centre, R, B / 2 + fr * 2);
  hand.position.set(at[0], at[1], at[2]);
  g.add(hand);
  return g;
}

// ------------------------------------------------------------------ component envelope ghosts (iteration 4)

/** A component ghost: a translucent solid plus an outline, dashed while the component is
 *  unreviewed (the hatched/dashed "guess" style of the panels, B5), solid once accepted. */
export function buildComponentGhost(g: GhostPose & { component: string }, p: Palette): THREE.Object3D {
  const grp = new THREE.Group();
  grp.name = `component:${g.component}`;
  const fill = new THREE.MeshStandardMaterial({ color: p.compGhost, transparent: true, opacity: g.dashed ? 0.16 : 0.26,
                                                depthWrite: false, roughness: 0.7, side: THREE.DoubleSide });
  const line = g.dashed
    ? new THREE.LineDashedMaterial({ color: p.compGhost, dashSize: 3, gapSize: 2.5, transparent: true, opacity: 0.95 })
    : new THREE.LineBasicMaterial({ color: p.compGhost, transparent: true, opacity: 0.95 });
  let solid: THREE.BufferGeometry;
  const pts: THREE.Vector3[] = [];
  if (g.shape === "cylinder") {
    const [r, L] = g.size;
    solid = new THREE.CylinderGeometry(r, r, L, 40, 1, true);
    const n = 48;
    for (const y of [-L / 2, L / 2]) {
      for (let i = 0; i < n; i++) {
        const a0 = (i / n) * Math.PI * 2, a1 = ((i + 1) / n) * Math.PI * 2;
        pts.push(new THREE.Vector3(r * Math.cos(a0), y, r * Math.sin(a0)), new THREE.Vector3(r * Math.cos(a1), y, r * Math.sin(a1)));
      }
    }
    for (let i = 0; i < 4; i++) {
      const a = (i / 4) * Math.PI * 2;
      pts.push(new THREE.Vector3(r * Math.cos(a), -L / 2, r * Math.sin(a)), new THREE.Vector3(r * Math.cos(a), L / 2, r * Math.sin(a)));
    }
  } else {
    const [x, y, z] = g.size;
    solid = new THREE.BoxGeometry(x, y, z);
    const c = [-0.5, 0.5];
    const corner = (i: number, j: number, k: number) => new THREE.Vector3(c[i] * x, c[j] * y, c[k] * z);
    for (const [a, b] of [[[0, 0, 0], [1, 0, 0]], [[0, 1, 0], [1, 1, 0]], [[0, 0, 1], [1, 0, 1]], [[0, 1, 1], [1, 1, 1]],
                          [[0, 0, 0], [0, 1, 0]], [[1, 0, 0], [1, 1, 0]], [[0, 0, 1], [0, 1, 1]], [[1, 0, 1], [1, 1, 1]],
                          [[0, 0, 0], [0, 0, 1]], [[1, 0, 0], [1, 0, 1]], [[0, 1, 0], [0, 1, 1]], [[1, 1, 0], [1, 1, 1]]]) {
      pts.push(corner(a[0], a[1], a[2]), corner(b[0], b[1], b[2]));
    }
  }
  const mesh = new THREE.Mesh(solid, fill);
  mesh.renderOrder = 2;
  const seg = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), line);
  if (g.dashed) seg.computeLineDistances();
  grp.add(mesh, seg);
  const [bx, by, bz] = g.basis;
  grp.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(
    new THREE.Vector3(bx[0], bx[1], bx[2]), new THREE.Vector3(by[0], by[1], by[2]), new THREE.Vector3(bz[0], bz[1], bz[2])));
  grp.position.set(g.position[0], g.position[1], g.position[2]);
  grp.traverse((o) => { o.raycast = () => {}; });   // ghosts never take picks from the part
  return grp;
}

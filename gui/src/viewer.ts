// Imperative three.js viewport: shaded model with visible edges, face picking, standard views,
// an axis triad, and a greyed "last good" ghost (docs/gui.md §2 item 2, §4).

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { bounds, edgeSegments, faceOfTriangle, type DecodedMesh } from "./mesh";

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
}

export type FaceState = "base" | "hover" | "lit" | "selected" | "dim" | "fail" | "failLit" | "failTouched";

interface Callbacks {
  onHover: (face: number | null, x: number, y: number) => void;
  onClick: (face: number | null) => void;
}

const VIEW_DIRS: Record<ViewName, [number, number, number]> = {
  // Z up (the engine's convention); front looks along -Y (from +Y), side along -X (from +X)
  iso: [1.25, 1.0, 0.85],
  front: [0, 1, 0],
  side: [1, 0, 0],
  top: [0, 0, 1],
};

export class Viewer {
  private renderer: THREE.WebGLRenderer;
  private scene = new THREE.Scene();
  private camera: THREE.PerspectiveCamera;
  private controls: OrbitControls;
  private model = new THREE.Group();
  private mesh: THREE.Mesh | null = null;
  private edges: THREE.LineSegments | null = null;
  private ghost = new THREE.Group();
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

  constructor(private host: HTMLElement, palette: Palette, private cb: Callbacks, triad: HTMLCanvasElement) {
    this.palette = palette;
    this.triad = triad;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    host.appendChild(this.renderer.domElement);
    this.renderer.domElement.className = "viewport-canvas";
    this.camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100000);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(300, -360, 270);
    this.camera.add(this.light);
    this.light.position.set(0.4, 1, 0.6);
    this.scene.add(this.camera, this.hemi, this.model, this.ghost);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = false;
    this.controls.screenSpacePanning = true;
    this.controls.addEventListener("change", () => this.render());
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
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  // ------------------------------------------------------------------ geometry
  setMesh(m: DecodedMesh): void {
    this.data = m;
    this.disposeGroup(this.model);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(m.positions, 3));
    g.setAttribute("normal", new THREE.BufferAttribute(m.normals, 3));
    g.setAttribute("color", new THREE.BufferAttribute(new Float32Array(m.positions.length), 3));
    g.setIndex(new THREE.BufferAttribute(m.indices, 1));
    const mat = new THREE.MeshStandardMaterial({
      vertexColors: true, roughness: 0.82, metalness: 0.08, polygonOffset: true, polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    });
    this.mesh = new THREE.Mesh(g, mat);
    const es = edgeSegments(m);
    const eg = new THREE.BufferGeometry();
    eg.setAttribute("position", new THREE.BufferAttribute(es.positions, 3));
    this.edges = new THREE.LineSegments(eg, new THREE.LineBasicMaterial({ color: this.palette.edge }));
    this.model.add(this.mesh, this.edges);
    if (this.faceStates.length !== m.nFaces) this.faceStates = new Array(m.nFaces).fill("base");
    this.paint();
    if (!this.fitted) {
      this.setView("iso");
      this.fitted = true;
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
      const o = c as THREE.Mesh;
      o.geometry?.dispose();
      const mm = o.material as THREE.Material | THREE.Material[];
      if (Array.isArray(mm)) mm.forEach((x) => x.dispose());
      else mm?.dispose();
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

  // ------------------------------------------------------------------ camera
  setView(name: ViewName | "fit"): void {
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
    const dir = name === "fit"
      ? this.camera.position.clone().sub(this.controls.target).normalize()
      : new THREE.Vector3(...VIEW_DIRS[name]).normalize();
    const fov = (this.camera.fov * Math.PI) / 180;
    const aspect = Math.max(0.2, this.camera.aspect);
    const dist = (radius * 1.15) / Math.sin(Math.min(fov, fov * aspect) / 2);
    this.camera.up.set(0, 0, 1);
    if (name === "top") this.camera.up.set(0, 1, 0);
    this.controls.target.copy(center);
    this.camera.position.copy(center).add(dir.multiplyScalar(dist));
    this.camera.near = dist / 100;
    this.camera.far = dist * 100;
    this.camera.updateProjectionMatrix();
    this.controls.update();
    this.render();
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

  pick(clientX: number, clientY: number): number | null {
    if (!this.mesh || !this.data) return null;
    const r = this.renderer.domElement.getBoundingClientRect();
    this.pointer.set(((clientX - r.left) / r.width) * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hit = this.raycaster.intersectObject(this.mesh, false)[0];
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
    // the triangle with the largest area, at its centroid: always on the face
    let best = -1, bi = s;
    const v = (i: number) => new THREE.Vector3(m.positions[i * 3], m.positions[i * 3 + 1], m.positions[i * 3 + 2]);
    for (let t = s; t < s + n; t++) {
      const a = v(m.indices[t * 3]), b = v(m.indices[t * 3 + 1]), c = v(m.indices[t * 3 + 2]);
      const area = b.clone().sub(a).cross(c.clone().sub(a)).length();
      if (area > best) { best = area; bi = t; }
    }
    const a = v(m.indices[bi * 3]), b = v(m.indices[bi * 3 + 1]), c = v(m.indices[bi * 3 + 2]);
    const p = a.add(b).add(c).multiplyScalar(1 / 3).project(this.camera);
    const r = this.renderer.domElement.getBoundingClientRect();
    return { x: r.left + ((p.x + 1) / 2) * r.width, y: r.top + ((1 - p.y) / 2) * r.height };
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
    const w = Math.max(1, this.host.clientWidth), h = Math.max(1, this.host.clientHeight);
    this.renderer.setSize(w, h, false);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.render();
  }

  render(): void {
    if (this.frame) return;
    this.frame = requestAnimationFrame(() => {
      this.frame = 0;
      this.renderer.render(this.scene, this.camera);
      this.drawTriad();
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

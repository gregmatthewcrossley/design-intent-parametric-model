// Thumbnails of proposal geometry for the alternatives compare view (iteration 4).  One shared
// offscreen renderer draws a decoded mesh from a fixed iso direction, fitted to its bounds, and
// returns a PNG data URL (cached by mesh id).

import * as THREE from "three";
import { bounds, type DecodedMesh } from "./mesh";

let renderer: THREE.WebGLRenderer | null = null;
const cache = new Map<string, string>();

export function thumbnail(key: string, m: DecodedMesh, colors: { bg: string; model: string; edge: string },
                          w = 240, h = 170): string {
  const k = `${key}:${colors.bg}:${colors.model}:${w}x${h}`;
  const hit = cache.get(k);
  if (hit) return hit;
  if (!renderer) {
    renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1);
  }
  renderer.setSize(w * 2, h * 2, false);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(colors.bg);
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(m.positions, 3));
  g.setAttribute("normal", new THREE.BufferAttribute(m.normals, 3));
  g.setIndex(new THREE.BufferAttribute(m.indices, 1));
  const mat = new THREE.MeshStandardMaterial({ color: colors.model, roughness: 0.55, metalness: 0.05 });
  scene.add(new THREE.Mesh(g, mat));
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.3));
  const b = bounds(m.positions);
  const c = new THREE.Vector3((b.min[0] + b.max[0]) / 2, (b.min[1] + b.max[1]) / 2, (b.min[2] + b.max[2]) / 2);
  const r = Math.max(1, Math.hypot(b.max[0] - b.min[0], b.max[1] - b.min[1], b.max[2] - b.min[2]) / 2);
  const cam = new THREE.PerspectiveCamera(30, w / h, r / 50, r * 50);
  cam.up.set(0, 0, 1);
  const dir = new THREE.Vector3(1, -1.2, 0.9).normalize();
  cam.position.copy(c.clone().add(dir.multiplyScalar(r / Math.sin((15 * Math.PI) / 180) * 1.05)));
  cam.lookAt(c);
  const light = new THREE.DirectionalLight(0xffffff, 1.5);
  light.position.set(0.4, 1, 0.6);
  cam.add(light);
  scene.add(cam);
  renderer.render(scene, cam);
  const url = renderer.domElement.toDataURL("image/png");
  g.dispose();
  mat.dispose();
  cache.set(k, url);
  return url;
}

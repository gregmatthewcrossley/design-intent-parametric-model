// Binary mesh decoding (layout documented in src/dipm/server/mesh.py). Pure, no three.js.

export interface DecodedMesh {
  positions: Float32Array; // n_verts * 3
  normals: Float32Array; // n_verts * 3
  indices: Uint32Array; // n_tris * 3
  faceRanges: Uint32Array; // n_faces * 2: (first triangle, count)
  edgeRanges: Uint32Array; // n_edges * 2: (first point, count)
  edgePoints: Float32Array; // n_edge_pts * 3
  nFaces: number;
  nEdges: number;
}

const MAGIC = "DIPM";
export const MESH_VERSION = 1;

export function decodeMesh(buf: ArrayBuffer): DecodedMesh {
  const dv = new DataView(buf);
  const magic = String.fromCharCode(dv.getUint8(0), dv.getUint8(1), dv.getUint8(2), dv.getUint8(3));
  if (magic !== MAGIC) throw new Error("not a dipm mesh");
  const u = (i: number) => dv.getUint32(4 + i * 4, true);
  const version = u(0);
  if (version !== MESH_VERSION) throw new Error(`unsupported mesh version ${version}`);
  const nv = u(1), nt = u(2), nf = u(3), ne = u(4), nep = u(5);
  let off = 28;
  // slice() copies into aligned buffers; little-endian hosts only (every browser target).
  const f32 = (n: number) => {
    const a = new Float32Array(buf.slice(off, off + n * 4));
    off += n * 4;
    return a;
  };
  const u32 = (n: number) => {
    const a = new Uint32Array(buf.slice(off, off + n * 4));
    off += n * 4;
    return a;
  };
  const positions = f32(nv * 3);
  const normals = f32(nv * 3);
  const indices = u32(nt * 3);
  const faceRanges = u32(nf * 2);
  const edgeRanges = u32(ne * 2);
  const edgePoints = f32(nep * 3);
  if (off !== buf.byteLength) throw new Error("mesh length mismatch");
  return { positions, normals, indices, faceRanges, edgeRanges, edgePoints, nFaces: nf, nEdges: ne };
}

/** Face id owning triangle `tri` (binary search over the face ranges, which tile the triangles). */
export function faceOfTriangle(faceRanges: Uint32Array, tri: number): number {
  let lo = 0, hi = faceRanges.length / 2 - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const start = faceRanges[mid * 2], count = faceRanges[mid * 2 + 1];
    if (tri < start) hi = mid - 1;
    else if (tri >= start + count) lo = mid + 1;
    else return mid;
  }
  return -1;
}

/** Vertex index range [first, last] used by a face (vertices are per face, contiguous). */
export function faceVertexSpan(m: DecodedMesh, face: number): [number, number] {
  const s = m.faceRanges[face * 2], c = m.faceRanges[face * 2 + 1];
  if (c === 0) return [0, -1];
  let lo = Infinity, hi = -Infinity;
  for (let i = s * 3; i < (s + c) * 3; i++) {
    const v = m.indices[i];
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return [lo, hi];
}

/** Line-segment pairs (for THREE.LineSegments) and the edge id of each segment vertex. */
export function edgeSegments(m: DecodedMesh): { positions: Float32Array; edgeOfVertex: Uint32Array } {
  let nseg = 0;
  for (let e = 0; e < m.nEdges; e++) nseg += Math.max(0, m.edgeRanges[e * 2 + 1] - 1);
  const positions = new Float32Array(nseg * 6);
  const edgeOfVertex = new Uint32Array(nseg * 2);
  let k = 0;
  for (let e = 0; e < m.nEdges; e++) {
    const s = m.edgeRanges[e * 2], c = m.edgeRanges[e * 2 + 1];
    for (let i = 0; i + 1 < c; i++) {
      const a = (s + i) * 3, b = (s + i + 1) * 3;
      positions.set(m.edgePoints.subarray(a, a + 3), k * 6);
      positions.set(m.edgePoints.subarray(b, b + 3), k * 6 + 3);
      edgeOfVertex[k * 2] = e;
      edgeOfVertex[k * 2 + 1] = e;
      k++;
    }
  }
  return { positions, edgeOfVertex };
}

/** Axis-aligned bounds of the positions. */
export function bounds(p: Float32Array): { min: [number, number, number]; max: [number, number, number] } {
  const min: [number, number, number] = [Infinity, Infinity, Infinity];
  const max: [number, number, number] = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < p.length; i += 3) {
    for (let j = 0; j < 3; j++) {
      if (p[i + j] < min[j]) min[j] = p[i + j];
      if (p[i + j] > max[j]) max[j] = p[i + j];
    }
  }
  return { min, max };
}

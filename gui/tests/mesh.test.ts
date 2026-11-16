import { describe, expect, it } from "vitest";
import { bounds, decodeMesh, edgeSegments, faceOfTriangle, faceVertexSpan, MESH_VERSION } from "../src/mesh";

/** Encode like src/dipm/server/mesh.py: header, positions, normals, indices, face/edge ranges, edge points. */
function encode(pos: number[], nor: number[], idx: number[], faces: number[], edges: number[], epts: number[]): ArrayBuffer {
  const nv = pos.length / 3, nt = idx.length / 3, nf = faces.length / 2, ne = edges.length / 2, nep = epts.length / 3;
  const buf = new ArrayBuffer(28 + 4 * (pos.length + nor.length + idx.length + faces.length + edges.length + epts.length));
  const dv = new DataView(buf);
  "DIPM".split("").forEach((c, i) => dv.setUint8(i, c.charCodeAt(0)));
  [MESH_VERSION, nv, nt, nf, ne, nep].forEach((v, i) => dv.setUint32(4 + 4 * i, v, true));
  let off = 28;
  for (const v of pos) { dv.setFloat32(off, v, true); off += 4; }
  for (const v of nor) { dv.setFloat32(off, v, true); off += 4; }
  for (const v of idx) { dv.setUint32(off, v, true); off += 4; }
  for (const v of faces) { dv.setUint32(off, v, true); off += 4; }
  for (const v of edges) { dv.setUint32(off, v, true); off += 4; }
  for (const v of epts) { dv.setFloat32(off, v, true); off += 4; }
  return buf;
}

// two faces: a quad (2 triangles) on z=0 and a triangle on z=1; two edges, the second degenerated
const quad = [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0];
const tri = [0, 0, 1, 1, 0, 1, 0, 1, 1];
const buf = encode([...quad, ...tri], new Array(21).fill(0).map((_, i) => (i % 3 === 2 ? 1 : 0)),
                   [0, 1, 2, 0, 2, 3, 4, 5, 6], [0, 2, 2, 1], [0, 3, 3, 0], [0, 0, 0, 1, 0, 0, 1, 1, 0]);

describe("mesh decoding", () => {
  it("decodes every section", () => {
    const m = decodeMesh(buf);
    expect(m.nFaces).toBe(2);
    expect(m.nEdges).toBe(2);
    expect(Array.from(m.indices)).toEqual([0, 1, 2, 0, 2, 3, 4, 5, 6]);
    expect(Array.from(m.positions.slice(12, 15))).toEqual([0, 0, 1]);
    expect(Array.from(m.faceRanges)).toEqual([0, 2, 2, 1]);
  });

  it("maps triangles to face ids and faces to vertex spans", () => {
    const m = decodeMesh(buf);
    expect([0, 1, 2, 3].map((t) => faceOfTriangle(m.faceRanges, t))).toEqual([0, 0, 1, -1]);
    expect(faceVertexSpan(m, 0)).toEqual([0, 3]);
    expect(faceVertexSpan(m, 1)).toEqual([4, 6]);
  });

  it("turns edge polylines into segments, skipping degenerated edges", () => {
    const s = edgeSegments(decodeMesh(buf));
    expect(s.positions.length).toBe(2 * 6);
    expect(Array.from(s.edgeOfVertex)).toEqual([0, 0, 0, 0]);
    expect(bounds(decodeMesh(buf).positions)).toEqual({ min: [0, 0, 0], max: [1, 1, 1] });
  });

  it("rejects foreign or truncated data", () => {
    expect(() => decodeMesh(new ArrayBuffer(28))).toThrow(/not a dipm mesh/);
    expect(() => decodeMesh(buf.slice(0, buf.byteLength - 4))).toThrow();
  });
});

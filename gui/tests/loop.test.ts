// Iteration 4 (docs/purpose-loop.md §4 GUI): impact marks, the purpose tree diff, grouping
// alternatives, and the pose of component ghosts.
import { describe, expect, it } from "vitest";
import {
  alternativeGroups, asTerm, checkCounts, checkRows, diffCounts, ghostPose, ghostsToShow, impactOf, impactRows,
  nodeImpact, shortReason, treeDiff,
} from "../src/loop";
import { needsOverride, canAccept, isOpen } from "../src/edit";
import type { BuildJ, ImpactJ, IntentDocJ, ProposalJ } from "../src/types";
import { bracket } from "./fixture";

const impact: ImpactJ = {
  terms: { removed: ["shelf"], added: ["fishing", "rod"] },
  changes: [{ id: "R", new: false, fields: ["statement"],
              before: { statement: "Support a shelf on a wall", checks: [], assumptions: [] },
              after: { statement: "Support a fishing rod on a wall", checks: [], assumptions: [] } }],
  removed_nodes: [],
  nodes: { R: { class: "changed", reasons: ["statement changed"] }, A: { class: "survives", reasons: [] },
           B: { class: "invalidated", reasons: ["uses 'shelf'"] }, "B.1": { class: "invalidated", reasons: ["nested under B"] } },
  checks: { "R.c1": { class: "invalidated", reasons: ["uses 'shelf'"] }, "R.c2": { class: "survives", reasons: [] } },
  assumptions: { "R.a1": { class: "invalidated", reasons: ["supports R.c1"] } },
  features: { "B.1.screw": { class: "invalidated", reasons: ["serves B.1"] } },
  summary: {}, any_change: true, method: "lexical",
};

describe("impact", () => {
  it("marks nodes and lists changed before invalidated", () => {
    const b = { ...bracket(), impact } as BuildJ;
    expect(nodeImpact(b, "B")).toBe("invalidated");
    expect(nodeImpact(b, "A")).toBe("survives");
    expect(nodeImpact(b, "R")).toBe("changed");
    const rows = impactRows(impact);
    expect(rows[0]).toMatchObject({ kind: "node", id: "R", cls: "changed" });
    expect(rows.map((r) => r.id)).toEqual(["R", "B", "B.1", "R.c1", "R.a1", "B.1.screw"]);
    expect(rows.some((r) => r.id === "A" || r.id === "R.c2")).toBe(false);
  });
  it("shows nothing when nothing changed or there is no baseline", () => {
    expect(impactOf({ ...bracket(), impact: { ...impact, any_change: false } } as BuildJ)).toBeNull();
    expect(nodeImpact({ ...bracket(), impact: null } as BuildJ, "B")).toBeNull();
  });
});

const before: IntentDocJ = { design: "d", intents: [{ id: "R", statement: "Support a shelf", checks: [{ id: "R.c1", statement: "load" }],
  children: [{ id: "A", statement: "Wall mounting" }, { id: "B", statement: "Shelf support", children: [{ id: "B.1", statement: "screw" }] }] }] };
const after: IntentDocJ = { design: "d", intents: [{ id: "R", statement: "Support a fishing rod",
  checks: [{ id: "R.c1", statement: "load", binding: { form: "load" } as never }],
  children: [{ id: "A", statement: "Wall mounting" }, { id: "C", statement: "Cradle", checks: [{ id: "C.c1", statement: "holds" }] }] }] };

describe("purpose tree diff", () => {
  const rows = treeDiff(before, after, [
    { id: "C.c1", node: "C", statement: "holds", form: "holds_cylinder", binding: { form: "holds_cylinder" },
      reads_as: "Holds rod", made_by: "model", reviewed: false, state: "not run", reason: "no export" }]);
  it("classifies added, removed, changed and same nodes", () => {
    const st = Object.fromEntries(rows.map((r) => [r.id, r.status]));
    expect(st).toEqual({ R: "changed", A: "same", C: "added", B: "removed", "B.1": "removed" });
    expect(diffCounts(rows)).toEqual({ added: 1, removed: 2, changed: 1, same: 1 });
    const r = rows.find((x) => x.id === "R")!;
    expect(r.before).toBe("Support a shelf");
    expect(r.checks[0].change).toBe("changed");
  });
  it("keeps tree order with removed nodes under their old parent", () => {
    expect(rows.map((r) => [r.id, r.depth])).toEqual([["R", 0], ["A", 1], ["C", 1], ["B", 1], ["B.1", 2]]);
  });
  it("carries each check's binding in plain language", () => {
    const c = rows.find((x) => x.id === "C")!.checks[0];
    expect(c).toMatchObject({ change: "added", form: "holds_cylinder", reads_as: "Holds rod", reviewed: false });
  });
});

function prop(id: string, over: Partial<ProposalJ>): ProposalJ {
  return { id, created: "", summary: id, rationale: "", addresses_nodes: [], revises: null, source: "mcp", base_hashes: {},
           patches: {}, status: "ready", status_detail: "", evaluation: null, feedback: [], ...over };
}

describe("alternatives", () => {
  const ck = (id: string, state: string) => ({ id, node: "R", state, plain: id });
  const ps = [
    prop("p1", { kind: "purpose" }),
    prop("p3", { kind: "geometry", group: "p2", alternative: "B",
                 evaluation: { ok: true, after: { status: {} as never, kernel: "pass", ok: true, errors: [], stale_nodes: [],
                   intent_checks: [ck("R.c1", "ample"), ck("B.c2", "failing"), ck("B.c3", "not run")] } } }),
    prop("p2", { kind: "geometry", group: "p2", alternative: "A",
                 evaluation: { ok: true, after: { status: {} as never, kernel: "pass", ok: true, errors: [], stale_nodes: [],
                   intent_checks: [ck("R.c1", "thin"), ck("B.c4", "ample")] } } }),
    prop("p9", { kind: "patch" }),
  ];
  it("groups geometry proposals by group, in label order", () => {
    const g = alternativeGroups(ps);
    expect([...g.keys()]).toEqual(["p2"]);
    expect(g.get("p2")!.map((p) => p.alternative)).toEqual(["A", "B"]);
  });
  it("unions the check rows and counts states honestly (not run is not passing)", () => {
    const alts = alternativeGroups(ps).get("p2")!;
    expect(checkRows(alts)).toEqual(["R.c1", "B.c4", "B.c2", "B.c3"]);
    expect(checkCounts(alts[1].evaluation!.after!.intent_checks!)).toEqual({ run: 2, failing: 1, thin: 0, ample: 1, notRun: 1 });
  });
  it("turns a summary headline into a margin-bar term relative to its limit", () => {
    const t = asTerm({ name: "x", unit: "mm", nominal: 3, worst: 4, limit: 10, limit_worst: 8, margin: 7, margin_worst: 4 }, "thin");
    expect(t.state).toBe("thin");
    expect(t.margin_rel).toBeCloseTo(0.5);
  });
  it("purpose proposals never need an override; trying ones stay open and acceptable", () => {
    const p = prop("p1", { kind: "purpose", status: "trying", evaluation: { ok: false, failing_checks: ["R.c1"] } });
    expect(needsOverride(p)).toBe(false);
    expect(isOpen(p) && canAccept(p)).toBe(true);
  });
});

describe("component ghosts", () => {
  it("poses a cylinder along its axis with an orthonormal basis, dashed while unreviewed", () => {
    const g = ghostPose({ component: "rod", shape: "cylinder", center: [0, 45, 77], axis: [2, 0, 0], diameter: 10, length: 120,
                          made_by: "model", reviewed: false });
    expect(g.basis[1]).toEqual([1, 0, 0]);
    const [x, y, z] = g.basis;
    const dot = (a: number[], b: number[]) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
    expect(Math.abs(dot(x, y)) + Math.abs(dot(y, z)) + Math.abs(dot(x, z))).toBeLessThan(1e-12);
    expect(g.size).toEqual([5, 120]);
    expect(g.dashed).toBe(true);
  });
  it("poses a box by its axes and sizes; reviewed ghosts are solid", () => {
    const g = ghostPose({ component: "reel", shape: "box", center: [140, 45, 10], axes: [[1, 0, 0], [0, 2, 0], [0, 0, 1]],
                          size: [115, 75, 110], made_by: "model", reviewed: true });
    expect(g.basis[1]).toEqual([0, 1, 0]);
    expect(g.size).toEqual([115, 75, 110]);
    expect(g.dashed).toBe(false);
  });
  it("shows one ghost per component (the nominal pose listed first)", () => {
    const b = { ...bracket(), ghosts: [
      { component: "rod", shape: "cylinder", center: [0, 0, 0], made_by: "model", reviewed: false, note: "nominal" },
      { component: "reel", shape: "box", center: [1, 0, 0], made_by: "model", reviewed: false },
      { component: "rod", shape: "cylinder", center: [9, 9, 9], made_by: "model", reviewed: false, note: "Ø14" }] } as BuildJ;
    expect(ghostsToShow(b).map((g) => [g.component, g.center[0]])).toEqual([["rod", 0], ["reel", 1]]);
  });
});

describe("not-run reasons", () => {
  it("drop the long list of what exists but keep short parentheticals", () => {
    expect(shortReason("holds_cylinder: 'cradle_seat' is not an export (corner_blend, gusset_hyp)"))
      .toBe("holds_cylinder: 'cradle_seat' is not an export");
    expect(shortReason("learned score (rung 3): no pinned scorer yet")).toBe("learned score (rung 3): no pinned scorer yet");
  });
});

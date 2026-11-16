import { describe, expect, it } from "vitest";
import { connected, faceLabel, howRows, isUnder, layoutKeys, shortOp, transitionMap, whyRows, worst } from "../src/model";
import { bracket } from "./fixture";

describe("row ordering", () => {
  it("WHY follows the intent tree, with features as callouts at their most specific node", () => {
    const rows = whyRows(bracket());
    expect(rows.map((r) => r.id)).toEqual(["R", "A", "A.P", "A.P.1", "A.P.2", "A.3", "B", "B.1", "C"]);
    expect(rows.map((r) => r.depth)).toEqual([0, 1, 2, 3, 3, 2, 1, 2, 1]);
    const by = Object.fromEntries(rows.map((r) => [r.id, r]));
    expect(by["R"].chips.map((c) => c.key)).toEqual(["feat:R.body", "feat:R.fillet"]);
    expect(by["A"].chips).toEqual([]);
    expect(by["A.P.2"].chips.map((c) => c.key)).toEqual(["inst:A.P.holes:1"]);
    expect(by["A.P"].uses).toEqual(["R.body", "C.gusset"]);
  });

  it("HOW follows build order, with served intents and instance nodes as callouts", () => {
    const rows = howRows(bracket());
    expect(rows.map((r) => r.id)).toEqual(["R.body", "C.gusset", "A.P.holes", "A.3.cable", "B.1.screw", "R.fillet"]);
    expect(rows[2].chips.map((c) => c.id)).toEqual(["A.P", "A.P.1", "A.P.2"]);
    expect(rows[2].sub).toBe("hole ×2");
    expect(rows[3].uses).toEqual(["R.body", "C.gusset"]);
  });

  it("untagged features get a 'no intent' group in WHY", () => {
    const b = bracket();
    b.features.push({ ...b.features[3], id: "X.untagged", index: 6, serves: [], nodes: [], tags: [] });
    const last = whyRows(b).at(-1)!;
    expect(last.kind).toBe("group");
    expect(last.chips.map((c) => c.id)).toEqual(["X.untagged"]);
  });

  it("worst status and short op labels", () => {
    expect(worst(["ok", "warn", "ok"])).toBe("warn");
    expect(worst(["ok", "fail", "warn"])).toBe("fail");
    expect(worst([])).toBe("ok");
    expect(shortOp(bracket().features[0])).toBe("extrude");
  });
});

describe("WHY ⇄ HOW transition mapping", () => {
  it("features morph from callout to row, intents from row to callout", () => {
    const b = bracket();
    const m = transitionMap(whyRows(b), howRows(b));
    expect(m.morph).toContain("feat:A.P.holes");   // callout in WHY, row in HOW
    expect(m.morph).toContain("node:A.P");         // row in WHY, callout in HOW
    expect(m.shared).toContain("node:A.P.2");
    expect(m.enter).toEqual([]);                   // every HOW element exists in WHY
    expect(m.exit).toEqual(expect.arrayContaining(["node:A", "node:B", "inst:A.P.holes:0"]));
  });

  it("is symmetric and keys are unique per layout except repeated callouts", () => {
    const b = bracket();
    const fwd = transitionMap(whyRows(b), howRows(b)), back = transitionMap(howRows(b), whyRows(b));
    expect(new Set(back.shared)).toEqual(new Set(fwd.shared));
    expect(new Set(back.enter)).toEqual(new Set(fwd.exit));
    const keys = layoutKeys(whyRows(b)).filter((k) => !k.startsWith("node:"));
    expect(new Set(keys).size).toBe(keys.length);
  });
});

describe("connected (what lights up)", () => {
  it("a tree node lights its subtree, the faces it created and their features", () => {
    const lit = connected({ kind: "node", id: "A.P" }, bracket());
    expect([...lit.faces].sort()).toEqual([1, 2]);
    expect([...lit.nodes].sort()).toEqual(["A.P", "A.P.1", "A.P.2"]);
    expect([...lit.features]).toEqual(["A.P.holes"]);
    expect(lit.params.has("screw")).toBe(true);
  });

  it("the root R lights everything; an instance node only its instance", () => {
    expect(connected({ kind: "node", id: "R" }, bracket()).faces.size).toBe(4);
    expect([...connected({ kind: "node", id: "A.P.2" }, bracket()).faces]).toEqual([2]);
    expect(isUnder("C", "R") && isUnder("A.P.1", "A.P") && !isUnder("A.3", "A.P")).toBe(true);
  });

  it("a face lights its intent nodes (instance first) and features", () => {
    const lit = connected({ kind: "face", id: 2 }, bracket());
    expect(lit.primaryNode).toBe("A.P.2");
    expect([...lit.nodes]).toEqual(["A.P.2", "A.P", "A"]);
    expect(faceLabel(bracket(), 2)).toBe("A.P.holes · countersink(1)");
  });

  it("a parameter lights the features it drives directly, and marks the ones it drives through uses", () => {
    const lit = connected({ kind: "param", id: "screw" }, bracket());
    expect([...lit.features].sort()).toEqual(["A.P.holes", "B.1.screw"]);
    const sd = connected({ kind: "param", id: "shelf_depth" }, bracket());
    expect([...sd.features].sort()).toEqual(["C.gusset", "R.body"]);
    expect([...sd.indirectFeatures].sort()).toEqual(["A.3.cable", "A.P.holes", "B.1.screw", "R.fillet"]);
  });

  it("a feature lights its intents and marks what it uses", () => {
    const lit = connected({ kind: "feature", id: "A.3.cable" }, bracket());
    expect([...lit.nodes].sort()).toEqual(["A", "A.3"]);
    expect([...lit.indirectFeatures].sort()).toEqual(["C.gusset", "R.body"]);
    expect(connected(null, bracket()).faces.size).toBe(0);
  });
});

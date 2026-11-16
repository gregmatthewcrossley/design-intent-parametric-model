// Iteration 2 pure logic (src/edit.ts, model.isUnder with an intent file).
import { describe, expect, it } from "vitest";
import {
  canAccept, canDrop, centreMove, compareStates, diffLines, featuresUnder, isOpen, moveTargets, semanticSummary,
  staleFeatures, staleNodes, subtree,
} from "../src/edit";
import { connected, isUnder } from "../src/model";
import type { BuildJ, EvaluationJ, ProposalJ } from "../src/types";
import { bracket } from "./fixture";

/** The fixture as an intent-file tree, with A.3 moved under B (ids unchanged). */
function fromFile(moveA3 = false): BuildJ {
  const b = bracket();
  b.tree.from_file = true;
  for (const n of Object.values(b.tree.nodes)) n.in_file = true;
  if (moveA3) {
    b.tree.nodes.A.children = ["A.P"];
    b.tree.nodes.B.children = ["B.1", "A.3"];
    b.tree.nodes["A.3"].parent = "B";
    b.tree.order = ["R", "A", "A.P", "A.P.1", "A.P.2", "B", "B.1", "A.3", "C"];
  }
  return b;
}

describe("intent tree from the file", () => {
  it("isUnder follows the nesting, not the dotted id, once a node has moved", () => {
    const b = fromFile(true);
    expect(isUnder("A.3", "B", b)).toBe(true);
    expect(isUnder("A.3", "A", b)).toBe(false);
    expect(isUnder("A.3", "A")).toBe(true); // tag-derived trees keep the dotted rule
    const L = connected({ kind: "node", id: "B" }, b);
    expect([...L.nodes].sort()).toEqual(["A.3", "B", "B.1"]);
  });

  it("subtree, drop targets and move targets", () => {
    const b = fromFile();
    expect(subtree(b, "A")).toEqual(["A", "A.P", "A.P.1", "A.P.2", "A.3"]);
    expect(canDrop(b, "A.3", "B")).toBe(true);
    expect(canDrop(b, "A.3", "A")).toBe(false); // already its parent
    expect(canDrop(b, "A", "A.P.1")).toBe(false); // into its own subtree
    expect(canDrop(b, "R", "B")).toBe(false); // the root never moves
    expect(canDrop(bracket(), "A.3", "B")).toBe(false); // no intent file: nothing is editable
    expect(moveTargets(b, "A.3")).toEqual(["R", "A.P", "A.P.1", "A.P.2", "B", "B.1", "C"]);
  });

  it("features under a node (what loses its intent on delete)", () => {
    const b = fromFile();
    expect(featuresUnder(b, "C")).toEqual(["C.gusset"]);
    expect(featuresUnder(b, "A.P.1")).toEqual(["A.P.holes"]); // through the instance tag
  });

  it("stale nodes and the features that realize them", () => {
    const b = fromFile();
    b.tree.nodes["A.3"].stale = true;
    b.features.find((f) => f.id === "A.3.cable")!.stale = ["A.3"];
    expect(staleNodes(b)).toEqual(["A.3"]);
    expect([...staleFeatures(b).entries()]).toEqual([["A.3.cable", ["A.3"]]]);
    expect(staleFeatures(null).size).toBe(0);
  });
});

describe("proposals", () => {
  const ev: EvaluationJ = {
    ok: true,
    semantic_diff: {
      intent: { added: [], removed: [], moved: [], changed: [{ id: "A.3", statement: { before: "centered", after: "offset" } }] },
      features: { added: [], removed: [], changed: [{ id: "A.3.cable", detail: { before: { centres: [[0, 5, 32.5]] }, after: { centres: [[0, 5, 19]] } } } as never] },
      checks: { before: { status: "Kernel ✓", errors: 0 }, after: { status: "Kernel ✓", errors: 0 }, features: [],
                diagnostics_after: { no_intent: [], no_feature: [], multi_intent: [], cross_intent: [] } },
      interpretations: { added: [], removed: [{ id: "A.3.cable/centered_on.point", chosen: "exposed_region_midpoint" }],
                         changed: [], questions: [0, 0], notices: [0, 0] },
    },
  };

  it("summarizes the semantic diff and the hole move", () => {
    expect(semanticSummary(ev)).toEqual([
      "intent A.3: “centered” → “offset”",
      "feature A.3.cable: detail changed",
      "interpretation − A.3.cable/centered_on.point (was exposed_region_midpoint)",
    ]);
    expect(centreMove(ev, "A.3.cable")).toEqual({ before: [[0, 5, 32.5]], after: [[0, 5, 19]] });
    expect(centreMove(ev, "R.body")).toBeNull();
    expect(semanticSummary(null)).toEqual([]);
  });

  it("classifies unified-diff lines", () => {
    const d = "--- a/x.py\n+++ b/x.py\n@@ -1,2 +1,2 @@\n ctx\n-old\n+new\n";
    expect(diffLines(d).map((l) => l.cls)).toEqual(["meta", "meta", "hunk", "ctx", "del", "add"]);
  });

  it("open / acceptable statuses and changed-face states", () => {
    const p = (status: ProposalJ["status"]) => ({ status } as ProposalJ);
    expect(["pending", "ready", "failed", "stale", "accepted", "rejected"].map((s) => isOpen(p(s as never))))
      .toEqual([true, true, true, false, false, false]);
    expect(canAccept(p("ready")) && !canAccept(p("stale")) && !canAccept(p("failed"))).toBe(true);
    expect(compareStates(4, [1, 3])).toEqual(["base", "selected", "base", "selected"]);
  });
});

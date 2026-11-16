// A hand-made, minimal build payload shaped like the bracket's (src/dipm/server/serialize.py).
import type { BuildJ, FeatureJ, IntentNodeJ, Status } from "../src/types";

const tag = (node: string, word: string, note = "") => ({ node, word, note, text: `${word}@${node}${note ? ` (${note})` : ""}` });

function feat(id: string, index: number, nodes: string[], over: Partial<FeatureJ> = {}): FeatureJ {
  return {
    id, index, op: "cut", lowered_from: null, tags: nodes.map((n) => tag(n, "w")), nodes, serves: nodes.slice(0, 1),
    instances: {}, status: "ok", ms: 1, uses: [], references: [], reads: [], params: [], params_all: [], slots: [],
    error: null, detail: {}, checks: [], counts: null, volume: 1, refs: [], refs_ok: true, ...over,
  };
}

function node(id: string, parent: string | null, children: string[], realized: string[], status: Status = "ok",
              instances: [string, string][] = []): IntentNodeJ {
  return { id, label: `label ${id}`, parent, children, words: [], notes: [], features: realized, instances,
           realized_by: realized, status, implicit: false };
}

export function bracket(): BuildJ {
  const features = [
    feat("R.body", 0, ["R"], { op: "extrude", params: ["shelf_depth", "t"], params_all: ["shelf_depth", "t"] }),
    feat("C.gusset", 1, ["C"], { op: "extrude", params: ["shelf_depth", "t"], params_all: ["shelf_depth", "t"] }),
    feat("A.P.holes", 2, ["A.P", "A"], {
      lowered_from: "hole(countersink, through_plate)", uses: ["R.body", "C.gusset"], params: ["screw"],
      params_all: ["screw", "shelf_depth", "t"],
      instances: { "0": [tag("A.P.1", "hole")], "1": [tag("A.P.2", "hole")] },
    }),
    feat("A.3.cable", 3, ["A.3", "A"], { lowered_from: "hole(plain, through_plate)", uses: ["R.body", "C.gusset"],
                                          params_all: ["shelf_depth", "t"] }),
    feat("B.1.screw", 4, ["B.1", "B"], { uses: ["R.body"], params: ["screw"], params_all: ["screw", "shelf_depth", "t"] }),
    feat("R.fillet", 5, ["R"], { op: "fillet", uses: ["R.body"], params: ["t"], params_all: ["shelf_depth", "t"] }),
  ];
  const nodes: Record<string, IntentNodeJ> = {
    R: node("R", null, ["A", "B", "C"], ["R.body", "R.fillet"]),
    A: node("A", "R", ["A.P", "A.3"], []),
    "A.P": node("A.P", "A", ["A.P.1", "A.P.2"], ["A.P.holes"]),
    "A.P.1": node("A.P.1", "A.P", [], [], "ok", [["A.P.holes", "0"]]),
    "A.P.2": node("A.P.2", "A.P", [], [], "ok", [["A.P.holes", "1"]]),
    "A.3": node("A.3", "A", [], ["A.3.cable"]),
    B: node("B", "R", ["B.1"], []),
    "B.1": node("B.1", "B", [], ["B.1.screw"]),
    C: node("C", "R", [], ["C.gusset"]),
  };
  const entry = (tagText: string, feature: string, role: string, source: string | null, intent: string[], inst: string[] = []) => ({
    tag: tagText, feature, role, source, op: "cut", lowered_from: null,
    intent: intent.map((n) => tag(n, "w")), instance_intent: inst.map((n) => tag(n, "hole")), events: [] as [string, string][],
  });
  const face = (id: number, e: ReturnType<typeof entry>, nodesOf: string[]) => ({
    id, kind: "face" as const, surface: "Plane", descriptor: "", entries: [e], nodes: nodesOf, features: [e.feature],
    touched_by: [e.feature], failing: false, failing_touched: false, text: "",
  });
  return {
    design: "shelf_bracket", params: { shelf_depth: 200, t: 5, screw: "#8" }, ok: true, status: "PASS", error_count: 0,
    errors: [], ms: 40, features, failing: [],
    tree: { roots: ["R"], order: ["R", "A", "A.P", "A.P.1", "A.P.2", "A.3", "B", "B.1", "C"], nodes },
    diagnostics: { no_intent: [], no_feature: [], multi_intent: [], cross_intent: [] },
    interpretations: { source: "lock", unchecked: false, slots: [], questions: [], notices: [] },
    signature: null,
    faces: [
      face(0, entry("R.body.side(wall)", "R.body", "side", "wall", ["R"]), ["R"]),
      face(1, entry("A.P.holes.wall(0)", "A.P.holes", "wall", "0", ["A.P", "A"], ["A.P.1"]), ["A.P.1", "A.P", "A"]),
      face(2, entry("A.P.holes.countersink(1)", "A.P.holes", "countersink", "1", ["A.P", "A"], ["A.P.2"]), ["A.P.2", "A.P", "A"]),
      face(3, entry("C.gusset.side(hypotenuse)", "C.gusset", "side", "hypotenuse", ["C"]), ["C"]),
    ],
    edges: [], mesh_id: "m", coverage: { faces: 4, with_genealogy: 4 }, warnings: [],
  };
}

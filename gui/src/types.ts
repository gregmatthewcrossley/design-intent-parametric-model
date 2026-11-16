// Shapes of the JSON served by `dipm serve` (src/dipm/server/serialize.py).

export interface ParamInfo {
  name: string;
  default: number | string;
  range: [number, number] | null;
  choices: string[] | null;
  unit: string;
  doc: string;
  kind: "range" | "choice" | "fixed";
}

export interface IntentTagJ {
  node: string;
  word: string;
  note: string;
  text: string;
}

export interface DesignInfo {
  name: string;
  doc: string;
  file: string | null;
  params: ParamInfo[];
  features: { id: string; op: string; tags: IntentTagJ[] }[];
  lock: string | null;
  prefs: string | null;
  current_params?: Record<string, number | string>;
  resolving?: boolean;
}

export interface CheckJ {
  name: string;
  ok: boolean;
  expected: unknown;
  got: unknown;
  note: string;
}

export interface ErrorJ {
  kind: string;
  message: string;
  feature: string | null;
  intent: string[];
  invariant: string | null;
  expected: string | null;
  got: string | null;
  details: Record<string, string>;
}

export type Status = "ok" | "warn" | "fail" | "not_built";

export interface FeatureJ {
  id: string;
  index: number;
  op: string;
  lowered_from: string | null;
  tags: IntentTagJ[];
  nodes: string[];
  serves: string[];
  instances: Record<string, IntentTagJ[]>;
  status: Status;
  ms: number | null;
  uses: string[];
  references: string[];
  reads: { what: string; features: string[] }[];
  params: string[];
  params_all: string[];
  slots: string[];
  error: ErrorJ | null;
  detail: Record<string, unknown>;
  checks: CheckJ[];
  counts: string | null;
  vefrsh?: number[] | null;
  volume: number | null;
  refs: { ref: string; count: number; genealogies: string[] }[];
  refs_ok: boolean;
}

export interface IntentNodeJ {
  id: string;
  label: string;
  parent: string | null;
  children: string[];
  words: string[];
  notes: string[];
  features: string[];
  instances: [string, string][];
  realized_by: string[];
  status: Status;
  implicit: boolean;
}

export interface WhyEntryJ {
  tag: string;
  feature: string;
  role: string;
  source: string | null;
  op: string;
  lowered_from: string | null;
  intent: IntentTagJ[];
  instance_intent: IntentTagJ[];
  events: [string, string][];
}

export interface FaceJ {
  id: number;
  kind: "face";
  surface: string;
  descriptor: string;
  entries: WhyEntryJ[];
  nodes: string[];
  features: string[];
  touched_by: string[];
  failing: boolean; // created by a failing feature
  failing_touched: boolean; // created or modified by a failing feature
  text: string;
}

export interface EdgeJ {
  id: number;
  kind: "edge";
  degenerated: boolean;
  descriptor: string;
  entries: WhyEntryJ[];
  derived_from: number[];
  nodes: string[];
  features: string[];
  text: string;
}

export interface EliminationJ {
  reading: string;
  feature: string;
  check: string;
  point: Record<string, unknown>;
  message: string;
  failed_points: number;
  of_points: number;
}

export interface SlotJ {
  id: string;
  word: string;
  slot: string;
  feature: string;
  node: string;
  statement: string;
  chosen: string;
  made_by: string;
  rationale: string;
  status: string;
  sensitivity: string;
  sensitivity_detail: string;
  readings: string[];
  alternatives: string[];
  eliminated: EliminationJ[];
  used?: string | null;
  mismatch?: boolean;
}

export interface QuestionJ {
  id: string;
  text: string;
  options: { reading: string; rationale: string; effect: string }[];
  default: string;
  answer_with: string;
}

export interface NoticeJ {
  id: string;
  kind: string;
  text: string;
  sensitivity: string;
}

export interface Diagnostics {
  no_intent: string[];
  no_feature: string[];
  multi_intent: { feature: string; nodes: string[] }[];
  cross_intent: { from: string; to: string; from_nodes: string[]; to_nodes: string[] }[];
}

export interface BuildJ {
  design: string;
  file?: string;
  params: Record<string, number | string>;
  ok: boolean;
  status: "PASS" | "FAIL";
  error_count: number;
  errors: ErrorJ[];
  ms: number;
  features: FeatureJ[];
  failing: string[];
  tree: { roots: string[]; order: string[]; nodes: Record<string, IntentNodeJ> };
  diagnostics: Diagnostics;
  interpretations: {
    source: string;
    unchecked: boolean;
    slots: SlotJ[];
    questions: QuestionJ[];
    notices: NoticeJ[];
  };
  signature: { VEFRSH: number[]; volume: number } | null;
  faces: FaceJ[];
  edges: EdgeJ[];
  mesh_id: string | null;
  last_good_mesh_id?: string | null;
  coverage: { faces: number; with_genealogy: number };
  warnings: string[];
  resolving?: boolean;
  generation?: number;
  answer?: { key: string; warning: string; prefs: string };
}

export type Selection =
  | { kind: "face"; id: number }
  | { kind: "edge"; id: number }
  | { kind: "node"; id: string }
  | { kind: "feature"; id: string }
  | { kind: "param"; id: string };

export type ServerEvent =
  | { type: "hello"; generation: number }
  | { type: "design-changed"; design: DesignInfo; changed: string[] }
  | { type: "rebuilt"; reason: string; build: BuildJ }
  | { type: "design-error"; message: string };

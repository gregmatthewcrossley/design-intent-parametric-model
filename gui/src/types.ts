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
  stale?: string[]; // stale intent nodes this feature serves (iteration 2)
}

export interface CheckSpec {
  id: string;
  statement: string;
  kind?: string;
  source?: string;
  priority?: string;
  grounded_as?: string;
  [k: string]: unknown;
}

export interface AssumptionSpec {
  id: string;
  statement: string;
  made_by?: string;
  rationale?: string;
  supports?: string[];
  sensitivity?: string;
  status?: string;
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
  // iteration 2: from <design>.intent.yaml (absent / empty for tag-derived trees)
  statement?: string;
  checks?: CheckSpec[];
  assumptions?: AssumptionSpec[];
  in_file?: boolean;
  stale?: boolean;
  hash?: string;
}

export interface NodeContent {
  statement: string;
  checks: CheckSpec[];
  assumptions: AssumptionSpec[];
}

export interface StaleInfo {
  hash: string;
  reviewed_hash: string | null;
  reviewed: NodeContent | null;
  current: NodeContent;
  changed: string[];
  new: boolean;
}

export interface IntentDocJ {
  design: string;
  context?: Record<string, string>;
  intents: IntentDocNode[];
}

export interface IntentDocNode {
  id: string;
  statement: string;
  checks?: CheckSpec[];
  assumptions?: AssumptionSpec[];
  children?: IntentDocNode[];
}

export interface IntentInfo {
  file: string;
  exists: boolean;
  hash: string | null;
  design_hash?: string | null;
  loaded_hash?: string | null;
  error: string[] | null;
  doc?: IntentDocJ | null;
  stale: Record<string, StaleInfo>;
  review_file: string;
  review_exists: boolean;
}

export type IntentOp =
  | { op: "edit_statement"; id: string; statement: string }
  | { op: "add_child"; parent: string; statement?: string }
  | { op: "delete"; id: string }
  | { op: "move"; id: string; parent: string; index?: number }
  | { op: "add_check"; id: string; check: Partial<CheckSpec> }
  | { op: "edit_check"; id: string; check_id: string; fields: Partial<CheckSpec> }
  | { op: "remove_check"; id: string; check_id: string }
  | { op: "edit_assumption"; id: string; assumption_id: string; fields: Partial<AssumptionSpec> }
  | { op: "mark_reviewed"; ids: string[] };

export type ProposalStatus = "pending" | "evaluating" | "ready" | "failed" | "accepted" | "rejected" | "stale";

export interface FeedbackJ { at: string; kind: string; by: string; comment: string }

export interface EvaluationJ {
  ok: boolean;
  error?: string;
  params?: Record<string, unknown>;
  before?: { status: string; ok: boolean; stale_nodes: string[] };
  after?: { status: string; ok: boolean; errors: ErrorJ[]; stale_nodes: string[] };
  sweep?: { points: number; failing: { params: Record<string, unknown>; errors: string[] }[] };
  semantic_diff?: {
    intent: { added: { id: string; statement: string; parent: string | null }[]; removed: { id: string; statement: string }[];
              moved: { id: string; from: string | null; to: string | null }[];
              changed: ({ id: string; statement?: { before: string; after: string } } & Record<string, unknown>)[] };
    features: { added: string[]; removed: string[]; changed: ({ id: string } & Record<string, { before: unknown; after: unknown } | string>)[] };
    checks: { before: { status: string; errors: number }; after: { status: string; errors: number };
              features: { id: string; before: string | null; after: string; failed_checks: CheckJ[] }[];
              diagnostics_after: Diagnostics };
    interpretations: { added: { id: string; chosen: string }[]; removed: { id: string; chosen: string }[];
                       changed: { id: string; before: string; after: string }[]; questions: number[]; notices: number[] };
  };
  text_diff?: Record<string, string>;
  meshes?: { before?: string; after?: string };
  changed_faces?: { before: number[]; after: number[] };
  face_tags?: { before: string[]; after: string[] };
  ms?: number;
}

export interface ProposalJ {
  id: string;
  created: string;
  summary: string;
  rationale: string;
  addresses_nodes: string[];
  revises: string | null;
  source: string;
  base_hashes: Record<string, string>;
  patches: Record<string, { kind: string; diff?: string; new_hash?: string }>;
  status: ProposalStatus;
  status_detail: string;
  evaluation: EvaluationJ | null;
  feedback: FeedbackJ[];
  accepted?: { at: string; written: string[]; reviewed: string[] };
}

export interface RequestJ {
  id: string;
  created: string;
  node: string;
  note: string;
  change: StaleInfo | null;
  status: string;
  proposals: string[];
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
  missing_in_file?: string[];
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
  tree: { roots: string[]; order: string[]; nodes: Record<string, IntentNodeJ>; from_file?: boolean;
          missing?: Record<string, string[]> };
  stale?: Record<string, StaleInfo>;
  intent?: Omit<IntentInfo, "doc">;
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
  | { type: "design-error"; message: string }
  | { type: "intent-changed"; intent: IntentInfo; changed: string[] }
  | { type: "proposals-changed"; id?: string };

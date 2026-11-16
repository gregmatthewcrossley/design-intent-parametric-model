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
  about?: string;
  value?: string;
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
  check_state?: "" | "failing" | "thin" | "ample";
  checks_not_run?: number;
  review_state?: "" | "reviewed" | "unreviewed" | "stale" | "reviewed_failing";
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
  components?: Record<string, string>[];
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
  | { op: "mark_reviewed"; ids: string[]; all?: boolean }
  | { op: "set_binding"; id: string; check_id: string; status?: string; binding?: Record<string, string> }
  | { op: "edit_component"; component_id: string; fields: Record<string, string> };

export type ProposalStatus = "pending" | "evaluating" | "ready" | "failed" | "accepted" | "rejected" | "stale" | "trying";

export interface FeedbackJ { at: string; kind: string; by: string; comment: string }

export interface EvaluationJ {
  ok: boolean;
  error?: string;
  failing_checks?: string[];
  needs_override?: boolean;
  params?: Record<string, unknown>;
  view_params?: Record<string, unknown>;
  before?: { status: TieredStatus; kernel: string; ok: boolean; stale_nodes: string[] };
  after?: { status: TieredStatus; kernel: string; ok: boolean; errors: ErrorJ[]; stale_nodes: string[];
            intent_checks?: SummaryCheckJ[]; unreviewed?: AssumedJ[] };
  // iteration 4 (docs/purpose-loop.md): purpose review and what a geometry alternative assumed
  purpose?: PurposeReviewJ;
  assumed?: AssumedJ[];
  sweep?: { points: number; failing: { params: Record<string, unknown>; errors: string[] }[] };
  semantic_diff?: {
    intent: { added: { id: string; statement: string; parent: string | null }[]; removed: { id: string; statement: string }[];
              moved: { id: string; from: string | null; to: string | null }[];
              changed: ({ id: string; statement?: { before: string; after: string } } & Record<string, unknown>)[] };
    features: { added: string[]; removed: string[]; changed: ({ id: string } & Record<string, { before: unknown; after: unknown } | string>)[] };
    checks: { before: { status: string; kernel?: string; errors: number }; after: { status: string; kernel?: string; errors: number };
              intent?: { id: string; before: string | null; after: string }[];
              features: { id: string; before: string | null; after: string; failed_checks: CheckJ[] }[];
              diagnostics_after: Diagnostics };
    interpretations: { added: { id: string; chosen: string }[]; removed: { id: string; chosen: string }[];
                       changed: { id: string; before: string; after: string }[]; questions: number[]; notices: number[] };
  };
  text_diff?: Record<string, string>;
  meshes?: { before?: string; after?: string };
  changed_faces?: { before: number[]; after: number[]; outline_before?: number[]; outline_after?: number[] };
  face_tags?: { before: string[]; after: string[] };
  ms?: number;
}

// ------------------------------------------------------------------ iteration 4 (docs/purpose-loop.md)

export type ImpactClass = "changed" | "invalidated" | "survives";
export interface ImpactItemJ { class: ImpactClass; reasons: string[]; statement?: string; node?: string; parent?: string | null;
                               features?: string[]; new?: boolean }
export interface ImpactJ {
  terms: { removed: string[]; added: string[] };
  changes: { id: string; new: boolean; fields: string[]; before: NodeContent | null; after: NodeContent }[];
  removed_nodes: string[];
  nodes: Record<string, ImpactItemJ>;
  checks: Record<string, ImpactItemJ>;
  assumptions: Record<string, ImpactItemJ>;
  features: Record<string, ImpactItemJ>;
  summary: Record<string, Record<ImpactClass, number>>;
  any_change: boolean;
  method: string;
}

export interface QuantityJ { nominal: number; lo: number; hi: number; unit: string; source: string; made_by: string;
                             label: string; placeholder: boolean }
export interface ComponentJ { id: string; shape: "cylinder" | "box"; statement: string; dims: Record<string, QuantityJ>;
                              mass: QuantityJ | null; pack: string; source: string; made_by: string; status: string;
                              reviewed: boolean; placeholder: boolean }
export interface GhostJ {
  component: string; shape: "cylinder" | "box"; made_by: string; reviewed: boolean; note?: string; check?: string;
  center: number[];
  axis?: number[]; diameter?: number; length?: number; shortened?: boolean;      // cylinder
  axes?: number[][]; size?: number[];                                           // box
}

export interface SummaryTermJ { name: string; unit: string; sense: "<=" | ">="; nominal: number; worst: number; limit: number;
                                limit_worst: number; margin: number; margin_worst: number; state: "ample" | "thin" | "failing" }
export interface SummaryCheckJ {
  id: string; node: string; state: string; plain: string; reason?: string;
  headline?: Omit<SummaryTermJ, "sense" | "state"> | null;
  form?: string | null; binding_text?: string; made_by?: string | null; binding_reviewed?: boolean;
  terms?: SummaryTermJ[]; method_assumptions?: string[]; ghosts?: GhostJ[];
}
export interface AssumedJ { kind: string; id: string; text: string; made_by: string }
export interface PurposeCheckJ { id: string; node: string; statement: string; form: string | null;
                                 binding: Record<string, string> | null; reads_as: string; made_by: string | null;
                                 reviewed: boolean; state: string; reason: string;
                                 headline?: Omit<SummaryTermJ, "sense" | "state"> | null }
export interface PurposeReviewJ { before: IntentDocJ | null; after: IntentDocJ; checks: PurposeCheckJ[];
                                  components: ComponentJ[]; validation: Record<string, string[]> }
export interface AttemptJ { n: number; at: string; summary: string; headline: string; kernel: string | null;
                            failing: string[]; not_run: string[]; error?: string | null }

export interface ProposalJ {
  id: string;
  kind?: "patch" | "purpose" | "geometry";
  design?: string;
  group?: string | null;
  alternative?: string;
  purpose?: string | null;
  attempts?: AttemptJ[];
  budget?: number;
  validation?: Record<string, string[]>;
  designer_edits?: { at: string; ops: unknown[] }[];
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
  accepted?: { at: string; written: string[]; reviewed: string[]; override?: { failing: string[]; reason: string } };
}

export interface RequestJ {
  id: string;
  kind?: string;
  design?: string;
  created: string;
  node: string;
  note: string;
  change: StaleInfo | null;
  status: string;   // open | running | proposed | failed | answered (iteration 4b)
  proposals: string[];
  status_detail?: string;
  runs?: string[];
}

// ------------------------------------------------------------------ iteration 4b: headless Claude runs

export interface RunStepJ {
  at: string;
  kind: "start" | "tool" | "result" | "proposed" | "say" | "warn" | "error" | "done" | string;
  text: string;
  tool?: string;
  proposals?: string[];
}

export interface RunJ {
  id: string;
  design: string;
  requests: string[];
  status: "running" | "done" | "failed" | "cancelled" | "timeout" | string;
  trigger?: string;
  started: string;
  ended: string | null;
  reason: string;
  proposals: string[];
  usage_line?: string;
  model?: string | null;
  session_id?: string | null;
  steps: RunStepJ[];
  auth_error?: boolean;
  timeout_s?: number;
}

export interface ClaudeStatusJ {
  available: { ok: boolean; bin: string; source: string; reason: string; login?: string };
  settings: { auto_run: boolean; model: string | null; timeout_s: number };
  running: boolean;
  run: RunJ | null;
  runs: Pick<RunJ, "id" | "status" | "requests" | "started" | "ended" | "reason" | "proposals">[];
  waiting: number;
  runnable: string[];
  prompt: string;
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
  size?: string; // "Ø4.5 hole (#8) · 9.0 mm from edge" (size-on-hover callouts)
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
  feasible?: string[]; // B3: readings that pass every check
  resolution?: "unconfirmed" | "confirmed" | "author";
  confirmed_by?: string[];
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

// ------------------------------------------------------------------ iteration 3 (docs/gui.md §8)

export interface CheckTermJ {
  name: string;
  plain: string;
  unit: string;
  sense: "<=" | ">=";
  nominal: number;
  worst: number;
  limit: number;
  limit_worst: number;
  margin: number;
  margin_worst: number;
  margin_rel: number | null;
  state: "ample" | "thin" | "failing";
  inputs: { name: string; nominal: number; lo: number; hi: number; unit: string; source: string; made_by: string;
            label: string; placeholder: boolean }[];
  method: string;
  formula: string;
}

export interface IntentCheckJ {
  id: string;
  node: string;
  statement: string;
  plain: string;
  kind: string;
  rung: number;
  state: "ample" | "thin" | "failing" | "not run";
  reason: string;
  governing: string;
  terms: CheckTermJ[];
  headline: CheckTermJ | null;
  assumptions: { id: string; statement: string; made_by: string; reviewed: boolean; in_file?: boolean }[];
  method_assumptions: string[];
  features: string[];
  faces: number[];
  priority: string;
  source: string;
  reviewed: boolean;
  binding?: Record<string, string> | null;
  binding_text?: string;
  binding_reviewed?: boolean;
  spec_made_by?: string;
  ghosts?: GhostJ[];
}

export interface TieredStatus {
  kernel: { state: "pass" | "fail"; failures: number; features: number };
  intent: { total: number; run: number; not_run: number; failing: number; thin: number; ample: number;
            failing_ids: string[]; thin_ids: string[]; ample_ids: string[]; not_run_ids: string[] };
  headline: string;
  text: string;
  guesses?: number;
}

export interface ContextItem { value: string; made_by: string; status: string; reviewed: boolean; source: string }

export interface OrientationCand {
  up: number[]; overhang_mm2: number; support_mm3: number; bed_mm2: number; cost: number; down_face: string;
}

export interface OrientationJ {
  up: number[];
  label: string;
  rationale?: string;
  made_by: string;
  reviewed: boolean;
  status?: string;
  source?: string;
  chosen?: OrientationCand;
  runner_up?: OrientationCand | null;
  candidates?: OrientationCand[];
  assumption_id?: string;
}

export interface AppearanceJ {
  process: string;
  layer_pitch: number;
  extrusion_width: number;
  nozzle: number;
  top_line_angle_deg: number;
  flags: Record<string, boolean>;
  roughness: number;
  material: string;
  build_direction?: number[];
  orientation_reviewed?: boolean;
}

export interface ProvenanceJ { made_by: string | null; reviewed: boolean; guess: boolean; label: string; value?: string;
                               node?: string }

export interface ReferencesJ {
  screws: Record<string, { major: number; head: number; clearance: number; length: number }>;
  card: { width: number; height: number; corner_radius: number; thickness: number };
  fingertip: { breadth: number; length: number; placeholder: boolean };
  hand: { length: number; breadth: number; placeholder: boolean };
}

export interface BuildJ {
  design: string;
  file?: string;
  params: Record<string, number | string>;
  ok: boolean; // kernel invariants only: never shown as a bare PASS (B1)
  kernel_ok?: boolean;
  status: TieredStatus;
  intent_checks?: IntentCheckJ[];
  context?: { items: Record<string, ContextItem>; summary: string; assumed: boolean };
  orientation?: OrientationJ | null;
  appearance?: AppearanceJ | null;
  provenance?: Record<string, ProvenanceJ>;
  guesses?: string[];
  references?: ReferencesJ;
  components?: ComponentJ[];
  ghosts?: GhostJ[];
  impact?: ImpactJ | null;
  overrides?: Record<string, { failing: string[]; reason: string; at: string; proposal?: string }>;
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
  | { type: "proposals-changed"; id?: string }
  | { type: "claude-run"; status: ClaudeStatusJ };

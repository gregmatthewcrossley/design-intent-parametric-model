# User Experience and Integration

*Status: early draft, 2026-11-15, from conversation. Decided: standalone for now (§5).*

How a designer actually uses this: workspace, versioning, GUI, and connections to the tools they already use.

---

## 1. Source of truth is text; geometry is a build artifact

The solution side is deterministic once fully locked: source + interpretations lock + prefs + pinned kernel and packages (architecture principle 2 and §7, which list where non-determinism still leaks). The source of truth is therefore **text**:
- the intent tree, checks, and assumptions
- the DSL
- a **lockfile** pinning the kernel, solver, and package versions

Geometry is rebuilt from these exactly, like a compiled binary. It is not committed.

### 1.1 Storage formats (decided 2026-11-16)

**Text files are the source of truth; databases hold only derived, rebuildable data.**

| Data | Format | Why |
|---|---|---|
| Intent tree: statements, checks, assumptions, context (`<design>.intent.yaml`) | **Schema-validated YAML**, always rewritten in canonical form | Versioned in git, reviewable line diffs, readable and writable by designers and by Claude, small per design |
| Solution (`<design>.py`) | The DSL (embedded Python today; possibly a dedicated textual DSL later) | Code |
| Machine-written locks (`<design>.interpretations.json`, …) | JSON | Unambiguous; not hand-edited |
| Review record (`<design>.review.json`: accepted intent-node hashes) | JSON, committed | Staleness is part of the design's state |
| Proposals from Claude (`.dipm/proposals/`) | JSON, gitignored | Transient until accepted; an accepted proposal becomes an ordinary file change |
| Caches, build history, telemetry | **SQLite** (gitignored, deletable, regenerated from text) | Fast queries, transactions |
| Large datasets (procedural training corpus, later) | SQLite or Parquet | Volume; machine-only |

**YAML rules.**
- Use a safe subset with a schema, so values can't silently change type (the "Norway problem").
- Round-trip editing keeps comments (ruamel.yaml).
- Keys are written in a stable order, so diffs stay minimal.
- All reads and writes go through one small load/save module, so the format can be swapped without touching the rest of the code.

**Noted alternative: KDL**, a node-based document language. It fits the intent tree best: `intent "A.P" "Wall screw pattern" { check … }` maps directly onto id, statement, and children. It reads like a design document and has no type surprises. It was not chosen now because its Python tooling is less mature, especially comment-preserving rewrites, and models write YAML more reliably. Revisit if the tooling matures, or fold intent into a dedicated textual DSL if one is built. (CUE, which unifies data, schema, and constraints, was considered as inspiration only, since it overlaps the project's own check system.)

**Concurrent edits** (GUI, a text editor, and Claude on the same file):
- Writes are atomic (temp file + rename).
- Every GUI write carries the content hash it was based on. A stale write is rejected, and the GUI reloads and re-applies or shows the conflict, rather than overwriting.

**Later, multi-user:** a server plus a CRDT (e.g. Automerge) for live collaboration, still exporting canonical text for versioning and review.

## 2. Versioning

**Git or similar.**

- **Branches are design alternatives**, replacing `bracket_v3_final_FINAL.sldprt`. Onshape already gives designers git-like versions and branches, so the idea is familiar.
- **Diffs work at two levels:**
  - *Semantic:* "assumption R.a1 changed static → dynamic load; R.c1 and R.c4 re-ran; screw pattern re-spread."
  - *Visual:* before/after renders overlaid, changed faces highlighted.
- **Reviews work like pull requests:** the model proposes; the designer approves or challenges specific assumptions and checks.
- Reference photos, scans, and sketches go in Git LFS or similar.

## 3. GUI

A designer thinks spatially, so a text-only tool would fail them. The GUI doesn't replace CAD on day one. It has a few coordinated panes:

| Pane | Purpose |
|---|---|
| **3D viewport** | Rebuilt geometry. Click any face → **"why is this here?"**: the intent that created it, the checks it serves, the assumptions behind it |
| **Intent tree** | A feature tree of *purposes*, with pass/fail status per node |
| **Assumptions** | Sorted by sensitivity; accept / challenge each |
| **Input** | Text, pen sketch, dropped photo / drawing / scan |
| **DSL view** | Optional, for power users (like Onshape's FeatureScript view) |

**Direct manipulation edits intent, not coordinates.** Dragging a centered hole 10 mm left shouldn't silently write `x = 47.5`. It asks: *"This hole was centered. Make it offset from center by 10 mm, or relative to something else?"*

**Parameter edits don't need the model.** They rebuild instantly, from the locked solution. The model is involved only when *intent* changes.

**Platform: the browser is the primary GUI** (direction agreed 2026-11-15).
- Precedent: Onshape shows professionals will do serious CAD in a browser.
- No install, and any device, including tablets with a pen: browsers expose pen pressure and tilt.
- Still "standalone": the engine runs locally and serves the GUI at `localhost` (Jupyter-style), and could later be wrapped as a desktop app.
- **v0 is a browser GUI talking to a local engine.** A backend is needed anyway, for frontier-model API keys and the native Python/ML ecosystem.

**Architecture:** a headless engine with a CLI and API first, the browser GUI on top, and the same engine exposed as an **MCP server** so AI agents can drive it.

Iteration 1 of the browser GUI is specified in [`gui.md`](gui.md).

### 3.1 Redline review: feedback with a red marker

Designers already review drawings by **redlining** them. The GUI makes this a first-class input:

- **Marks resolve to geometry.** Strokes drawn on the 3D view are projected onto the model (raycast) and become **structural references** to the faces, edges, or features they touch, so "this" is exact.
- **The model sees both** the marked-up image *and* the structured list of what each mark touched, which is far more reliable than a vision model guessing from pixels.
- **A light markup vocabulary,** like proofreading marks, with free-form notes always allowed:
  - circle = look here
  - arrow = move / direction
  - X = remove
  - parallel ticks = equal / align
  - scribbled number = dimension
  - handwriting = intent
- **Review works like code review.** Each mark becomes a comment anchored to an intent node, like a PR comment on a line. The model responds with **proposed intent changes shown as a diff** (e.g. "A.3: 'between screws' → 'centered on plate'"), which the designer accepts or challenges.
- **Drawings too.** Generated 2D drawings can be redlined exactly like paper; marks resolve to the same references.

## 4. Interfaces with existing software

| Target | Route | What survives |
|---|---|---|
| **Onshape** | (a) STEP export; (b) compile DSL → FeatureScript features via the API (dsl.md §6.3) | (a) geometry; (b) full parametric feature tree. Onshape is the natural first parametric target. API call limits (≈2,500/yr on standard plans) mean export on demand, not in a loop |
| **SolidWorks / Fusion** | STEP now; native APIs later | Geometry; parametrics later and harder |
| **3D printing** | **3MF** (units, multiple bodies, orientation) rather than STL. The walkthrough's *fabricate* stage picks orientation | — |
| **Slicers as check engines** | Headless PrusaSlicer / OrcaSlicer / Bambu Studio CLIs | Turns "printable?" into measured checks: support volume, time, warnings |
| **CNC / CAM** | STEP into Fusion CAM or FreeCAD CAM; DXF for laser, waterjet, sheet metal | Geometry |
| **Drawings** | Generate 2D drawings dimensioned **from the intent tree** | The dimensions that matter to intent |
| **Electronics (KiCad)** | Import board outline / STEP as context for enclosure intents | Board geometry as `receives` references |

### 4.1 Onshape parity (researched 2026-11-16)

Full notes: [`research_notes/Onshape parity/onshape-api-parity.md`](../research_notes/Onshape%20parity/onshape-api-parity.md).

- **Verdict:** dipm trees can be recreated natively with clean *geometry and parameters*, but not with their *intent* if only standard features are used.
  - **Every op maps cleanly** to a native feature the REST API can create.
  - **Parameters map cleanly** to Variable Studio variables and configuration inputs.
  - **Placements are lossy:** `centered_on`, `face_point`, `distribute` and `centerline.before` are computed from 3D at build time and partly export as literals.
  - **No native equivalent:** interpretations, branch tags, ΔH/ΔS/volume contracts, reference cardinality, and policies.
- **Recommended strategy: hybrid, standard features first.**
  - All geometry is standard features driven by `#variables`, so engineers edit what they know.
  - A small, versioned **dipm FeatureScript library of placement features** (`centered_on`, `distribute`, …) outputs locating points that native Hole features consume, so drawings and callouts stay standard.
  - A final **dipm checks feature** re-runs intent checks inside Onshape, so hand edits that break intent show as warnings in the native tree. This is the answer to PAIN-09.
  - The way back starts with reading the tree after edits (parameter edits, added standard features); full intent recovery comes later.
- **Main gaps:**
  1. Onshape has no persistent entity ids, so references are resolved once at export to deterministic ids, and their survival under engineer edits needs a live test.
  2. Literals survive until dipm keeps expressions symbolic through lowering (engine TODO 2).
  3. Verification needs a topology-normalization rule, because Onshape's kernel differs from OCCT on seams and auto-merging.
  4. API caps: 2,500 calls/yr on Free/Standard, 5,000 Professional, 10,000 Enterprise; about 25–30 calls per bracket export. Apps listed publicly in the Onshape App Store don't count against the cap.

**The round trip is the hard part.** Hand edits made in an exported Onshape model don't flow back into the intent tree. Early versions treat this project as the **source of truth** and Onshape as an **output**. Pulling edits back means inferring intent from a feature tree, the reverse-engineering problem from the survey. That is a later goal.

## 5. Decision: where does the designer work?

> **Decided 2026-11-15: standalone for now.** The project is its own app and engine; Onshape is an export target (STEP, later FeatureScript). The options below remain on record for revisiting; nothing in the design should preclude a later Onshape-tab front end.

- **Standalone app**, with Onshape as an export target.
- **Inside Onshape:** Onshape supports third-party apps in a document tab, so the intent tree and assumptions could sit beside the real feature tree.
- **Both:** standalone engine first, with Onshape integration as the main front end later.

This decision shapes the GUI work more than any other.

## 6. Suggested phasing

1. **v0:** text files in git; CLI engine; simple browser 3D viewer served by the local engine; STEP / 3MF export.
2. **v1:** browser GUI with intent tree, "why is this here?", assumptions review, edit-intent-by-dragging, and redline review.
3. **v2:** Onshape FeatureScript compile target; slicers as fabrication checks.

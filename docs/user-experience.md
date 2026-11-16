# User Experience and Integration

*Status: early draft, 2026-11-15, from conversation. Decided: standalone for now (§5).*

How a designer actually uses this: workspace, versioning, GUI, and connections to the tools they already use.

---

## 1. Source of truth is text; geometry is a build artifact

The solution side is deterministic (architecture principle 2). The source of truth is therefore **text**:
- the intent tree, checks, and assumptions
- the DSL
- a **lockfile** pinning the kernel, solver, and package versions

Geometry is rebuilt from these exactly, like a compiled binary. It is not committed.

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

**Parameter edits don't need the model.** They rebuild instantly and deterministically. The model is involved only when *intent* changes.

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

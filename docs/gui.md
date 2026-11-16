# Web GUI: Iteration 1 Spec

*Status: agreed 2026-11-16 (scope, layout, and style chosen by the user). Context: [`user-experience.md`](user-experience.md) §3. Engine: [`src/dipm/NOTES.md`](../src/dipm/NOTES.md).*

## 1. Goal

Show a design **live in the browser** and make its **intent visible**. Design files are still edited in a text editor, by the designer or by Claude. The GUI watches the file and rebuilds on save. Redline markup, model conversation, drag-to-edit intent, drawings, git diffs, and a stability-sweep view are **out of scope** (iteration 2+).

## 2. Scope: nine features

| # | Feature | Behavior | Engine source |
|---|---|---|---|
| 1 | **`dipm serve <design.py>`** | Starts a local server on `127.0.0.1` (localhost only), prints the URL, and opens the browser | CLI |
| 2 | **3D viewport** | Shaded model with visible edges; orbit/pan/zoom; fit; standard views (iso, front, side, top); axis triad; mm units | Deterministic tessellation that preserves **face and edge identity** |
| 3 | **Parameters bar** | A slider per ranged parameter, a dropdown per choice parameter, a numeric field beside each slider. Rebuilds on change (debounced) and shows build time. A failed build keeps the last good model, greyed, and shows the errors | `Design.build(**params)` |
| 4 | **Intent tree** | Hierarchy derived from intent-node ids (R → A → A.P → A.P.1 …), labeled with each tag's note. A status dot per node shows the worst status of the features beneath it | Feature ids + intent tags |
| 5 | **Inspector: "why is this here?"** | Hover a face to highlight it and show a tooltip (feature · role). Click to pin the full genealogy in the inspector: feature id, role, intent tags, history, lowered-from. Clicking a **tree node** highlights every face it created and dims the rest. Selection syncs both ways | `Build.why()` |
| 6 | **Checks panel** | Per feature: validity, Euler, ΔH, ΔS, volume sign, references. Failures appear here, on the tree node, and as tinted faces | Report data |
| 7 | **Interpretations panel** | Per slot: the chosen reading and why, eliminated readings and why, sensitivity, `made_by`. Notices (e.g. *default overridden*) are visually distinct. **Questions** get one button per surviving reading; choosing one records a preference and rebuilds | `interpret.py` (lock + prefs) |
| 9 | **Intent ↔ feature connections** | A **WHY ⇄ HOW** toggle in one panel (§3): the intent tree and the ordered feature list (as in SolidWorks/Onshape), with connector lines to the intent nodes each feature serves (many-to-many), *uses* arrows between features (from resolved references), and the parameters each feature depends on. Hovering or selecting an intent, feature, parameter, or face lights up everything connected in all views. **Diagnostics:** features with no intent, intents with no feature, features serving several intents (coupling), and dependencies between intents that shouldn't know about each other (false coupling, architecture §5.1) | Feature order, intent tags, the resolution log of references each feature uses, and parameter dependencies of feature expressions (may need a small engine addition to expose) |
| 8 | **Live reload** | Saving the design file (or its lock/prefs) pushes a rebuild over a WebSocket and keeps the current parameters, selection, and camera | File watcher |

## 3. Layout: classic CAD panels

```
┌──────────┬───────────────────────┬────────────┐
│ INTENT   │                       │ INSPECTOR  │
│ TREE     │       3D VIEWPORT     │ why is     │
│ R        │                       │ this here? │
│ ├ A      │                       ├────────────┤
│ │ ├ A.P ●│                       │ CHECKS     │
│ │ └ A.3 ●│                       ├────────────┤
│ ├ B.1   ●│                       │ INTERPRE-  │
│ └ C     ●│                       │ TATIONS    │
├──────────┴───────────────────────┴────────────┤
│ PARAMETERS  shelf_depth ━━●━━  t ━●━━  screw ▾│
└───────────────────────────────────────────────┘
```

- **The left panel shows both trees in one window**, with a prominent **WHY ⇄ HOW** toggle (agreed 2026-11-16):
  - **WHY (intent first):** the intent tree is primary, and each node shows the features that realize it as side callouts.
  - **HOW (features first):** the ordered feature list (as in SolidWorks/Onshape) is primary, and each feature shows the intent nodes it serves and its *uses* dependencies as callouts.

```
WHY ◉ ─── ○ HOW                                WHY ○ ─── ◉ HOW
R  Support a shelf      ● ┊ 1 R.body · 6 R.fillet   1 R.body     extrude      ● ┊ R
├ A  Wall mounting      ● ┊                         2 C.gusset   extrude +    ● ┊ C
│ ├ A.P  Screw pattern  ● ┊ 3 A.P.holes ◄uses 2     3 A.P.holes  hole ×2 ◄2   ● ┊ A.P · A.P.1 · A.P.2
│ └ A.3  Cable hole     ● ┊ 4 A.3.cable ◄uses 2     4 A.3.cable  hole    ◄2   ● ┊ A.3
├ B  Shelf support      ● ┊                         5 B.1.screw  hole         ● ┊ B.1
│ └ B.1  Shelf screw    ● ┊ 5 B.1.screw             6 R.fillet   fillet       ● ┊ R (R.c2 printable)
└ C  Stiffening         ● ┊ 2 C.gusset
```

  - **Animated transition:** a shared-element morph of about 300 ms. Items present in both views (e.g. `A.P.holes`) glide between callout and main row; rows reorder from tree order to build order; selection, scroll anchor, and status dots carry across. It is instant under `prefers-reduced-motion`.
  - **"Show links"** draws connector lines between main rows and callouts. The panel's **expanded** state (widened over the viewport) is the full intent ⇄ feature ⇄ parameter connections diagram.
  - Selecting a parameter in the bottom bar highlights every row it drives, in either view.
- Side panels are resizable and collapsible. Right-panel sections are collapsible.
- Desktop-first (≥1024 px). Below that, panels become tabs over the viewport. Tablet-quality touch comes in a later iteration.
- A header strip shows the design name, file path, build status (PASS / FAIL with count), build time, and a light/dark toggle.

## 4. Visual style: drawing-sheet

The same visual language as the overnight review page:

- **Palette:** cool paper and graphite neutrals, steel blue for the model and selection, **red reserved for attention** (failures, notices, questions, and later, redlines), and semantic green/amber for check states. Light and dark themes are defined as tokens.
- **Type:** Archivo (headings), IBM Plex Sans (UI), IBM Plex Mono (ids, numbers, dimensions). The fonts are **vendored locally** (both are under the SIL Open Font License) so the app works offline.
- **Feel:** technical-drawing conventions where they carry meaning: hairline panel rules, tabular numerals, mm units, intent-node ids in mono.
- **Model rendering:** matte steel-tinted faces with dark edges. Hovered faces are lighter; selected faces are steel; faces of a failing feature are tinted red.

## 5. Architecture

```
 browser (TypeScript + Vite + three.js + Preact)
     │  HTTP JSON + binary mesh, WebSocket events
 dipm server (Python: Starlette + uvicorn + watchfiles)  ── localhost only
     │
 dipm engine (Design.build, why(), interpret, report data)
```

**API (proposed):**

| Endpoint | Purpose |
|---|---|
| `GET /api/design` | Name, doc, file path, parameters (name, default, range/choices, unit, doc) |
| `POST /api/build` `{params}` | Build result: status, features with invariant results, derived intent tree, interpretations (slots, questions, notices), signature, timings, per-face genealogy table, and a mesh id |
| `GET /api/mesh/{id}` | Compact binary mesh: positions, normals, indices, **per-face triangle ranges** and **per-edge polylines**, keyed by stable face and edge ids that match the genealogy table |
| `POST /api/answer` `{assumption_id, reading}` | Record a preference (same semantics as `dipm answer`), re-resolve, rebuild |
| `WS /api/events` | `design-changed`, `rebuilt` |

**Determinism:** tessellation uses fixed deflection settings, so the same build produces the same mesh. Mesh face ids are derived from the build's face order and tied to `why()`.

**Code layout:**
- `src/dipm/server/` holds the API and static serving.
- `gui/` holds the frontend source.
- `npm run build` writes into `src/dipm/server/static/` (gitignored).
- `npm run dev` runs Vite with an API proxy for frontend work.

## 6. Acceptance criteria

1. `dipm serve examples/shelf_bracket.py` opens the bracket. The tree shows R, A, A.P, A.P.1, A.P.2, A.3, B, B.1, C with green dots.
2. Dragging `shelf_depth` 200 → 300 rebuilds visibly. The holes re-spread and the cable hole stays at the exposed-plate midpoint.
3. Clicking a countersink face shows `A.P.holes.countersink(1)` · `hole@A.P.2` · `pattern@A.P (wall screw pattern)`, and highlights A.P.2 in the tree.
4. Clicking A.P in the tree highlights both screw holes' faces and nothing else.
5. The interpretations panel shows four slots. The A.3 *default overridden* notice is visible and distinct, and there are zero questions.
6. A fixture design with divergent readings shows a question. Clicking an answer writes the preference, the question disappears, and the model rebuilds.
7. Building with a deliberately failing parameter (e.g. a negative-control fixture) shows the failure in the checks panel, the tree, and the tinted faces, while the last good model stays visible.
8. Editing and saving the design file triggers a rebuild in the open browser within about a second, keeping the camera and selection.
9. The Connections view for the bracket shows all six features linked to their intents; *uses* arrows from A.P.holes and A.3.cable to C.gusset; and parameter links (e.g. `screw` → A.P.holes, B.1.screw). Selecting `shelf_depth` lights up every feature it drives. A fixture with an untagged feature shows it flagged as "no intent".
10. Light and dark themes both read well.
11. Python API tests (pytest + TestClient) cover every endpoint. The frontend builds cleanly; type-checking passes.

## 7. Open items for later iterations

- Redline layer: marks resolve to structural references and become comments on intent nodes (user-experience §3.1).
- Previewing a reading's geometry before answering a question.
- Model conversation panel; drag-to-edit intent; stability-sweep view; drawings; semantic diffs.
- Running the engine in the browser via WASM (explore-further §4).

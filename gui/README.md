# dipm GUI (iterations 1 and 2)

The browser front end for `python -m dipm serve <design.py>`. The spec is [`docs/gui.md`](../docs/gui.md). Iteration 1 shows a design live, makes its intent visible, and rebuilds whenever the design file is saved. Iteration 2 (§7) makes the **intent editable** in the GUI (`<design>.intent.yaml`), tracks which solutions are **stale** after an intent edit, and puts **Claude in the loop** through an MCP server whose proposals the designer reviews and accepts here. The DSL itself is still edited in a text editor, or through accepted proposals.

## Build and run

You need Node ≥ 20 (tested on 20.12) and the repo's Python `.venv` (see the top-level `CLAUDE.md`).

```bash
uv pip install --python .venv/bin/python -e ".[test]"   # from the repo root: dipm + server deps (Starlette, uvicorn, watchfiles)
cd gui
npm ci                     # exact versions from package-lock.json
npm run build              # tsc --noEmit, then vite build -> ../src/dipm/server/static/ (gitignored)
cd ..
.venv/bin/python -m dipm serve examples/shelf_bracket.py              # prints the URL and opens the browser
.venv/bin/python -m dipm serve examples/shelf_bracket.py --no-open --port 8765 --prefs prefs.json
```

The server binds to `127.0.0.1` only. If the port is busy it tries the next one. Without a built frontend the API still works, and `/` explains how to build it.

## Develop

```bash
.venv/bin/python -m dipm serve examples/shelf_bracket.py --no-open --port 8765   # terminal 1: API
cd gui && npm run dev                                                           # terminal 2: Vite on :5173, proxies /api (HTTP + WS)
```

Set `DIPM_API=http://127.0.0.1:<port>` if the API runs on another port.

## Test

```bash
npm run typecheck          # tsc --noEmit
npm test                   # vitest: row ordering, WHY⇄HOW transition mapping, "what lights up", mesh decoding
npx playwright install chromium   # once
npm run build && npm run e2e      # Playwright: the gui.md §6 acceptance criteria against real `dipm serve` processes
npm run screenshots        # writes screenshots/*.png (light and dark; DIPM_SHOTS=1 adds the iter2-*.png flows)
```

`e2e/acceptance.spec.ts` covers gui.md §6 (iteration 1); `e2e/iteration2.spec.ts` covers §7.2 criteria 1–6 and §7.3, with Claude simulated by `e2e/simulate_claude.py` (it drives `python -m dipm mcp` over stdio with the official MCP client, exactly as Claude Code does).

The e2e tests start their own servers from `../.venv` (`e2e/server.ts`). Tests that write preferences or edit a design work on temp copies of the fixtures in `tests/fixtures/`. WebGL runs headless through SwiftShader (`playwright.config.ts`).

Python side: `.venv/bin/python -m pytest -q tests/test_server.py tests/test_connections.py tests/test_intent_store.py tests/test_intent_server.py tests/test_proposals.py tests/test_mcp.py tests/test_codemod.py`.

Fixtures for manual checks:

| Design | Shows |
|---|---|
| `examples/shelf_bracket.py` | The worked example: 9 intent nodes, 6 features, 4 interpretation slots, 0 questions, 0 notices |
| `tests/fixtures/question_channel.py` | A hole whose extent is a real **question** (answer buttons; the answer goes to `question_channel.prefs.json`) |
| `tests/fixtures/invariant_fail.py` | Slide `hole_u` over the rib (about 0.63–0.87): ΔH fails, the faces are tinted, the last good model stays greyed |
| `tests/fixtures/diagnostics.py` | Every connection diagnostic: no intent, intent with no feature, several intents, cross-intent dependency |

Run the iteration-2 flows on a **copy** of the bracket, since editing intent and accepting proposals write files:

```bash
D=$(mktemp -d) && cp examples/shelf_bracket.{py,intent.yaml,interpretations.json,review.json} $D/
.venv/bin/python -m dipm serve $D/shelf_bracket.py
```

## Using it

- **Left panel, WHY ⇄ HOW.** WHY puts the intent tree first, with the features that realize each node as callouts. HOW puts the features first, in build order, with the intents each serves (and its *uses*) as callouts. Toggling animates shared elements (about 300 ms; instant under `prefers-reduced-motion`). **links** draws leader lines and *uses* arrows. **⤢** opens the expanded **Connections** view (intents ⇄ features ⇄ parameters) over the viewport. Esc closes it.
- **Hover** anything (a face, row, chip, parameter name) to light up everything connected to it in every view. **Click** to pin it; click again or press Esc to clear. Pinning a face shows its genealogy in the inspector and highlights its intent nodes; pinning a tree node highlights the faces it created and dims the rest.
- **Viewport:** drag to orbit, right-drag or shift-drag to pan, scroll to zoom. **fit / iso / front / side / top** (keys `f`, `0`, `1`, `3`, `7`). The axis triad is bottom left; the overall size in mm is bottom right.
- **Parameters:** a slider plus numeric field per ranged parameter, a dropdown per choice. Rebuilds are debounced at 140 ms. Build time is shown in the bar and the header (engine time · round trip).
- **Right panel:** the inspector; checks (validity, Euler, ΔH, ΔS, volume sign, references per feature; hover a cell for expected/got); interpretations (chosen reading and why, eliminated readings, sensitivity, `made_by`). **Questions** get one button per surviving reading. **Notices** are red-bordered and hatched, distinct from ordinary rows.
- Side panels resize (drag the inner edge) and collapse (‹ ›). Right-panel sections collapse. Below 1024 px the panels become tabs over the viewport. The theme toggle is in the header; the default follows the OS.

## Editing intent (iteration 2a)

A design's intent tree lives in `<design>.intent.yaml` next to it (`examples/shelf_bracket.intent.yaml`): statements, checks, assumptions and context, with the hierarchy given by nesting. Features still name the nodes they serve by id (`tags=intent("A.3", "hole", …)`). Without an intent file a design works exactly as in iteration 1: the tree is derived from its tags and nothing is editable.

- **WHY view.** Select a node to reveal its row actions: **✎** edit the statement inline (or **F2** / double-click), **+** add a child (it gets the next free dotted id, e.g. `B.2`, and shows "intent with no feature" until something realizes it), **×** delete (an in-page confirmation lists the features that will show "no intent"; **Del** on a focused row does the same). **Drag** a row onto another to reparent it; ids never change on a move. Rows are focusable (**Tab**, **Enter** to pin).
- **Inspector** (a selected node): the statement, **Add child**, **Delete…**, **move under …** (the keyboard alternative to dragging), **rename id…**, the **checks** editor (kind, priority, source, statement; descriptive in 2a) and the **assumptions** editor (status: proposed / accepted / challenged / replaced; rationale).
- **Rename id** rewrites the id in the intent file and the matching intent-id string literals in the DSL (`intent("…")` and `instance_tags=[…]`, via a LibCST codemod that keeps formatting and comments), and moves the review record with it.
- Every write is canonical YAML (comments, key order and quote style preserved; a one-line edit is a one-line diff), atomic, and carries the hash of the file it was based on.
- **Conflicts.** If the file changed on disk since your edit started (an editor, Claude, another tab), the write is refused (HTTP 409) and a red **CONFLICT** banner offers **Reload (drop my edit)** or **Re-apply my edit** on top of the new file. Nothing is overwritten silently. An invalid intent file (bad YAML or schema) shows a banner with the readable errors and the GUI keeps the last good tree.

**Stale solutions.** Each node's content (statement, checks, assumptions) is hashed; `<design>.review.json` records the hashes (and a snapshot) the designer accepted. The first time a design with an intent file is served, the current content becomes the baseline. An edited node, and the features that realize it, show **Δ intent changed · solution not reviewed** in the WHY tree (amber chips), the HOW list and the connections view. The inspector shows what it said before, a **Mark reviewed** button ("the solution still fits"), and **Ask Claude**.

## Claude in the loop (iteration 2b)

`python -m dipm mcp <design.py>` is a stdio MCP server for one design (official Python `mcp` SDK). Its tools: `get_design`, `get_intent`, `build(params)`, `why(face_id)`, `get_stale_nodes`, `get_requests`, `get_source`, `propose_patch(summary, rationale, files, base_hashes, addresses_nodes, revises?)`, `list_proposals`, `get_proposal_feedback`. The tools **never write design files**: `propose_patch` only stores a proposal (full text or a unified diff per file, for `<design>.py` and `<design>.intent.yaml` only; any other path is refused) under `<design dir>/.dipm/proposals/` (gitignored), shared with `dipm serve`.

**Register it with Claude Code** (one server per design; use absolute paths). From the repo root:

```bash
claude mcp add dipm -- "$PWD/.venv/bin/python" -m dipm mcp "$PWD/examples/shelf_bracket.py"
# or, to share it with everyone working in this repo (writes .mcp.json):
claude mcp add --scope project dipm -- "$PWD/.venv/bin/python" -m dipm mcp "$PWD/examples/shelf_bracket.py"
claude mcp list            # check it is connected
```

The syntax is `claude mcp add [options] <name> -- <command> [args...]` (stdio is the default transport; `--scope local|user|project`, default `local`). Inside a Claude Code session, `/mcp` shows the server and its tools.

**Workflow, end to end:**

1. Run `dipm serve <design.py>` and edit an intent in the GUI, e.g. A.3 from "Cable pass-through, centered on the plate" to "…, offset 10 mm above the lower screw". A.3 and `A.3.cable` turn stale.
2. In the inspector, optionally write a note and click **Ask Claude**. This stores an open request (`.dipm/requests/`).
3. In Claude Code, ask: *"Handle the open dipm requests."* Claude calls `get_stale_nodes` (what changed, the note, the features), `get_source` (texts + base hashes), maybe `build` / `why`, then `propose_patch`.
4. The proposal is evaluated in a temp copy: build, checks at the defaults and at every stability sample point, interpretations (re-resolved for the new source), a semantic diff (intent tree, features, checks, interpretations), the DSL text diff, and before/after meshes with the changed faces matched by genealogy tag and surface. Claude gets the evaluation back immediately.
5. The **PROPOSALS** panel (right side) lists it. Select it to see the checks, semantic diff and text diff, and toggle the viewport between **before**, **after** and **overlay** (after solid, before as a ghost), changed faces highlighted; **live model** returns to the current build.
6. **Accept** applies the patch atomically (all files or none), writes the interpretations lock resolved during evaluation, records review hashes for the addressed nodes (staleness clears) and closes their requests. Or **Reject with comment**: Claude reads it with `get_proposal_feedback` and proposes again with `revises=<id>`.

A proposal whose base hashes no longer match the files is marked **stale** and cannot be applied; ask Claude to regenerate it. Accepted patches are ordinary file changes, visible in `git diff`.

## Architecture

```
gui/src/
  main.tsx, App.tsx          layout: header · left | viewport | right · parameter bar; tabs below 1024 px
  store.ts                   app state (Preact signals): design, build, last good build, params, view,
                             hover/selection -> `lit` (computed), debounced requestBuild, answer
  intent.ts                  iteration 2 state: intent file + base hash, inline edit, 409 conflict, review,
                             requests, proposals, before/after comparison
  edit.ts                    pure: subtree, drop targets, staleness, diff lines, semantic-diff summaries
  api.ts                     fetch wrappers + WebSocket with reconnect
  types.ts                   JSON shapes served by src/dipm/server/serialize.py
  model.ts                   pure: WHY/HOW rows, transitionMap (shared elements), connected() (what lights up)
  mesh.ts                    pure: binary mesh decoder, triangle -> face id, edge segments
  viewer.ts                  three.js: shaded mesh with per-face vertex colours, edges, picking, views, triad, ghost
  components/                Header, IntentPanel (WHY⇄HOW, FLIP transition, links, diagnostics, editing, drag),
                             IntentEditor (inline edit, confirm, node/check/assumption editors, banners),
                             Proposals, Connections, Viewport (+ proposal compare), RightPanel, ParamBar
  styles.css, fonts.css      drawing-sheet tokens (light/dark) and the vendored fonts
public/fonts/                Archivo, IBM Plex Sans, IBM Plex Mono (woff2, SIL OFL 1.1; OFL-*.txt)
```

**Server** (`src/dipm/server/`):

- `app.py`: a `Session` per design file (load, build, answer, watch, intent edits, proposals). Starlette routes:
  - `GET /api/design`
  - `POST /api/build {params}`
  - `GET /api/mesh/{id}`
  - `POST /api/answer {assumption_id, reading, scope?, note?}`
  - `GET /api/intent`; `PATCH /api/intent {base_hash, ops}` (ops: `edit_statement`, `add_child`, `delete`, `move`, `add_check`, `edit_check`, `remove_check`, `edit_assumption`, `add_assumption`, `mark_reviewed`; 409 with the current state on a stale base); `POST /api/intent/rename {base_hash, design_hash, old, new}`
  - `GET|POST /api/proposals`, `GET /api/proposals/{id}`, `GET /api/proposals/{id}/mesh/{before|after}`, `POST /api/proposals/{id}/accept|reject|evaluate`
  - `GET|POST /api/requests` ("Ask Claude")
  - `WS /api/events`, which sends `hello`, `design-changed`, `rebuilt`, `design-error`, `intent-changed` and `proposals-changed`
- Engine-side modules for iteration 2: `intent_store.py` (the only code that knows the YAML format), `review.py` (node hashes, `<design>.review.json`), `proposals.py` (store, diffs, evaluation, accept/reject, requests), `mcp_server.py` (`dipm mcp`), `codemod.py` (rename id).
- `serialize.py`: a build becomes features (checks, refs, uses, parameter dependencies), the intent tree, diagnostics, interpretations, and the face/edge genealogy tables. Engine logic lives in `src/dipm/connections.py`.
- `mesh.py`: the binary layout is documented in its docstring. Face and edge ids are positions in `Build.faces()` and `Build.edges()`, the same ids the genealogy table uses.

**Data flow:**

1. A parameter change makes the client POST `/api/build`.
2. The response carries `mesh_id`. The client fetches `/api/mesh/{id}` (cached by id), decodes it, and paints per-face colours from hover, selection and failure state.
3. A file save makes the server re-import the design, rebuild with the current parameters, and push `rebuilt`. The client keeps its camera and selection.
4. A stale lock is re-resolved in the background, followed by a second `rebuilt`.

**Shared-element transition:** each row's id label and each callout chip carry `data-flip=<key>` (`node:A.P`, `feat:A.P.holes`). On toggle the panel snapshots the rects, renders the other view, then animates each key's first element from its old rect (FLIP, Web Animations API). New elements fade in. `model.transitionMap` is the unit-tested mapping.

Engine decisions behind all this are in `src/dipm/NOTES.md`, DECISIONS #32–#43 (iteration 1) and #44–#57 (iteration 2).

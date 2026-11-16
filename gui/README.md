# dipm GUI (iteration 1)

The browser front end for `python -m dipm serve <design.py>`. The spec is [`docs/gui.md`](../docs/gui.md). This shows a design live, makes its intent visible, and rebuilds whenever the design file is saved. Design files are still edited in a text editor.

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
npm run screenshots        # writes screenshots/*.png (light and dark)
```

The e2e tests start their own servers from `../.venv` (`e2e/server.ts`). Tests that write preferences or edit a design work on temp copies of the fixtures in `tests/fixtures/`. WebGL runs headless through SwiftShader (`playwright.config.ts`).

Python side: `.venv/bin/python -m pytest -q tests/test_server.py tests/test_connections.py`.

Fixtures for manual checks:

| Design | Shows |
|---|---|
| `examples/shelf_bracket.py` | The worked example: 9 intent nodes, 6 features, 4 interpretation slots, 0 questions, 0 notices |
| `tests/fixtures/question_channel.py` | A hole whose extent is a real **question** (answer buttons; the answer goes to `question_channel.prefs.json`) |
| `tests/fixtures/invariant_fail.py` | Slide `hole_u` over the rib (about 0.63–0.87): ΔH fails, the faces are tinted, the last good model stays greyed |
| `tests/fixtures/diagnostics.py` | Every connection diagnostic: no intent, intent with no feature, several intents, cross-intent dependency |

## Using it

- **Left panel, WHY ⇄ HOW.** WHY puts the intent tree first, with the features that realize each node as callouts. HOW puts the features first, in build order, with the intents each serves (and its *uses*) as callouts. Toggling animates shared elements (about 300 ms; instant under `prefers-reduced-motion`). **links** draws leader lines and *uses* arrows. **⤢** opens the expanded **Connections** view (intents ⇄ features ⇄ parameters) over the viewport. Esc closes it.
- **Hover** anything (a face, row, chip, parameter name) to light up everything connected to it in every view. **Click** to pin it; click again or press Esc to clear. Pinning a face shows its genealogy in the inspector and highlights its intent nodes; pinning a tree node highlights the faces it created and dims the rest.
- **Viewport:** drag to orbit, right-drag or shift-drag to pan, scroll to zoom. **fit / iso / front / side / top** (keys `f`, `0`, `1`, `3`, `7`). The axis triad is bottom left; the overall size in mm is bottom right.
- **Parameters:** a slider plus numeric field per ranged parameter, a dropdown per choice. Rebuilds are debounced at 140 ms. Build time is shown in the bar and the header (engine time · round trip).
- **Right panel:** the inspector; checks (validity, Euler, ΔH, ΔS, volume sign, references per feature; hover a cell for expected/got); interpretations (chosen reading and why, eliminated readings, sensitivity, `made_by`). **Questions** get one button per surviving reading. **Notices** are red-bordered and hatched, distinct from ordinary rows.
- Side panels resize (drag the inner edge) and collapse (‹ ›). Right-panel sections collapse. Below 1024 px the panels become tabs over the viewport. The theme toggle is in the header; the default follows the OS.

## Architecture

```
gui/src/
  main.tsx, App.tsx          layout: header · left | viewport | right · parameter bar; tabs below 1024 px
  store.ts                   app state (Preact signals): design, build, last good build, params, view,
                             hover/selection -> `lit` (computed), debounced requestBuild, answer
  api.ts                     fetch wrappers + WebSocket with reconnect
  types.ts                   JSON shapes served by src/dipm/server/serialize.py
  model.ts                   pure: WHY/HOW rows, transitionMap (shared elements), connected() (what lights up)
  mesh.ts                    pure: binary mesh decoder, triangle -> face id, edge segments
  viewer.ts                  three.js: shaded mesh with per-face vertex colours, edges, picking, views, triad, ghost
  components/                Header, IntentPanel (WHY⇄HOW, FLIP transition, links, diagnostics), Connections,
                             Viewport, RightPanel (Inspector, Checks, Interpretations), ParamBar
  styles.css, fonts.css      drawing-sheet tokens (light/dark) and the vendored fonts
public/fonts/                Archivo, IBM Plex Sans, IBM Plex Mono (woff2, SIL OFL 1.1; OFL-*.txt)
```

**Server** (`src/dipm/server/`):

- `app.py`: a `Session` per design file (load, build, answer, watch). Starlette routes:
  - `GET /api/design`
  - `POST /api/build {params}`
  - `GET /api/mesh/{id}`
  - `POST /api/answer {assumption_id, reading, scope?, note?}`
  - `WS /api/events`, which sends `hello`, `design-changed`, `rebuilt` and `design-error`
- `serialize.py`: a build becomes features (checks, refs, uses, parameter dependencies), the intent tree, diagnostics, interpretations, and the face/edge genealogy tables. Engine logic lives in `src/dipm/connections.py`.
- `mesh.py`: the binary layout is documented in its docstring. Face and edge ids are positions in `Build.faces()` and `Build.edges()`, the same ids the genealogy table uses.

**Data flow:**

1. A parameter change makes the client POST `/api/build`.
2. The response carries `mesh_id`. The client fetches `/api/mesh/{id}` (cached by id), decodes it, and paints per-face colours from hover, selection and failure state.
3. A file save makes the server re-import the design, rebuild with the current parameters, and push `rebuilt`. The client keeps its camera and selection.
4. A stale lock is re-resolved in the background, followed by a second `rebuilt`.

**Shared-element transition:** each row's id label and each callout chip carry `data-flip=<key>` (`node:A.P`, `feat:A.P.holes`). On toggle the panel snapshots the rects, renders the other view, then animates each key's first element from its old rect (FLIP, Web Animations API). New elements fade in. `model.transitionMap` is the unit-tested mapping.

Engine decisions behind all this are in `src/dipm/NOTES.md`, DECISIONS #32–#43.

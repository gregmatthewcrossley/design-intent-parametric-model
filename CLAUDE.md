# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

The project and its Python package are named **dipm**: *design imperatives → parametric models* (pronounced "dip-em"; alternative name in reserve: "follows"; plain `dip` is taken on PyPI, npm, crates.io and RubyGems). Early build phase. dipm is a **design environment**, not a model: the designer states verbal, qualitative **purposes** (each with a priority), and language models plus dipm's engine derive the relations ("hole centered on face") and build the feature tree. Terminology:
- "Imperatives" appears only in the name, in its everyday sense; the README explains the declarative/imperative inversion for programmers.
- The "intent tree" in code is the purpose tree.
- The DSL's "intent layer" is design intent in the CAD sense (architecture §1).
- "The model" means the plugged-in language model. The repo holds design docs, two feasibility spikes, and the v0 DSL core in `src/dipm/`. **The docs are the source of truth for decisions**; `src/dipm/NOTES.md` records implementation decisions and TODOs. Read the relevant one before proposing designs:

- `docs/architecture.md`: intent tree → deterministic DSL "solution"; checks and the determinism ladder (§4.1); rule/human packs; assumptions; passes (§5); idiomatic score (§6); worked shelf-bracket example (§8); open questions (§10).
- `docs/dsl.md`: core vs. intent layers, packages, reference rules (§3.4), invariants run on every solid (§5), engine/backends (§6), open risks (§7).
- `docs/user-experience.md`: standalone app, browser GUI served by a local engine, redline review, integrations.
- `docs/explore-further.md`: research threads, each with a status line.
- `reports/` + `research_notes/<same title>/`: deep-research outputs (a report plus the notes behind it).

Decisions marked *provisional* ("yes until proven otherwise") are working assumptions: OCCT as the kernel, an in-house constructive sketch solver, standalone for now. Don't treat them as settled.

**After any design discussion or experiment, update the affected docs** (and status lines in `explore-further.md`, plus the README index) so that decisions don't live only in chat.

## Commands

Python 3.12 virtualenv at the repo root (`.venv`, created with `uv`; Python 3.13/3.14 untested for OCP wheels):

```bash
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e .   # dipm + pinned build123d/OCP + pytest
```

DSL core (from the repo root):

```bash
.venv/bin/python -m pytest -q                                              # all core tests (~15–25 s)
.venv/bin/python -m pytest -q tests/test_bracket.py::test_edit_t_5_to_8   # single test
.venv/bin/python -m dipm build examples/shelf_bracket.py -p shelf_depth=300 --faces   # report + "why is this here?"
.venv/bin/python -m dipm stability examples/shelf_bracket.py              # sweep declared parameter ranges
.venv/bin/python -m dipm interpret examples/shelf_bracket.py              # re-resolve ambiguous readings → <design>.interpretations.json lock
.venv/bin/python -m dipm answer examples/shelf_bracket.py <assumption-id> <reading> --prefs prefs.json   # record a designer answer
.venv/bin/python -m dipm infer examples/shelf_bracket.py                  # re-infer assumed context + print orientation → <design>.resolution.json
```

The CLI exits 0 when the kernel invariants pass and no intent check fails, 1 on an invariant or reference failure, 2 on bad parameters, and 3 when the kernel passes but an intent check fails (the bracket currently exits 3: R.c1 load fails honestly). There is no bare PASS: status is tiered (kernel · intent checks run/not run/failing · margins).

Web GUI (needs Node ≥ 20; toolchain pinned to what runs on 20.12, see NOTES #40):

```bash
uv pip install --python .venv/bin/python -e ".[test]"   # server deps + test extras
(cd gui && npm ci && npm run build)                     # builds into src/dipm/server/static/ (gitignored)
.venv/bin/python -m dipm serve examples/shelf_bracket.py   # localhost only; opens the browser
.venv/bin/python -m dipm mcp examples/shelf_bracket.py     # stdio MCP server for Claude: proposes patches only, never writes design files
# register (don't run automatically; the user decides): claude mcp add dipm -- "$PWD/.venv/bin/python" -m dipm mcp "$PWD/examples/shelf_bracket.py"
(cd gui && npm test && npm run typecheck)               # vitest + tsc
(cd gui && npm run build && npm run e2e)                # Playwright acceptance tests (first run: npx playwright install chromium)
```

Spikes (run from the spike directory; modules import each other by bare name):

```bash
../../.venv/bin/python run_all.py                     # all three questions, ~45 s, writes results/*.json + run_all.log
../../.venv/bin/python -m pytest -q                   # 25 regression tests, ~2 s
../../.venv/bin/python -m pytest -q test_spike.py::test_genus_deltas   # single test
# spike 02 works the same way from spikes/02-operation-history/ (85 tests, ~6 s; run_all ~40 s)
```

No linter or build system is configured yet.

## Architecture in brief

- **Intent vs. solution.** Intent (learned, non-deterministic) decomposes into a tree of intent nodes. Each node carries checks, which flow down to its children and are re-verified on the way up. Solutions are DSL programs that must compile to **identical geometry every time, given a fully locked solution** (source + interpretations lock + prefs + pinned kernel/packages; architecture §7 lists where non-determinism still leaks in). The guiding principle is "determinize early": push checks toward exact, kernel-verifiable form as high in the tree as possible.
- **DSL: two layers.** A rich intent layer (`midpoint`, `hole`, `pattern`, …) is meant to lower to a small core grounded in solid-modelling theory (no explicit core IR yet; don't call it "proven" or "valid by construction"), and intent tags survive the lowering. User features, library solutions, rule packs, and human packs are all one artifact type, a *package*.
- **Engine.** OpenCascade via build123d/OCP sits behind a backend interface; Onshape FeatureScript is an export target; Manifold is a candidate for previews and interference checks. The sketch solver, reference layer, and checks are ours.

## DSL core code map

`src/dipm/` is laid out as follows; module ↔ dsl.md section mapping is in `NOTES.md` §1:
- **Program model:** `program.py` (`Design`, `Build`, `why()`).
- **Kernel boundary:** `kernel.py` (raw OCP; booleans always take a tool list; parallel BOP pinned off).
- **Reference layer:** `refs.py` (ledger, cardinality, policies, `edges_between`).
- **Checks:** `invariants.py` (validity, Euler parity, ΔH/ΔS/volume sign, signatures, BRep bytes). The Euler check solves for H, so it is only a parity test; the per-feature ΔH/ΔS contracts are the real check. The adjacency hashes are WL pre-filters, not canonical (dsl.md §5.4).
- **Core and trusted ops:** `ops.py`, each declaring roles, `Expect`, and failure classes.
- **Intent layer:** `intent_layer.py` (relations, fastener stand-ins, `Hole`).
- **Sketches:** `sketch.py` (named-point profiles with a winding branch tag; no solver yet).
- **Edit tests:** `stability.py`.
- **Connections:** `connections.py` (intent tree derivation, per-feature *uses* and parameter dependencies, diagnostics).
- **Server:** `server/` (Starlette API, deterministic mesh, file watching). Frontend source is in `gui/` (Preact + three.js); see `gui/README.md`.
- **Intent file and review:** `intent_store.py` is the only module that knows the `<design>.intent.yaml` format (ruamel round-trip, canonical, base-hash conflicts). `review.py` handles staleness (`<design>.review.json`). The MCP server and proposals live under `server/`, with proposals stored in a gitignored `.dipm/`.
- **Checks with margins (iteration 3):** `quantity.py` (values with ranges, worst-case propagation), `checks.py` (executable intent checks: R.c1 load hand calc, R.c2 overhang, R.c4 tool access; nominal/worst/limit/margin), `assess.py` (tiered status), `packs.py` (process/material/anchor data; **numbers are placeholders**, NOTES #58), `resolution.py` (`<design>.resolution.json`: machine-written assumed context and inferred print orientation; accepting writes the intent file via `intent_store`, nothing else does), `display.py` (CoreGraphics physical display size for `/api/display`; macOS only).
- **Purpose loop (iteration 4, docs/purpose-loop.md):** `impact.py` (old vs. new purpose tree → changed / invalidated / survives), `vocabulary.py` (the fixed set of computable check forms; bindings live in the intent file and are validated on proposal; unbindable checks are *descriptive, not run*), `components.py` (off-the-shelf parts as ranged envelopes). Purpose proposals change only the intent file; `evaluate` is the model's inner loop (budget 6 builds per alternative); alternatives are submitted 2–3 at a time. MCP tools added: `get_impact`, `get_check_vocabulary`, `get_components`, `propose_purposes`, `evaluate`, `propose_alternatives`. Pack entries carry a basis (e.g. mean ultimate), the source's own factor, and sourced/provisional/placeholder status; safety factors apply per protected quantity (4 anchors, 5 wood screws, 4 printed plastic sustained).
- **Automatic pickup (iteration 4b, purpose-loop.md §7):** `claude_runner.py` lets `dipm serve` launch headless Claude Code (`claude -p`, restricted to the dipm MCP tools) for queued requests, so `claude mcp add` is optional. Env: `DIPM_CLAUDE_BIN`, `DIPM_CLAUDE_AUTORUN`, `DIPM_CLAUDE_TIMEOUT`. **Tests never start the real `claude`**: they use the stub `tests/fixtures/fake_claude`. The `propose_*` MCP tools take an optional `requests` list. Iteration-4 tests use the frozen seed `tests/fixtures/rod_holder/`; `examples/rod_holder` holds the accepted V-saddle (p5).
- **Interpretations:** `interpret.py`. Ambiguous intent-word slots (hole extent, `centered_on`) list readings. Readings are eliminated by checks across sample points, then sensitivity is graded and a ranked default chosen. Results go to a lock file next to the design; preferences are kept in JSON. Spec: architecture §10 item 2.

Examples: `examples/shelf_bracket.*` (the regression fixture) and `examples/rod_holder.*` (the purpose-loop test case: the bracket with its root purpose changed to a fishing-rod holder).

Designs are pure functions of declared parameters, so tests re-build with new values instead of mutating state. Every feature carries intent tags (intent-tree node ids); keep them flowing through any new op so `Build.why()` can explain every face.

## Spike code map and OCCT gotchas

Spike 01: `topo.py` (counting, Euler check, signatures, serialization), `refs.py` (reference ledger with declared cardinality), and `bracket.py` (parametric shelf bracket built on **raw OCP**, so every operation's history object is available) are the reusable pieces. Spike 02 (`spikes/02-operation-history/`) imports these and extends the ledger (`Ledger2`: follow-`Generated`, merge detection) in `common.py`/`ops.py`. Its RESULTS.md §6 is the per-operation role vocabulary. In each spike the `q*_*.py` modules are the experiments and `RESULTS.md` holds verdicts and evidence.

Hard-won findings to respect in any future engine code:

- **Euler counting rule:** dedupe sub-shapes by TShape + location, ignoring orientation; **exclude degenerated edges** (sphere/cone poles *and* fillet corners); never dedupe by TShape alone (an extrude's end cap shares its start cap's TShape).
- **Genus deltas are computed per feature from how it interacts with existing geometry**, not fixed per feature type: a through-hole crossing another hole gives ΔH = +2.
- **History:** build123d's history API is too coarse; use OCP builders (`Generated`/`Modified`, `FirstShape`/`LastShape`). **`IsDeleted` is wrong after fillets and chamfers.** Fragment order after a split is arbitrary, so never reference fragments by position.
- **Draft/offset** report face images via `Generated` (not `Modified`) and drop edge history, so name edges with `edges_between`. **Full revolves**: `Generated` is empty for axis-perpendicular profile edges; fall back to `Revol().Shape(edge)`. Take sweep spine edges from the built wire (`MakeWire` copies edges).
- **Never pass possibly-overlapping tools as one compound** to a boolean: it silently cuts nothing yet passes BRepCheck and Euler. Use a tool list, and check ΔS and volume after every feature.
- **`BRepOffset` join mode is not byte-deterministic.** Compare fingerprints, not BRep bytes, for those ops.
- **Performance:** iterating OCP lists in Python costs ~2.5 ms each. Use `topo.occ_list` (copy-and-pop).
- **OCP 8 API:** maps live in `OCP.collections`; `TopoDS.Edge_s` → `TopoDS.Edge`, but other statics keep `_s` (e.g. `BRep_Tool.Degenerated_s`).
- **BRep text is the byte-comparison serialization** (byte-identical across builds on one machine; not a canonical form). STEP embeds a timestamp and a per-process product-name counter, so strip both before comparing.
- Determinism has only been verified on macOS/arm64 with OCCT 8.0.1. Cross-platform behavior is the main open risk.

Generated geometry (`*.brep`, `*.step`, `*.stl`, `*.3mf`) is gitignored: geometry is a build artifact, rebuilt from source.

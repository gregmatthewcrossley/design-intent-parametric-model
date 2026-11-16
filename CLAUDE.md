# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Design phase. The project aims to turn physical design intent (text, sketches, images, drawings, 3D geometry) into parametric CAD that encodes *intent as relations* ("hole centered on face"), not measured coordinates. Most of the repo is design documentation; the only code is a feasibility spike. **The docs are the source of truth for decisions.** Read the relevant one before proposing designs:

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
uv venv --python 3.12 .venv && uv pip install -r spikes/01-occt-feasibility/requirements.lock.txt
```

Spike 01 (run from `spikes/01-occt-feasibility/`; modules import each other by bare name):

```bash
../../.venv/bin/python run_all.py                     # all three questions, ~45 s, writes results/*.json + run_all.log
../../.venv/bin/python -m pytest -q                   # 25 regression tests, ~2 s
../../.venv/bin/python -m pytest -q test_spike.py::test_genus_deltas   # single test
```

No linter or build system is configured yet.

## Architecture in brief

- **Intent vs. solution.** Intent (learned, non-deterministic) decomposes into a tree of intent nodes. Each node carries checks, which flow down to its children and are re-verified on the way up. Solutions are DSL programs that must compile to **identical geometry every time**. The guiding principle is "determinize early": push checks toward exact, kernel-verifiable form as high in the tree as possible.
- **DSL: two layers.** A rich intent layer (`midpoint`, `hole`, `pattern`, …) lowers to a small, mathematically grounded core, and intent tags survive the lowering. User features, library solutions, rule packs, and human packs are all one artifact type, a *package*.
- **Engine.** OpenCascade via build123d/OCP sits behind a backend interface; Onshape FeatureScript is an export target; Manifold is a candidate for previews and interference checks. The sketch solver, reference layer, and checks are ours.

## Spike 01 code map and OCCT gotchas

`topo.py` (counting, Euler check, signatures, serialization), `refs.py` (reference ledger with declared cardinality), and `bracket.py` (parametric shelf bracket built on **raw OCP**, so every operation's history object is available) are the reusable pieces. The `q*_*.py` modules are the experiments; `RESULTS.md` holds verdicts and evidence.

Hard-won findings to respect in any future engine code:

- **Euler counting rule:** dedupe sub-shapes by TShape + location, ignoring orientation; **exclude degenerated edges** (sphere/cone poles *and* fillet corners); never dedupe by TShape alone (an extrude's end cap shares its start cap's TShape).
- **Genus deltas are computed per feature from how it interacts with existing geometry**, not fixed per feature type: a through-hole crossing another hole gives ΔH = +2.
- **History:** build123d's history API is too coarse; use OCP builders (`Generated`/`Modified`, `FirstShape`/`LastShape`). **`IsDeleted` is wrong after fillets.** Fragment order after a split is arbitrary, so never reference fragments by position.
- **Performance:** iterating OCP lists in Python costs ~2.5 ms each. Use `topo.occ_list` (copy-and-pop).
- **OCP 8 API:** maps live in `OCP.collections`; `TopoDS.Edge_s` → `TopoDS.Edge`, but other statics keep `_s` (e.g. `BRep_Tool.Degenerated_s`).
- **Canonical serialization is BRep text** (byte-identical across builds). STEP embeds a timestamp and a per-process product-name counter, so strip both before comparing.
- Determinism has only been verified on macOS/arm64 with OCCT 8.0.1. Cross-platform behavior is the main open risk.

Generated geometry (`*.brep`, `*.step`, `*.stl`, `*.3mf`) is gitignored: geometry is a build artifact, rebuilt from source.

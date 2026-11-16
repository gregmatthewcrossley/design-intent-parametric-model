# Design Intent → Parametric Model

A model that turns physical **design intent** into **parametric CAD** that captures that intent. Intent can come from text, sketches, images, drawings, or 3D geometry. A hole "in the middle" should be a midpoint relation, not a measured coordinate. The model is optimized, unapologetically, for the humans who will see, use, build, maintain, and edit what it makes.

*Personal project, kept general enough to be useful to others. Status: design phase (2026-11).*

## Documents

| Doc | What's in it |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | The core design: intent tree → deterministic DSL solution, checks and the determinism ladder, rule and human packs, assumptions, passes, idiomatic score, worked shelf-bracket example |
| [`docs/dsl.md`](docs/dsl.md) | DSL and engine: core vs. intent layers, packages, references, invariants, solver vs. kernel, backends |
| [`docs/user-experience.md`](docs/user-experience.md) | How a designer uses it: versioning, GUI, interfaces to Onshape, slicers, CAM |
| [`docs/explore-further.md`](docs/explore-further.md) | Research and inspiration threads still to pull on |
| [`reports/Parametric CAD generation survey.md`](reports/Parametric%20CAD%20generation%20survey.md) | Literature and open-source survey of AI → parametric CAD (2026) |
| [`reports/DSL mathematical foundations.md`](reports/DSL%20mathematical%20foundations.md) | Primary-source review: Euler operators, B-rep topology, solid-modeling theory, geometry axioms, persistent naming |
| `research_notes/` | Raw notes behind each report |
| [`spikes/01-occt-feasibility/RESULTS.md`](spikes/01-occt-feasibility/RESULTS.md) | First code: OpenCascade feasibility (Euler check, history-based references, determinism). All three: yes / mostly yes |

## Key ideas, in one breath

The project is built around a split between **intent** (reasoned about, learned, not deterministic) and **solution** (a DSL that always builds the same geometry).

- **Decomposition:** intents decompose into a tree of sub-intents.
- **Checks:** every intent node carries checks that flow down the tree, and are pushed toward deterministic form **as early as possible**.
- **Packages:** world knowledge, human-factors knowledge, library solutions, and user features are all one kind of artifact, a package.
- **Assumptions:** they are explicit and reviewable.
- **Passes:** multiple passes, including a virtual-prototype walkthrough, refine solutions until a computable idiomatic score is met.
- **Engine:** OpenCascade is the kernel, behind a backend interface. The project owns the sketch solver, the reference layer, and the checks. This is provisional: yes until proven otherwise.
- **Product shape:** standalone for now, with Onshape as an export target. The browser is the primary GUI, served by a local engine, and supports redline (red-marker) review. WebAssembly is the planned sandbox for shared packages.

## License

[Apache License 2.0](LICENSE).

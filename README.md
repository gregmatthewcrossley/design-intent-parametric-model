# dipm: design imperatives → parametric models

*dipm is pronounced "dip-em". (The alternative name kept in reserve: **follows**, after Louis Sullivan's "form follows function".)*

**dipm is a design environment where you state what a part is for, and AI builds the parametric model.** In CAD, "capture design intent" has come to mean *don't draw and dimension; use features and relations instead*. That is one rung above raw geometry, but still geometric and numeric. **dipm aims one rung higher:** you work in **purposes**, stated in your own words and each with a priority ("must hold a shelf to a wall", "should be easy to install alone", "nice if it feels calm"). Language models and dipm's engine derive the relations and build the feature tree, checking every step.

dipm is **not a model**. The language model plugs into it (today a frontier model such as Claude, over MCP). dipm is the environment around it, much as an IDE is for code:
- a **language** for purposes and relations;
- a **verifying compiler** to parametric CAD (OpenCascade);
- the **harness** an AI agent works inside: tools, checks, proposals the designer reviews;
- an **inspector** that answers "why is this here?" for every face.

| Level | You say | Example | Where it lives in dipm |
|---|---|---|---|
| **Purposes** (verbal, qualitative, prioritized) | "It must… / should… / it'd be nice if…" | Hold a shelf to a wall; install alone; feel calm | The purpose tree, its checks, and packs |
| **Design intent** (CAD sense: relations) | "Keep this centered" | `centered_on(mount_face)`, symmetric, through the plate | The DSL's intent layer |
| **Geometry** (dimensions) | "Put it at 37.5" | `x = 37.5` | The kernel |

**What's new.** Qualitative intent has been captured before: design-rationale tools (IBIS, QOC), function–behavior–structure models, and knowledge-based engineering rules. But that happened in the pre-LLM era, and largely as *extra* work a designer did **after** defining the quantitative, geometric design intent by hand, which is why those tools went unmaintained. dipm flips the order. The designer states purposes; language models and the computer derive the relations and build the feature tree, checking every step. Purposes come first and drive the geometry, rather than being documentation added after it (see [`docs/architecture.md` §1.1](docs/architecture.md#11-prior-art-and-whats-actually-new)).

Purposes can come from text, sketches, images, drawings, or 3D geometry. dipm is optimized, unapologetically, for the humans who will see, use, build, maintain, and edit what it makes.

### A note for programmers: why "imperatives", when the purposes are declarative?

In programming terms, the naming is inverted, and deliberately so. A designer's purposes ("must hold a shelf", "should install with one hand") say *what*, not *how*, so they are the most **declarative** layer in dipm. The most **imperative** artifact is the output: a CAD feature tree is an ordered sequence of steps (sketch, extrude, cut, fillet), and its order matters. **You write what it's for; dipm writes the imperative program that builds it.**

The name uses "imperatives" in its everyday and design sense, not the programming one: things a product must, should, or would ideally do, stated in the designer's voice, as in a design brief. It also keeps the name clear of "design intent", which in CAD already means relations and constraints (the middle row of the table above). The working term in the docs is **purposes** (the GUI and code still say "intent" and will follow). "Imperatives" appears only in the name.

*Personal project, kept general enough to be useful to others. Status: early build phase (2026-11). Design docs, two OCCT feasibility spikes, a v0 DSL core that builds the worked shelf-bracket example with full invariant checking, and a browser GUI with editable purposes and a Claude proposal-review loop over MCP.*

## Documents

| Doc | What's in it |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | The core design: intent tree → deterministic DSL solution, checks and the determinism ladder, rule and human packs, assumptions, passes, idiomatic score, worked shelf-bracket example |
| [`docs/dsl.md`](docs/dsl.md) | DSL and engine: core vs. intent layers, packages, references, invariants, solver vs. kernel, backends |
| [`docs/tolerance-uncertainty.md`](docs/tolerance-uncertainty.md) | Tolerance, uncertainty, guesses and scale: engine model, visualization, scale cues, order of work |
| [`reports/Fresh eyes review.md`](reports/Fresh%20eyes%20review.md) | Independent expert review (65 items) and the author's [response](reports/Fresh%20eyes%20review.response.md) |
| [`docs/review-response.md`](docs/review-response.md) | Action plan from the fresh-eyes review |
| [`docs/gui.md`](docs/gui.md) | Web GUI iteration 1 spec: scope, layout, style, API, acceptance criteria |
| [`gui/README.md`](gui/README.md) | The GUI as built: build, run, develop, test; `python -m dipm serve examples/shelf_bracket.py` |
| [`docs/user-experience.md`](docs/user-experience.md) | How a designer uses it: versioning, GUI, interfaces to Onshape, slicers, CAM |
| [`docs/explore-further.md`](docs/explore-further.md) | Research and inspiration threads still to pull on |
| [`reports/Parametric CAD generation survey.md`](reports/Parametric%20CAD%20generation%20survey.md) | Literature and open-source survey of AI → parametric CAD (2026) |
| [`reports/DSL mathematical foundations.md`](reports/DSL%20mathematical%20foundations.md) | Primary-source review: Euler operators, B-rep topology, solid-modeling theory, geometry axioms, persistent naming |
| `research_notes/` | Raw notes behind each report |
| [`src/dipm/NOTES.md`](src/dipm/NOTES.md) | v0 DSL core (`src/dipm`): architecture, how to run, implementation DECISIONS, TODOs. Example: [`examples/shelf_bracket.py`](examples/shelf_bracket.py) |
| [`spikes/01-occt-feasibility/RESULTS.md`](spikes/01-occt-feasibility/RESULTS.md) | First code: OpenCascade feasibility (Euler check, history-based references, determinism). All three: yes / mostly yes |
| [`spikes/02-operation-history/RESULTS.md`](spikes/02-operation-history/RESULTS.md) | Reference history, invariants, and determinism for revolve, chamfer, shell, loft, sweep, draft, pattern, mirror, `clean()`; per-operation role vocabulary |

## Key ideas, in one breath

The project is built around a split between **intent** (reasoned about, learned, not deterministic) and **solution** (a DSL that builds the same geometry every time once fully locked: source, interpretations lock, prefs, and pinned kernel and packages; see [architecture §7](docs/architecture.md#7-determinism-requirements)).

- **Decomposition:** intents decompose into a tree of sub-intents.
- **Checks:** every intent node carries checks that flow down the tree, and are pushed toward deterministic form **as early as possible**.
- **Packages:** world knowledge, human-factors knowledge, library solutions, and user features are all one kind of artifact, a package.
- **Assumptions:** they are explicit and reviewable.
- **Passes:** multiple passes, including a virtual-prototype walkthrough, refine solutions until a computable idiomatic score is met.
- **Engine:** OpenCascade is the kernel, behind a backend interface. The project owns the sketch solver, the reference layer, and the checks. This is provisional: yes until proven otherwise.
- **Prior art:** most of the architecture builds on semantic feature modelling, knowledge-based engineering, requirement allocation and design-rationale systems. What is new is narrower: interpretations with sensitivity-gated questions, per-feature topological contracts, and an edit-stability benchmark. See [architecture §1.1](docs/architecture.md#11-prior-art-and-whats-actually-new).
- **Product shape:** standalone for now, with Onshape as an export target. The browser is the primary GUI, served by a local engine, and supports redline (red-marker) review. WebAssembly is the planned sandbox for shared packages.

## License

[Apache License 2.0](LICENSE).

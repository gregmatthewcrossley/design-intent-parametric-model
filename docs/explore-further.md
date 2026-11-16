# To explore further

A running list of threads worth pulling on. Each entry says why it matters, what to find out, and where to start. Design-level open questions live in [`architecture.md` §10](architecture.md#10-open-questions); this list is for research and inspiration.

*Started 2026-11-15.*

---

## 1. Mathematical foundations of the DSL — primary sources, with a focus on B-rep topology and Euler operators

> **Status (2026-11-15):** first research pass done. See [`reports/DSL mathematical foundations.md`](../reports/DSL%20mathematical%20foundations.md). Open follow-ups: read Mäntylä (1984) for the exact completeness theorem; calibrate the Euler–Poincaré check on OpenCascade primitives (seam and degenerate edges).
>
> **Corrections (2026-11-16, fresh-eyes review):** Laman covers 2D bar-joint (distance-only) frameworks, not CAD sketches with angles, tangency and incidence; see [`dsl.md` §5.5](dsl.md#5-invariants-checked-on-every-compiled-solution). The Euler check as implemented is a parity test; the per-feature ΔH/ΔS contracts do the real work. r-set validity does not imply manifoldness. Cartan–Dieudonné and PGA have no operational role yet. See the errata at the top of the report.

**Why.** The DSL plan has a small, theoretically grounded *core* layer under a rich *intent* layer. The minimality and completeness results cited in conversation (Mohr–Mascheroni, Poncelet–Steiner, Tarski/Pieri, Laman, Cartan–Dieudonné, Requicha's r-sets, Euler operators) came from background knowledge, not a research pass. They need checking against primary sources before the core is built on them.

**Main focus: B-rep topology and Euler operators.** These are the closest thing to a proven minimal, orthogonal, complete operator set in solid modeling, but for manifold *topology* only, not for designs or geometry.

- What exactly do they guarantee: completeness (every valid topology reachable), independence, closure under inverses? For which class of solids (manifold only? with holes/genus? with inner loops)?
- The Euler–Poincaré formula and its variables (V, E, F, loops, shells, genus): how the five-operator basis follows from it, and what changes for non-manifold topology (e.g. Weiler's radial-edge structure).
- What they offer us *in practice*:
  - as a **validity invariant** checked on every compiled solution
  - as a **topological description** for comparing solutions, deduplicating data, and defining brevity (counts and WL hashes are pre-filters, not canonical; exact equality needs graph canonical labelling such as nauty)
  - as the substrate for **persistent naming**, i.e. stable references to faces and edges across rebuilds
  - as a possible **training or tokenization target**, e.g. for the reverse-engineering (mesh → history) direction
- How commercial kernels (Parasolid, ACIS, OpenCascade) use Euler operators or their equivalents internally today.
- Their limits: geometry vs. topology. Euler operators guarantee consistent topology, not that the geometry is valid (e.g. it can still self-intersect).

**Also verify:**
- **Requicha (1980):** r-sets, regularized Booleans, and the properties of a representation (validity, completeness, uniqueness).
- **Tarski, Pieri and Gupta:** minimal primitives and independence for Euclidean geometry.
- **Laman's theorem:** 2D rigidity of bar-joint (distance-only) frameworks, the status of the 3D case, and what modern geometric constraint solvers actually rely on (answer so far: decomposition, DOF analysis and numeric rank checks, not Laman; see [`dsl.md` §5.5](dsl.md#5-invariants-checked-on-every-compiled-solution)).
- **Cartan–Dieudonné:** reflections generating all isometries, and whether that suggests an elegant transform/pattern core.
- **Mohr–Mascheroni and Poncelet–Steiner:** probably inspiration only.
- **F-rep / Rvachev R-functions:** as an alternative core, and what we'd lose for B-rep export.

**Start with:**
- Braid, Hillyard & Stroud (1978), *Stepwise construction of polyhedra in geometric modelling*
- Mäntylä, *An Introduction to Solid Modeling* (1988)
- Baumgart's winged-edge papers (1970s)
- Weiler's radial-edge thesis (1986)
- Requicha, *Representations for Rigid Solids*, ACM Computing Surveys (1980)
- Tarski & Givant, *Tarski's System of Geometry* (1999)
- Laman (1970)
- Pasko et al. (1995) on F-rep
- The OpenCascade documentation on its topology data model

---

## 2. Programming-language parallels: small core, rich surface

> **Status (2026-11-15):** two-layer structure (core + intent layer, with intent tags preserved through lowering) adopted in [`dsl.md` §1](dsl.md#1-two-layers-one-meaning). Deeper research not yet done.

**Why.** Successful languages separate a tiny, rigorous core from a rich, human-friendly surface: Scheme's derived forms, Rust's lowering to a small intermediate representation. That matches the planned core/intent split, and principle 6 (optimized for humans, as Ruby is for programmers). There is likely much more to borrow.

**Questions:**
- **Core and derived forms.** How do Scheme (R7RS derived expression types, `syntax-rules`), Racket ("languages as libraries", `#lang`) and Lisp macros define new constructs that are first-class yet precisely specified?
- **Lowering pipelines.** Rust (HIR → MIR), GHC (Haskell → Core, a tiny typed lambda calculus), LLVM IR, WebAssembly. What makes a good intermediate language? How do they keep source-level meaning (spans, names) through lowering? This is our "intent tags survive reduction" problem.
- **Normal forms and equivalence.** Canonical forms, term rewriting, e-graphs (egg), and their use for equivalence checking and optimization. These may power the consolidation and idiom-refactor passes.
- **Determinism and reproducibility.** Lockfiles, Nix-style hermetic builds, and pinned toolchains as models for pinning kernels and packs.
- **Human-optimized design.** Ruby's philosophy (Matz on programmer happiness), Elm's error messages, Python's "one obvious way to do it". What would the CAD equivalents be?
- **Contracts and refinement types.** Design-by-contract (Eiffel), refinement and dependent types (Liquid Haskell, F*, Dafny). These are formal versions of "checks flow down the tree" and "assumptions".
- **Program synthesis.** DreamCoder-style library learning, sketch-based synthesis, and how synthesizers use a small core language.
- **The Turing tar-pit.** Perlis's epigrams and other writing on the gap between minimal and usable.

**Start with:**
- R7RS (chapter 7, derived expression types)
- The Racket "Languages as Libraries" paper
- The Rust compiler dev guide (HIR/MIR)
- GHC Core documentation and the System FC papers
- The egg / e-graphs papers
- Matz interviews on Ruby's design
- Perlis, *Epigrams on Programming*

---

## 3. Extensibility the Onshape way: user features as first-class citizens

> **Status (2026-11-15):** direction adopted. User features, library solutions, rule packs, and human packs are all one artifact type, a *package*. See [`dsl.md` §2](dsl.md#2-extensibility-one-kind-of-artifact). The questions below are still open.

**Why.** In Onshape, FeatureScript is the language Onshape's own built-in features (extrude, fillet, …) are written in, not a scripting layer added on top. Users write custom features in the same language, and those features sit in the feature tree exactly like built-in ones. We want the same for this project:
- a set of basic features and operations
- user-written plug-in features that live as scripts alongside the tree, with no distinction between "core" and "custom"

This connects to the rule/human packs, the solution library (architecture §3.3), and the intent layer of the DSL.

**Questions:**
- **How FeatureScript works.** The structure of a feature definition (preconditions, parameter types, the feature body), its query system (`qCreatedBy`, etc.) for stable topology references, and how the standard library is published and versioned. Is each document pinned to a specific standard-library version?
- **Custom features.** How they participate in rebuilds, regeneration, and the feature tree's UI, i.e. parameters and dialogs generated from the definition.
- **Sharing.** How custom features are shared, versioned, and trusted across documents and users. Is there a marketplace or library model, and what were the lessons?
- **Limits.** What FeatureScript can't do, and its performance and sandboxing constraints.
- **Mapping to our architecture.** A plug-in feature is a user-defined intent-layer word, defined in terms of core operations, with its own checks, assumptions and intent tags. What does a "feature package" look like? Could rule and human packs, library solutions and user features all be one kind of artifact?
- **Training implications.** Can the model learn to *use* new user-defined features from their definitions and documentation alone, without retraining? Can it *propose* new features, as library learning does?
- **Prior art elsewhere.** SolidWorks API macros and add-ins (bolted on, for contrast), Fusion 360 add-ins, Grasshopper components, CadQuery and build123d plugins, Zoo KCL modules, OpenSCAD libraries.

**Start with:**
- The Onshape FeatureScript documentation and standard-library source (a public Onshape document)
- Onshape developer blog posts on FeatureScript's design
- The FeatureScript paper or talks by its designers, if any exist
- Community custom-feature repositories

---

## 4. WASM: engine in the browser, sandbox everywhere

**Why.** The browser is the primary GUI (see [`user-experience.md` §3](user-experience.md#3-gui)), and WASM is the planned package sandbox (see [`dsl.md` §2](dsl.md#2-extensibility-one-kind-of-artifact)). Running the *engine itself* as WASM could also give **cross-machine determinism**. WASM arithmetic is specified exactly (apart from edge cases like NaN bit patterns and relaxed-SIMD), so one pinned WASM build of the kernel could produce identical geometry everywhere. Native builds can differ by compiler and CPU (e.g. fused multiply-add).

**Questions:**
- **OCCT in WASM.** How mature is opencascade.js and OCCT's own Emscripten build? Size, speed vs. native, memory limits (wasm32 4 GB; memory64 status), threading.
- **Determinism.** Does a WASM OCCT build actually produce bit-identical BRep output across browsers and OSes? Compare against the native spike results (`spikes/01-occt-feasibility`).
- **Python in the browser.** Can Pyodide run build123d/OCP? Or should the long-term engine core be written in a language that compiles to both native and WASM (C++, Rust)?
- **Other components.** WASM builds of Manifold and planegcs, and their maturity.
- **Package sandbox.** wasmtime (server) vs. browser execution; the host API exposed to packages; what language package authors write in (a FeatureScript-like DSL compiled to WASM? Python via a WASM interpreter?).
- **Hybrid split.** Which parts run in the browser (viewer, interactive rebuilds, redline raycasting) vs. the local engine (model calls, ML, heavy analysis)?

**Start with:** the opencascade.js docs and repo; OCCT's WebAssembly build docs; the WebAssembly spec's determinism notes; the Pyodide package list; the manifold-3d npm package; the wasmtime docs.


---

## 5. Prior art to read properly: semantic features, valid ranges, KBE, design rationale

> **Status (2026-11-16):** citations collected and checked; papers not yet read. Added after the fresh-eyes review (NOV-01..03, ISS-05). The list, and what is and isn't new in dipm, is in [`architecture.md` §1.1](architecture.md#11-prior-art-and-whats-actually-new).

**Why.** Much of dipm's architecture re-derives semantic feature modelling, valid-parameter-range computation, knowledge-based engineering, requirement allocation and design-rationale systems. Those fields have known failure modes (rule-base maintenance cost, rationale capture cost, Grudin's asymmetry) that dipm needs answers to, not just citations.

**Questions:**
- How exactly do Bidarra & Bronsvoort specify and maintain feature validity, and how does that differ from dipm's per-feature ΔH/ΔS/volume contracts?
- Can the Hoffmann & Kim and Joan-Arinyo valid-range methods replace the stability harness's 9 sample points for some constraint classes?
- What do the Company / Contero / Camba / Otey rubrics measure, and can they serve as an external yardstick for the idiomatic score?
- Why did KBE rule bases and IBIS-style rationale tools stall, and what would make dipm's packs and intent trees different in practice?

**Start with:** Bidarra & Bronsvoort (2000); Hoffmann & Kim (2001); La Rocca (2012); Grudin (1988); Bracewell et al. (2009). Full references in architecture §1.1.

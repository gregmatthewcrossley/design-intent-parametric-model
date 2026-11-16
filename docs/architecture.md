# Architecture: Purposes → Solution

*Status: working draft, 2026-11-15. Concepts are stable enough to build against; all syntax (YAML schemas, DSL) is illustrative and provisional.*

Background research: [`reports/Parametric CAD generation survey.md`](../reports/Parametric%20CAD%20generation%20survey.md), [`reports/DSL mathematical foundations.md`](../reports/DSL%20mathematical%20foundations.md)

Related: [`dsl.md`](dsl.md) (DSL and engine), [`user-experience.md`](user-experience.md) (how designers use it), [`explore-further.md`](explore-further.md)

---

## 1. Purpose and principles

**dipm: design imperatives → parametric models.** **dipm is a design environment where you state what a part is for, and AI builds the parametric model.** In CAD, "capture design intent" has come to mean *don't draw and dimension; use features and relations instead*. That is one rung above raw geometry, but still geometric and numeric. **dipm aims one rung higher:** you work in **purposes**, stated in your own words and each with a priority ("must hold a shelf to a wall", "should be easy to install alone", "nice if it feels calm"). Language models and dipm's engine derive the relations and build the feature tree, checking every step.

**Terminology (2026-11-16).** dipm works across three levels: Rasmussen's abstraction hierarchy, or Gero's function–behavior–structure.
- **Purposes:** verbal, qualitative statements of what the part is for, each with a priority (must / should / nice to have). The project name calls them "imperatives" in the everyday sense; see the README's note for programmers on why that word is not the programming-language one.
- **Design intent**, in its established CAD sense: relations, features, and constraints.
- **Geometry.**

What this document calls the **intent tree** is the **purpose tree**. dipm itself is a *design environment*, not a model: "the model" in these docs always means the language model plugged into it, and "parametric model" means the CAD output. "Intent" in the DSL (`intent_layer.py`, intent words such as `centered_on`) means design intent in the CAD sense. File and code names (`<design>.intent.yaml`, `intent_store.py`, `IntentTag`) still use "intent" for the purpose tree; renaming them is an open question (§10).

Purposes can be expressed as text, sketches, drawings, or 3D geometry, and become **parametric CAD models whose relations serve those purposes**, not merely reproduce a shape.

Six principles drive everything below:

1. **Intent is relational, not numeric.** "Put the hole in the middle" is a *midpoint relation*, not `x = length / 2` measured from today's geometry. A model that produces the right shape with the wrong relations has failed, even though shape metrics (Chamfer distance, IoU) cannot tell.
2. **Solutions are deterministic, once fully locked.** A solution is a program in a DSL of known, atomic geometric operations. A *fully locked* solution is the DSL source plus its interpretations lock, the designer's prefs, and pinned kernel and package versions. A fully locked solution compiles to the same geometry every time (on one platform so far; §7). The DSL source alone does not: without a lock, interpretation resolution picks readings (§10.2), and that choice can depend on the previous lock it starts from. Non-determinism is meant to live on the intent side, but today it also leaks into the build in a few named places, listed in §7.
3. **Intent decomposes.** Large intents are broken into smaller supporting intents until each is small enough to solve directly. Solutions compose back up into a single program.
4. **Quality must be computable.** "Idiomatic," "correct," and "done" are defined by checks and scores a machine can evaluate. Anything we cannot measure, we cannot iterate toward or train on — and loops that optimize unmeasured qualities tend to game whatever *is* measured.
5. **Determinize early.** The model's foundational motivation: decompose non-deterministic intents and checks into deterministic ones *as early in the tree as possible*. Every check should be pushed as close to rung 1 of the determinism ladder (§4.1) as it will go, at the node where it enters. The less judgment that survives to the leaves, the more of the design is verifiable, repeatable, and trainable.
6. **Optimized for humans, unapologetically.** As Ruby is optimized for programmer happiness, dipm optimizes for the people who will look at, use, understand, assemble, maintain, and later edit what it makes. Visual harmony is necessary but not sufficient; a balanced panel no newcomer can operate has failed. Human factors get the same treatment as everything else: packaged knowledge, pushed toward deterministic checks (§4.7).

### 1.1 Prior art and what's actually new

*Added 2026-11-16 after the fresh-eyes review (NOV-01..04, ISS-05). Citations checked against publisher or indexing records on that date unless marked otherwise.*

Most of the conceptual architecture below re-derives older work. It is listed here so the docs stop implying otherwise, and so the known failure modes of that work are on the table.

| dipm idea | Prior art | What that work already does |
|---|---|---|
| Features carry validity constraints, checked after every edit (§4, [`dsl.md` §4.3](dsl.md#43-trusted-primitives)) | **Semantic feature modelling:** Bidarra & Bronsvoort, "Semantic feature modelling", *Computer-Aided Design* 32(3):201–225, 2000. Background: Shah & Mäntylä, *Parametric and Feature-Based CAD/CAM*, Wiley, 1995 | Feature semantics specified as constraints and maintained through every modelling operation. This is the closest prior art to per-feature contracts and intent checks |
| Stability harness: sweep parameters, check the model still regenerates the same way (§6, [`dsl.md` §5.7](dsl.md#5-invariants-checked-on-every-compiled-solution)) | **Valid parameter ranges:** Hoffmann & Kim, "Towards valid parametric CAD models", *Computer-Aided Design* 33(1):81–90, 2001. Joan-Arinyo & Mata, "Applying constructive geometric constraint solvers to geometric problems with interval parameters", *Nonlinear Analysis* 47(1):213–224, 2001, and later Hidalgo & Joan-Arinyo work on h-graphs | Computes the parameter intervals within which a model regenerates, for some constraint classes. dipm samples about 9 points of a space this work computes exactly |
| Edit stability and "relations, not literals" as a quality measure (§6) | **CAD-education design-intent rubrics:** Company et al. (co-author list not checked), "Approach for developing coordinated rubrics to convey quality criteria in MCAD training", *Computer-Aided Design* 63:101–117, 2015. Otey, Company, Contero & Camba, "Revisiting the design intent concept in the context of mechanical CAD education", *CAD&A* 15(1):47–60, 2018. Otey et al., "Assessment of parametric assembly models based on CAD quality dimensions", *CAD&A* 16(4):628–653, 2019 | Rubrics that score models on validity, completeness, consistency, conciseness, clarity and design intent, where intent is largely "behaves as expected when altered" |
| Rule packs, feature-choice rules, the idiomatic score (§4.6, §4.7, §6) | **Knowledge-based engineering:** ICAD (1980s), Siemens NX Knowledge Fusion, CATIA Knowledgeware, Creo Behavioral Modeling; review in La Rocca, "Knowledge based engineering: Between AI and CAD", *Advanced Engineering Informatics* 26(2):159–179, 2012. Also DFM/DFA checkers and CAD model-quality checkers (Q-Checker, CADIQ, VDA 4955, SASIG PDQ; product and guideline names, not checked individually) | Rule bases behind geometry, and model-quality metrics much like "no unexplained literals" and "tree depth". KBE's documented lesson: rule bases are expensive to keep up and tend to end up owned by one person |
| Check flow-down: pass / allocate / translate / derive (§4.2) | **Systems-engineering requirement allocation and budgets** (e.g. the INCOSE *Systems Engineering Handbook*; mass and error budgets) | Standard requirement decomposition, allocation to subsystems, and re-verification at integration |
| Intent → checks → solution | **Gero's Function–Behaviour–Structure:** Gero, "Design prototypes: a knowledge representation schema for design", *AI Magazine* 11(4):26–36, 1990 | Function, expected behaviour, and structure as separate layers, with behaviour derived from structure and compared against expectations |
| "The tree is the design rationale" (§3.4) | **Design-rationale systems:** IBIS (Kunz & Rittel, "Issues as elements of information systems", IURD Working Paper 131, 1970); gIBIS (Conklin & Begeman, *ACM TOIS* 6(4):303–331, 1988); QOC (MacLean, Young, Bellotti & Moran, *Human–Computer Interaction* 6(3–4):201–250, 1991); DRed (Bracewell, Wallace, Moss & Knott, "Capturing design rationale", *Computer-Aided Design* 41:173–186, 2009) | Structured capture of issues, options and arguments. They mostly failed on capture cost, and on **Grudin's asymmetry** (Grudin, "Why CSCW applications fail", CSCW 1988, pp. 85–93): the person who has to do the extra work is not the person who benefits |

**What is actually new, narrowly stated.** The review found three concrete things it could not match to prior art. They are smaller than the rest of this document suggests, and they are what dipm should lead with:

1. **Interpretations** (§10.2, `src/dipm/interpret.py`). An intent word declares its candidate readings. Readings are eliminated by build checks across the parameter range, and the designer is asked only when the survivors give different geometry. The nearest analogue is disambiguation in programming by example (Mayer et al., "User interaction models for disambiguation in programming by example", UIST 2015), not anything known in CAD.
2. **Per-feature topological contracts.** Expected ΔH, ΔS and volume sign are computed from how each feature interacts with the existing geometry, not fixed per feature type ([`dsl.md` §5.3](dsl.md#5-invariants-checked-on-every-compiled-solution)).
3. **An edit-stability benchmark** over an open, kernel-neutral DSL.

**The primary claim: purposes first, geometry derived.** Qualitative intent has been captured before (the design-rationale, FBS and KBE work in the table). That was done in the pre-LLM era, and largely as *additional* work the designer did **after** defining the quantitative, geometric design intent by hand. Grudin's cost asymmetry explains why it decayed. dipm reverses the order: the designer works in purposes, and language models plus the engine derive the relations and build the feature tree, verified at every step. The three items above are the concrete mechanisms that make that reversal checkable. This claim is a hypothesis to prove, not a result: no model is wired in yet (ISS-04).

The rest (intent trees, flow-down, packs, executable rationale) is a recombination. Its claim to be different is that the rationale is *executable* and bound to kernel history, and that a language model may absorb the authoring cost that sank KBE and design-rationale tools. Neither claim has evidence in this repo yet. There may also be unpublished industrial equivalents of all three items above.

**"Nobody measures intent" is too broad.** The survey's heading says so ([`reports/Parametric CAD generation survey.md`](../reports/Parametric%20CAD%20generation%20survey.md)). It holds for the recent ML literature on CAD generation, whose benchmarks measure shape similarity. It does not hold for CAD research and education: the rubrics and valid-range work above measure exactly that.

---

## 2. Core concepts

```
              ┌────────────────────────────── INTENT side (learned, non-deterministic)
              │   Intent nodes, decomposition, check allocation, plan review
              │
  intent ─────┤
              │
              └────────────────────────────── SOLUTION side (deterministic once fully locked, §7)
                  DSL program → compiler → CAD kernel → B-rep geometry
                                                  │
                  checks evaluated against ◄──────┘
```

### 2.1 Intent node

An intent node is one unit of design purpose. It holds:

| Field | Meaning |
|---|---|
| `id` | Stable identifier (e.g. `A.2`) |
| `statement` | Natural-language intent — *why* this exists |
| `receives` | Named references from the parent (faces, edges, datums, parameters) it may build on |
| `exports` | Named references it promises to provide to siblings / parent |
| `checks` | Verifiable acceptance criteria (§4) |
| `children` | Sub-intents, *or* — if a leaf — a `solution` |
| `solution` | A DSL fragment written against `receives` (leaves only, and parents for their skeleton) |

```yaml
# illustrative schema
id: A.1
statement: "Clearance hole for a wall screw"
receives: [mount_face, screw]
exports: [hole_axis]
checks: [A.1.c1, A.1.c2, A.1.c3]
solution: |
  hole(on=mount_face, at=layout.points[0], spec=clearance(screw), extent=THROUGH)
```

### 2.2 Solution (DSL)

The DSL is a small, typed language of atomic operations (sketch, constrain, extrude, revolve, hole, fillet, chamfer, shell, pattern, mirror, boolean, …) with three non-negotiable properties:

- **Relations are first-class.** `midpoint`, `symmetric`, `equal`, `concentric`, `distribute`, `through_all`, `up_to(face)` are vocabulary, not afterthoughts. Literal numbers appear only for true design parameters.
- **Geometry is referenced by query, never by index.** `plate.face(normal=-Y)` or a named export like `mount_face`, never `face[17]`. This is what makes rebuilds stable (the "topological naming problem").
- **It compiles deterministically**, once fully locked (§7), to a pinned kernel (initial target: build123d/CadQuery on OpenCascade; FeatureScript as a later export target).
- **It has two layers.** A rich *intent layer* (`midpoint`, `hole`, `pattern`, `gusset`) is meant to lower to a small *core layer* grounded in solid-modelling theory, and intent tags survive the lowering. v0 has no explicit core IR yet, and most real features (fillet, chamfer, shell, draft) sit outside the theory as runtime-checked trusted primitives ([`dsl.md` §4.3](dsl.md#43-trusted-primitives)). Sketch steps carry explicit **branch tags** so constraints can't "flip". References are resolved through kernel history and declare their cardinality. Full design: [`dsl.md`](dsl.md).

### 2.3 References and interfaces

Children cannot be solved in isolation and then glued together: a hole needs a face to sit on, and "sensible location" is relative to that face's edges. So solving is **skeleton-first, top-down; composition is bottom-up**:

1. A parent solves its own **skeleton** (primary bodies, key faces, datums).
2. It hands **named references** to its children via `receives`.
3. Each child's solution is a DSL fragment parameterized by those references — effectively a function.
4. The parent's final solution is its skeleton plus its children's fragments, in dependency order.

This mirrors the skeleton / master-sketch practice experienced CAD users already follow.

---

## 3. The intent tree

### 3.1 Decomposition

Starting from a root intent, each node either:

- **decomposes** into supporting sub-intents (allocating checks to them, §4.2), or
- **is a leaf**, and is solved directly in DSL.

### 3.2 Stopping criterion

A node stops decomposing when its checks can be satisfied by **a single DSL operation or a known library pattern** (§3.3). "Can I write this as one idiomatic feature?" is the test.

### 3.3 Solution library

Leaf solutions recur: "counterbored hole for a #8 screw," "gusset between two perpendicular faces," "mounting hole pattern." Validated, parameterized solutions are promoted into a library of named DSL functions. The library shortens future trees and grows the model's vocabulary over time (cf. library learning in program synthesis, e.g. DreamCoder).

**One kind of artifact.** Library solutions, user-written features, rule packs (§4.6), and human packs (§4.7) are all **packages**: intent-layer words with their lowering, checks, assumptions, tags, and documentation. Built-in features ship as packages too, in the spirit of Onshape FeatureScript. See [`dsl.md` §2](dsl.md#2-extensibility-one-kind-of-artifact).

### 3.4 The tree is the primary artifact

The tree (intents + checks + provenance + solutions) is more valuable than the final DSL alone:

- **It is the design rationale.** Every feature traces to a reason.
- **It localizes edits.** "Make it hold a heavier shelf" re-solves only the affected subtree.
- **It is the training data.** A procedural generator can emit (intent tree, solution) pairs directly. The intent labels are exact, but only *for the generator's own ontology*: a model trained on them learns the generator's intents, not designers'. Real-designer data is needed too (§9).

---

## 4. Checks

### 4.1 Kinds of check

Every check is labeled with its kind. The kinds form a **determinism ladder**; principle 5 says to push every check as far up this list (toward exact) as it will go, as early as possible:

| Rung | Kind | Examples | Evaluated by | Deterministic? | Accurate? |
|---|---|---|---|---|---|
| 1 | **relation** | centered, concentric, through-all, symmetric | CAD kernel | Yes | Exact |
| 1 | **rule** | clearance-hole tables, edge distance ≥ 2d, min wall, overhang ≤ 45° | computation | Yes | Exact (given the rule) |
| 2 | **analysis** | holds 20 kg; tip deflection ≤ 1 mm | hand-calc / FEA, pinned solver + settings | Yes | Only as good as the model (load case, boundary conditions, material) |
| 3 | **learned score** | visual balance, style conformance | pinned scorer on deterministic renders | Only with deterministic inference (CPU or deterministic GPU kernels); otherwise give scores a noise band. Pinned weights alone are not enough | Statistical; validated against human ratings |
| 4 | **live judgment** | "does this look right to you?" | VLM or human | No | Varies |

Two separate questions: *is it repeatable* and *does it reflect reality*. Analysis is fully repeatable once its assumptions are grounded; its uncertainty lives in those assumptions, which is where grounding effort goes.

Rung 1 also includes **invariants that run on every compiled solution regardless of intent**: kernel validity, an Euler–Poincaré parity check, per-feature topological deltas (each feature computes its expected change in genus and shell count from how it interacts with existing geometry), a stored topological signature, sketch constraint health, and reference determinism. The Euler check on its own is weak: dipm solves for genus H from the formula, so it only fails when V − E + F − R is odd or H comes out negative. The real protection is the per-feature ΔH/ΔS contracts, which compare against an expectation computed independently. See [`dsl.md` §5](dsl.md#5-invariants-checked-on-every-compiled-solution).

Rungs 1–2 can be hard gates. Rungs 3–4 are soft scores: they rank and refine, but early versions don't block on them.

### 4.2 Flow-down: how checks travel to children

When a node writes its sub-intents, it decides, for each of its checks, how it reaches the children — and may invent new ones:

| Action | Meaning | Example |
|---|---|---|
| **pass** | Child inherits the check unchanged | "Printable without supports" → every child |
| **allocate** | Split a budget among children | "Hold 20 kg" → each screw carries its share + margin |
| **translate** | Restate in the child's terms | "Mounts to a wall" → "hole Ø ≥ clearance(#8)" |
| **derive** | New check the node thinks up itself | "Hole ≥ 2×Ø from any edge" (tear-out) |

Global, cross-cutting intents (aesthetics, manufacturability, overall strength) live as root-level checks and flow down via *pass* / *translate*, rather than as subtrees.

### 4.3 Provenance

Every check records where it came from:

```yaml
id: A.1.c2
statement: "Hole center ≥ 2×Ø from any edge of mount_face"
kind: rule
origin: { action: derive, from: A.1, reason: "screw tear-out under load" }
expr: min_edge_distance(hole_axis, mount_face) >= 2 * hole.diameter
```

Provenance makes the design explainable, makes intent-level edits traceable to exactly the checks they affect, and makes over-constraint diagnosable.

### 4.4 Upward verification

Children passing their checks does **not** guarantee the parent passes — the bracket's strength is emergent from plate + arm + gusset + screws. So after composing its children, **every node re-evaluates its own checks**.

- If a parent fails while all children pass, **the decomposition missed or mis-allocated a check.** That failure is precisely attributable to the parent's decomposition step — a clean training signal for "which checks to pass down."
- Unsatisfiable checks (contradictions) should fail at the node that created them, not levels below.

### 4.5 Guardrail: no extraneous checks

Inventing checks risks over-constraining the design — the very thing this project exists to avoid. Each derived check must be justified by an intent (its `origin.reason`), and the set should be minimal.

### 4.6 Geometric vs. world-derived intent

Check *kind* (§4.1) says **how a check is verified**. A second, independent axis says **where its knowledge comes from**:

- **geometric** — needs nothing beyond geometry itself: "evenly spaced," "centered," "symmetric," "fill this face with a hole grid."
- **world** — needs knowledge of the physical world: manufacturing processes, materials, standards, physics, human factors. "Easily injection molded," "fits a #8 screw," "holds 20 kg."

| | Rung 1 (relation / rule) | Rung 2 (analysis) | Rungs 3–4 (learned score / judgment) |
|---|---|---|---|
| **geometric source** | evenly spaced, centered, symmetric | — | — |
| **world source** | draft ≥ 1° on pull-parallel faces; wall 1.5–3 mm; Ø = clearance(#8) | holds 20 kg (once load case, supports, material are grounded) | — |
| **human source** (§4.7) | consistent radii, shared axes, visual-mass centroid over support | — | looks balanced; fits "minimal industrial" style |

**Grounding.** World intents should be *translated* into geometric checks as early as possible, at the node where they enter the tree. "Injection-moldable" grounds into draft, wall-thickness, undercut, and corner-radius checks; after that, everything below is geometric and deterministic. Grounding is where the language model's broad world knowledge meets the kernel's exact geometry, and it is a distinct, trainable skill.

**Rule packs.** World knowledge is made explicit in versioned, sourced, parameterized **rule packs** rather than left latent in the model:

```yaml
pack: injection_molding        # v0.1, illustrative
params: [material, pull_direction]
rules:
  draft_min:
    applies_to: faces parallel to pull_direction
    expr: draft_angle >= lookup(material, "draft_min", default=1 deg)
    source: "<DFM guide / supplier spec, cited>"
  wall_range:
    expr: lookup(material, "wall_min") <= wall_thickness <= lookup(material, "wall_max")
  no_undercuts:
    expr: undercuts(pull_direction) == 0     # unless side actions are allowed
  inner_corner_radius:
    expr: inner_radius >= 0.5 * wall_thickness
```

Other early packs: `fdm_printing`, `fasteners`, `sheet_metal`, `cnc_milling`. The model's job is to **select and parameterize** packs. It may **propose** new rules, but they are marked `unverified` in provenance and never treated as fact until reviewed.

**World context.** World-derived checks depend on context (process, material, quantity, environment), which lives at the root and flows down with *pass*. When the designer hasn't specified it, the model **assumes a default early** (PLA on a standard FDM printer) as a visible, unreviewed assumption. The same process pack then drives checks, as-made prediction, *and* the render's surface detail (see [`tolerance-uncertainty.md` §4.2](tolerance-uncertainty.md#42-assume-material-and-fabrication-early)).

**Provenance** gains a `source` field: `geometric`, `world:<pack>.<rule>@<version>`, or `world:model-proposed`.

**Conflicts.** World and geometric intents can collide (crisp sharp corners vs. a molding radius minimum). Checks carry a priority; manufacturability and safety typically outrank aesthetics, and every override is recorded in the tree.

**Different data and evaluation.** Geometric intents can be procedurally generated, with labels that are exact for the generator's ontology (§9). Grounding needs curated knowledge (DFM guides, fastener and material standards) and expert-authored test cases: "given this intent and context, these checks must appear."

### 4.7 Human packs

The sister to rule packs. Rule packs encode knowledge of the physical world; **human packs encode knowledge of the people who will see, use, understand, and maintain the result** (principle 6). Same principle applies: **determinize as much as possible, learn the remainder.**

Human packs cover five facets:

| Facet | Question | Example proxies (deterministic where possible) |
|---|---|---|
| **Perception** | Is it pleasing to look at? | visual balance, radius family, alignment, rhythm, proportion (§4.7.1) |
| **Use** | Is it easy and comfortable to operate? | Fitts's-law cost of controls weighted by use frequency; reach envelopes and grip sizes from anthropometric tables; min control size and spacing |
| **Understanding** | Can a newcomer figure it out? | Hick's-law choice count per decision; control↔indicator mapping (each control adjacent to and aligned with what it affects); functional grouping matches spatial grouping; rank correlation of importance vs. prominence |
| **Care** | Can it be assembled, serviced, repaired? | tool access clearance for every fastener; distinct tool count; fastener count (DFA); serviceable parts reachable without disassembling unrelated ones |
| **Model readability** | Can a new engineer understand and safely edit the CAD? | named features from the intent tree; tree depth/breadth limits; no unexplained literals; edit stability (§6) |

The last facet matters because a model has two human audiences: people who use the physical object, and people who will open the design file later. Ruby is optimized for the programmer; this model should be optimized for both.

**Usage models are assumptions.** Use and Understanding proxies need to know *what is important and how often it's used*. That comes from the intent tree as an explicit, reviewable usage model: `start_pause: every session`, `delay_wash: rare` (§4.8).

**Geometry must carry purpose.** To evaluate mapping or grouping, the compiled model needs to know that *this* recess is the Start button and *that* window is the time readout. Those semantic tags come from the intent nodes that created the features; the DSL must preserve them through compilation.

#### Case study: a washing machine control panel

A well-regarded washer control panel family (one manufacturer has used essentially the same layout across many models for years) shows these facets working together. What makes it work, and how each maps to a check:

| Observation | Principle | Computable proxy |
|---|---|---|
| The cycle dial, the main decision every use, is the largest control and the visual anchor | Prominence ∝ importance × frequency | Rank correlation of control size/centrality vs. usage model |
| Power and Start/Pause flank the dial as two identical round buttons, left then right | Order of use; consistency | Left-to-right/top-to-bottom order matches task sequence; same function class → same control form |
| Cycle names fan out radially in two balanced columns with leader lines to the dial | Natural mapping; balance | Each label's leader resolves to a unique dial position; column item counts and extents within tolerance |
| Temp / Spin / Soil / Signal buttons sit directly beneath the indicator column they change | Mapping; visibility of state | Each control horizontally aligned with its indicator group; every adjustable state has a visible indicator |
| Rarely used options are smaller and pushed to the flanks of the display | Progressive disclosure | Prominence of low-frequency controls below a threshold |
| Advanced functions are hidden behind "hold 3 seconds", flagged by an asterisk legend | Progressive disclosure, signifiers | Hidden functions each have a visible signifier |
| Largest readout (time remaining) sits top-right, where the eye lands after acting | Glanceability | Readout size ranks by glance frequency |
| One grid, one typeface, consistent separators, a single accent color | Order and calm | Alignment near-misses = 0; distinct typefaces/colors ≤ N |

Almost every row is determinizable once the usage model is stated as an assumption. What remains (does the whole feel *calm*?) is the learned-scorer layer.

#### 4.7.1 Perception (aesthetic) detail

Each perception pack has two layers:

1. **Deterministic proxies (rung 1).** Much of aesthetics reduces to computable geometry:
   - *visual weight:* centroid of visible mass relative to the support or symmetry axis
   - *radius family:* all fillets/chamfers drawn from a small set of sizes
   - *alignment:* features share axes and edges; few "almost aligned" near-misses
   - *rhythm:* regular spacing; consistent wall thickness and edge treatment
   - *proportion:* primary-dimension ratios within the style's preferred ranges
   - *economy:* few distinct dimensions in the design
2. **Learned scorer (rung 3)** for what the proxies miss: a pinned, image-trained model that scores deterministic multi-view renders of the compiled DSL. Video encoding's VMAF is the precedent: a model of human perception trained on human ratings, used as a repeatable objective metric.

```yaml
pack: minimal_industrial       # v0.1, illustrative
proxies:
  radius_family:   { expr: distinct(fillet_radii) <= 2 }
  alignment:       { expr: near_miss_alignments(tol=0.5 mm) == 0 }
  visual_balance:  { expr: horizontal_offset(visual_centroid, support_axis) <= 0.1 * width }
scorer:
  model:   "balance-scorer@<pinned hash>"
  renders: [iso, front, side]          # fixed cameras, lighting, resolution
  use:     soft                         # ranks candidates; never a hard gate
```

**Training data comes cheap from parametric models.** Varying one tree's parameters yields near-identical variant pairs, ideal for pairwise "A or B?" human preference collection.

**Cautions.**
- Taste isn't universal. Packs are *named styles* selected in the root `context`, like process and material, not a single standard of beauty.
- Goodhart's law: optimizing hard against a learned scorer yields "scores well," not "looks good." Learned scores stay soft, are capped in weight within the idiomatic score, and get periodic human review (rung 4).
- Provenance `source` gains `human:<pack>.<check>@<version>`.

### 4.8 Assumptions

Grounding (§4.6) almost always requires assumptions: "the load is static and applied at the arm tip," "Start/Pause is used every session," "the installer has a standard screwdriver." The model is **empowered to make them**, because without them it can't move from world intent to deterministic checks. Every assumption is a **first-class, reviewable object in the tree**:

```yaml
id: R.a1
statement: "Shelf load is static, applied as a point load at the arm tip (worst case)"
made_by: model            # model | user | pack default
rationale: "Books may be pushed to the front edge; tip loading maximizes moment"
supports: [R.c1]          # checks whose grounding depends on it
sensitivity: high         # computed: how much dependent check margins move when it's varied
status: proposed          # proposed | accepted | challenged | replaced
```

- **Visible by design.** Assumptions are listed in the tree next to the checks they ground, so a reviewer can see what the model took for granted.
- **Sensitivity is computable.** Perturbing an assumption and re-running dependent checks shows which ones the design hinges on (the same mechanism as edit tests, §6). High-sensitivity assumptions are surfaced first for review.
- **Challenging one is cheap.** Marking an assumption `challenged` or replacing it invalidates exactly the checks in `supports`, and only those subtrees are re-solved.
- **Prefer conservative defaults.** When unsure, assume the worst reasonable case and say so in `rationale`.

---

## 5. Passes

Inspired by multi-pass video encoding — whose first pass *analyzes* globally so the second can *allocate* well — and by compiler optimization passes. Passes are **distinct in purpose**, not one loop repeated.

| # | Pass | Does | Analogy |
|---|---|---|---|
| 1 | **Decompose** | Build the intent tree top-down; allocate checks; solve skeletons | Encoder analysis pass |
| 2 | **Plan review** | Each parent reviews its children's *proposed* plans together before they solve; catches shared concerns early | Encoder lookahead |
| 3 | **Solve** | Write DSL for leaves; compose upward | — |
| 4 | **Verify up** | Re-run every node's checks after composition; on failure, re-allocate or re-decompose that node | Test suite |
| 5 | **Walkthrough** | Virtually "live with" the part across its lifecycle (fabricate → assemble → install → use → maintain → retire), generating and running checks for each stage (§5.2) | Printing a prototype and assembling it |
| 6 | **Consolidate** | Cross-level simplification: hoist shared concerns into parents; push down over-specification (§5.1) | Refactoring: pull-up / CSE |
| 7 | **Idiom refactor** | Rewrite correct solutions into more idiomatic ones (cut-extruded cylinder → hole feature; duplicated features → mirror/pattern; literals → relations) | Peephole optimization |

**Order matters: valid → correct → idiomatic.** Passes 6–7 run only on solutions that pass all hard checks. Passes 4–7 may loop, terminating when the idiomatic score (§6) reaches a threshold, stops improving by more than ε, or hits an iteration budget.

### 5.1 Consolidation (cross-level simplification)

Siblings each see only their own slice. Relations *between* siblings — aligned, evenly spaced, symmetric — are invisible to each child but obvious to the parent.

- **Detect:** siblings that reference the same face, use the same feature type, or have related parameters.
- **Hoist:** the parent (or a new intermediate node) takes ownership of the shared structure, e.g. a layout of hole centers; children reduce to "place a hole at point *i*" or merge into one patterned feature.
- **Push down:** the inverse, when a parent over-specifies something only one child cares about.

Two consequences:

1. **Consolidation often reveals a missing intent.** Three holes on one face usually means the tree skipped a level ("a mounting hole pattern") — a real intent with its own checks. The right output is frequently a *new tree node*, which also teaches the decomposer what it missed.
2. **Beware false coupling.** Geometric proximity is not shared purpose. Coupling a cable pass-through into a screw pattern because they share a face adds exactly the extraneous constraint we're trying to avoid. **Hoisting requires shared purpose, which only the intent tree knows.**

Consolidation is a refactor: all checks must still pass with provenance intact, the idiomatic score must improve, and edit tests must confirm the coupling is intended.

### 5.2 Walkthrough: the virtual prototype

Experienced designers print early and often, because many problems only appear once the part is in hand: a screw no driver can reach, a clip that can't be inserted in the only possible order, a button the thumb can't find. Every geometric check can pass while the object is still wrong. The walkthrough pass tries to catch these *before* the print, by systematically "living with" the part through each lifecycle stage and asking what a person would physically do:

| Stage | Simulated question | Example checks generated |
|---|---|---|
| **Fabricate** | Can it be made as drawn? | overhangs, bridging, min feature size, bed orientation, support removal access |
| **Assemble** | Can parts go together, in some order, with hands and tools? | assembly-sequence feasibility; insertion paths clear; tool-access cylinders; hand/finger clearance envelopes |
| **Install** | Can one person mount it where it goes? | drill/driver access at the installation site; can it be held in place while fastening; is there a level/alignment reference |
| **Use** | Does it work for a hand, eye, and body? | reach and grip envelopes; control prominence vs. usage model; sightlines to readouts; pinch points |
| **Maintain** | Can wear parts be reached and replaced? | serviceable parts reachable without removing unrelated parts; fastener and tool commonality |
| **Retire** | Can it come apart? | disassembly sequence exists; materials separable |

Each stage turns the vague "would this work in my hands?" into concrete, mostly rung-1 geometric checks: swept access volumes, motion paths, clearance envelopes from anthropometric data. That is principle 5 again, applied to the physical experience. Stages and their check generators live in human and rule packs.

**Walkthroughs generate assumptions too.** "The installer works alone," "the installer uses a standard driver," "the part is printed on its back face." These enter the tree like any other assumption (§4.8).

**The model won't replace printing; it should plan the prints.** Some things (feel, snap-fit force, a specific printer's tolerances) need physical parts. The model can still help: high-sensitivity assumptions and checks with thin margins (§4.8) are exactly what the next prototype should test. The walkthrough should output a **prototype plan** saying which region to print first, often as a small test coupon rather than the whole part, and which assumption it tests.

**Every physical gotcha becomes a permanent check.** When a real print reveals a problem the walkthrough missed, it is encoded into a pack as a new check generator, the way a bug becomes a regression test. Over time the packs accumulate a designer's hard-won "I've been burned by this before" knowledge, and that knowledge is shareable, versioned, and never forgotten.

---

## 6. Idiomatic score

A computable, weighted score over a solution (and its tree). Components:

| Component | Measures | How |
|---|---|---|
| **Edit stability** | Does intent survive edits? | Perturb free parameters across a range; rebuild; re-run relation checks. Score = fraction that rebuild and pass |
| **Constraint health** | Fully but not over-constrained | Solver DoF analysis: 0 remaining DoF, 0 redundant/conflicting constraints |
| **Relations vs. literals** | Intent expressed as relations | Fraction of dimensions that are relations or parameter expressions vs. raw literals |
| **Feature choice** | Right operation for the job | Rule set: hole feature vs. cut cylinder, pattern/mirror vs. copies, shell vs. manual subtraction |
| **Brevity** | Minimal program | Op count / description length among programs passing all checks |
| **Library reuse** | Uses known patterns | Fraction of leaves solved by library functions |

Components can conflict (shortest ≠ clearest), so the score is a weighted combination, or candidates are ranked on a Pareto front — like an encoder's quality/size/speed trade-off. The weights are themselves something to tune.

This score is both the **pass-loop termination criterion** and, later, a **training reward**.

---

## 7. Determinism requirements

The guarantee is **"same fully locked solution → identical geometry"**, not "same DSL → identical geometry". A fully locked solution is the DSL source, the interpretations lock, the designer's prefs, and pinned kernel and package versions. (Review INC-01 / ISS-03, corrected 2026-11-16.)

**Where non-determinism lives today**, outside that guarantee:

- **Interpretation resolution.** Without a lock, `Design.build()` uses unchecked ranked defaults, so the same `.py` can build different geometry depending on which lock and prefs files sit next to it. Resolution is Gauss–Seidel, warm-started from the previous lock, so its result can depend on history (`src/dipm/NOTES.md` DECISIONS #26, #30).
- **Background re-resolution in the server.** The GUI shows one geometry, re-resolves interpretations in the background, and may rebuild with different readings about 2.5 s later (NOTES #38).
- **Learned scorers** (rung 3). GPU rendering and inference are not bit-reproducible by default (§4.1).
- **`BRepOffset` join mode.** Its BRep bytes differ on every build, though geometry and references stay the same ([`dsl.md` §5.4](dsl.md#5-invariants-checked-on-every-compiled-solution)).
- **The DSL is arbitrary Python** today, and the server does not reload imported modules (NOTES #38).

The direction is to make the lock mandatory for any build that is displayed or exported, and to fail closed when it is missing or stale (review INC-01). The lock key must also cover the lowering code, not just the design file (work item B6 in [`review-response.md`](review-response.md)).

Within the guarantee, determinism requires:

- A pinned kernel, solver, compiler, and package versions (a lockfile), recorded with every solution.
- Query-based topological references only (§2.2): structural references resolved through kernel history, declared cardinality, no ordinal indices, no references to contingent fragments ([`dsl.md` §3.4](dsl.md#34-references-the-topological-naming-problem)).
- Explicit branch tags on every sketch construction step, so a constraint system's choice of solution is written down rather than inherited from previous geometry.
- Determinism verified in CI by rebuilding and comparing topological signatures and BRep text bytes (byte equality, not a canonical form; see [`dsl.md` §5.4](dsl.md#5-invariants-checked-on-every-compiled-solution) for what each hash is stable under). Spike 01 found byte-identical output across 64 builds per model, in-process and across processes, with OCCT's parallel mode on and off (single machine; cross-platform untested).
- Deterministic evaluation order in the compiler; no reliance on hash ordering or float-sensitive tie-breaking without explicit tolerance rules.
- A canonical serialization of solutions, so equality can be checked textually as well as geometrically. This is a goal: BRep text is a stable serialization on one platform, not a canonical one, and a canonicalizing serializer is an open item.

---

## 8. Worked example: shelf bracket

Hand-worked to stress-test the format before any model is involved.

### 8.1 Root

```yaml
id: R
statement: "A solid that supports a shelf on a wall"
parameters:            # true design parameters — the only literals
  shelf_depth: 200 mm
  load:        20 kg
  screw:       "#8"
  t:           5 mm    # material thickness
context:               # world context (§4.6)
  process:  fdm_printing
  material: PETG
  install:  drywall with anchors
  style:    minimal_industrial
checks:
  R.c1: { kind: analysis,      source: world,                          statement: "Carries `load` at shelf front edge, safety factor ≥ 2",
          grounded_as: "point load at arm tip; leg fixed at screw locations; PETG allowable from fdm_printing pack (layer-direction strength)" }
  R.c2: { kind: rule,          source: "world:fdm_printing.overhang",   statement: "Printable without supports (overhang ≤ 45°)" }
  R.c3: { kind: learned score, source: "human:minimal_industrial",      statement: "Proportions look balanced",
          grounded_as: "radius_family, alignment, visual_balance proxies + pinned scorer (soft)" }
  R.c4: { kind: rule,          source: "human:care.tool_access",       statement: "Every wall screw can be driven by a standard screwdriver",
          grounded_as: "Ø30 mm straight access cylinder, ≥ 150 mm long, coaxial with each screw, clear of the part" }
assumptions:
  R.a1: { statement: "Load is static, point load at arm tip (worst case)", made_by: model, supports: [R.c1], sensitivity: high }
  R.a2: { statement: "PETG strength across layers ≈ 50% of in-layer",    made_by: pack default, supports: [R.c1], sensitivity: high }
  R.a3: { statement: "Installer uses a standard screwdriver or drill, no right-angle adapter", made_by: model, supports: [R.c4], sensitivity: medium }
skeleton: |
  # L-shaped profile on the side plane: vertical leg against the wall, horizontal arm under the shelf
  profile = sketch(on=SIDE_PLANE):
      L(leg=0.75 * shelf_depth, arm=0.8 * shelf_depth, thickness=t)
  body = extrude(profile, distance=6 * t, symmetric=True)
exports: [wall_face, mount_face, shelf_face, inner_corner]
```

> **Known issues in this example (review INC-02, INC-03, ISS-09; noted 2026-11-16, not yet fixed).**
> - **"The only literals" is not true.** The skeleton and §8.5 also contain 0.75, 0.8, 6, 0.4, `u=0.75`, `v=0.5`, and `diameter=8 mm`, `examples/shelf_bracket.py` adds `plain(8.0)` and `across=(X, 0.5)`, and `src/dipm/intent_layer.py` hard-codes `TOOL_ACCESS_DIAMETER = 30.0`. The engine adds its own epsilons (1 mm and 2 mm overshoots, a 0.01 mm exposure tolerance, 16 rays). Multiplying a number by a parameter does not make it a relation. These are three different things and should be counted separately in the relations-vs-literals metric (§6): **relations**, **ratio constants** (design decisions that need a reason), and **engine epsilons**.
> - **Convenience couplings.** `width = 6 * t` means changing material thickness from 5 to 8 mm widens the bracket from 30 to 48 mm. `leg = 0.75 * shelf_depth` and `gusset size = 0.4 * shelf_depth` tie the leg and gusset to shelf depth with no stated purpose. This is the false coupling §5.1 warns against. Each should become an independent parameter, or get an intent node and a check that explains the ratio.

### 8.2 First decomposition

```
R  Support a shelf on a wall
├── A  Wall mounting: fix the bracket to the wall with screws        receives: mount_face, wall_face
│   ├── A.1  Clearance hole for a wall screw (upper)
│   ├── A.2  Clearance hole for a wall screw (lower)
│   └── A.3  Cable pass-through for a shelf light
├── B  Shelf support: hold the shelf and fix it from below          receives: shelf_face
│   └── B.1  Clearance hole for a screw up into the shelf
└── C  Stiffening: resist the arm bending under load                 receives: inner_corner
    └── (leaf) gusset between leg and arm
```

Check flow-down from R (excerpt):

| Check | Action | To | Becomes |
|---|---|---|---|
| R.c1 (load) | allocate | A.1, A.2 | "Each screw carries ≥ load/2 × SF" |
| R.c1 (load) | translate | C | "Arm tip deflection ≤ 1 mm at `load`" |
| R.c2 (printable) | pass | A, B, C | unchanged |
| — | derive (A) | A.1, A.2 | "Hole center ≥ 2×Ø from any edge" |
| — | translate (A) | A.1, A.2 | "Hole Ø = clearance(screw)" |

### 8.3 Plan review catches a shared concern (pass 2)

A.1 and A.2 each propose positioning their own hole with its own dimensions from the face edges. Parent A sees that both act on `mount_face`, both are wall-screw holes, and both share a purpose. A.3 is also on `mount_face` but has a **different purpose** (cable routing).

Consolidation inserts a missing intent node and leaves A.3 alone:

```
A  Wall mounting
├── A.P  Wall screw pattern          ← new node discovered by consolidation
│   │    checks: symmetric about mount_face vertical centerline;
│   │            spread as far apart as edge distance allows (resists moment);
│   │            Ø = clearance(screw); edge distance ≥ 2×Ø
│   ├── A.P.1  hole at layout point 0
│   └── A.P.2  hole at layout point 1
└── A.3  Cable pass-through          ← NOT coupled to the pattern
         checks: Ø ≥ 8 mm; centered horizontally; clear of A.P holes by ≥ Ø
```

### 8.4 Upward verification catches a mis-allocation (pass 4)

Root check R.c1 is re-evaluated after composition. Because the shelf load acts as a moment about the bottom of the leg, the **upper screw is in tension and carries far more than load/2**; the naïve even split in §8.2 was wrong. All children passed their (wrong) checks; the root failed. The failure is attributed to R's allocation step, which re-allocates: *"upper screw: pull-out ≥ moment / lever arm × SF."* A.P's derived check "spread as far apart as edge distance allows" now matters quantitatively.

This is the exact training signal described in §4.4.

### 8.4a The walkthrough catches a usability bug (pass 5)

The first draft of this example placed a single gusset on the bracket's mid-plane, and the wall screw pattern on the mount face's vertical centerline. Every geometric check passed. But R.c4 (tool access) fails: the gusset sits directly in front of the upper screw, so no screwdriver can reach it. This bug was in the hand-written example itself until the walkthrough's *assemble/install* stage generated a tool-access check. It's exactly the kind of gotcha a first print would have revealed.

Candidate fixes the solver can compare by idiomatic score:

1. Replace the mid-plane gusset with **a mirrored pair at the side edges**, widening the body enough for R.c4's access cylinder between them.
2. Keep one gusset but **confine the screw pattern below the gusset's footprint** (adds a relation: `pattern.top ≤ gusset.bottom − clearance`).

Option 2 is shown below: it keeps one gusset (brevity) and adds one meaningful relation. Note this shrinks the lever arm between the screws, which re-triggers R.c1 — exactly how upward verification is supposed to interact with new checks.

> **Known open finding: option 2 probably fails R.c1 (review INC-06, noted 2026-11-16).** Choosing option 2 for brevity contradicts §5, where idiom passes run only on solutions that pass all hard checks, and R.c1 was never actually evaluated. In the v0 build the wall screws sit at about z ≈ 9 and 50 mm on a 150 mm leg. A simplified rigid-pivot estimate about the bottom of the leg gives M ≈ 196 N × 0.16 m ≈ 31 N·m and an upper-anchor pull-out of T = M·z₁/Σzᵢ² ≈ **600 N at 20 kg before the safety factor** (≈ 1.2 kN with SF 2). Screws near the top of the leg would see about 220 N. The model ignores how the leg bears on the wall and the anchors' stiffness, so the absolute numbers are rough; the factor of about 2.7 between the layouts is the robust part. Drywall anchors are unlikely to hold 1.2 kN. The example is left as it is for now. Work item B2 ([`review-response.md`](review-response.md)) implements R.c1 as an executable rung-2 hand-calc, which should make option 2 fail upward verification for real and let option 1 (twin edge gussets) win. Until then, the GUI's PASS on this example means only that the kernel invariants passed.

### 8.5 Final solution (illustrative DSL)

```python
param shelf_depth = 200 mm
param load        = 20 kg
param screw       = "#8"
param t           = 5 mm

# --- R skeleton ---
profile = sketch(on=SIDE_PLANE):
    L(leg=0.75 * shelf_depth, arm=0.8 * shelf_depth, thickness=t)
body = extrude(profile, distance=6 * t, symmetric=True)

wall_face    = body.face(normal=-Y, largest=True)
mount_face   = wall_face.opposite()
shelf_face   = body.face(normal=+Z, largest=True)
inner_corner = body.edge(between=(mount_face, shelf_face.opposite()))

# --- C gusset (placed before the screw pattern, which must avoid it: R.c4) ---
g = gusset(at=inner_corner, size=0.4 * shelf_depth, thickness=t, mid_plane=True)

# --- A.P wall screw pattern ---
wall_pts = distribute(
    along  = mount_face.centerline(axis=VERTICAL).below(g.footprint, clearance=tool_access(screw)),
    count  = 2,
    inset  = edge_distance(clearance(screw)),     # spread as far as allowed
)
hole(on=mount_face, at=wall_pts, spec=countersink(screw), extent=THROUGH)

# --- A.3 cable pass-through (independent of the pattern) ---
hole(on=mount_face,
     at=between(wall_pts[0], wall_pts[1]),        # relation, not a coordinate
     diameter=8 mm, extent=THROUGH)

# --- B.1 shelf screw ---
hole(on=shelf_face,
     at=shelf_face.point(u=0.75, v=0.5),          # toward front, centered across width
     spec=clearance(screw), extent=THROUGH)

# --- global: R.c2 printable ---
fillet(inner_corner, radius=t)
```

> Note `between(wall_pts[0], wall_pts[1])` for A.3: is that intent, or false coupling? If the cable hole's real intent is "centered on the plate," it should reference `mount_face.center()` instead. This is exactly the kind of ambiguity the tree must resolve from *purpose*, and it should be written as an explicit check so an edit test can tell the difference. Open question kept in the example deliberately.

> **Implementation finding (v0 core, 2026-11-16).** Choosing "centered on the plate" exposed a second issue: with the §8.4a option-2 layout, the mount face's literal center lies *under the gusset footprint* at every shelf_depth. The v0 example interprets "the plate" as the exposed part of the mount face below the gusset (see `src/dipm/NOTES.md` DECISIONS #8). This is a real design conflict between C (gusset) and A.3. A tree-level resolution, re-examining option 1 (twin edge gussets) or redefining A.3's intent, is a good test case for upward verification and consolidation.

### 8.6 Edit tests

| Edit | Expected | Verifies |
|---|---|---|
| `shelf_depth` 200 → 300 | Holes stay symmetric, re-spread to new insets; gusset scales | Relations, not literals |
| `screw` #8 → #10 | Hole Ø and edge insets grow; pattern stays symmetric | Rule checks drive geometry |
| `t` 5 → 8 | Fillet radius and gusset thickness follow | Parameter expressions |
| Move wall pattern | Cable hole does **not** move (if its intent is "plate center") | No false coupling |

> The first three tests pass partly *because of* the convenience couplings noted in §8.1: "gusset scales" is the 0.4 × `shelf_depth` ratio doing its job, not evidence that the scaling is meant. Once those ratios are justified or replaced, these tests need restating.

---

## 9. Where learning happens

The solution side is deterministic software. Learning targets the intent side:

| Skill | Trained on / rewarded by |
|---|---|
| Decomposition | Upward-verification failures attributed to the node (§4.4); consolidation discovering missing nodes (§5.1) |
| Check allocation & derivation | Same; plus penalties for unsatisfiable or unjustified checks |
| Human-pack scorer (rung 3) | Pairwise human preferences over parametric variants; validated by agreement with held-out ratings |
| Making assumptions | Reviewer acceptance rate; whether high-sensitivity assumptions were surfaced; conservatism (did the design survive when an assumption was replaced by reality?) |
| Grounding (world → geometric checks) | Expert-authored cases: required checks present, correct rule packs selected and parameterized, no hallucinated rules |
| Intent → DSL (leaf solving) | Hard checks pass; kernel validity; idiomatic score |
| Branch-tag inference | The solver itself is deterministic software; the intent layer learns to infer branch tags from intent, rewarded by the stability harness (no flips across parameter ranges) |
| Refactoring (passes 6–7) | Idiomatic-score improvement with all checks preserved |
| Multimodal grounding | Matching dimensions/relations extracted from images, drawings, or meshes |

Data strategy (from the survey): most large public CAD datasets are non-commercial and strip constraints. A **procedural generator that emits full intent trees with checks** gives license-clean data with exact intent labels, something no public dataset provides.

**The limit of procedural data (corrected 2026-11-16, review INC-12 / ISS-04).** Earlier drafts called this "ground-truth intent by construction". That is circular. The labels are ground truth *of the generator's ontology*: the intents someone wrote into the generator. A decomposer trained on them learns to recover those intents, not the ones real designers hold, and evaluating it on more generator output can only confirm that. Procedural data is good for pre-training and for regression tests. It cannot tell us whether the system understands designers.

**Real-designer data, needed from day one, at least for evaluation.** A small corpus of (designer intent, designer's model, designer's judgment) is the minimum. Plausible sources, roughly in order of cost:

- **The designer's own answers** to interpretation questions (§10.2) and assumption reviews (§4.8). Every answer is a labelled "this is what I meant".
- **Accepted and rejected proposals.** When the system proposes a decomposition, check, or refactor, the designer's accept, edit, or reject is a preference label.
- **Redlines** (see [`user-experience.md`](user-experience.md)): marked-up corrections on renders say what was wrong and where.
- **Hand-authored evaluation cases:** a few dozen real parts modelled by experienced designers, with their stated intent and their own edit tests, held out from any training.
- **Licensed feature-tree datasets** (e.g. Onshape-derived or Fusion 360 Gallery data, subject to their licenses, several of which are non-commercial or evaluation-only). They record real feature and end-condition choices, though not the reasons behind them.

None of this corpus exists yet.

The first working system will likely use a frontier model as the intent engine (agent + tools); fine-tuning a smaller open model comes later, rewarded by the same checks and score.

---

## 10. Open questions

1. **Check language.** How formal? A small expression language over kernel queries (as in §4.3) vs. natural language with a learned verifier. Likely: formal for *relation*/*rule*, free-form for *judgment*.
2. **Intent ambiguity → interpretations (proposed 2026-11-16; v0 implemented in `src/dipm/interpret.py`, see `src/dipm/NOTES.md` §6 and DECISIONS #23–31).** Ambiguities like "centered on *which* plate?" or "through *what*?" will keep arising, and the designer can't be asked about each one. Proposed mechanism:
   - **Declare readings.** Each intent word lists its candidate readings in its package. Examples: `centered_on` → face centroid / exposed-region midpoint / between siblings; hole extent → through this plate / through all / up to next face / blind.
   - **Eliminate by checks.** Each reading is lowered and evaluated against the node's checks across the declared parameter ranges. Readings that fail are dropped automatically (e.g. the face centroid lies under the gusset).
   - **Measure whether it matters.** If the surviving readings produce the same geometry everywhere in range, the ambiguity has zero sensitivity and nobody is asked.
   - **Choose a default by a ranked prior:** the package default with its rationale, then the simplest relation (MDL), then a learned prior.
   - **Record the choice** as an assumption (§4.8) with its computed sensitivity.
   - **Ask only when it matters:** when readings diverge within range *and* all pass the checks.
   - **Flag silent substitutions.** If the default reading is eliminated, a *default overridden* notice is raised only when the chosen reading interacts with features the default would not have (e.g. `through_all` drilling into the gusset). An elimination for structural impossibility, such as a placement point that isn't on the face, is ordinary (v0, 2026-11-16).
   - **Remember the answer** as a preference in a user or house-style package, so the same question isn't asked again.

   Real-world data is needed for one part only: improving the learned prior, i.e. which reading designers usually mean. Feature-tree datasets record exactly these choices, such as extrude and hole end conditions, subject to license caveats. The designer's own answers become data too.
3. **Analysis checks.** When to bring in FEA, and what hand-calc approximations are good enough for early versions.
4. **Library governance.** When does a recurring leaf solution become a library function, and how is it versioned?
5. **Inputs beyond text.** How images, drawings, and meshes enter the tree — as root intents, as evidence attached to nodes, or as checks ("matches this silhouette")?
6. **Assemblies.** Out of scope for v1; the tree structure should not preclude it (mates as relations between parts' exports).
7. **Rule-pack sourcing.** Which DFM guides and standards can be encoded and cited without licensing problems, and how packs get reviewed and versioned.
8. **Human packs.** Which styles and facets to start with; how many human ratings a scorer needs to be trustworthy; how much weight learned scores get relative to rung-1 proxies; where Use/Understanding knowledge is sourced (HCI literature, anthropometric data) and under what licenses.
9. **Semantic tags through compilation.** How the DSL carries "this recess is the Start button" from intent node to B-rep so Use/Understanding checks can evaluate it.
10. **Assumption review UX.** How assumptions are presented to a human reviewer so the high-sensitivity ones actually get challenged.
11. **DSL and engine.** See [`dsl.md` §7](dsl.md#7-open-risks) for DSL-specific risks.
12. ~~**Where the designer works.**~~ Decided: standalone for now. See [`user-experience.md` §5](user-experience.md#5-decision-where-does-the-designer-work).
13. **Score weights.** How to set and validate the idiomatic-score weights — possibly against human CAD-expert rankings.
14. **Rename "intent" → "purpose" in files, code and UI?** E.g. `<design>.purposes.yaml`, `IntentTag` → `PurposeTag`, the GUI's "Intent tree" label → "Purposes", so the code matches the terminology above. Deferred; the docs disambiguate in the meantime.

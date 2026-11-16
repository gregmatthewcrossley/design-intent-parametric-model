# DSL and Engine Design

*Status: working draft, 2026-11-15. Direction agreed in conversation; details provisional. First implementation: [`src/dipm/`](../src/dipm/NOTES.md) (v0; no constructive solver or explicit core IR yet). Engine assumptions tested in [`spikes/01-occt-feasibility/RESULTS.md`](../spikes/01-occt-feasibility/RESULTS.md) and [`spikes/02-operation-history/RESULTS.md`](../spikes/02-operation-history/RESULTS.md). Grounding and citations: [`reports/DSL mathematical foundations.md`](../reports/DSL%20mathematical%20foundations.md). Architecture context: [`architecture.md`](architecture.md).*

---

## 1. Two layers, one meaning

Small, theoretically grounded alphabets exist for several parts of geometry (§3): Euler operators for manifold topology, Requicha's r-sets for solids, distance and angle relations for sketches. Their completeness results are narrower than they sound, and some are not yet read in full (§7.1), so the core is *grounded in* them, not proven complete. A minimal alphabet is still the wrong language to write intent in. In Tarski's system "midpoint" isn't a word, only a definition built from betweenness and equidistance, so writing in it erases the intent. That is the **Turing tar-pit** (Perlis): everything is possible, nothing of interest is easy.

So the DSL has two layers, the same way programming languages do: Scheme's small core and derived forms, Rust lowering to MIR, GHC lowering to Core.

| Layer | Character | Who writes it | Examples |
|---|---|---|---|
| **Intent layer** | Rich, deliberately *not* orthogonal; every word is a unit of design intent | The model, designers, pack authors | `midpoint`, `symmetric`, `hole`, `pattern`, `fillet`, `shell`, `gusset`, `wall_screw_pattern` |
| **Core layer** | Small, orthogonal, grounded in solid-modelling theory (a goal: v0 has no explicit core IR) | Nobody, directly: intent forms *lower* to it | primitives, planar extrude/revolve, regularized Booleans, reflection, distance/angle/side relations |

Rules:

- **Every intent word has a precise lowering** into core operations, plus any trusted primitives (§4.3).
- **Intent tags survive lowering.** Each core node records which intent word and intent-tree node produced it, as compilers keep source spans. "This is a midpoint" is never lost.
- **Equivalence is decided on the core (goal).** Two programs mean the same thing when they lower to the same canonical core form. That would support determinism checks, deduplicating training data, and the brevity metric. It is not implemented: v0 has no explicit core IR (`src/dipm/NOTES.md` DECISIONS #4) and no canonical form for it.
- **The model writes intent words; checks run on the core.**

---

## 2. Extensibility: one kind of artifact

Inspired by Onshape FeatureScript, where the built-in features are written in the same language users write custom features in. Extensibility is the language itself, not a scripting layer added on top.

**A user feature, a library solution, a rule pack, and a human pack are all one kind of artifact: a *package*.** A package defines intent-layer words, plus any of:

- their lowering into core operations (and trusted primitives)
- the checks they generate, with kind, source, and provenance
- the assumptions they introduce, with defaults and rationale
- the semantic tags they attach to geometry
- documentation the model can read in order to use them

The built-in features ship as packages too. If our own `hole` and `pattern` can be written as packages, that is good evidence the extension mechanism is expressive enough. Packages are versioned and pinned in a lockfile (§6).

Open questions are tracked in [`explore-further.md` §3](explore-further.md): FeatureScript details, sharing, sandboxing, and whether the model can use a new package from its documentation alone.

**Sandboxing.** If packages are plain Python modules, sharing them means running other people's code with full system access. FeatureScript avoids this by being its own sandboxed language. **Direction (2026-11-15): WebAssembly as the package sandbox.** WASM has no file, network, or system access unless the host grants it, and it runs both in the browser and server-side (e.g. wasmtime). v0 may still use embedded Python while only the project author writes packages. The package format should be designed so packages can move to WASM execution without changing their meaning.

---

## 3. Core layer (proposed)

From the research report §7.1. All entries are proposals pending implementation experience.

### 3.1 Solids

- Bounded primitives: box, cylinder, cone, sphere, torus.
- **Planar-profile extrude and revolve.** A revolve must not cross its own axis.
- Rigid motions.
- **Regularized union / intersection / difference**, with no complement.

Requicha's r-set theory means a well-formed core tree denotes a valid *r-set*: a bounded, regular, semi-analytic set. That is weaker than it sounds:

- **r-sets need not be manifold.** Two boxes sharing an edge, or touching at a vertex, are valid r-sets but not manifold solids. The empty set is an r-set too. So r-set validity does not imply an OCCT-valid manifold B-rep, nor one the Euler–Poincaré formula applies to. A separate manifoldness check is needed (every edge used by exactly two faces; not yet implemented).
- **It holds for the exact program, not the kernel's floating-point output** (§5, §7.2).
- **It covers little of a real part.** The core (primitives, planar extrude and revolve, Booleans) excludes fillet, chamfer, countersink, shell and draft. Most of the shelf bracket's interesting features are trusted primitives (§4.3), which have no closure theorem and are checked at runtime instead.

### 3.2 Sketches

- **Entities:** points, lines, circles, arcs.
- **Core relations:** distance, angle, and an **orientation/side predicate**. Other relations lower to these:
  - incidence = distance 0
  - parallel / perpendicular = angle 0° / 90°
  - tangency and concentricity as distance relations
- **Construction steps** are ruler-and-compass placements.
- **Every step carries an explicit branch tag.** Constraint systems are polynomial and usually have several solutions: an arc can bulge either way; a point can sit on either side of a line. Commercial numeric solvers choose whichever solution is *nearest the current geometry*, which is why sketches "flip" when a dimension changes a lot. We make the branch **explicit and part of the intent**: "bulges away from the profile center," "left of line L," "profile stays convex." Branch tags are checks, so a flip fails loudly instead of happening silently.
- The intent layer fills in branch tags automatically (`tangent(side=OUTSIDE)`, `symmetric`), so authors rarely write them by hand.
- Splines and other non-quadratic cases go through a marked numeric escape hatch with a deterministic seed.

### 3.3 Transforms

- **`reflect(plane)` is the generator.** By Cartan–Dieudonné, every rigid motion is a composition of reflections.
- Mirror, rotate, translate, linear and circular pattern, and symmetric are intent forms that lower to reflections, or to the group they generate.
- Transforms are compared as (rotation matrix, translation) with explicit tolerances.
- Compilation emits **native** rotate/translate/pattern features, never long mirror chains.

*Note (2026-11-16, review MATH-05).* Cartan–Dieudonné and projective geometric algebra (PGA) are correct background but have no operational role yet: transforms are re-emitted as native features, so nothing a user or check sees depends on the reflection form. Comparing transforms as PGA versors would also need sign canonicalisation (a versor and its negation are the same motion) and a tolerance, so it is not a free canonical form.

### 3.4 References (the topological naming problem)

- **Reference only entities an operation creates by its structure**, e.g. `E.cap(END)`, `E.side(from=sketch.edge("top"))`, `F.created()`. Resolve them through kernel history and record them as (feature id, role, source).
- **Every query declares its cardinality** (`one()`, `exactly(n)`, `at_least(n)`). A mismatch is a compile error.
- Geometric predicates carry explicit tolerances and return *sets* on ties. **Ordinal indices (`face[17]`) are never used.**
- **No identity references to contingent entities** such as fragments left by a later cut. Kernel history gives them no stable order. This costs some expressiveness, deliberately.
- **Named exports** (architecture §2.3) carry explicit split/merge policies: `propagate_all`, `error_on_split`, `error_on_merge`. These policies apply to *any* reference, not just exports.
- **Supported creator roles.** Spike 01 validated extrude caps (start/end), side faces from a sketch edge, edges from a sketch vertex, hole walls, cut rim edges, and fillet blend faces. [spike 02](../spikes/02-operation-history/RESULTS.md) extended this to revolve, chamfer, shell, loft (partial), sweep, draft (partial), pattern, mirror, and `clean()`. Its **§6 role-vocabulary table** is the current per-operation reference (e.g. `R.cap(END)`, `C.corner(at=v)`, `Sh.rim(opening=f)`, `P.instance(k).wall`, `M.image(of=r)`).
- **Derived references are structural.** `edges_between(face_ref, face_ref)` and similar intersections of structural references count as structural. They are the *only* way to name edges after draft and offset, whose edge history the kernel drops.
- **A pattern instance index `k` is a declared index, not an ordinal.**
- **Merges are explicit.** `clean()`, coplanar fuses, and mirrors can make two references alias one face. The ledger emits `merged` events: a warning by default, an error under `error_on_merge`.
- **References to a shell's opening face continue onto the rim**, unless a policy forbids it. A spike reference layer of about 80 lines resolved all 18 shelf-bracket references with declared cardinality and stayed stable across a 20-rebuild parameter sweep. Spike 01 also confirmed that fragment order after a split is arbitrary: it reverses with the sketch's start vertex. That justifies the ban on referencing contingent fragments by position.

### 3.5 Kept out of the core

- **Euler operators as authoring vocabulary.** Using them that way would need our own kernel and would be far too verbose. They are used as *checks* (§5).
- **F-rep as the authoritative representation.** It breaks STEP/FeatureScript fidelity and naming. It may be used later for previews, interference checks, and lattices.
- **Halfspace CSG** for authoring. It may still serve as a canonical normal form.

---

## 4. Intent layer

### 4.1 Relations

`midpoint`, `centered_on`, `symmetric`, `equal`, `concentric`, `tangent(side=…)`, `distribute`, `between`, `through_all`, `up_to(face)`, … each defined by lowering to core relations plus branch tags.

### 4.2 Features

`hole` (semantic composite: revolve-cut or cylinder subtraction, plus tags), `pattern`, `mirror`, `gusset`, … each a package (§2).

### 4.3 Trusted primitives

Some operations have no closure theorem but are indispensable: **fillet, chamfer, shell/offset, draft, sweep, loft, thicken.** They come from the kernel as trusted primitives. "Trusted" means *checked after every use*. Each must:

- declare its expected topological deltas and the roles of the entities it creates (e.g. a fillet creates `blend` faces generated from each input edge)
- be followed by the validity checks in §5
- act only on named exports with split/merge policies
- be followed by validity, ΔH/ΔS, and **volume-sign** checks ("material removed > 0" for cuts)

**Three failure classes**, each observed in [spike 02](../spikes/02-operation-history/RESULTS.md):

| Class | Example | Caught by |
|---|---|---|
| **Fails loudly** | chamfer or draft overreach raises | exception |
| **Silently invalid** | collapsing shell; self-intersecting sweep (passes Euler!) | BRepCheck |
| **Silently wrong but valid** | overlapping pattern instances passed as *one compound tool* cut nothing; the result passes BRepCheck *and* Euler | only ΔS, volume, and reference cardinality |

The third class is why per-feature ΔS and volume checks are mandatory, not optional. Booleans always take a *list* of tools, never a possibly self-overlapping compound.

---

## 5. Invariants checked on every compiled solution

These are the rung-1 checks (architecture §4.1) that run regardless of intent:

1. **Kernel validity:** `BRepCheck_Analyzer` with geometric checks on; closed shells; positive volume.
2. **Euler–Poincaré parity:** for manifold solids, **V − E + F − R = 2(S − H)**, where R = inner loops, S = shells, H = genus, with integer H ≥ 0. This is *necessary, not sufficient*: it checks topology only, not geometry such as self-intersection. **It is also weaker than it looks in dipm.** H is not measured independently; `euler_counts` *solves* for it, H = S − (V − E + F − R)/2. So the check can only fail when V − E + F − R is odd or H comes out negative. In practice it is a parity and integrality test that catches gross counting or topology errors. The real protection is item 3: per-feature ΔH and ΔS against an expectation computed independently from the feature's interaction with existing geometry. (A genuine genus check would compute H another way, e.g. the first Betti number from a homology computation on the face–edge–vertex complex. Not planned yet.) **Counting rule for OCCT (validated in spike 01 on 14 solids):**
   - count each sub-shape once by identity *plus location, ignoring orientation*, so seam edges count once;
   - **exclude degenerated edges**, which appear at sphere and cone poles *and at fillet corners*;
   - **never** count by underlying shape (`TShape`) alone: an extrude's end cap shares its start cap's `TShape`, which inflates H.

   Spike 02 confirmed the rule on revolve, sweep, and torus seams with no refinement.
3. **Per-feature topological deltas (ΔH *and* ΔS)** derived from intent. ΔS is as important as ΔH: it was the only invariant that caught the compound-tool error above. The per-operation ΔH/ΔS rules are tabulated in [spike 02](../spikes/02-operation-history/RESULTS.md) §2. Each feature *computes its expected deltas from how it interacts with existing geometry*; there is no fixed rule per feature type. A through-hole usually adds 1 to H, but one that crosses an existing hole adds 2 (spike 01). A blind hole adds 0; "split into two parts" adds a shell or solid. This check catches faults that reference checks miss: in spike 01, a shelf hole that turned blind against the gusset still resolved all its references, but its ΔH was wrong.
4. **Topological signature** stored with each solution: (V, E, F, R, S, H) plus **two** order-independent face-adjacency hashes, alongside pinned versions (§6). None of these hashes is canonical or a true invariant. What each is stable under (corrected 2026-11-16, review INC-09, MATH-06):

   | Signal | What it is | Stable under | Not stable under / can't tell apart |
   |---|---|---|---|
   | **Geometry hash** (`adjacency_hash(geometric=True)`) | 4-round Weisfeiler–Lehman (WL) hash of the face-adjacency graph; faces labelled by surface type, area to 6 significant figures, and wire count; edges by curve type | Rebuilding the same locked solution on the same platform; face and sub-shape *order* | Any geometry change (by design). Values that round differently near a 6-figure boundary, which can flip across platforms |
   | **Topology-only hash** (`adjacency_hash(geometric=False)`) | Same WL hash with no surface or curve types: faces labelled by wire and edge-use counts | Parameter edits that keep the face–edge structure; surface-type flips (e.g. equal loft sections) | Legitimate edits that change topology, such as a new pattern count or a fillet consuming a face. A change is **a signal to review**, not proof of a fault (that is why `allow_topology_change` exists) |
   | **Role-geometry fingerprint** (`role_geometry_fingerprint`) | For each reference tag, the sorted, rounded (centroid, area or length) of what it resolves to | Sub-shape order and BRep byte changes, so it works for `BRepOffset` join mode | Geometry changes (by design); rounding-boundary flips as above |
   | **BRep sha** (OCCT BRep text) | Hash of the kernel's own serialization | Rebuilds of the same locked solution on one machine, except `BRepOffset` join mode | Anything at all, including sub-shape order. It is byte equality, not a canonical form |

   **WL hashes are not canonical.** Equal hashes do not prove equal graphs: 4-round WL cannot separate many regular or symmetric graphs, which are common in CAD (a box's faces, symmetric patterns). Use the hash as a fast pre-filter; exact topological equality needs graph canonical labelling (nauty or bliss), and geometric equality needs a tolerance-aware comparison.

   **OCCT's BRep text format is the serialization used for byte comparison.** It was byte-identical across 64 builds per model in spike 01 and for 26 of 29 models in spike 02. **Exception:** `BRepOffset` join mode (shells with no openings, outward shells, closed voids) produces different BRep bytes on every build, even single-threaded, while geometry and reference resolution stay identical. For those, compare (V,E,F,R,S,H), the adjacency hashes, and an **order-free role-geometry fingerprint** (each role's rounded centroid and area). A canonicalizing serializer is an open item. The topology-only hash should not include surface type, which equal loft sections can flip without any topology change. STEP is an interchange format only: it embeds a timestamp and a per-process product-name counter, both of which must be stripped before comparing.
5. **Sketch constraint health:** structural degree-of-freedom counting at compile time, *as a heuristic*, plus numeric Jacobian rank, redundancy, and conflict detection at an actual configuration, *as the source of truth*. Report "well-constrained at this configuration", not "well-constrained".
   - **Laman does not cover CAD sketches** (corrected 2026-11-16, review MATH-02). Laman's theorem (1970; earlier Pollaczek-Geiringer, 1927) characterises *generic* rigidity of 2D *bar-joint* frameworks: points joined by distance constraints only. CAD sketches mix distances with angles, incidence, parallelism, perpendicularity and tangency, and are non-generic on purpose (collinear points, parallel lines, symmetric layouts). Normalising every constraint to distance plus angle (Bouma et al. 1995) does not bring Laman's theorem back. Earlier drafts said "Laman-style; exact in 2D"; that was wrong for this use.
   - **What to use instead.** For mixed direction-and-length constraints there is a separate combinatorial theory (Servatius & Whiteley, "Constraining plane configurations in computer-aided design: combinatorics of directions and lengths", *SIAM J. Discrete Math.* 12(1):136–153, 1999; Jackson & Jordán's later work on direction-length global rigidity, not checked individually). Practical solvers combine graph decomposition and DOF analysis (Owen 1991; Fudos & Hoffmann 1997; Hoffmann, Lomonosov & Sitharam 2001; survey: Jermann, Trombettoni, Neveu & Mathis, "Decomposition of geometric constraint systems: a survey", *Int. J. Comput. Geom. Appl.* 16(5–6):379–414, 2006) with numeric checks. The **witness configuration method** (Michelucci & Foufou, "Geometric constraint solving: the witness configuration method", *Computer-Aided Design*, 2006) analyses the Jacobian at an easy-to-compute configuration that shares the sketch's incidences, and finds dependencies that graph counting misses.
   - 3D point-distance rigidity is an open problem, so we promise nothing for free 3D point constraints.
6. **Reference determinism:** cardinality declared and met; no ordinals; tolerances explicit.
7. **Stability harness:** perturb each design parameter across its declared range, rebuild, and assert that every reference keeps its cardinality and genealogy, and every branch tag holds. This doubles as the *edit stability* component of the idiomatic score (architecture §6).

---

## 6. Engine: solver, kernel, backends

### 6.1 Solver vs. kernel

| | Sketch solver | Geometry kernel |
|---|---|---|
| Job | Turns **relations into positions** | Turns **operations into solids** (B-rep) |
| Works on | relations among tens to hundreds of entities | surfaces, intersections, topology, tolerances, file I/O |
| Difficulty | moderate, bounded, well-studied | very high, open-ended (decades of team effort) |
| Carries design intent? | **Yes**: midpoint, tangent, and symmetric live here | **No**: it executes operations |
| How it fails | usually clearly ("over-defined," "can't solve") or by branch flip | often subtly (failed fillet, sliver face, invalid solid) |

```
 sketch + relations ──► SOLVER ──► solved 2D geometry ──┐
                                                        ├──► KERNEL ──► solid ──► invariants + checks
 feature operations ────────────────────────────────────┘
```

### 6.2 Decision (provisional): borrow the kernel, own the solver

> **Adopted 2026-11-15 as a working decision: "yes until proven otherwise."** Revisit if the technical spike or later experience shows OCCT can't meet our determinism, reference, or robustness needs, or if the constructive solver proves impractical.

**Kernel: OpenCascade (OCCT), via build123d / OCP, behind a backend interface.** Do not build a kernel.

- The kernel's hardest problems (Booleans, fillets, offsets, healing, STEP) are not where this project's value is, and building one would consume the project.
- OCCT doesn't expose Euler operators. That doesn't matter: we compute topological counts ourselves for checks.
- OCCT's operation history (`Generated` / `Modified` / `IsDeleted`) provides the raw material for structural references (§3.4). We build our own reference layer on it rather than using OCCT's TNaming.
- Parasolid is commercial and costly. We reach it *indirectly* through Onshape (§6.3).

| OCCT weakness | Mitigation |
|---|---|
| Fillets and shells are less robust than Parasolid's | Trusted primitives with runtime checks; failures become clear errors |
| Tolerance quirks; seam and degenerate edges | Calibrate invariants on primitives; lint for near-coincident geometry |
| Parallel Boolean modes may break determinism | Pin version; verify determinism in CI by rebuild-and-compare. Spike 01: byte-identical BRep with parallel mode both on and off, on one machine; cross-platform not yet tested |
| History must come from OCP-level operations | build123d's own history API is too coarse (can't tell an end cap from a side face); the reference layer wraps OCP builders directly |
| `IsDeleted` is unreliable for fillet **and chamfer** (reports untouched edges as deleted) | Infer deletion from `Modified`/`Generated` and from presence in the result, never trust `IsDeleted` alone |
| Draft and offset report face images via `Generated`, not `Modified`, and give no edge history | Ledger follows same-type `Generated` (opt-in per primitive); edges via `edges_between` |
| Full 360° revolve: `Generated` empty for profile edges perpendicular to the axis | Fall back to `MakeRevol.Revol().Shape(edge)` |
| `MakeThickSolid` with no openings makes an offset, not a hollow | Lower "hollow" to offset + cut |
| Collapsing offsets return invalid/null shapes without raising | Post-checks after every trusted primitive |
| Compound tools that self-overlap make booleans silently cut nothing | Booleans take a list of tools |
| `BRepOffset` join mode isn't byte-deterministic | Fingerprint comparison for those ops (§5.4) |
| `clean()` (UnifySameDomain) merges faces | Its `History()` was complete and correct; run it **explicitly** after boolean-like ops, history-chained, never implicitly via build123d |
| Python iteration over OCP lists is slow (~2.5 ms per list) | Use the workaround from spike 01 (`topo.py`); shelf bracket builds with all checks in ~33 ms |
| Dense documentation | Use through build123d / OCP |

**Solver: our own constructive sketch solver**, with a numeric solver (e.g. FreeCAD's planegcs; check its license) as a fallback for sketches that can't be built constructively. The solver is small, and it is where relational intent and branch behavior live. Owning it gives us explicit branch tags, constraint-health analysis, and provenance from each constraint back to its intent.

The solver is really a small family:
- a constructive 2D sketch solver
- 3D placement logic that resolves relations like "centered on *this face*" by querying the kernel and feeding results into sketches

### 6.3 Backends

The core IR compiles to a backend interface:

| Backend | Role |
|---|---|
| **OCCT** (via build123d / OCP) | Primary: local, headless, fast compile-and-check loop |
| **Onshape FeatureScript** | Parametric export target, with Parasolid quality. Must rely on FeatureScript query semantics (emit `evaluateQueryCount` guards, never `qNthElement`), not on matching OCCT genealogy |
| **Manifold** (mesh Booleans) | Candidate for fast previews and walkthrough interference checks (tool-access cylinders, clearance envelopes) |

> **Onshape parity strategy (2026-11-16):** a hybrid of standard features + a dipm placement-feature library + a final checks feature. See [`user-experience.md` §4.1](user-experience.md#41-onshape-parity-researched-2026-11-16).

If any backend becomes a bottleneck, it is swapped behind the interface; the project doesn't change.

---

## 7. Open risks

1. Mäntylä's 1984 completeness theorem hasn't been read in full yet. Don't claim "proven complete" until it has.
2. "Valid by construction" holds only for the exact program, only in the r-set sense (not manifold; §3.1), and only for the small core. It says nothing about the kernel's floating-point output or about trusted primitives, which are most real features. Prefer "checked after every feature" over "valid by construction".
3. ~~OCCT counting conventions may break a naive Euler check.~~ **Resolved by spike 01:** the counting rule is in §5.2.
4. Coarse kernel history: contingent entities can't be named stably (accepted restriction).
5. build123d's history is too coarse; the reference layer uses OCP directly. History is now validated for revolve, chamfer, shell, loft (partial), sweep, draft (partial), pattern, mirror, and `clean()` ([spike 02](../spikes/02-operation-history/RESULTS.md)). **Still untested:** feature-level mirror/pattern, fillet corner faces, sweep and loft options, and FeatureScript parity (see spike 02 §9).
6. Branch tags add authoring burden unless the intent layer infers them reliably.
7. **Cross-platform determinism is untested.** Spike 01 ran on one macOS/arm64 machine with OCCT 8.0.1. Linux/x86 and other OCCT versions are the main remaining risk (see also explore-further §4 on WASM).

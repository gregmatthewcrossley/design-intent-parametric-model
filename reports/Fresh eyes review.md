# Fresh eyes review

*Independent review, 2026-11-16. Scope: committed state at `e84902b` plus the docs; uncommitted iteration-2 work was ignored. Read only. Every item has a stable ID, so you can reply item by item. The same items are in [`Fresh eyes review.items.json`](Fresh%20eyes%20review.items.json).*

**ID scheme.** `NOV` novelty and usefulness · `INC` logical inconsistency · `HN` Hacker News comment · `MATH` mathematics · `PAIN` human pain point · `ISS` top-10 ranked issue (these mostly point to the items above) · `GOOD` what the project gets right. Severity is high, medium or low. Where I am unsure, the item says so.

---

## Verdict

dipm is an unusually honest and well-instrumented engineering notebook. It has a small, genuinely good core: history-based references with declared cardinality, per-feature ΔH/ΔS/volume contracts, and an edit-stability harness. Around that core sits a large conceptual architecture (intent trees, check flow-down, rule and human packs, assumptions, seven passes, an idiomatic score) that is mostly a re-derivation of semantic feature modelling, knowledge-based engineering, systems-engineering requirement allocation and design-rationale systems. The project does not engage that literature or the reasons it stalled. The headline framing, "an LLM-like system that turns intent into CAD", is not yet supported by the repo: there is no model, no intent-level check, and no constraint solver. What exists is a hand-written Python parametric DSL with very good kernel hygiene. The biggest near-term risk is **false assurance**. The GUI shows a green PASS on a worked example whose stated intent (carry 20 kg on drywall anchors with SF ≥ 2) it never checks and probably fails. The interpretations mechanism also lets the invariants *choose* geometry, which quietly turns a negative control into a fix. The most valuable thing to ship soon is the reference layer, the invariants and the edit-stability benchmark, as an open verification harness for CAD agents. The parts most likely to hurt designers are the assumption that they know their intent and are willing to state it, and a text, git and Python workflow that most industrial designers do not live in.

---

## 1. Novelty and usefulness to a designer

**NOV-01 · medium · The intent tree with check flow-down is systems-engineering requirement allocation plus design rationale, not a new idea.**
The pass / allocate / translate / derive table (arch §4.2) is standard requirement decomposition and budget allocation (INCOSE handbook; error and mass budgets). The structure of intent, then checks, then solution matches Gero's Function–Behaviour–Structure framework (1990). "The tree is the design rationale" (arch §3.4) is the promise of IBIS (Kunz & Rittel 1970), gIBIS (Conklin 1988), QOC (MacLean et al. 1991) and DRed (Bracewell et al., Cambridge). None of these is cited. *Remedy:* add a prior-art section that states what dipm does differently, mainly that rationale is executable and attached to geometry, and why that answers the known reasons these tools failed (see PAIN-04).

**NOV-02 · medium · Rule packs and the idiomatic score have decades of commercial precedent.**
KBE systems put rule bases behind geometry: ICAD (1984), Siemens NX Knowledge Fusion, CATIA Knowledgeware, and Creo's Behavioral Modeling. So do DFM/DFA checkers (Boothroyd Dewhurst, DFMPro) and CAD model-quality checkers (Q-Checker, CADIQ, the VDA 4955 and SASIG PDQ guidelines). The idiomatic score's "feature choice", "no unexplained literals" and "tree depth" are already PDQ-style metrics. The documented lesson of KBE is that rule bases are expensive to keep up and end up owned by one person. *Remedy:* position the packs against KBE explicitly, and budget for maintaining them.

**NOV-03 · high · The closest prior art, semantic feature modelling, is missing.**
Bidarra & Bronsvoort (2000, *CAD* 32, "Semantic feature modelling") attach validity constraints to features and check them after every edit. That is dipm's per-feature contracts and intent checks. Related work: Shah & Mäntylä's *Parametric and Feature-Based CAD/CAM* (1995); the line on valid parameter ranges (Hoffmann & Kim 2001; Joan-Arinyo and co-authors), which is the rigorous version of the stability harness; and the CAD-education "design intent / model quality" rubrics (Company, Contero, Camba, Otey, 2015–2018), which already measure alterability under edits. The survey's claim that "nobody measures intent" (survey, "Benchmarks measure shape similarity…") is true only of the ML literature. *Remedy:* read these papers, cite them, and narrow the novelty claim.

**NOV-04 · low (positive) · The genuinely new parts are smaller and more concrete than the docs suggest.**
(a) **Interpretations.** An intent word declares its readings. Readings are eliminated by build checks over the parameter range, and the designer is asked only when the survivors diverge (`interpret.py`). The nearest analogue is disambiguation in programming by example (Mayer et al. 2015, "distinguishing inputs"), not anything in CAD that I know of. (b) **Per-feature topological contracts.** ΔH, ΔS and volume sign are computed from how a feature interacts with existing geometry (NOTES #7). (c) **An edit-stability benchmark** over an open, kernel-neutral DSL. All three are publishable and useful. *Uncertainty:* there may be unpublished industrial equivalents.

**NOV-05 · medium · The user who would adopt it first is not the early-stage industrial designer.**
Realistic first users: (1) people building **parametric families or configurators**, where edits are frequent and edit stability pays for itself; (2) **makers and 3D-print designers** who already write CadQuery or build123d; (3) **AI agents**, through the planned MCP server, as a verifier for generated CAD. The third is the strongest case. The survey's own data says frontier models plus kernel feedback are the winning paradigm, and they lack exactly this verifier. Early-stage ID, which the docs imply ("intent from sketches, images"), is the weakest fit (PAIN-01, PAIN-02). *Remedy:* say so in the README, and design v1 around the agent-verifier use case.

**Where it overclaims.** The README says "a model that turns design intent into parametric CAD". Arch §9 lists nine learned skills, and none is implemented or has data. "Provably complete alphabets" (dsl §1) and "valid by construction" sit next to a v0 with no core IR (NOTES #4). See INC-07 and ISS-04.

---

## 2. Logical inconsistencies

**INC-01 · high · "All non-determinism lives on the intent side" is false in the shipped engine.**
Arch §1 principle 2 and §7 make this claim. But in the engine, (a) a build depends on the lock file, the prefs file and the reading tables. `Design.build()` without a lock "uses unchecked ranked defaults" (NOTES #30), so the same `.py` can build different geometry depending on what files sit next to it. (b) Resolution is Gauss–Seidel, warm-started from the old lock, and never explores the product of readings (NOTES #26). The result can therefore depend on history, because different starting points can converge to different fixed points. (c) The server shows one geometry, re-resolves in the background, then rebuilds ~2.5 s later (NOTES #38). (d) BRepOffset join mode is byte-nondeterministic on the solution side (dsl §5.4). (e) The "DSL" is arbitrary Python, and imported modules are not reloaded (NOTES #38). *Remedy:* restate the principle as "a fully locked solution (DSL + lock + prefs + pinned versions) is deterministic". Make the lock mandatory for any build that is displayed or exported, and fail closed when it is missing.

**INC-02 · medium · "Literals only for true design parameters" is contradicted by the worked example.**
Arch §2.2 says literals appear only for true design parameters, and `shelf_bracket.py` comments "the only literals". Yet the example contains 0.75, 0.8, 6, 0.4, `shelf_hole_u=0.75`, `plain(8.0)`, `across=0.5`, and `TOOL_ACCESS_DIAMETER = 30.0`. The engine adds its own magic numbers: overshoot 1 mm, +2 mm, `EXPOSED_EPS = 0.01`, `UP_TO_NEXT_RAYS = 16`. Multiplying by a parameter does not make a number a relation. *Remedy:* separate "relation", "ratio constant (a design decision)" and "engine epsilon", and count them separately in the relations-vs-literals metric.

**INC-03 · medium · The example commits the false coupling the architecture warns against.**
Arch §5.1 says "hoisting requires shared purpose". The example has `width = 6 * t`: changing material thickness from 5 to 8 makes the bracket 30 → 48 mm wide. `leg = 0.75 * shelf_depth` ties the wall-leg height to shelf depth, and `gusset_size = 0.4 * shelf_depth` does the same for the gusset. These are convenience couplings with no stated purpose. The §8.6 edit tests then pass *because of* them ("gusset scales"). *Remedy:* make width and leg separate parameters, or give each ratio an intent node and a check that explains it.

**INC-04 · high · Interpretations turn checks into selection pressure, so checks stop being independent evidence.**
Arch §10.2 and `interpret.py` step 2 say "eliminate by checks". The same invariants then report PASS on the reading they selected. Spike 01's negative control (`shelf_hole_u=0.4`) used to fail loudly on ΔH. Re-resolved, it now silently drills `through_all` through the gusset and raises only a non-blocking notice (NOTES #28, #32). Rule #32 was also narrowed until the showcase had "0 notices". *Remedy:* (1) when the package default is eliminated *and* the survivor touches more features, ask, don't notify. (2) Keep a hold-out set of checks that are never used for elimination. (3) Show "selected by elimination" distinctly from "verified".

**INC-05 · medium · A check compiled into a construction can never fail.**
R.c4 (tool access) is a check in arch §8.1, but in the example it is implemented as a placement, `before(gusset, clearance=tool_access_radius)`. The walkthrough check thus became part of the solution, and nothing verifies it independently. If the gusset or the driver geometry changes shape, nothing fails. *Remedy:* keep checks as separate objects (NOTES TODO 4), even when a relation also enforces them, so they act as redundant verification.

**INC-06 · high · The worked example's final layout conflicts with its own root check, and the docs picked it for brevity.**
Arch §8.4a chooses option 2 ("keeps one gusset (brevity)"), although §5 says idiom passes "run only on solutions that pass all hard checks". Option 2 puts the wall screws at z ≈ 9 and 50 mm (NOTES #8 numbers) on a 150 mm leg. A rigid-pivot estimate gives about 600 N tension on the upper anchor at 20 kg, or about 1.2 kN with SF 2. Screws near the top of the leg (z ≈ 140) would see about 220 N. This is the result of `M = 196 N × 0.16 m ≈ 31 N·m; T = M·z₁/Σzᵢ²`. *Uncertainty:* a simplified pivot model that ignores wall bearing distribution and anchor stiffness, but the factor of about 2.7 is robust. *Remedy:* make the example demonstrate upward verification for real. Implement R.c1 as a hand-calc, show option 2 failing, and let option 1 (twin edge gussets) win.

**INC-07 · medium · "Proven" language outruns both the report and the code.**
dsl §1 says "minimal, provably complete alphabets exist" and "equivalence is decided on the core". NOTES #4 says there is no core IR. The math report itself says not to claim "proven complete" until Mäntylä 1984 has been read (§7.5). dsl §5.5 says "Laman-style; exact in 2D", but the report says generic only, paired with a Jacobian check (§5.3). *Remedy:* replace "provably" with "grounded in"; mark §1's equivalence claim as a goal.

**INC-08 · medium · "Sensitivity none" conflates "no alternative survived" with "the choice doesn't matter".**
In NOTES §6, A.3 reports `sensitivity none` because only one reading survived. Arch §10.2 says "the same geometry *everywhere* in range", but the check runs at 9 sample points (one-at-a-time sweep plus 2 corners). *Remedy:* add a separate state, "forced: 1 survivor". Say "identical at N sampled points", not "everywhere".

**INC-09 · low · The topology-only hash is described as invariant under legitimate edits, but it isn't.**
`invariants.py` says "constant across legitimate parameter edits", yet `allow_topology_change` exists (NOTES #20) precisely because legitimate edits, such as pattern counts or a fillet consuming a face, change topology. *Remedy:* reword it as "a change is a signal to review".

**INC-10 · low · Stable dotted IDs and hierarchy-from-dots contradict each other.**
gui.md §7.4 says IDs are stable labels that are never rewritten when a node moves. `connections.intent_tree` derives the hierarchy from the dots. After a reparent, `A.P.1` living under `B` will be shown under A. *Remedy:* use opaque IDs plus explicit parents, or rewrite IDs on move.

**INC-11 · low · The lock key misses the lowering code.**
`readings_digest()` hashes reading names, priors and complexity, but not the lowering implementations. Changing what `through_plate` *does* leaves the lock "fresh". *Remedy:* include the dipm version per package and a hash of the lowering source.

**INC-12 · low · Circular data claim.**
Arch §3.4 and §9 say procedurally generated trees give "ground-truth intent by construction". It is ground truth *of the generator's ontology*. A decomposer trained on it learns the generator's intents, not designers'. *Remedy:* say so, and plan a small real-designer corpus for evaluation from day one.

---

## 3. Hacker News (Show HN: dipm, design intent → parametric CAD)

**HN-01 · ex-Pro/E applications engineer.** "'Capture design intent, not coordinates' was PTC's sales pitch in 1988. ICAD and NX Knowledge Fusion did rule packs in the 90s. Every KBE shop I've seen ended with a 40,000-line rule base one retiree understood. What's different this time besides YAML?"
*Fair.* This is NOV-01, NOV-02 and PAIN-04. The honest answer: executable checks tied to kernel history, and an LLM to absorb the cost of authoring them. That answer needs evidence the repo doesn't have yet.

**HN-02 · ML researcher.** "I read the whole README looking for the model. There isn't one. It's a build123d/OCP wrapper with asserts and a very long design doc. Nine 'learned skills' in a table, zero training runs."
*Mostly fair.* This is ISS-04. Unfair in one respect: the survey argues persuasively that the verifier should come first.

**HN-03 · structural/mechanical engineer. Strongest critique.** "The demo bracket shows PASS. Its wall screws sit at 9 and 50 mm up a 150 mm leg because the gusset ate the top. Take moments: ~31 N·m from 20 kg at 160 mm gives ~600 N pull-out on the top screw into drywall anchors, before the safety factor. The 'PASS' is Euler's formula passing. That badge will get someone's shelf on the floor."
*Fair, with the caveat of the simplified model.* This is INC-06, ISS-01 and PAIN-05.

**HN-04 · CAD researcher. Most useful pointer to prior art.** "Read Bidarra & Bronsvoort 'Semantic feature modelling' (CAD 2000). Read Hoffmann & Kim on valid parameter ranges, and Kripac '97 and Capoyleas/Chen/Hoffmann '96 for naming (you cite those, good). Then the Owen/D-Cubed root-identification papers. Your 'stability harness' samples 9 points of a space people have computed exact validity intervals for."
*Fair.* This is NOV-03 and MATH-07.

**HN-05 · CadQuery user. Supportive.** "Ignore the grand vision. `cardinality=exactly(2)`, never trusting `IsDeleted`, ΔH asserts per feature, and 'overlapping compound tool silently cuts nothing' are worth the visit. The spike RESULTS files are the most honest OCCT write-up I've read. Please ship the reference layer as a standalone library."
*Fair.* See GOOD-01 to GOOD-03.

**HN-06 · industrial designer.** "I don't know my intent until I've drawn forty thumbnails and hated thirty-eight of them. This automates the last 20% of my job, the part I already do fine in SolidWorks, and makes me write a requirements doc for the fun part."
*Fair for early ID; less fair for configurators.* This is PAIN-01 and PAIN-12.

**HN-07 · dismissive.** "Tarski, Cartan–Dieudonné, Laman, Euler–Poincaré, r-sets, projective geometric algebra… for an L-bracket with four holes. Mathematical cosplay."
*Half fair.* The report is careful and labels its own uncertainty. The docs, however, carry more theory than the code uses (MATH-05). The Euler check in code is a parity test (MATH-01).

**HN-08 · Onshape power user.** "FeatureScript already has `qCreatedBy`, custom features written the same way as built-ins, tracking queries and attributes. The authors know this because they cite it. Why build a new kernel stack and GUI instead of an Onshape tab plus FeatureScript, where the users and Parasolid already are?"
*Fair as a strategy question.* This is PAIN-09 and the decision in UX §5. A standalone tool is defensible for determinism and for running locally, but the round trip is the deal-breaker in organisations.

---

## 4. Mathematical fundamentals

**MATH-01 · medium · The Euler–Poincaré "check" is a parity test.**
`euler_counts` solves `H = S − (V−E+F−R)/2`, and the check passes if H is an integer ≥ 0 (`invariants.py`). Because H is defined by the formula, the only things that can fail are odd V−E+F−R and H < 0. All the diagnostic power is in ΔH against an *independently* computed expectation. That part is good, and spike 01's blind-hole case proves it. *Remedy:* call it "Euler parity". If a real check is wanted, compute H independently, for example the first Betti number of the boundary from a small homology computation on the face–edge–vertex complex.

**MATH-02 · high · Laman is misapplied to CAD sketch constraints.**
Laman / Pollaczek-Geiringer characterise *generic* rigidity for *distance-only* bar-joint frameworks. CAD sketches mix distances, angles, incidence, parallelism and tangency, and are non-generic by design: collinear points, parallel lines, symmetric layouts. Mixed direction–length frameworks need different counts (Servatius & Whiteley 1999; Jackson & Jordán), and Bouma's normalisation to distance + angle does not restore Laman's theorem. dsl §5.5 "exact in 2D" is wrong for this use. *Remedy:* use structural counting only as a heuristic. Use numeric rank at a witness configuration (Michelucci & Foufou's witness method) as the source of truth, and report "well-constrained at this configuration".

**MATH-03 · medium · The ruler-and-compass core plus branch tags is underspecified.**
Owen's and Fudos–Hoffmann's methods cover decomposable, quadratically solvable systems. Ordinary sketches, such as arc chains with multiple tangencies or a symmetric linkage, are often not decomposable, and they then fall into the "numeric escape hatch". A deterministic seed gives repeatability, not continuity across parameters, and branch flips come back. A side predicate does not always select exactly one root, for example when two roots lie on the same side of L. *Remedy:* define branch tags as sign vectors of orientation determinants per construction step. Track the chosen root by continuation (homotopy) along the parameter path. Fail when the solution crosses a discriminant (a degenerate configuration).

**MATH-04 · medium · r-set closure doesn't buy what it seems to.**
r-sets include non-manifold solids (two boxes sharing an edge) and the empty set, so "a well-formed core tree denotes a valid solid" (dsl §3.1) does not imply a manifold, OCCT-valid B-rep that the Euler formula applies to. The proven core (primitives, planar extrude and revolve, Booleans) also covers almost none of the bracket's interesting features: fillet, countersink, and later draft and shell. *Remedy:* state that the guarantee is r-set-valid, not manifold. Add a manifoldness check (every edge has two face uses). Say plainly that real parts live mostly among the trusted primitives.

**MATH-05 · low · Cartan–Dieudonné and PGA are correct but have no operational role.**
dsl §3.3 lowers transforms to reflections, then re-emits native features. That changes nothing for users or checks. Comparing transforms as versors needs sign canonicalisation and a tolerance, which is not mentioned. *Remedy:* cut it to a footnote. Compare transforms as (rotation matrix, translation) with explicit tolerances.

**MATH-06 · medium · The hashes aren't canonical.**
`adjacency_hash` is a 4-round Weisfeiler–Lehman hash. WL cannot distinguish many regular and symmetric graphs, and CAD parts are highly symmetric, so "topology unchanged" can be a false negative. The docs and the report call it "canonical" (report §3.7 even says nauty-style). Geometric labels round to 6 significant figures, and the role fingerprint uses 6 decimals. Values near a rounding boundary will flip across platforms, which is exactly the cross-platform risk the project names. *Remedy:* use WL as a prefilter, nauty or bliss for exact equality, and tolerance-aware comparison of geometry instead of rounded hashes.

**MATH-07 · high · No tolerance or robustness model.**
Epsilons are scattered and unstated: 1 mm overshoot, +2 mm, 0.01 mm probes, a 1e-9 relative volume tolerance, OCCT's own vertex and edge tolerances. Nothing describes near-degenerate regions of parameter space, such as a hole tangent to an edge or a fillet radius near the wall thickness. Nine sample points will miss thin invalid slivers of the parameter box. *Remedy:* (1) a single documented tolerance policy, (2) a near-coincidence linter (already proposed in the report §7.5), (3) adaptive or interval sampling of the parameter space, or computed validity intervals (NOV-03).

**MATH-08 · medium · Differential geometry is absent, and it is where industrial design's aesthetics live.**
Human packs reduce perception to centroids, radius families and alignment (arch §4.7.1). Industrial designers judge surfaces by G1/G2/G3 continuity, curvature combs, highlight and zebra lines, and how light rolls over a transition. OCCT's rolling-ball fillets are G1, and a "radius family ≤ 2" proxy will happily approve visually harsh tangent-only blends. *Remedy:* add curvature continuity at blends and a highlight-line metric as rung-1 proxies, plus curvature-continuous blend primitives.

**MATH-09 · medium · Uncertainty is labelled but not modelled.**
Assumptions carry `sensitivity: high/medium/low` (arch §4.8; NOTES #25 grades it by volume %, which is blind to a hole moving at constant volume). There is no interval or probabilistic treatment of loads, material scatter (PETG layer adhesion varies a lot) or print tolerances. Rung 2 is called deterministic, which is about repeatability, not validity, and the docs only half acknowledge that difference. *Remedy:* use interval or Monte Carlo propagation for analysis checks, and margins rather than pass/fail. Grade sensitivity by distance between geometries (Hausdorff distance or per-role displacement), not by volume.

**MATH-10 · low · A pinned learned scorer is not automatically deterministic.**
Rung 3 says "deterministic given pinned weights". GPU rendering and inference are not bit-reproducible without care. *Remedy:* specify CPU or deterministic kernels, or treat rung-3 scores as having a noise band.

---

## 5. Human pain points missed

**PAIN-01 · high · Designers often don't know their intent yet.**
Design is co-evolution of problem and solution (Dorst & Cross 2001) and reflection-in-action (Schön 1983). Intent is discovered by drawing. dipm's flow starts from a stated root intent with checks (arch §3, §8.1). In Green's cognitive dimensions terms, it forces premature commitment. *Remedy:* a "loose" mode in which geometry comes first and intent is inferred and confirmed later. Make intent optional per node, and treat unconstrained and unexplained geometry as legitimate draft state.

**PAIN-02 · high · Design fixation and anchoring on defaults.**
"Ask only when it matters" and ranked defaults (arch §10.2) show a single solution. Jansson & Smith (1991) showed that exposure to one example anchors designers, and automation-proposed defaults anchor more strongly. *Remedy:* when readings diverge, or at the root, show several alternatives side by side, as Pareto fronts or thumbnails. Never show a single default first in exploratory phases.

**PAIN-03 · medium · Tacit knowledge doesn't become a rule just because it is encoded.**
Arch §5.2 says "every physical gotcha becomes a permanent check". Much of a designer's judgment is tacit (Polanyi): "this will feel cheap", "the snap will whiten". Encoding it costs time, and wrongly encoded rules over-constrain future designs. *Remedy:* rules carry an owner, a scope and an expiry or review date, and a "why I'm overriding this" path that costs one click.

**PAIN-04 · high · Design-rationale tools died because nobody maintained them.**
IBIS, gIBIS and QOC failed on capture cost borne by someone other than the beneficiary (Grudin's asymmetry; Conklin & Burgess-Yakemovic; Lee 1997). Iteration 2 moves intent to `.intent.yaml`, a second source of truth beside the `.py`. Arch §10.2 also admits "the designer can't be asked about each one". *Remedy:* rationale must be a by-product of actions the designer already takes, such as redlines, accepted proposals and answered questions, never a separate document. Measure staleness, and decay unreviewed nodes visibly.

**PAIN-05 · high · Automation bias: a green PASS on what doesn't matter.**
The GUI header and checks panel (screenshot `bracket-why-light.png`) show PASS and "all pass" for validity, Euler, ΔH, ΔS and volume. These are developer invariants. None of R.c1–R.c4 runs (NOTES TODO 4). Parasuraman & Riley (1997) and Lee & See (2004) predict the outcome: users will trust the badge. *Remedy:* the headline status must be about intent checks, for example "Kernel OK · 0 of 4 intent checks implemented". Show unverified checks as grey "not checked", never as green.

**PAIN-06 · medium · Explanation overload and engine jargon.**
Columns for Euler, ΔH and ΔS; `sensitivity none`; `exposed_region_midpoint`; `through_plate`; `A.P.holes.countersink(1)`. These are the right things for a kernel engineer and noise for a designer. *Remedy:* two audiences, two views. In designer view, show invariants only when one fails, and translate it: "the shelf screw no longer goes all the way through; it hits the gusset".

**PAIN-07 · medium · The intent tree adds cognitive load at scale.**
The bracket has 9 intent nodes for 6 features. Real products have hundreds of features across assemblies, plus a feature tree, an assembly tree and a BOM. A third hierarchy of purposes with dotted IDs will be pruned or ignored. *Remedy:* fold the intent tree into the feature tree as annotations by default. Allow many-to-many links without forcing a strict hierarchy. Test with a 150-feature real part early.

**PAIN-08 · high · Handoff to engineering and manufacturing is missing.**
There are no datums, tolerances, GD&T, surface finish or drawing standards. Yet tolerances are where design intent is legally and practically recorded (Requicha's own tolerancing theory, 1983; ASME Y14.5). UX §1 says "geometry is not committed", which collides with release culture. Released parts are frozen geometry with part numbers and ECOs, and a kernel upgrade must never silently change a released part. *Remedy:* a "release" step that freezes STEP plus a hash, and treats any rebuild difference as an ECO. Put datum and tolerance intent in the DSL roadmap before human packs.

**PAIN-09 · high · Round-trip editing.**
UX §4: "hand edits in Onshape don't flow back". In any team, engineering will edit in SolidWorks or Onshape the day after handoff, and the intent tree goes stale at once. *Remedy:* make the Onshape-tab or FeatureScript path (UX §5 option 2) the primary integration earlier, or limit the product to cases where dipm stays the source of truth (configurators, generated families).

**PAIN-10 · medium · Aesthetics beyond proxies, and the Birkhoff lesson.**
Birkhoff's *Aesthetic Measure* (1933, M = O/C) and generations of golden-ratio rules failed for the same reason the human packs risk failing. Proxies reward order and penalise the deliberate tension that good form uses. Arch §4.7.1 acknowledges Goodhart's law, but named styles such as "minimal_industrial" turn a culture into a checklist. CMF (colour, material, finish), surface quality and context are absent. *Remedy:* treat perception proxies as lint the designer can switch off, never as optimisation targets. Collect preferences from designers, not crowds.

**PAIN-11 · medium · Learning curve and culture.**
The workflow assumes Python, YAML and git. Most industrial designers work in Rhino, SolidWorks, KeyShot and paper, and version with file names because their tools give them nothing better. Branches as design alternatives (UX §2) is a good idea that needs a GUI, not git. *Remedy:* hide git behind "save alternative / compare / merge" in the GUI. Make Python authoring a power-user path.

**PAIN-12 · medium · Stating intent explicitly has a cost, and the system's guesses become the designer's intent.**
When the system infers intent (interpretations, model-made assumptions), the rationale records the *model's* reading under the designer's design. Over time, nobody can tell what was meant and what was guessed. `made_by` exists but is buried. *Remedy:* make model-made and unreviewed items visibly different everywhere, and let them expire into "unknown" rather than harden into fact.

**PAIN-13 · low · Geometry that changes on its own.**
The server shows the old lock's choice, then rebuilds 2.5 s later with new interpretations (NOTES #38). Geometry moving without a user action undermines trust. *Remedy:* show "re-resolving…", and require a click when the result differs.

---

## 6. Top 10 issues, ranked by severity

| ID | Sev. | What | Why it matters | Where | Remedy |
|---|---|---|---|---|---|
| **ISS-01** | high | PASS badge with no intent checks; the demo likely fails its load intent | False assurance; automation bias | GUI header; NOTES TODO 4; arch §8.1 R.c1 (INC-06, PAIN-05) | Status line reports intent checks; implement R.c1 as a hand-calc first |
| **ISS-02** | high | Interpretations use invariants to select geometry | Negative controls become silent fixes; checks lose independence | NOTES #28, #32; `interpret.py` (INC-04) | Ask on extra interaction; hold-out checks; "selected" ≠ "verified" |
| **ISS-03** | high | Determinism claim leaks (lock, prefs, warm start, background re-resolve, BRepOffset) | The project's central guarantee is weaker than stated | arch §1 p2, §7; NOTES #26, #30, #38 (INC-01) | Define "fully locked solution"; fail closed without a lock |
| **ISS-04** | high | No model; nine learned skills with no data; the training-data argument is circular | Headline overclaims; the hardest part is untested | README; arch §3.4, §9 (INC-12) | Reframe v1 as a verifier for agents; build a small real-designer eval set |
| **ISS-05** | high | Core prior art missing (semantic features, KBE, design rationale, SE allocation, parameter-range validity) | Reinvention; misses known failure modes | survey; explore-further (NOV-01 to NOV-03) | Prior-art section; narrow the novelty claims |
| **ISS-06** | high | Handoff and round trip: no tolerances or datums; geometry uncommitted; one-way export | Blocks use in any team | UX §1, §4 (PAIN-08, PAIN-09) | Release/freeze step; datum and tolerance intent; Onshape path sooner |
| **ISS-07** | high | Laman "exact in 2D"; no tolerance or robustness model | Constraint-health and stability verdicts may be wrong | dsl §5.5; scattered epsilons (MATH-02, MATH-07) | Witness-rank checks; one tolerance policy; adaptive sampling |
| **ISS-08** | medium | Assumes known, stateable intent; fixation on defaults | Misfit with early-stage ID | arch §3, §10.2 (PAIN-01, PAIN-02, PAIN-12) | Geometry-first loose mode; show alternatives |
| **ISS-09** | medium | Literals and convenience couplings in the canonical example | Undermines principle 1 in its own showcase | `shelf_bracket.py`; arch §2.2, §5.1 (INC-02, INC-03) | Separate params; classify ratios; fix the metric |
| **ISS-10** | medium | Hashes called canonical; Euler check is parity; "sensitivity none" is ambiguous | Misleading signals in the place meant to be exact | `invariants.py`; NOTES #25 (MATH-01, MATH-06, INC-08) | Rename; nauty for equality; a "forced" state |

---

## 7. What the project gets notably right

**GOOD-01. The reference layer.** References name entities by creator, role and source, declare their cardinality, never use ordinals, never trust `IsDeleted`, and treat split and merge as events with policies. This is the correct synthesis of the persistent-naming literature, and it is tested (`refs.py`, dsl §3.4).

**GOOD-02. Per-feature contracts computed from interaction.** ΔH, ΔS and volume sign are derived from how a feature meets existing geometry. Spike 02 found the "silently wrong but valid" class, an overlapping compound tool that cuts nothing, which BRepCheck and Euler both miss. That finding is useful to everyone working on OCCT.

**GOOD-03. Epistemic honesty.** The report labels claims confirmed, corrected or unverified. The spikes record negative findings (BRepOffset nondeterminism, the STEP counter). The NOTES mark known gaps, including the interpretation gap that ISS-02 builds on. Few projects of this kind write things down this well.

**GOOD-04. Verifier before model.** The survey's conclusion, that the DSL, compiler and benchmark matter more than the model, is correct, and the build order follows it.

**GOOD-05. "Direct manipulation edits intent, not coordinates"** (UX §3), and treating an edited intent as a *stale* solution rather than pretending the geometry updated (gui.md §7.1). Both are sound HMI choices.

**GOOD-06. The "why is this here?" inspector.** Every face traces back to the feature, the intent word and the intent node (screenshot). This is the most designer-legible thing in the repo.

**GOOD-07. The walkthrough and prototype-plan idea** (arch §5.2). Planning *which coupon to print* from high-sensitivity assumptions matches how good designers actually work.

# Review Response and Action Plan

*Started 2026-11-16. Source: [`reports/Fresh eyes review.md`](../reports/Fresh%20eyes%20review.md) (65 items), the author's response in [`reports/Fresh eyes review.response.md`](../reports/Fresh%20eyes%20review.response.md), and the structured items in `reports/Fresh eyes review.items.json`. Item IDs below refer to those files.*

## Positioning that came out of the review

The author disagreed with HN-06 ("this automates the last 20% and makes me write a requirements doc for the fun part"), and the disagreement sharpens who dipm is for:

> When designing a product that connects many complex off-the-shelf components, each with electrical, mechanical, thermal and human-interface constraints, hours go into drawing sketches, defining features and editing the feature tree. That work feels like typing code without autocomplete or LLM help.

**dipm's first target is integration-heavy detail design:** turning known constraints from components, interfaces and manufacturing into well-structured parametric models. That is the "autocomplete for the feature tree". Early, exploratory ideation, where intent isn't known yet (PAIN-01, ISS-08, which the author strongly agreed with), is a real and separate need. The architecture must not *assume* stated intent, but it is not the first thing to optimize. See work item E1.

## Work items

Status: ☐ open · ◐ in progress · ☑ done

### A. Honesty and correctness fixes in the docs (no code)

| # | Items | Action | Status |
|---|---|---|---|
| A1 | NOV-01..04, ISS-05 | Add a **prior-art section** (semantic feature modelling: Bidarra & Bronsvoort 2000; Shah & Mäntylä 1995; valid parameter ranges: Hoffmann & Kim, Joan-Arinyo; KBE; SE requirement allocation; Gero FBS; IBIS/QOC/DRed; design-intent rubrics: Company, Contero, Camba, Otey). Narrow the novelty claims to the concrete new parts | ☑ 2026-11-16: architecture §1.1; survey errata; explore-further §5. Citations checked except Company 2015 co-authors, Jackson & Jordán, and KBE/PDQ product names. Papers themselves not yet read |
| A2 | INC-07, MATH-04/05 | Remove or qualify "proven" language. State what r-sets, Cartan–Dieudonné and PGA actually buy (or don't) | ☑ 2026-11-16: dsl §1, §3.1 (r-sets not manifold), §3.3 note, §7; arch §2.2; CLAUDE.md |
| A3 | MATH-01, ISS-10 | Describe the Euler check honestly: with H solved from the formula it is a parity/integrality test. The real protection is the per-feature ΔH/ΔS contracts | ☑ 2026-11-16: dsl §5.2, arch §4.1, CLAUDE.md, math-report errata |
| A4 | MATH-02, ISS-07 | Correct Laman: it covers 2D bar-joint (distance) rigidity, not CAD sketches with angles, tangency or incidence. Point to the proper constraint-solver literature | ☑ 2026-11-16: dsl §5.5 (Servatius & Whiteley, decomposition survey, witness method), math-report errata, explore-further §1 |
| A5 | INC-01, ISS-03, MATH-10 | Restate determinism precisely: deterministic *given* source + lock + prefs + pinned kernel; name where non-determinism lives (interpretation resolution, background re-resolution, learned scorers) | ☑ 2026-11-16: arch principle 2 and §7 (where non-determinism lives), §4.1 rung 3, README, CLAUDE.md |
| A6 | INC-09, MATH-06 | Stop calling hashes "canonical"/"invariant" where they aren't; define what each hash is stable under | ☑ 2026-11-16: dsl §5.4 table of what each hash is stable under; arch §7; CLAUDE.md |
| A7 | INC-12, ISS-04 | Fix the circular "ground truth by construction" data claim: procedural data teaches the generator's intents. State what real-designer data is needed and how to get it | ☑ 2026-11-16: arch §3.4, §4.6, §9 (real-designer data and sources) |
| A8 | INC-02/03/06, ISS-09 | Annotate the worked example: literals that aren't design parameters, the convenience coupling, and the likely load-check failure | ☑ 2026-11-16: arch §8.1, §8.4a, §8.6 notes. The actual fix is B2 |

### B. Engine and GUI fixes (after GUI iteration 2 lands)

| # | Items | Action | Status |
|---|---|---|---|
| B1 | ISS-01, PAIN-05 | **No bare PASS.** Show which tiers ran ("kernel invariants ✓ · intent checks: none run"). Never a green badge for checks that didn't run | ☐ |
| B2 | ISS-01, INC-06 | Implement R.c1 (load) as a rung-2 hand-calc check, plus tool access (R.c4). Expect the bracket to **fail** and redesign it honestly | ☐ |
| B3 | ISS-02, INC-04/05 | Interpretations must not let invariants select geometry unchecked. Separate "feasible" from "meant"; require an intent-level check before a survivor counts as resolved; a check compiled into a construction must still be independently verified | ☐ |
| B4 | INC-08 | Split "sensitivity none" into **forced** (only one reading survives) vs. **insensitive** (readings agree); grade by geometric distance, not volume % | ☐ |
| B5 | PAIN-12, PAIN-13 | **Model-made/unreviewed items are visually distinct** from designer-made/designer-reviewed ones, everywhere: tree, inspector, interpretations, assumptions. Unreviewed guesses can expire to "unknown". Geometry never changes "on its own" without a visible cause | ☐ |
| B6 | INC-11 | The lock key includes the lowering code / package versions, not just the design file | ☐ |
| B7 | INC-10 | Reconcile stable ids with hierarchy-from-dots (affects iteration 2's move/reparent) | ☐ |
| B8 | PAIN-06, PAIN-07 | Plain-language UI and progressive disclosure: engine terms (ΔH, ledger, genus) behind a details toggle; scale the tree (focus, folding, search) | ☐ |
| B9 | Iteration 2 review (NOTES #44–57) | Changes the author requested: intent-file header note on comment attachment (#44); remove duplicate wording from code tags (#45); no automatic review baseline, with a one-time prompt instead (#48); migrate preferences on rename, plus an optional feature-id rename checkbox (#49); show before/after at the current GUI parameters and highlight outline-changed faces (#53); **"Accept anyway…" with a recorded override** for failing proposals (#54); rename "Ask Claude" to "Queue for Claude" with a waiting-requests status (#55); an "inspection paused" note in comparison view (#57). Later: cross-process lock (#47), MCP audit log (#51), proposal housekeeping (#52), automatic request pickup (#55) | ☐ |

### C. New first-class concerns (to discuss, then design)

| # | Items | Topic | Status |
|---|---|---|---|
| C1 | MATH-07, MATH-09 | **Tolerance and uncertainty as first-class concerns.** One documented tolerance policy; a near-coincidence linter; interval or Monte Carlo propagation of loads, material scatter and print tolerance, with margins; validity intervals instead of 9 sample points | ☑ decided → [`tolerance-uncertainty.md`](tolerance-uncertainty.md) |
| C2 | MATH-09 (author's note) | **Visualizing uncertainty and scale.** Show tolerance/uncertainty in the viewport. Use **photographic scale cues** (e.g. depth of field that narrows when zoomed in close, as with a real macro lens) so small features read as small | ☑ decided → [`tolerance-uncertainty.md`](tolerance-uncertainty.md) |
| C3 | PAIN-09, ISS-06 | **Onshape parity:** verify that every dipm parametric tree can be recreated with native Onshape API / FeatureScript calls; find the gaps | ◐ researched → [`research_notes/Onshape parity/onshape-api-parity.md`](../research_notes/Onshape%20parity/onshape-api-parity.md); strategy in user-experience §4.1 |
| C4 | PAIN-04 | Rationale capture cost. Make rationale a by-product of actions the designer already takes (redlines, accepted proposals, answers) rather than separate authoring | ☐ discuss |
| C5 | MATH-08, PAIN-10 | Differential geometry for ID aesthetics (curvature continuity, highlight lines, zebra), beyond proxy checks | ☐ later |

### D. Later

| # | Items | Topic |
|---|---|---|
| D1 | PAIN-08 | Handoff to engineering and manufacturing: drawings, GD&T, tolerances, BOMs |
| D2 | PAIN-11 | Learning curve; versioning culture for designers |
| D3 | PAIN-09 | **Onshape export, standard features first:** all geometry as standard features driven by `#variables` (user-experience §4.1) |
| D4 | PAIN-09 | **dipm FeatureScript placement library:** `centered_on`, `distribute`, … as versioned custom features that output locating points for native Hole features |
| D5 | PAIN-09 | **dipm checks feature** at the end of the Onshape tree: re-run intent checks natively, so engineer edits that break intent show as warnings |
| D6 | PAIN-09 | **dipm as a public Onshape App Store app.** Calls from publicly listed apps don't count against the per-user API cap (2,500/yr on Standard). The author exhausted that cap having an LLM edit designs by verbal instruction. As a listed app, dipm could make that workflow sustainable. Verify the exemption's terms, app-review requirements, and OAuth flow first. This revisits the "inside Onshape" option in user-experience §5 |

### E. Strategy

| # | Items | Topic |
|---|---|---|
| E1 | PAIN-01/02, ISS-08 | **Exploration and unknown intent.** Support intent as a *hypothesis*: sketch-first, several alternatives side by side (branches), intent inferred from what the designer does, and negotiation between competing constraints. Avoid anchoring on defaults (fixation) |
| E2 | ISS-04, NOV-05 | The model: what "learned" means concretely, what data it needs, and who the first adopters are (integration-heavy detail design, per the positioning above) |

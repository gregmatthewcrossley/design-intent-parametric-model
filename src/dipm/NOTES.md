# dipm: v0 DSL core (notes for review)

*Written 2026-11-16, unattended. First non-spike code in the repo. Nothing in `docs/`, `spikes/`, `CLAUDE.md` or `README.md` was edited; doc updates are left for the coordinator. Section references (§) are to `docs/dsl.md` unless marked "arch" (`docs/architecture.md`).*

`dipm` ("design-intent parametric model", pronounced "dip-em") is the project and package name, confirmed by the user on 2026-11-16 (DECISIONS #1).

---

## 1. Architecture overview

A design is an ordered list of features plus declared parameters. Feature arguments are lazy: parameter expressions, structural references and relational placements. `Design.build(**params)` is a pure function. It makes a fresh `Context`, evaluates each feature on raw OCP, carries the reference ledger through every operation's history, and runs the invariants after every feature.

| Module | What it does | dsl.md / architecture.md |
|---|---|---|
| `kernel.py` | The backend boundary. Thin raw-OCP helpers: `Vec3`, sub-shape maps, `occ_list` (fast list iteration), measures, normals, booleans that always take a **tool list**, transforms, BRep/STEP I/O, STEP canonicalisation. Parallel BOP is pinned off. | §6.2, §6.3 |
| `expr.py` | Lazy expressions over parameters (`0.75 * shelf_depth`, `clearance(screw)`), and `Param` (default, range or choices, sweep samples). | arch §2.2 "literals only for true design parameters", arch §6 |
| `sketch.py` | v0 profiles: a `Plane`, plus `Profile` with **named points** (expressions or small constructions: `midpoint`, `between`, `offset`, `line_line`, `on_side`) and **named edges** that become reference sources. Checks for zero-length edges, self-intersection, zero area, and the **winding branch tag**. | §3.2 (partial, no solver) |
| `refs.py` | The reference layer. `Tag(feature, role, source)`; `Ledger` carries tags through `Modified`, presence in the result, and opt-in same-type `Generated`. Splits and merges are genealogy events, and `IsDeleted` is never trusted. `Ref` has declared cardinality (`one`/`exactly`/`at_least`) and policies (`propagate_all`, `error_on_split`, `error_on_merge`). `edges_between` is the derived reference. | §3.4 |
| `invariants.py` | Validity (BRepCheck, null, positive volume); Euler–Poincaré under the validated counting rule; ΔH, ΔS and volume sign against each op's `Expect`; signature = (V,E,F,R,S,H) + geometry WL hash + topology-only WL hash + order-free role-geometry fingerprint; canonical bytes (BRep text, or fingerprint JSON for non-byte-deterministic ops). | §5.1–5.4, §5.6 |
| `ops.py` | Core and trusted ops on raw OCP. Each declares roles, `Expect` (ΔH/ΔS/volume sign, computed from interaction where needed) and failure classes. Ops: `Extrude` (new/add/cut), `Revolve` (new/add/cut, with the full-revolve fallback), `Fillet`, `Chamfer`, `Transform`, `Mirror` (+ history-chained `clean`), `Clean`, `Shell` (inward with openings), `Draft` (follow-Generated). | §3.1, §3.3, §4.3; spike 02 §2, §6, §7 |
| `intent_layer.py` | The intent layer. Relations computed from resolved references: `centered_on`, `face_point`, `centerline(...).before(ref, clearance)`, `.midpoint()`, `midpoint`, `distribute`, `linear_pattern`, `circular_pattern`, `at` (literal escape hatch). A v0 fastener table: `clearance`, `countersink`, `edge_distance`, `tool_access_radius`. **`Hole`** lowers to one core cut with a tool list and per-instance roles `wall(k)`, `countersink(k)`, `floor(k)`; its ΔH comes from interaction. | §4.1, §4.2; arch §8 |
| `program.py` | `Design` (params, features, exports, convenience constructors, `use_lock`), `IntentTag`, `Context` (the resolver, which logs every resolution, and `interpret()` for ambiguous slots), `Build` (records, exports, signature, `canonical()`, **`why(sub)`**, `slots`, `interpretation`), `FeatureRecord`. | §1 (tags survive lowering); arch §2, §7 |
| `interpret.py` | **Interpretations** of ambiguous intent-word slots: `Reading`/`ReadingSet`, elimination by checks over the stability sample points, sensitivity, ranked default, `Assumption`/`Question`/`Notice` records, `Preferences` (remembered answers), the lock file. See §6. | arch §10 item 2, §4.8, §7 |
| `stability.py` | The stability harness. Snapshots exports, every feature's input resolutions and every ledger tag (cardinality + genealogy), plus VEFRSH and the topology hash. `run()` (one-at-a-time sweep plus corners), `grid_points()`, `edit_test()`. | §5.7; arch §6 edit stability, §8.6 |
| `report.py`, `cli.py`, `__main__.py` | Human-readable report and the `python -m dipm` CLI (`build`, `stability`, `interpret`, `answer`, `serve`). | — |
| `connections.py` | Intent ⇄ feature ⇄ parameter views for the GUI: parameter dependencies (deep walk of feature arguments), the intent tree derived from tags, connection diagnostics (#34–#36). | docs/gui.md §2 items 4, 9 |
| `server/` | `dipm serve`: Starlette app (`app.py`), build → JSON (`serialize.py`), deterministic tessellation with face/edge identity (`mesh.py`). The browser frontend lives in `gui/` and builds into `server/static/` (gitignored). | docs/gui.md §5 |
| `errors.py` | Structured errors: `InvariantError`, `CardinalityError`, `PolicyError`, `InteractionError`, `SketchError`, `KernelError`, `ParameterError`. Each names the feature, its intent tags, the invariant, and expected vs. got. | §4.3 failure classes |

**Where intent lives in a result.** Each `FeatureRecord` holds its intent tags, the core op it ran (`op`), and the intent word it was lowered from (`lowered_from`, e.g. `hole(countersink, through_all)`). It also holds per-instance tags (`k=1 → hole@A.P.2`). `Build.why(face_or_edge)` joins the ledger entry, the record and the event history:

```
face: Cone axis=(0, 1, 0) half-angle=45deg
  created as A.P.holes.countersink(1)  [op cut lowered from hole(countersink, through_all)]
  intent: hole@A.P.2, pattern@A.P (wall screw pattern), wall_mount@A  history: A.P.holes:modified
```

An edge that no feature tagged is explained as `edges_between` its adjacent faces, each with its own genealogy. On the bracket, all 19 faces have a genealogy.

## 2. Install, run, test

From the repo root, using the existing `.venv`:

```bash
uv pip install --python .venv/bin/python -e .          # deps pinned to spike 01's lock
.venv/bin/python -m dipm build examples/shelf_bracket.py                       # report
.venv/bin/python -m dipm build examples/shelf_bracket.py -p shelf_depth=300 -p t=8 -p screw=#10
.venv/bin/python -m dipm build examples/shelf_bracket.py --faces               # + "why is this here?" per face
.venv/bin/python -m dipm build examples/shelf_bracket.py --out out --step      # writes out/*.brep, *.step (gitignored)
.venv/bin/python -m dipm stability examples/shelf_bracket.py                   # sweep declared ranges
.venv/bin/python -m dipm interpret examples/shelf_bracket.py                   # re-resolve interpretations, write the lock
.venv/bin/python -m dipm answer examples/shelf_bracket.py <assumption-id> <reading> --prefs prefs.json
.venv/bin/python examples/shelf_bracket.py                                     # same report, as a script
.venv/bin/python -m dipm serve examples/shelf_bracket.py                       # web GUI on 127.0.0.1 (build gui/ first)

.venv/bin/python -m pytest -q                                                  # all tests (~25 s)
.venv/bin/python -m pytest -q tests/test_bracket.py::test_edit_t_5_to_8        # one test
```

The CLI exits 0 on PASS, 1 if any invariant or reference fails (the report says which), and 2 on bad parameters.

Tests: `test_refs.py` (resolution, cardinality, split/merge policies, `edges_between`, draft follow-Generated, IsDeleted distrust), `test_invariants.py` (counting rule, the ΔH/ΔS/volume negative controls, signature, canonical fallback, readable errors), `test_ops.py`, `test_sketch.py`, `test_why.py`, `test_bracket.py` (§8.6 edits, the stability harness, in-process and cross-process determinism), `test_cli.py`, `test_interpret.py` (§6: the bracket's zero-question outcome, elimination, divergence/questions on a C-channel, preferences, explicit bypass, opt-in `between_siblings`, the default-overridden notice on the spike-01 negative control, determinism, lock round trip and staleness, the `interpret`/`answer`/`build` CLI round trip). `test_connections.py` (intent tree, parameter dependencies, diagnostics) and `test_server.py` (every `dipm serve` endpoint, mesh format and determinism, the answer round trip, failure payloads, reload and WebSocket events). Frontend tests live in `gui/` (`npm test`, `npm run e2e`; see `gui/README.md`).

## 3. DECISIONS

Items marked **[REVIEW]** are the ones most worth your attention in the morning.

> **User review, 2026-11-16:**
> - **Approved:** #1, #2 (a dedicated textual DSL may come later), #4, #6, #9 (rule packs get a deeper pass later), #13 (after explanation), #15.
> - **Questioned:** #8, which led to the general "interpretations" mechanism proposed in `docs/architecture.md` §10 item 2.
> - **Change requested:** #11. Hole extents should be resolved by the same interpretation mechanism rather than hard-coded per hole.

1. **Package name `dipm`**: confirmed 2026-11-16 as the project and package name, pronounced "dip-em" (plain `dip` is taken on PyPI, npm, crates.io and RubyGems). Originally a placeholder ("design-intent parametric model"). Renaming means one directory rename plus the imports and `pyproject.toml`.
2. **[REVIEW] Embedded Python, design-as-data.** Features are frozen dataclasses with lazy arguments, appended to a `Design` in order. A build re-evaluates them against a parameter dict in a fresh `Context`. I preferred this to a CadQuery-style imperative script that would be re-run, because it keeps the program inspectable: relations vs. literals can be counted, references are listed, and tags are attached. It is not yet a separate textual DSL or a canonical core IR.
3. **Hierarchical feature ids are prefixed by the intent node** (`R.body`, `C.gusset`, `A.P.holes`, `A.3.cable`, `B.1.screw`, `R.fillet`). They also carry explicit `IntentTag(node, word, note)`s, including the parent node (`wall_mount@A`) and per-instance tags (`A.P.1`, `A.P.2`). Reference strings therefore read `A.P.holes.wall(0)`.
4. **[REVIEW] Lowering happens inside each intent feature** (`Hole.apply` emits one core boolean cut). It is recorded as `op` + `lowered_from`. There is no separate core-IR pass yet, so "equivalence is decided on the core" (§1) is **not** implemented.
5. **Reference sources are strings.** A fillet blend's source is the input reference's text (`R.fillet.blend(R.body.lateral_edge(inner))`); a mirror image's source is the original tag. Cap-boundary edges are not tagged at creation: they are named with `edges_between`, and `why()` derives them. Only extrude lateral edges, revolve circle edges, and hole/fillet/chamfer faces get edge or face tags. That gives full face coverage on the bracket.
6. **[REVIEW] No constraint solver tonight.** Sketch points are parameter expressions or small constructions (`midpoint`, `between`, `offset`, `line_line`), and the `on_side` construction is an explicit branch tag. Profiles carry a declared **winding branch tag** (default `"ccw"`), so a parameter edit that flips the profile fails loudly. Lines only: no arcs or circles in profiles. **The real constructive solver (§3.2, §6.2) is the next piece of work.**
7. **ΔH from interaction.** Each through-hole instance adds +1 **only if** its tool is disjoint from every other hole tool, both earlier holes and other instances of the same feature. Contact raises `InteractionError` unless the author declares `expect={"dH": ...}`; the test shows a declared crossing gives +2, as spike 01 found. The interaction probes are clipped at the face, so tool overshoot above the face doesn't count. Hole-vs-solid interactions (e.g. a hole that turns blind on the gusset) are deliberately left to the ΔH invariant. Extrude `add` must touch the body and `cut` must overlap it, or they raise early; their ΔH defaults to 0 and is declared by the author.
8. **[REVIEW] A.3 cable hole: "centred on the plate".** *(Superseded 2026-11-16 by the interpretations mechanism, #24: A.3 is now `centered_on(mount_face)` and the same point is reached by elimination. Original text kept for the record.)* The plate is read as **the exposed part of the mount face**: the midpoint of the mount face's vertical centreline, cut off at the gusset footprint (`centerline(mount_face, Z).before(gusset.lateral_edge("down")).midpoint()`), horizontally centred. A literal `centered_on(mount_face)` is impossible here, because the face centroid lies **under the gusset footprint** at every `shelf_depth`: the gusset bottom is at 0.35·d − t and the plate centre is at ≈0.375·d − t/2. This is a finding about §8.4a option 2. The chosen relation never references the screw pattern, so the §8.6 "move wall pattern" edit can tell the two readings apart: changing `screw` moves the lower screw while the cable hole stays put (tested). At the defaults the cable is at z = 32.5 and `between(wall_pts)` would be at z = 29.5.
9. **[REVIEW] Fastener values are uncited stand-ins for a `fasteners` rule pack.** Clearance Ø: #6 3.7, #8 4.5, #10 5.2, M3 3.4, M4 4.5, M5 5.5 mm. Head Ø (90° countersink): 7.2 / 8.6 / 9.8 / 6.3 / 8.4 / 10.4. Edge distance = 2×Ø (arch §8.2). Tool access = Ø30 (R.c4), independent of screw size.
10. **Parallel BOP is pinned off** (`BOPAlgo_Options.SetParallelMode(False)` and `SetRunParallel(False)`). Spike 01 saw no difference with it on, but only on one machine, so this removes one variable for cross-platform runs.
11. **[REVIEW] Hole extents.** *(Changed 2026-11-16 per the user's review: extents are now interpreted, #23. `through(t)`, `blind(d)` and `THROUGH_ALL` remain as explicit, author-made extents. Original text kept for the record.)* `THROUGH_ALL` uses a tool as long as the body's bounding-box diagonal + 2 mm. `through(thickness)` means "through this plate": the tool is the thickness + 2 mm. If something backs the plate, the hole turns blind and **ΔH catches it**, which is spike 01's negative control. B.1 uses `through(t)` for exactly that reason. Tools start 1.0 mm outside the face (as in the spikes). Countersinks are 90° cones sized so the head Ø is at the face.
12. **`shelf_depth` range is 180–300 mm**, not the spike's 150–300. At 150 with t=8 the cable hole meets the lower countersink. The interaction check catches that loudly (tested), but it falls outside the design's intent. `t` is 4–8; `screw` is #6/#8/#10.
13. **[REVIEW] The topology-only hash excludes surface type *and* curve type.** Node label = wire count + edge-use count; edge label = seam or not. A box and a 90° revolved block hash equal (tested). The geometry hash keeps the spike-01 labels.
14. **ΔS counts shells** (§5.2's S, so void shells count). Solid count is recorded but not separately checked.
15. **[REVIEW] `clean()` (UnifySameDomain) is explicit, not automatic.** It is a `Clean` op and runs by default inside `Mirror`, history-chained so `merged` events reach the ledger. Booleans do **not** auto-clean. Spike 02 recommended always running it after booleans; I held back to keep v0's topology identical to the spikes' and to avoid surprise merges while there is no merge-warning UX. This is easy to flip.
16. **Shell is limited to inward shells with ≥1 opening**, the byte-deterministic case. The fingerprint canonical form for BRepOffset join-mode ops is implemented and tested with a stand-in op, but no real join-mode op ships in v0.
17. **Single-body designs.** `mode="new"` is allowed only for the first feature, and `add` must touch the body.
18. **Failure modes.** `build()` raises the first `DipmError` by default. `build(on_fail="record")`, which the CLI uses, records failures and continues after ΔH/ΔS/volume failures, but stops after a validity/Euler failure or a kernel exception.
19. **Volume sign** is `'+'` for add/mirror, `'-'` for cut/hole/shell, `'0'` for transform/clean, and "any nonzero" for fillet/chamfer/draft (the sign depends on convexity).
20. **Stability harness defaults.** Each parameter is swept one at a time over (lo, default, hi), or over every choice, plus the all-lo and all-hi corners. Each point is compared with the defaults build on cardinality and genealogy of exports, feature inputs and ledger tags, and on VEFRSH plus the topology hash. `allow_topology_change(params)` lets the author declare legitimate flips. The bracket test also runs the full 12-corner grid.
21. **build123d is a pinned dependency but is not imported.** All modelling is raw OCP (`cadquery-ocp-novtk 8.0.1.1`) so that history is available.
22. **Housekeeping:** `pyproject.toml` (src layout) at the repo root; `.gitignore` gains `*.egg-info/` and `out/`.

*Decisions 23–31 were added 2026-11-16 with the interpretations mechanism (§6).*

23. **[REVIEW] Hole extents are interpreted** (the #11 change). `d.hole(...)` with no extent leaves it to three readings, in prior order:
    - `through_plate` (package default; complexity 2): the tool runs through "the plate", meaning the face plus its **nearest opposing parallel planar face whose in-plane extent overlaps it**. The tool is that distance + 2 mm. If more material backs the plate, the hole turns blind and ΔH catches it, which keeps spike 01's negative control.
    - `through_all` (complexity 1): the tool spans the body diagonal. **Expected ΔH = the number of separate material layers the axis crosses** (previously 1 per instance). Drilling a C-channel through both flanges is +2 and is correct.
    - `up_to_next` (complexity 3): the first run of material along the axis **and along 16 lines around the bore**, so that an oblique exit face (the gusset hypotenuse) is cleared across the whole diameter. The first, axis-only version left a step at oblique exits, and that made it diverge from `through_all` on the negative control. Sampling is deterministic but approximate; the 1 mm overshoot covers the residual.

    `blind(d)` and `through(t)` are explicit-only. Any explicit extent is recorded `made_by: author`.
24. **[REVIEW] `centered_on(face)` readings and "exposed region".**
    - `face_centroid` (package default, prior 1): the face's area centroid, as before.
    - `exposed_region_midpoint` (prior 2): the face minus the footprint of material attached to it. Holes and slots are voids, not cover, so they are bridged. Through the centre of the face's bounding rectangle (in-plane axes = the global axes most perpendicular to the normal), take the face's material chords along each axis. Bridge every gap where the point 0.01 mm above it (along the normal) is not inside the solid. The longest bridged chord wins (first axis on a tie), and its midpoint is the point.
    - `between_siblings` (opt-in via `consider=("between_siblings",)`): the mean centre of earlier holes on the same face. It is opt-in because it **adds a coupling** to sibling features that "centred on the face" does not state (§8.6, "cable hole does not move"). Offering it by default would ask a question about a dependency the author never implied.

    **Limits:** the chord rule only looks along two axes through the bounding centre, so an L- or ring-shaped exposed region can pick an off-centre chord. Faces are planar and axis-aligned for exactness. An alternative worth reviewing is making `exposed_region_midpoint` the package default, since it is what a designer looks at. That would remove the A.3 notice (#28) but change `centered_on` for faces with prior holes, where the area centroid shifts.
25. **[REVIEW] Sensitivity grading.** Surviving readings are compared with the chosen one at every sample point on (V,E,F,R,S,H), the role-geometry fingerprint, and volume (relative tolerance 1e-9).
    - **none:** identical everywhere.
    - **high:** topology differs anywhere, or |ΔV|/V ≥ 1 %.
    - **medium:** differs at ≥ half the points, or |ΔV|/V ≥ 0.1 %.
    - **low:** otherwise.

    A moved feature with equal volume and topology at every point is therefore "medium". A "default overridden" slot is forced to "high" (#28).
26. **[REVIEW] Resolution algorithm.**
    - **Sample points** are the stability harness's points: defaults first, then the one-at-a-time sweep, then the corners (9 for the bracket).
    - **Slots** are discovered by building (each intent word calls `Context.interpret`). Their ids are `<feature>/<word>.<slot>`, with `#2`… only if one feature has two distinct slots of the same word.
    - **Order:** each slot is resolved in build order, with every other slot at its *current* choice (Gauss-Seidel). This repeats until no choice changes or no new slot appears (at most 4 passes). The **full product of readings across slots is never explored**, so a pair of slots that only fail or diverge in combination can be missed.
    - **Blame rule.** A failure at the slot's own feature counts unless every reading fails the same way there; that case is recorded as an "undecidable" notice. A failure at a later feature counts only if another reading of the slot got past that feature at the same point. Without this rule, `exposed_region_midpoint` was blamed for B.1's failure, which `face_centroid` never reached.
    - **Caching and cost:** builds are memoized per (choices, point). The bracket costs 163 builds (~4.7 s) cold and 72 (~2.5 s) warm-started from the lock.
27. **Ranked default and `made_by`.** Readings are ranked by: (1) a remembered preference, (2) the package prior rank, (3) the simplest relation, (4) a learned prior, then declaration order.
    - **Simplest relation (MDL proxy):** `complexity`, the number of geometric references the lowering reads.
    - **Learned prior:** `set_learned_prior()` is an interface stub only.
    - **`made_by` values:** `pack default` (the prior-1 reading was chosen), `model` (anything else chosen by ranking, e.g. after the default was eliminated), `user preference`, `author`.
    - **Status:** `accepted` for user and author; otherwise `proposed`. `supports` lists the feature.
28. **[REVIEW] "Default overridden" is a notice, never a question, and applies uniformly.** *(Narrowed 2026-11-16 by #32, per the user's review: the notice now fires only when the survivor interacts with features the default did not. The bracket's A.3 elimination is now an ordinary elimination with no notice. Original text kept for the record.)* When the package default is eliminated and another reading survives (and no preference chose), the report shows a `default_overridden` notice and sensitivity is high.
    - **Bracket:** this fires for **A.3** (`face_centroid` lies in the gusset notch, so the "centre inside face" check eliminates it). The bracket therefore shows **0 questions and 1 notice**.
    - **Known gap (spike-01 negative control, `shelf_hole_u=0.4`):** `through_plate` turns blind and is eliminated by ΔH. `through_all` drills through the arm *and the gusset*, passes every invariant, and is chosen; `up_to_next` is identical. Nothing checks whether a screw can actually reach or seat there: that needs intent-level checks such as tool access (TODO 4, checks as first-class objects). Until those exist, this notice is the only signal.
    - The existing negative-control test still builds with the bracket's lock (B.1 = `through_plate`), so ΔH still fails loudly. A new test asserts that re-resolving that variant raises the notice.
29. **Preferences** are a JSON file passed with `--prefs`, with entries `{"answers": {"<word>.<slot>@<context>": {"reading", "note"}}}`. Lookup goes from most to least specific:
    - `<design>:<intent node>`, e.g. `hole.extent@shelf_bracket:A.3`;
    - `<design>:*`;
    - `*` (a house default for the word).

    The intent node, not the feature id, is the design-specific context, so an answer follows the intent. A preference both selects the reading and suppresses the question. If a check eliminates the preferred reading, a `preference_overridden` notice is shown instead. `python -m dipm answer <design> <assumption-id> <reading> --prefs F [--scope node|design|house] [--note …]` records the answer, then re-resolves and rewrites the lock.
30. **[REVIEW] Lock file `<design>.interpretations.json`**, committed next to the design like a package lock. It holds the choices plus the full assumption, question and notice records, and has no timestamps.
    - **Key:** sha256 of the design source file, of the preferences, and of the reading tables, plus the dipm version.
    - **Fresh lock:** `build` reads it as-is (fast, deterministic).
    - **Missing or stale lock:** re-resolved in memory, warm-started from the old choices, with a warning. `interpret` rewrites it.
    - **Designs opt in** with `d.use_lock(__file__)` (the bracket does); the CLI attaches `<file stem>.interpretations.json` automatically. A Python `Design.build()` with no lock uses **unchecked** ranked defaults, and the report says so.
    - **Coarse key:** any edit to the design file (even a comment) makes the lock stale. A variant built by the same file (`make_design(shelf_hole_u=0.4)`) reuses the lock as-is.
31. **`interpret` CLI exit code** is 0 even when questions are pending (questions aren't failures). It is 1 only if some slot has no surviving reading.

*Decisions 32–43 were added 2026-11-16 with GUI iteration 1 (`dipm serve`, `gui/`; spec in `docs/gui.md`).*

32. **[REVIEW] "Default overridden" only for extra interaction** (user-approved rule change to #28). The notice is raised only when the chosen survivor **interacts with features the default reading would not have**.
    - **Interaction set** of a feature at one sample point = the features named by the structural references it resolved (`Build.references`) ∪ the features whose ledger-tagged sub-shapes its operation modified, split, regenerated, merged or deleted (`Build.touched`, from genealogy events). It is computed per build in `interpret._summarize`.
    - **Extra** = the union over sample points of (chosen's set − default's set), skipping points where the chosen reading itself fails at the slot's feature. If the default never ran its operation (its placement was impossible), its set is just what it resolved before failing: the face it is placed on.
    - **Bracket A.3:** `face_centroid` is eliminated (centre not on the face); `exposed_region_midpoint`'s tool touches only `R.body`, as the default's reference did → **no notice**, sensitivity graded normally ("none": one survivor), detail "package default eliminated (no extra interaction)". The bracket now has **0 notices**.
    - **Negative control (`shelf_hole_u=0.4`):** `through_all` touches `C.gusset`; `through_plate` (which ran and went blind) touched only `R.body` → notice, naming `C.gusset`.
    - **Limits:** geometry read without a reference (#33) does not count as interaction, and `between_siblings` reads sibling holes' centres without a reference, so its coupling is invisible to this rule (it is opt-in). Touching is detected through the ledger, so a tool that meets material *without changing any tagged face* (e.g. ending inside a body) is not an interaction.
33. **[REVIEW] *Uses* = references + implicit reads.** `Build.uses(f)` is the features `f` resolved references to, plus features whose geometry its lowering read without a reference, logged with `Context.note_read`. `exposed_region_midpoint` logs the features owning the faces that bound its winning chord, so `A.3.cable` uses `C.gusset` (gui.md criterion 9). Reads are kept on `FeatureRecord.reads`, not as `Resolution`s, so stability snapshots are unchanged. `ref_features` maps reference text to feature ids (longest id wins: `A.P.holes.wall(0)` names `A.P.holes`, not `A.P`).
34. **[REVIEW] Intent tree derivation** (`connections.intent_tree`). Dotted ids give the hierarchy and missing ancestors are created (marked implicit). By convention **`R` is the root** and parents every other top-level id (A, B, C …); a design without `R` gets an implicit one. Siblings sort **named before numbered** (A.P before A.3), then by name or number. **Labels:** `Design.label_intent(node, label)` (new, optional) wins, else the first tag note, else the intent words. The bracket now labels R, A, B, C (its source changed, so its lock was regenerated). **Status** = the worst of the features at or beneath the node: fail > warn (a question or notice on one of its slots) > not built > ok. Each feature is shown as a callout at its *most specific* feature-level nodes (`A.P.holes` at A.P, not at A); instance tags (A.P.1, A.P.2) become instance callouts.
35. **[REVIEW] Diagnostics** (`connections.diagnostics`).
    - *No intent:* a feature with no tags.
    - *Intent with no feature:* a node (e.g. one only labelled) with no feature at or beneath it.
    - *Serves several intents:* more than one feature-level node after dropping ancestors (`[A.P, A]` → `[A.P]`). Instance tags are not counted.
    - *Cross-intent dependency:* `f` uses `g` and none of `f`'s nodes is related (equal, ancestor, descendant) to any of `g`'s. This is a prompt to review for false coupling (architecture §5.1), not an error. The bracket shows two, `A.P.holes → C.gusset` (R.c4 driver access) and `A.3.cable → C.gusset` (exposed region), both legitimate; the GUI styles them as info, not warnings.
36. **Parameter dependencies** are static: a deep walk of each feature's arguments (expressions, dataclass fields, profiles, placements, and closure cells, since `centerline(...).before(...)` segments are closures). `params_all` adds the parameters of everything a feature uses, transitively; selecting `shelf_depth` lights `R.body`, `C.gusset` directly and the other four through uses. The walk cannot see parameters read by plain Python outside lazy expressions (none today).
37. **[REVIEW] Mesh** (`server/mesh.py`). `BRepMesh_IncrementalMesh` on a **copy** of the solid (meshing in place would put triangulations into the canonical BRep text), single-threaded, linear deflection 0.05 mm, angular 0.2 rad. Face id i / edge id j = position in `Build.faces()` / `Build.edges()`, the same order as the genealogy table. Vertices are per face. `ComputeNormals` ignores face orientation, so normals are negated (and winding flipped) on reversed faces; outward normals are tested. The mesh id is a content hash. Deterministic in-process and across processes (tested); the solid's canonical bytes are unchanged by meshing (tested). Edges are polylines from `GCPnts_TangentialDeflection` with the same deflections.
38. **[REVIEW] Server behaviour** (`server/app.py`).
    - Bound to 127.0.0.1 only; if the port is busy it tries the next 19.
    - **A stale or missing lock never blocks a rebuild:** the old lock's choices (or unchecked defaults) are used at once, interpretations are re-resolved in a background thread, and a second `rebuilt` event follows. This is what keeps "save → rebuilt" under a second (measured ~100 ms end to end for the fixtures; the bracket's re-resolution then takes ~2.5 s).
    - The server writes the lock **only** for `/api/answer`, exactly as `dipm answer` does (shared `cli.record_answer` + `_interpret_and_write` semantics). Answers go to `--prefs`, else the prefs file the lock records, else `<design stem>.prefs.json`. Its own prefs/lock writes are ignored by the watcher (paths marked as being written, then content hashes).
    - Watched: the design file, its lock and its prefs (resolved with `realpath`: macOS `/var` → `/private/var` broke matching). Each reload is a fresh import of the design file; **modules the design itself imports are cached by Python and are not reloaded**.
    - Builds are serialized; parameters persist across reloads while still declared and valid.
39. **Failure display.** On a failed build the viewport shows the failed build's geometry (if any) with faces *created* by a failing feature in red and faces it only modified lightly tinted, plus the **last good model as a translucent grey ghost** (toggleable). The checks panel, tree dots and a banner show the failure.
40. **[REVIEW] Frontend toolchain pinned to what runs on Node 20** (the local default is 20.12): Vite 6.4.6, Vitest 4.1.12 (3.x had open advisories), Preact 10.29.8 (not the month-old 11), TypeScript 5.9.3 (not 7), three 0.187.0, @preact/signals 2.11.4, Playwright 1.65.1, @types/node 20.19.43. Vite 8 and Vitest 5 need Node ≥ 20.19/22.12.
41. **Fonts are vendored** in `gui/public/fonts/` from Google Fonts (latin, latin-ext and, for Plex Sans, greek subsets, so ΔH/ΔS render in Plex), with the three SIL OFL 1.1 license files from `google/fonts`.
42. **Test hook:** the page exposes `window.__dipm = {viewer, build}` so Playwright can find a visible point of a face and read face display states. Harmless, but it is a global.
43. **Python test client:** Starlette 1.10 deprecates `httpx` for `TestClient`, so the test extra pins `httpx2==2.16.2`.

## 4. Implemented vs. TODO

**Implemented and tested.** Everything in scope items 1–11:

- the program model with parameters, tags and the pure build;
- the reference layer: cardinality, split/merge policies and merge events, `edges_between`, follow-Generated, no ordinals, IsDeleted distrust;
- all six invariants, with negative controls (blind-on-gusset → ΔH; overlapping compound tool → volume/ΔS while BRepCheck and Euler pass; volume-sign lie; null shape; collapsing shell);
- the ops: extrude/revolve (new, add, cut), fillet, chamfer, transform, mirror, clean, shell, draft, and hole (clearance or countersink; through-all, through-plate or blind);
- sketch profiles with constructions and branch tags;
- the intent relations;
- `why()`;
- the stability harness;
- the bracket example;
- the §8.6 edit tests (shelf_depth, t, screw, "cable hole does not move");
- determinism (in-process and cross-process);
- the CLI.

**TODO, roughly in priority order:**

1. The constructive sketch solver (§3.2, §6.2): relations to positions, branch tags on every step, DoF/Laman health (§5.5). Arcs and circles in profiles.
2. A canonical core IR and an explicit lowering pass, so equivalence, brevity and "relations vs. literals" can be computed on the core (§1, arch §6).
3. A package format (§2): `hole`, `distribute`, the fastener table → a real `fasteners` rule pack with sources and provenance. Reading tables (`HOLE_EXTENT`, `CENTERED_ON`) and house preferences belong in packages too.
4. Checks as first-class objects (arch §4). These are also what interpretations need to eliminate readings that pass every kernel invariant but are wrong in intent (DECISIONS #28: `through_all` through the gusset): the §8.3 checks ("symmetric", "edge distance ≥ 2Ø", "cable clear of A.P by ≥ Ø", R.c4 tool access) as rung-1 relation/rule checks re-evaluated in the stability harness. Today only the kernel invariants and reference checks run.
5. A `gusset(at=inner_corner, ...)` intent word that places itself from the referenced edge. Today its profile is written from parameters.
6. Feature-level pattern and mirror (patterns of non-hole features); a general `boolean(tool_body)`; multi-body designs.
7. Holes on non-planar faces; counterbores; hole-vs-non-hole interaction prediction (e.g. predicting "blind on the gusset" rather than only detecting it).
8. A decision on auto-`clean()` after booleans (DECISIONS #15), plus a warning when two `one()` references alias one face.
9. Closed/outward shells (offset + cut), with fingerprint canonical form in use; loft and sweep ops.
10. Cross-platform determinism CI (Linux x86/arm) against the canonical BRep hashes.
11. The Onshape FeatureScript backend (§6.3).

## 5. Known limitations

- **Interpretations** (§6): slots are resolved one at a time, never as a product (#26). Elimination uses only kernel invariants and placement/reference checks, not intent-level checks (#28). The exposed-region rule looks along two axes only (#24). `up_to_next` samples 16 lines (#23). The lock key is the design file's bytes, so line-ending conversion marks it stale (slow, but still correct).

- **No solver:** sketch geometry is explicit expressions. Constraint health (§5.5) is not checked.
- **Branch tags** cover only profile winding and `on_side`; constructions with real choices (circle–line intersections) do not exist yet.
- **`extent_along` samples curved edges** (16 per edge). That is deterministic but approximate for arc-bounded faces. `centered_on` uses the area centroid, which is exact only for symmetric faces.
- **Hole interaction is detected with exact distance**, filtered by bounding box first. Expect O(n²) cost in hole count; fine for tens of holes, slow for hundreds.
- **Hole instances become one `cut`.** The per-instance `wall(k)` roles survive, but a pattern instance that falls off the part raises (centre not inside face) instead of being declared `exactly(0)`.
- **Fillet `corner` faces are a set-level role** (untested in the spikes for fillet). Revolve sides for edges *on* the axis are simply absent.
- **Build time:** ~50 ms warm per bracket build with all invariants, ~200 ms cold (first OCP calls); the spike was 33 ms. The extra cost is the per-feature BRepCheck/volume/Euler plus the interaction distances.
- **Determinism is verified only here** (macOS arm64, OCCT 8.0.1), in-process and in one extra process.
- **Errors raised during export resolution** in `on_fail="record"` are attached to `Build.errors` with `details["export"]`; the feature field reads `<exports>`.

## 6. Interpretations (architecture §10 item 2; added 2026-11-16)

**Problem.** Intent words leave choices open: "through" *what*? Centred on *which* centre? The designer can't be asked about every one of these, and shouldn't be asked twice. This is the mechanism proposed in architecture §10 item 2, implemented in `interpret.py`; the decisions are #23–#31.

**How it works.**
1. **Readings are declared by the intent word.** Its reading table lists them in a fixed order, each with a name, a one-line rationale, a prior rank and an MDL proxy. Lowerings live with the word in `intent_layer.py`. While lowering, the word calls `ctx.interpret(READING_SET, explicit=...)`, which returns the reading to use and records a `SlotUse`. An explicit value bypasses interpretation (`made_by: author`).
2. **`resolve(design)` builds each reading at every stability sample point** and eliminates the readings that fail any check, recording the feature, check, first failing point and failure count. The same invariants run as in every build: validity, Euler, ΔH, ΔS, volume sign, cardinality, interaction, placement preconditions.
3. **It compares the survivors** (VEFRSH, role-geometry fingerprint, volume) and grades the sensitivity (#25).
4. **It ranks** (#27), **records an assumption** (§4.8 fields: id, statement, chosen, alternatives, eliminated, sensitivity, made_by, rationale, status, supports), and **asks a question only if** ≥ 2 readings survive, they diverge, and no preference decides.
5. **Notices** report decisions the system made automatically that a reviewer should still see:
   - `default_overridden` (#28, narrowed by #32: only when the survivor interacts with features the default did not);
   - `preference_overridden`;
   - `undecidable` (every reading fails identically: the design is broken there for another reason);
   - `no_survivor`;
   - `not_converged`.
6. **The result is written to the lock** (#30), and the build report gains an "Interpretations" section.

**Bracket outcome (verified, 9 sample points):**

| Slot | Chosen | Eliminated | Survivors / sensitivity |
|---|---|---|---|
| `A.P.holes/hole.extent` | `through_plate` (pack default) | none | `through_all`, `up_to_next` identical: none |
| `A.3.cable/centered_on.point` | `exposed_region_midpoint` (model) | `face_centroid`: "centre inside face" at 9/9 points (it lies in the gusset notch) | only one: none (an ordinary elimination since #32; no notice) |
| `A.3.cable/hole.extent` | `through_plate` | none | identical: none |
| `B.1.screw/hole.extent` | `through_plate` | none | identical: none |

That gives **0 questions and 0 notices** (since #32; it was 1 notice, A.3 default overridden, before). The cable hole lands at z = 32.5 at the defaults, exactly where DECISIONS #8 put it by hand, and the existing layout and §8.6 edit tests pass unchanged. The extents being equivalent to the old hand-written choices (`THROUGH_ALL` for A.P/A.3, `through(t)` for B.1) is what sensitivity "none" means.

**Spike-01 negative control** (`shelf_hole_u=0.4`, re-resolved): `through_plate` is eliminated by ΔH at 9/9 points. `through_all` is chosen (`up_to_next` is identical), and a `default_overridden` notice is raised with high sensitivity, naming the extra interaction (`through_all` also cuts `C.gusset`, which `through_plate` never touched); there are no questions. This is the documented gap (#28, #32, TODO 4).

**Tests changed because behaviour legitimately changed:** two `lowered_from` strings in `test_invariants.py::test_blind_hole_caught_by_delta_h_on_bracket` and `test_why.py::test_why_countersink_names_pattern_instance` now read `through_plate` instead of `through` and `through_all`. No other existing test was edited.

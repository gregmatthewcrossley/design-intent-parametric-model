# Onshape API parity: can dipm trees be recreated as native Onshape feature trees?

*Research notes, 2026-11-16. Responds to PAIN-09 / ISS-06 (`reports/Fresh eyes review.md`), tracked as C3 in `docs/review-response.md`. Read-only research: no Onshape calls were made and no documents were created. Evidence comes from Onshape's developer docs, FeatureScript std-library source, forum posts, and the source code and live-probe scripts of the installed `jarvis-onshape-mcp` plugin (v1.2.0, `~/.claude/plugins/cache/jarvis-onshape-mcp/jarvis-onshape-mcp/1.2.0/`). That plugin builds BTMFeature JSON against the live API, and its builders were validated by probe scripts (`scripts/probe_hole.py`, `probe_draft.py`, `probe_mirror.py`, `probe_native_shell.py`, …). Claims marked **[untested]** need a live spike.*

---

## 0. Verdict

**The geometry and the parametric skeleton can be recreated natively and cleanly. The design intent cannot be recreated with standard features alone.**

- **Clean:** every dipm v0 *op* has a native Onshape feature: extrude (new/add/cut, symmetric), revolve, fillet, chamfer, shell, draft, mirror, transform, and hole (simple/countersink; blind, up to next, through all). Each can be created over the REST API (`POST …/features` with a `BTFeatureDefinitionCall-1406` wrapping a `BTMFeature-134`). Design parameters become Variable Studio variables or configuration inputs, so an engineer's edit rebuilds the same way dipm would.
- **Lossy:** the *intent layer*. Placements such as `centered_on`, `distribute`, `centerline(...).before(..., clearance)` and `face_point` are evaluated by dipm against the B-rep at build time. They are not stored symbolically. Some of them can be rewritten as sketch constraints against projected edges. The rest end up frozen as numbers unless dipm emits a custom FeatureScript feature.
- **Impossible natively:** interpretations (readings, locks, questions), branch tags, ΔH/ΔS/volume-sign expectations, declared reference cardinality and split/merge policies, the `Clean` op as an explicit step, and per-instance roles. None of these has a place in a standard Onshape feature. FeatureScript can *check* them, though: custom features can report regen errors and warnings in the native tree.
- **Biggest structural gap:** references. dipm names entities as (feature id, role, source) through OCCT history. Standard Onshape features name entities through **deterministic IDs**, which are transient per microversion; Onshape's own persistent naming keeps the selection after that. Onshape exposes no persistent entity ID ([Associativity](https://onshape-public.github.io/docs/api-adv/associativity/)). dipm therefore has to translate each role into a deterministic ID *at export time*, after which Onshape's history-based naming takes over. FeatureScript has close analogues of dipm roles (`qCapEntity`, `qNonCapEntity`, `startTracking`, `qCreatedBy`, `qPatternInstances`, `qHoleFaces`), but they are available only *inside* FeatureScript: in a custom feature, or as `queryString` in a feature parameter.

**Recommendation (§3): hybrid, standard-first.** Use standard features for all geometry, so engineers edit what they already know. Add a small, versioned **dipm FeatureScript library** for relational placements that sketches can't express; each placement emits points or mate connectors that *native* hole features consume. End the tree with a **dipm checks** custom feature that re-runs intent checks inside Onshape, so a hand edit that breaks intent shows up as a red or yellow feature. Store the dipm id ↔ Onshape featureId map, the intent tree and the lock inside the document (app element / blob) and locally.

---

## 1. What the API offers for feature creation

### 1.1 Endpoints (Part Studio, API v9)

From [Feature access](https://onshape-public.github.io/docs/api-adv/featureaccess/), plus the plugin's `onshape_mcp/api/partstudio.py` and `feature_apply.py`:

| Purpose | Call |
|---|---|
| Read the tree | `GET /api/v9/partstudios/d/{did}/{wvm}/{wvmid}/e/{eid}/features` → features + `featureStates` + `rollbackIndex` + `sourceMicroversion` + `libraryVersion` |
| Add a feature | `POST …/e/{eid}/features`, body `{"btType":"BTFeatureDefinitionCall-1406","feature":{"btType":"BTMFeature-134","featureType":"extrude","name":…,"parameters":[…]}}`. Sketches use `BTMSketch-151` with `featureType:"newSketch"`, `entities` and `constraints` |
| Update one feature | `POST …/features/featureid/{fid}`. You must resend `featureType` and `name`, or they get blanked |
| Batch update | `POST …/features/updates` (existing features only; no documented batch *add*) |
| Delete | `DELETE …/features/featureid/{fid}` |
| Read-only FeatureScript | `POST …/e/{eid}/featurescript` with a lambda (`function(context is Context, queries){…}`). It cannot mutate the tree ([FS eval](https://onshape-public.github.io/docs/api-adv/fs/)) |
| Feature specs | `GET …/featurespecs`: parameter schemas of built-in and custom features (the plugin uses it to capture defaults and the custom-feature microversion) |
| Mass properties / body topology | `GET …/massproperties`, `GET …/bodydetails` (the plugin calls both after every feature) |
| Entity ID mapping across edits | `POST /api/partstudios/d/{did}/w/{wid}/e/{eid}/idtranslations` → per ID `OK` / `SPLIT` / `FAILED_TO_RESOLVE` ([Associativity](https://onshape-public.github.io/docs/api-adv/associativity/)) |
| Variables | `POST /api/v6/variables/d/{did}/w/{wid}/variablestudio` (create), `POST|GET …/e/{vs}/variables` (the plugin's `api/variables.py`). Alternatively, Part-Studio-local `assignVariable` features (`#name`) |
| Configurations | `GET|POST …/e/{eid}/configuration`, `…/configurationencodings` ([Configurations](https://onshape-public.github.io/docs/api-adv/configs/)) |
| STEP export | async `POST …/export/step` → poll `GET /translations/{id}` → download externaldata or blob ([Translation](https://onshape-public.github.io/docs/api-adv/translation/)) |

The response to each add carries `featureState.featureStatus` (OK / INFO / WARNING / ERROR), so regen failures come back from the same call. The REST API gives **no per-constraint diagnostics** for over-constrained sketches; the plugin's skill doc says to bisect client-side.

### 1.2 Practical facts from the plugin's live-validated builders

- **The built-in `hole` has ~161 parameters** (V1/V2/V3 variants, standards, tolerances). The plugin captures featurespec defaults (`builders/_hole_defaults.json`) and overrides only diameter, depth, `locations` and `scope`. It writes every diameter and depth variant in lock-step, because a mismatch fails partially. Locations come from a sketch: `qSketchFilter(qCreatedBy(makeId("<sketchFid>"), EntityType.VERTEX), SketchObject.YES)`. The sketch filter matters: sketching on a body face imprints that face's corner vertices, and those would be drilled too.
- **Queries are `BTMParameterQueryList-148` holding `BTMIndividualQuery-138`** with either `deterministicIds: [...]` or `queryString: "query = <FS query>;"`. If both are sent, deterministicIds win. A `queryString` can be any FS query expression: the plugin uses `qCreatedBy(makeId("Front"), EntityType.FACE)` for datum planes, and the sketch-filter expression above.
- **Datum planes carry no edges or axes.** A linear pattern needs a real edge for its direction, and a revolve needs an axis edge (`builders/pattern.py`, `revolve.py`). The exporter must emit construction sketch lines or mate connectors for axes.
- **Sketches:** 14 constraint types work over the API (COINCIDENT, TANGENT, CONCENTRIC, PARALLEL, PERPENDICULAR, EQUAL, MIDPOINT, HORIZONTAL/VERTICAL on lines only, DISTANCE with MINIMUM/HORIZONTAL/VERTICAL, DIAMETER, RADIUS, ANGLE, OFFSET), with `#variable` expressions as values. The plugin calls anchoring to the Part Studio origin "known-broken": sketches don't expose the origin as a local entity, so the reference needs `externalFirst` with a query on the Origin feature.
- **Frames:** Front = XZ with normal −Y, Top = XY, Right = YZ. dipm's `YZ` profile goes on Right, and plane-local axes must be mapped explicitly.
- **Units:** the API works in metres. Expressions take unit strings (`"5 mm"`).
- **Deterministic IDs:** "stable across feature edits, but NEW features may remap them — always re-run `list_entities` … after a mutation before referencing" (plugin `server.py`). Forum: transient IDs "might change once something does" and are "not stable in the face of most upstream changes" ([forum search](https://forum.onshape.com/discussions/tagged/deterministicids)). Once a feature *stores* a selection, Onshape's server-side persistent naming keeps it, exactly as it does for UI picks. **[untested via API for parameter sweeps, but this is what UI-made models rely on]**

### 1.3 References: Onshape queries vs dipm structural references

| dipm reference (dsl.md §3.4, spike 02 §6) | FeatureScript equivalent | Usable from standard features? |
|---|---|---|
| `E.cap(START/END)` | `qCapEntity(id, CapType.START/END, EntityType.FACE)` | Yes, as `queryString` **[untested: does it survive a UI edit of the consuming feature?]**; or resolve to deterministicIds at export |
| `E.side(from=sketch.edge("wall"))` | `startTracking(context, sketchId, "wall")` → `qEntityFilter(track, FACE)` after the extrude ([forum](https://forum.onshape.com/discussion/7591/proper-way-to-extract-query-face-vertex-edge-out-of-a-rectangle-extrude-body-in-featurescript)). BTMSketch entities take client-chosen `entityId`s, so "wall" survives | Only inside a custom feature (tracking needs a feature context). From outside: geometric resolution (below) |
| `E.lateral_edge(from=vertex)` | Tracking *vertices* to get extruded edges does not work (forum). Use the intersection of two side faces (`qIntersection(qAdjacent…)`), which is dipm's `edges_between` | Derived, as in dipm |
| `edges_between(f1, f2)` | `qIntersection([qAdjacent(f1, AdjacencyType.EDGE, EntityType.EDGE), qAdjacent(f2, …)])` | queryString or deterministicIds |
| `F.blend(of=edge)` | `qCreatedBy(filletId, EntityType.FACE)`, with per-edge selection only geometrically | Partly |
| `holes.wall(k)`, `countersink(k)` | `qHoleFaces(seed)`; hole attributes; for patterns `qPatternInstances(id, name, …)` | No per-instance role natively |
| `M.image(of=r)` | none; mirror output via `qCreatedBy(mirrorId)` plus geometry | Lossy |
| Cardinality `one()/exactly(n)` | `evaluateQueryCount` guards (dsl.md §6.3 already requires this for the FS backend) | Not in standard features; a checks custom feature can do it |
| Split/merge policies | `idtranslations` returns `OK/SPLIT/FAILED_TO_RESOLVE`, the same event vocabulary as dipm's ledger | Only as an external check |

**Key correspondence.** FeatureScript distinguishes *historical* queries ("select entities based on the model history"), *state-based* queries and *transient* queries ("only valid until the context is modified again") (std `query.fs`, [mirror](https://raw.githubusercontent.com/javawizard/onshape-std-library-mirror/main/query.fs)). dipm's (feature, role, source) is a historical query. Onshape's operation `Id` hierarchy (`id + "extrude1"`, `ANY_ID`, `unstableIdComponent`) plays the role of dipm's hierarchical feature ids ([FsDoc](https://cad.onshape.com/FsDoc/library.html)). CADFS's query form `makeQuery(op id, query type, entity type, disambiguation)` is the same shape again ([CADFS](https://arxiv.org/html/2605.01925)).

**Export-time geometric resolution (recommended for standard features).** dipm already builds the model locally and keeps an order-free role-geometry fingerprint (rounded centroid and area per role; dsl.md §5.4). To hand a role to Onshape, dipm can make one FS eval call per step: filter `qCreatedBy(<featureId>, FACE)` with `qContainsPoint(…, centroid)` / `qParallelPlanes(…, normal)`, assert the count equals the declared cardinality, and return `transientQueriesToStrings(...)`, i.e. deterministicIds. These go into the next feature, after which Onshape persists the selection the same way it persists a UI pick. This is a *geometric* match, which dipm bans for its own references, but it is used only once, at export, at the default parameters, and it is checked against the OCCT result. Durability under later edits is Onshape's job, the same as for any hand-built model.

---

## 2. Mapping table

Grades: **clean** = the native feature reproduces geometry *and* stays parametric in the same way. **lossy** = geometry is reproduced, but some intent, parametric linkage or exact semantics is lost or approximated. **impossible** = no native carrier (a FeatureScript check or metadata at best).

### 2.1 Core and trusted ops (`src/dipm/ops.py`)

| dipm op | Onshape native | Grade | Notes |
|---|---|---|---|
| `Extrude(mode="new")` | sketch (`BTMSketch-151`) + `extrude` NEW, BLIND or SYMMETRIC | clean | Profile points are parameter expressions, so the exporter must *synthesise* sketch constraints (HORIZONTAL/VERTICAL + DISTANCE with `#expr` values, anchored to the origin) because v0 has no solver (DECISIONS #6). The geometry is exact; the *dimension scheme* is machine-made (see "profiles" below) |
| `Extrude(mode="add")` | `extrude` ADD, merge scope = the body | clean | dipm's "must touch" precondition has no native analogue (Onshape makes a separate part, or warns) |
| `Extrude(mode="cut")` | `extrude` REMOVE | clean | Direction trap: REMOVE on a face sketch defaults to cutting into air (plugin auto-flips) |
| `Revolve` (new/add/cut, 360° or angle) | `revolve` with an axis edge from a construction line in the same sketch | clean | Axis must be a real edge (§1.2). dipm's full-revolve history fallback is irrelevant natively |
| `Fillet(edges, radius)` | `fillet`, constant radius, edges as deterministicIds or queryString | clean | dipm's `IsDeleted` distrust is OCCT-only. Parasolid fillets are more robust, so Onshape may succeed where OCCT fails |
| `Chamfer(edges, distance)` | `chamfer`, equal distance | clean | |
| `Transform(translate, rotate)` | `transform` (translate by XYZ / rotate about an axis / by mate connectors) | clean | Rotation axis needs an emitted entity (sketch line or mate connector) |
| `Mirror(origin, normal, clean=True)` | `cPlane` (when the plane isn't a datum) + `mirror` PART with operationType ADD | clean (geometry) / lossy (refs) | `M.image(of=…)` roles and merge events are lost. Feature mirror (`patternType: FEATURE`) exists for later work |
| `Clean` (UnifySameDomain) | no feature. Parasolid booleans merge coplanar faces themselves **[unverified; spike 02 §9 flags it]** | lossy (implicit) | Emit nothing. Topology counts may differ from dipm whenever dipm *didn't* clean, so verification must normalise (§4) |
| `Shell(openings, thickness)` inward | `shell`, faces to remove, thickness, inward | clean | Native shell also handles the closed/outward cases that dipm lowers to offset + cut (TODO 9) |
| `Draft(faces, angle, neutral_origin, pull)` | `cPlane` at the neutral origin/normal + `draft` NEUTRAL_PLANE | clean | Draft faces as deterministicIds. dipm derives edges after draft through `edges_between`, and Onshape needs that equally |
| Boolean with a tool *list* | implicit in ADD/REMOVE, or the `boolean` feature | clean | The OCCT compound-tool bug does not apply |
| (Loft, sweep: not in v0) | `loft`, `sweep` | n/a | Native features exist; the plugin wraps both |

### 2.2 Hole (`intent_layer.Hole`)

| dipm | Onshape native | Grade | Notes |
|---|---|---|---|
| `plain(d)` / `clearance(screw)` | `hole` SIMPLE, diameter `#expr` | clean | Either keep dipm's diameters (stand-in table, DECISIONS #9) as variables, or switch to Onshape's *Clearance* spec (ANSI/ISO fits). The latter is more native, but the numbers will differ from dipm's table |
| `countersink(screw)` | `hole` COUNTERSINK, csink diameter + angle 90° | clean | dipm's "head Ø at the face" matches the native countersink diameter |
| extent `through_all` | `hole` end = Through all, scope = the part | clean | |
| extent `blind(d)` | Blind, depth `#expr` | clean | |
| extent `through(t)` | Blind with depth `#t` (+ offset), or Up to next | lossy | dipm's +2 mm overshoot is an OCCT tool artifact. Natively, use Up to next or Through all |
| extent `through_plate` (interpreted) | Up to next | lossy | Same intent ("through this plate"), different algorithm. Onshape's up-to-next is exact where dipm samples 16 lines. *Both* turn blind on a backed plate. The reading choice itself is lost |
| extent `up_to_next` | Up to next | clean | Native is more exact |
| Locations `at=points` | sketch on the face with points (or mate connectors) → `locations`; `scope` = part | clean (static) / lossy (relational) | A literal point list is clean. Relational placement: see §2.3 |
| Per-instance roles `wall(k)`, `countersink(k)`, `floor(k)` | none (`qHoleFaces`, hole attributes inside FS) | impossible (standard) | |
| ΔH from interaction, `InteractionError` | none | impossible (standard) | Checks feature (§3) |
| Callouts, hole tables in drawings | native for `hole` features; also for holes made by calling std `hole()` from a custom feature ([forum](https://forum.onshape.com/discussion/8286/use-hole-callout-on-holes-created-in-fs)) | (gain) | A reason to keep holes *native*, not boolean cuts |

### 2.3 Intent-layer relations (`intent_layer.py`)

| dipm relation | Native carrier | Grade | Notes |
|---|---|---|---|
| Parameters `d.param(...)` with range or choices | Variable Studio variables, or configuration inputs (quantity with default/min/max; list for choices) | clean | §2.4 |
| Derived quantities (`leg = 0.75*shelf_depth`, `width = 6*t`) | variables with expressions (`#leg = 0.75 * #shelf_depth`) | clean | Expressions support arithmetic, ternaries, `&&`/`||`, `min`/`max`/`clamp` ([numeric fields](https://cad.onshape.com/help/Content/numeric-fields.htm)) |
| Fastener table `clearance_diameter(screw)` etc. | configuration list `screw` + configured variables, or nested ternaries on a variable | clean | |
| Profile constructions `midpoint`, `between`, `offset`, `line_line` | sketch MIDPOINT, COINCIDENT, DISTANCE, intersections of construction lines | clean–lossy | Doable once dipm's constructions are kept symbolically (needs the core IR, TODO 2) |
| Winding branch tag, `on_side` | none; Onshape's solver takes the nearest solution | impossible (standard) | Can be checked in FS (signed area / side tests) |
| `centered_on(face)`, reading `face_centroid` | sketch on the face; point at the MIDPOINT of construction lines spanning projected (`use`d) face edges | lossy | Exact only for rectangular faces, which is also where dipm's centroid is exact |
| `centered_on`, reading `exposed_region_midpoint` (chosen for A.3) | **no sketch equivalent**: it needs the gusset footprint subtracted from the face | lossy (frozen number) / clean via custom feature | Either constrain the point to projected gusset and plate edges (bracket-specific, which loses the generic "exposed region" meaning) or emit `dipmCenteredOn` FS (§3) |
| `centerline(face, Z).before(ref, clearance=r)` | construction line on the face centreline (MIDPOINT across projected side edges) whose top endpoint sits a DISTANCE `#tool_access_r` from the projected gusset edge | lossy→clean | Works when the referenced edge projects into the sketch plane, as on the bracket |
| `distribute(along, count, inset)` | count = 2: two points constrained to the segment ends with inset distances. Count > 2: equal construction segments (EQUAL + COINCIDENT) or a native `linearPattern` of the hole with spacing `#expr` | lossy | Onshape's linear pattern takes distance + count; there is no "fit between references" mode, so the spacing must be an expression of a *symbolic* length dipm doesn't have yet **[verify current pattern options]** |
| `face_point(face, along=(Y,u), across=(X,0.5))` | no ratio constraint in sketches. Becomes `u·#arm` if dipm can produce the face length symbolically; otherwise a number, or a custom feature | lossy | Main reason for relation custom features |
| `linear_pattern` / `circular_pattern` placements | several points in one hole sketch (robust), or a native `linearPattern`/`circularPattern` FEATURE pattern of the hole | clean | The native pattern reads better to engineers. The point sketch keeps a single hole feature (as dipm does) |
| `midpoint(a, b)` | sketch MIDPOINT | clean | |
| `at(...)` literal | sketch point with numeric dims | clean | |
| `between_siblings` (opt-in) | constraints to the other holes' sketch points | lossy | |
| Named exports + policies | no named faces natively. FS `setAttribute` in a custom feature + `qAttributeFilter` | impossible (standard) / FS-only | Whether attributes survive downstream splits needs testing **[untested]** |
| Interpretations, assumptions, questions, lock | none | impossible | Metadata only (§3.4) |
| Intent tags, `lowered_from`, `why()` | feature names (`"A.P.holes · hole(countersink) · wall screw pattern"`), feature-tree folders | lossy | Names and folders survive and engineers can see them; the structured data does not |
| ΔH/ΔS/volume-sign `Expect`, Euler, cardinality, stability harness | none in standard features; FS can compute counts, `evVolume`, `evDistance` and report errors | impossible (standard) / FS-checkable | |

### 2.4 Parameters (Q4)

- **Variable Studio** (its own element, usable by every Part Studio in the workspace) via `POST /api/v6/variables/.../variables`. Upsert by name, but the plugin hit a bug where a POST *replaced* the whole set, so send the full set. Reading `GET variables` on the Part Studio returns `[]`; read the VS element instead. Engineers edit these in a table, and every feature written with `#shelf_depth` rebuilds.
- **Configuration inputs** where a parameter should drive assemblies and drawings, or where dipm declares a range or choices: a list for `screw` (#6/#8/#10), quantity inputs with default/min/max for `shelf_depth` (180–300) and `t` (4–8) ([tech tip](https://onshape.com/cad-blog/tech-tip-parametric-variables-vs-configuration-variables)). Exports and mass properties then take the encoded `configuration=` string. Configured *variables* (per-option values) carry the fastener table natively.
- **Equivalence:** editing `#shelf_depth` in Onshape rebuilds equivalently *for whatever was emitted symbolically*. Anything dipm resolved geometrically and froze as a number will not follow. That is why §2.3's lossy rows matter, and why dipm's core IR (TODO 2) is a prerequisite for a good exporter: it must emit `0.75*#shelf_depth`, not `150 mm`.
- **Range enforcement:** configuration inputs enforce min/max. Plain variables do not, and neither do FS-set ones (`setVariable`), but a custom feature's `isLength(..., bounds)` precondition does.

---

## 3. Recommended export strategy

### 3.1 Options compared

| | A. Standard features only | B. Custom features only (each intent word, or the whole design, as FS) | C. Hybrid, standard-first (**recommended**) |
|---|---|---|---|
| Engineers can edit natively | **Yes**: everything is a familiar feature | Parameters only, via the auto-generated dialog. Internals need FS skills | Yes for geometry; intent placements are FS features with plain parameter dialogs |
| Intent survives | No: relations freeze, checks vanish | **Yes**: placements, readings (as enum params), checks, cardinality guards, attributes | Mostly: relational placements and checks survive as FS; skeleton geometry is standard |
| Drawings, hole callouts, BOM | Native | Callouts work if FS calls std `hole()`; downstream feature references into FS output work through Ids | Native |
| Fidelity to dipm semantics | Lossy for placements | Highest: the FS backend can mirror dipm lowerings (dsl.md §6.3) | High |
| API calls per export | most (~25–30 for the bracket) | fewest (Feature Studio upload ~3 + ~1 per feature; ~5 if the whole design is one feature) | ~25–30, with the library uploaded once per version |
| Maintenance | builder per op; 161-param hole defaults drift across FS versions | an FS library to version and keep in step with dipm's Python lowerings (two implementations of each word) | both, but the FS part is small (placements + checks) |
| Round trip back | GET features diff; parameter-level edits map cleanly | parameter edits map 1:1; internal edits impossible | parameter + standard-feature edits map; FS features map 1:1 |
| PAIN-09 fit | good for the edit, bad for the intent | bad: it hides the tree engineers want to edit | **best of both** |

### 3.2 Hybrid design

1. **Parameters:** a Variable Studio plus a configuration (lists for choices, quantity inputs for ranges). Derived values become variables with expressions.
2. **Skeleton geometry as standard features:** sketches with synthesised constraints driven by `#variables`, then extrude, revolve, fillet, chamfer, shell, draft, mirror, transform and pattern. References go in as deterministicIds from export-time geometric resolution (§1.3). Feature names carry dipm ids and intent words; tree folders follow intent nodes (R, A, A.P, …).
3. **Relation features from a published dipm FS library** (a Feature Studio in a versioned, shared document, so customers pin a version): `dipmCenteredOn(face, reading enum)`, `dipmDistribute(along…, count, inset)`, `dipmCenterlineBefore(face, ref, clearance)` and `dipmFacePoint(face, u, v)`. Each **outputs mate connectors or sketch points** (and optionally `setVariable` values). **Native `hole` features** consume them, since holes accept mate connectors as locations ([hole help](https://cad.onshape.com/help/Content/hole.htm)). Engineers then see a "Centered on: Mount face (exposed region)" feature with a dropdown, and a normal Hole feature after it. The interpretation reading becomes a visible enum parameter, set to the locked choice and marked `made_by` in the feature name or description.
4. **A trailing `dipmChecks` custom feature:** re-evaluates declared cardinalities (`evaluateQueryCount`), hole ΔH via loop/genus counts, volume sign, edge distance ≥ 2Ø and tool access. It reports failures with `reportFeatureWarning` / regen errors. This is the piece that addresses PAIN-09 directly: once engineers edit the native tree, intent violations still show up natively, with no round trip needed to notice them.
5. **Provenance in the document:** the dipm id ↔ featureId map, the source microversion, the intent tree, the lock and the role fingerprints at defaults go into an app element ([structured storage](https://onshape-public.github.io/docs/app-dev/structuredstorage/)) or a JSON blob element, and are mirrored locally. Feature IDs are assigned by Onshape (e.g. `FWHg1NvqqOzMd0w`), so dipm ids can't be reused as Onshape ids.
6. **Not recommended as the handoff format:** a single "whole design" custom feature. It is the cheapest in calls and the most faithful, so keep it as a **verification path** (§4), not for handoff.

Reasons: PAIN-09 is about engineers editing natively, which favours standard features. The intent tree's value is the relations and checks, which favours FS exactly where standard features lose them. Keeping holes native keeps drawings, callouts and BOMs standard. The FS surface stays small: about four placement words plus one checks feature, rather than a full second implementation of dipm.

Prerequisites on the dipm side: (a) the canonical core IR, with symbolic expressions surviving into lowering (TODO 2), so the exporter emits `#expr` rather than numbers; (b) the constructive solver (TODO 1), so sketches carry *designer* dimension schemes rather than synthesised origin-distance dims; (c) placements expressed as structural constructions (segment, before, midpoint), not just evaluated points.

---

## 4. Verification (Q5)

Per export, at the default configuration and at each stability sample point (budget permitting, §6):

| Check | Onshape source | Compare with dipm | Tolerance / caveat |
|---|---|---|---|
| Regen status of every feature | `featureState` in each add response; `featureStates` from GET features | all OK/INFO | INFO "nothing was cut" = failure |
| Volume, area, centroid, inertia | `GET …/massproperties` (with `configuration=`) | `Build` volume / centroid | rel ~1e-6 (different kernels; Parasolid vs OCCT tolerances) |
| Bounding box | FS eval `evBox3d(..., tight=true)`. `boundingboxes` is "approximate", for graphics ([FS eval](https://onshape-public.github.io/docs/api-adv/fs/)) | dipm bbox | ~1e-6 m |
| Topology counts (V, E, F, loops, shells) | `bodydetails`, or one FS eval returning `evaluateQueryCount` per entity type + loop counts per face → compute H | (V,E,F,R,S,H) | **Systematic kernel differences expected:** Parasolid periodic faces may lack seam edges; Onshape may merge coplanar faces where dipm didn't `Clean`. Compare H and S exactly, compare V/E/F only after normalisation (run UnifySameDomain on both sides, seam-aware counting) |
| Role fingerprints | FS eval: for each role, its FS query (or the geometric match) → `evArea`, centroid | dipm order-free role-geometry fingerprint (dsl.md §5.4) | Doubles as the cardinality check |
| Face-level genealogy | No API for history. Partial: re-run role queries after a parameter change; `idtranslations` across microversions gives OK/SPLIT/FAILED, i.e. dipm's split/merge events | ledger events | Coarser than dipm's ledger; no `Generated`/`Modified` distinction |
| STEP round trip | async `export/step` (≥3 calls: POST, poll, download) → load in OCP → run dipm's invariants (BRepCheck, Euler, topology-only WL hash) | dipm's own STEP / BRep | Strip timestamp and product-name counter (dsl.md §5.4). Geometry-inclusive hashes will never match across kernels; topology-only hash after normalisation should |

Cheap variant: Parasolid export is synchronous (`/parasolid`, [Configurations](https://onshape-public.github.io/docs/api-adv/configs/)) but needs a Parasolid reader. STEP is more practical for OCP. One FS eval call can return mass, bbox, counts and all role fingerprints together (≈1 call instead of 4). **[untested: the size limits of an eval lambda's return value]**

The parity test is: dipm build → export → Onshape verify at defaults → apply each stability edit as a *configuration change* (1 call) → re-verify (1 eval) → compare signatures and role cardinalities with dipm at the same point. This tests whether *Onshape's* rebuild under edits matches dipm's, which is the property PAIN-09 needs.

---

## 5. Round trip back (Q6)

**Feasible:**
- **Detecting edits:** webhooks `onshape.model.lifecycle.changed` and `…createversion` ([webhooks](https://onshape-public.github.io/docs/app-dev/webhook/)) don't count against limits ([limits](https://onshape-public.github.io/docs/auth/limits/)). On notification, `GET features` (1 call) and diff against the stored export snapshot (featureIds, parameter JSON, suppression, order, rollback bar).
- **Parameter edits** (variables, configuration defaults, a hole diameter, a fillet radius, an FS placement feature's parameters) map **1:1** back to dipm `param` defaults or feature arguments, because the exporter knows which dipm expression each emitted parameter came from. This is the high-value, low-risk case.
- **Expression edits** (`#t` → `#t + 1 mm` on one extrude) map to a dipm expression change, parsed from the Onshape expression string.
- **Sketch edits:** constraint and dimension diffs in BTMSketch JSON. These are mappable when dipm owns the sketch's constraint scheme (needs the solver, TODO 1).
- **New standard features added by an engineer** (fillet, chamfer, hole, extrude): `featureType` maps to a dipm op. The selected entities (deterministicIds) are evaluated by FS to geometry and matched against dipm role fingerprints at the same parameters, giving a *structural* reference (`R.body.lateral_edge(...)`) where a unique role matches and `edges_between` otherwise. The result is a dipm feature with a **proposed** intent tag `made_by: engineer` (fits the PAIN-12 remedy: visibly unreviewed). Where no structural reference matches, flag it as a contingent reference (dsl.md §3.4 bans those) and ask.
- **Entity tracking across edits:** `idtranslations` from the export microversion to the current one.

**Hard or infeasible:**
- **Intent recovery** for structurally new edits (why the engineer added a rib) is the reverse-engineering problem from the survey; no API helps. At best, propose a reading and ask.
- Features with no dipm op (split, move face, replace face, delete face, sheet metal, direct edits) become an opaque **"native island"**. Options: refuse, keep as a pinned imported body, or add dipm ops.
- **Reordering, rollback-bar moves, suppression:** detectable; meaning mappable only partly.
- **Reading back FeatureScript programs:** "Onshape does not directly expose clean, executable FeatureScript programs for existing models". CADFS rebuilt them from the internal representation, normalised them (mm, ordered ids, `makeQuery(op id, type, entity type, disambiguation)`), and discarded about 15% that failed to reproduce ([CADFS](https://arxiv.org/html/2605.01925)). The feature JSON from `GET features` is the practical source. CADFS's normalisation steps are a good template for a "feature JSON → dipm" importer, and its query form matches dipm's (feature, role, source) closely.
- **Custom features (strategy B)** round-trip their parameters perfectly. Edits *inside* their FS code cannot map back.

Conclusion: aim the round trip at **parameter-level and additive standard-feature edits**, with the trailing checks feature catching intent violations natively. Full intent round trip stays a later goal (UX §4).

---

## 6. Practical limits and costs (Q7)

**Annual API call caps, re-verified 2026-11-16** ([API limits](https://onshape-public.github.io/docs/auth/limits/)):

| Plan | Calls/year |
|---|---|
| Free, Standard, EDU Student | **2,500 per user** (the UX doc's "≈2,500/yr on standard plans" is correct) |
| EDU Educator, Pro Discovery | 2,500 per company |
| Professional | 5,000 per user |
| Enterprise / Enterprise GOV | 10,000 per full user |
| EDU Enterprise | 10,000 per enterprise |

- **What counts:** only 2xx/3xx responses from API-key calls, private-app OAuth2 calls (charged to the app owner) and API Explorer calls made with keys or OAuth.
- **What doesn't count:** 4xx/5xx responses, browser/session traffic, webhooks, and **OAuth2 calls from apps publicly listed in the App Store**. A public, approved dipm Onshape app escapes the cap, which matters for any non-trivial use.
- **Limits:** a 429 when a per-endpoint rate limit is hit (thresholds undocumented); a **402** once the annual cap is gone. Extra calls can be bought.
- **Onshape's FeatureScript MCP Server** (Onshape Labs, Aug 2026; `https://fs-mcp.labs.onshape.app/mcp`) counts against the allocation ([PTC](https://www.ptc.com/en/news/2026/onshape-launches-featurescript-mcp-server), [Onshape blog](https://www.onshape.com/en/blog/featurescript-mcp-server-enables-text-code-cad)). It is FeatureScript-only, so it fits strategy B and C's FS library authoring, not tree building.

**Call budget, shelf bracket, hybrid strategy (estimate):**

| Step | Calls |
|---|---|
| Create document (returns workspace + Part Studio) | 1 |
| Variable Studio create + set all variables | 2 |
| Configuration update | 1 |
| Sketch + feature ×5 (body, gusset, A.P, A.3, B.1) + fillet | 11 |
| Reference resolution evals (mount face, shelf face, inner-corner edges, …), batched per step | ~4–5 |
| FS library: link/insert the versioned dipm library (already published) | ~1–2 |
| Verification: 1 combined FS eval + mass properties | 2 |
| STEP export: POST + ≥1 poll + download | ≥3 |
| **Total** | **≈ 25–30** |

On a Free/Standard key that is **≈ 85–100 full exports a year**. A 9-point stability parity sweep adds ~2 calls per point (≈18). Onshape is therefore an **export-on-demand target, never a CI loop**, unless dipm ships as a public App Store app or buys calls. Strategy B (one Feature Studio upload ~3 calls + 1 feature) costs ~5–8 per export, which makes it the cheap *verification* path for CI-style parity checks.

**Batching:** only feature *updates* batch (`features/updates`). Adds are one call per feature; failed (4xx) calls are free. Strategy B collapses a whole design into one add.

**Auth:**
- API keys (Basic or HMAC-signed; "operations run on behalf of the user who generated the keys") suit the CLI.
- OAuth2 is required for App Store distribution ([auth](https://onshape-public.github.io/docs/auth/)).
- The installed plugin uses Basic auth with keys (`api/client.py`).

**ToS:** "The API may not be used for scraping or data extraction from Onshape Public Documents" ([limits](https://onshape-public.github.io/docs/auth/limits/)). This rules out harvesting public docs for training (cf. the CADFS gray zone in `research_notes/Parametric CAD generation survey/datasets_metrics_tooling.md`). Exporting *our own* designs into a user's documents is fine. App Store apps go through Onshape's review checklist.

**Ecosystem help:**
- `jarvis-onshape-mcp` already has validated builders for every op in §2.1, hole defaults, the custom-feature upload dance (`api/custom_features.py`: create Feature Studio → POST source → read `sourceMicroversionId` from featurespecs → insert with `namespace="e{fsEid}::m{mv}"`), variables, STEP export and mass properties. It is the best reference implementation for a dipm `onshape` backend. Its tool API is agent-oriented, so dipm should reuse its *payload shapes*, not its MCP tools.
- FS version drift is real: the plugin's notes show source compiled against version 2242 silently produced an empty symbol table, so pin the version and discover it at runtime.

---

## 7. Open risks

1. **Durability of export-time deterministicIds under engineer edits** is Onshape's persistent naming, which is generally good but opaque, and nothing about it is guaranteed via the API ("NEW features may remap them"). It needs a live spike: export the bracket, sweep the configuration over dipm's 9 sample points, and check that every emitted reference stays on the right face.
2. **Whether `queryString` selections (e.g. `qCapEntity(...)`) persist cleanly** and stay editable when an engineer opens the feature in the UI. **[untested]** If they work, they are structurally closer to dipm than deterministicIds.
3. **Kernel topology differences** (Parasolid seams, automatic face merging) break naive VEFRSH equality; a normalisation rule is needed (cf. the spike 01 counting rule). `clean()` semantics vs Onshape are unverified (spike 02 §9).
4. **Frozen numbers:** until dipm keeps expressions symbolic through lowering (TODO 2), many placements export as literals and won't follow parameter edits in Onshape. **This gap is on the dipm side, not the Onshape side.**
5. **The synthesised sketch dimension scheme** (all dims from the origin) is ugly for engineers and may confuse them. It needs the constructive solver to emit designer-meaningful dims.
6. **Two implementations of every FS-backed intent word** (Python lowering + FeatureScript) can diverge. Parity tests per word are needed (strategy B as an oracle).
7. **Hole featurespec churn:** 161 parameters with V1/V2/V3 lock-step. Onshape can change them at any time ("parameters may change at any time"), so capture defaults from live featurespecs at export.
8. **FS library versioning:** customer documents pin a library version. Updating intent words means pushing "update custom feature" to each document.
9. **API cap** makes Onshape-side parity testing scarce on non-enterprise plans. The App Store route removes the cap but needs OAuth2 and approval.
10. **Ownership of truth after handoff:** even with round-trip parameter sync, two sources of truth exist. The checks feature limits the damage; a release/freeze step (PAIN-08) is still needed.
11. **Attributes and named exports** set by FS may not survive downstream standard-feature splits. **[untested]**
12. **The origin-anchoring quirk** in API sketches (plugin: `variableCenter` known-broken) may cost effort to get fully constrained sketches.

---

## 8. Citations

**Onshape developer docs**
- Feature access (endpoints, BTFeatureDefinitionCall, queries): https://onshape-public.github.io/docs/api-adv/featureaccess/
- FeatureScript eval endpoint: https://onshape-public.github.io/docs/api-adv/fs/
- Associativity / idtranslations (no persistent IDs): https://onshape-public.github.io/docs/api-adv/associativity/
- Configurations: https://onshape-public.github.io/docs/api-adv/configs/
- Translation / STEP export: https://onshape-public.github.io/docs/api-adv/translation/
- API limits (caps, 429/402, what counts, App Store exemption, scraping ban): https://onshape-public.github.io/docs/auth/limits/
- Authentication (API keys vs OAuth2): https://onshape-public.github.io/docs/auth/
- Webhooks: https://onshape-public.github.io/docs/app-dev/webhook/
- Structured storage (app elements): https://onshape-public.github.io/docs/app-dev/structuredstorage/
- API Explorer: https://cad.onshape.com/glassworks/explorer/

**FeatureScript**
- Standard library docs: https://cad.onshape.com/FsDoc/library.html
- std `query.fs` (mirror; historical/state/transient queries, `qCapEntity`, `qNonCapEntity`, `qHoleFaces`, `qPatternInstances`, QueryType enum): https://raw.githubusercontent.com/javawizard/onshape-std-library-mirror/main/query.fs

**Onshape help**
- Hole feature: https://cad.onshape.com/help/Content/hole.htm
- Numeric fields / expressions (ternaries): https://cad.onshape.com/help/Content/numeric-fields.htm
- Variables vs configuration variables: https://onshape.com/cad-blog/tech-tip-parametric-variables-vs-configuration-variables

**Forum**
- deterministicIds vs `qEverything`: https://forum.onshape.com/discussion/26062/please-help-me-deterministicids-do-not-in-all-ids-returned-by-qeverything
- startTracking for extruded side faces, cap queries: https://forum.onshape.com/discussion/7591/proper-way-to-extract-query-face-vertex-edge-out-of-a-rectangle-extrude-body-in-featurescript
- Faces from sketch edges: https://forum.onshape.com/discussion/27825/how-to-identify-faces-directly-created-from-sketch-edges-in-an-extruded-part-featurescript
- FS-created holes keep callouts: https://forum.onshape.com/discussion/8286/use-hole-callout-on-holes-created-in-fs
- deterministicIds tag: https://forum.onshape.com/discussions/tagged/deterministicids
- setVariable from custom features: https://forum.onshape.com/discussion/5066/how-to-make-a-variable-feature-with-multiple-variables
- Custom-feature namespace and upload flow (cited by the plugin): https://forum.onshape.com/discussion/26720/

**MCP and AI**
- PTC: Onshape FeatureScript MCP Server: https://www.ptc.com/en/news/2026/onshape-launches-featurescript-mcp-server
- Onshape blog: https://www.onshape.com/en/blog/featurescript-mcp-server-enables-text-code-cad
- jarvis-onshape-mcp (installed locally, v1.2.0): https://github.com/ReshefElisha/jarvis-onshape-mcp. Payload shapes: `onshape_mcp/builders/*.py`; custom-feature flow: `onshape_mcp/api/custom_features.py`; gotchas: `skills/onshape/SKILL.md`

**Datasets**
- CADFS (FeatureScript programs from ~450k Onshape designs; `makeQuery` form; ~15% failed reproduction): https://arxiv.org/html/2605.01925

**Project files used:** `docs/dsl.md` §3.4, §4, §5, §6.3; `src/dipm/NOTES.md`; `examples/shelf_bracket.py`; `spikes/02-operation-history/RESULTS.md` §6, §9; `docs/user-experience.md` §4–5; `reports/Fresh eyes review.md` (PAIN-08, PAIN-09); `research_notes/Parametric CAD generation survey/datasets_metrics_tooling.md`.

# Spike 01: OCCT feasibility (Euler check, history references, determinism)

*Run 2026-11-15. All numbers below come from `results/run_all.log` and `results/q{1,2,3}.json`, produced by `python run_all.py`.*

| Question | Verdict |
|---|---|
| **Q1** Euler–Poincaré on OCCT topology | **Yes.** It held on all 14 test solids once the counting convention below is used. The per-feature ΔH check works but needs a refinement for intersecting features. |
| **Q2** Operation history for structural references | **Yes for creator roles, partially overall.** Caps, sides-from-sketch-edge, lateral edges, tool faces, section edges and fillet blends are all available. Fragment order after a split is deterministic but arbitrary, and fillet `IsDeleted` is wrong. |
| **Q3** Determinism | **Yes on this machine.** BRep text was byte-identical across 64 builds per model: in-process, across 12 processes, parallel BOP off and on. STEP needs canonicalisation: a timestamp, plus a per-process product-name counter that we had not anticipated. |

---

## 0. Environment

| Item | Value |
|---|---|
| Machine | macOS 26.6.2, Apple Silicon (arm64) |
| Python | 3.12.9 (Homebrew), venv at repo root `.venv`, created with `uv 0.5.9` |
| build123d | 0.13.0 |
| OCP | `cadquery-ocp-novtk` 8.0.1.1 (pulled in by build123d) |
| **OCCT** | **8.0.1** (from `OCP/.dylibs/libTKernel.8.0.1.dylib`; OCP exposes no `Standard_Version`) |
| Full pin | `requirements.lock.txt` (61 packages, `uv pip freeze`) |

**Install notes.** `uv venv --python 3.12 .venv && uv pip install build123d pytest` worked first time, with no conda and no fallbacks. I deliberately chose 3.12 over the system 3.14 for wheel coverage; 3.13 and 3.14 were not tried. OCP 8 API differences that bit me, and will bite anyone porting OCP 7.x snippets:

- `TopTools_IndexedMapOfShape` and friends moved to `OCP.collections` (`IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher`, …).
- `TopoDS.Edge_s` became `TopoDS.Edge`; casts lost the `_s` suffix, but other statics like `BRep_Tool.Degenerated_s` kept it.
- **Iterating an OCP `List_TopoDS_Shape` in Python (`list(l)`, `for x in l`) costs ~2.5 ms per list.** This made a 19-face Euler count take 112 ms. Copy-and-pop (`topo.occ_list`) is about 500× faster: Euler count 0.44 ms, adjacency hash 1.5 ms, `BRepCheck_Analyzer` 1.4 ms on the bracket. The full bracket build plus all per-feature checks takes about 33 ms.
- `Interface_Static "write.step.product.name"` no longer exists (see Q3).

**Layout.** `topo.py` holds counting, the Euler check, signatures and serialisation. `refs.py` is the reference ledger. `bracket.py` is the parametric bracket on raw OCP. `q1_euler.py`, `q2_history.py` and `q3_determinism.py` run the three questions, `run_all.py` is the entry point, and `test_spike.py` holds 25 pytest regression tests pinning each finding, all passing. Run everything with `../../.venv/bin/python run_all.py` (~45 s) and the tests with `../../.venv/bin/python -m pytest -q` (~2 s).

**The bracket** (`bracket.py`) is built on raw OCP, not the build123d builder API, so every operation's history object is in hand:

- L-profile in the YZ plane: leg 0.75·d, arm 0.8·d, thickness t, built from named vertices and edges.
- Symmetric prism of width 6t (E).
- Mid-plane triangular gusset of size 0.4·d, fused (G).
- Two Ø4.5 wall-screw holes (W1, W2) with 90° Ø9 countersinks (K1, K2) on the mount-face centreline. They are placed below the gusset footprint less a 15 mm tool-access radius, at an edge distance of 2×Ø.
- An Ø8 cable hole midway between them (C).
- An Ø4.5 shelf hole at 0.75 of the arm (S).
- A radius-t fillet of the inner corner (F).

Each feature asserts its expected ΔH and runs `BRepCheck_Analyzer`. Defaults are d=200, t=5. The result is V=34, E=51, F=19, R=8, S=1, H=4, valid, volume 61 299 mm³.

---

## 1. Q1: Euler–Poincaré on OCCT topology. Verdict: yes

### 1.1 Counting convention that works

V − E + F − R = 2(S − H) gives an integer H ≥ 0 that matches the expected genus on every test solid, provided:

1. **Sub-shapes are de-duplicated by (TShape, Location), ignoring orientation.** This is exactly `TopExp::MapShapes` into an `IndexedMap` with `TopTools_ShapeMapHasher` (the `IsSame` identity). As a consequence, a **seam edge counts once**, even though its face uses it twice (FORWARD and REVERSED).
2. **Degenerated edges are excluded** (`BRep_Tool::Degenerated`). Their vertex is kept: it is the pole or apex.
3. R = Σ over faces of (wires − 1). S = number of shells (`TopAbs_SHELL`), so an internal void counts as a second shell. H is solved from the formula.

### 1.2 Raw counts (recommended convention)

| case | V | E | F | R | S | H | E incl. degen | degen | seam | valid | pass |
|---|---|---|---|---|---|---|---|---|---|---|---|
| box | 8 | 12 | 6 | 0 | 1 | 0 | 12 | 0 | 0 | ✓ | PASS |
| cylinder | 2 | 3 | 3 | 0 | 1 | 0 | 3 | 0 | 1 | ✓ | PASS |
| cone (apex) | 2 | 2 | 2 | 0 | 1 | 0 | 3 | 1 | 1 | ✓ | PASS |
| cone frustum | 2 | 3 | 3 | 0 | 1 | 0 | 3 | 0 | 1 | ✓ | PASS |
| sphere | 2 | 1 | 1 | 0 | 1 | 0 | 3 | 2 | 1 | ✓ | PASS |
| torus | 1 | 2 | 1 | 0 | 1 | 1 | 2 | 0 | 2 | ✓ | PASS |
| box + 1 through-hole | 10 | 15 | 7 | 2 | 1 | 1 | 15 | 0 | 1 | ✓ | PASS |
| box + 2 through-holes | 12 | 18 | 8 | 4 | 1 | 2 | 18 | 0 | 2 | ✓ | PASS |
| box + blind hole | 10 | 15 | 8 | 1 | 1 | 0 | 15 | 0 | 1 | ✓ | PASS |
| filleted box (all 12 edges) | 24 | 48 | 26 | 0 | 1 | 0 | 56 | **8** | 0 | ✓ | PASS |
| shelled box (top removed) | 16 | 24 | 11 | 1 | 1 | 0 | 24 | 0 | 0 | ✓ | PASS |
| hollow box (internal void) | 16 | 24 | 12 | 0 | **2** | 0 | 24 | 0 | 0 | ✓ | PASS |
| sphere with through-hole | 2 | 4 | 2 | 0 | 1 | 1 | 4 | 0 | 2 | ✓ | PASS |
| shelf bracket (default) | 34 | 51 | 19 | 8 | 1 | 4 | 51 | 0 | 6 | ✓ | PASS |

### 1.3 What breaks the check: solved H under other conventions

| case | recommended | incl. degenerated | orientation-sensitive (`IsEqual`) | TShape-only (`IsPartner`) | raw explorer |
|---|---|---|---|---|---|
| cone (apex) | 0 | **0.5** | 0 | 0 | −3 |
| sphere | 0 | **1** | −0.5 | 0 | −2.5 |
| filleted box | 0 | **4** | 12 | 0 | −68 |
| box | 0 | 0 | **2** | 0 | −14 |
| shelf bracket | 4 | 4 | 12.5 | **5** | −55.5 |

(The full table is in `results/q1.json`.)

- **Degenerated edges** occur at sphere and cone poles, as predicted. They also occur in **fillet corner patches**: filleting all 12 edges of a box adds 8 degenerated edges, one per vertex blend. Counting them gives H=4 for a filleted box.
- **Seam edges** are harmless *if* you de-duplicate ignoring orientation. Orientation-sensitive de-duplication double-counts every edge, seams included, and breaks even the box.
- **Shared TShapes are not just a multi-body issue.** `BRepPrimAPI_MakePrism` builds the END cap, and its edges and vertices, as the START cap's TShape plus a translation Location, *inside a single solid*. Booleans don't remove all of these; 7 shared vertex pairs survive in the final bracket. De-duplicating by TShape alone makes the bracket report H=5. On a compound of two placed copies of one box, TShape-only counting gives V=8, E=12, F=6 for two solids (H=1, wrong). The rule is to always use `IsSame` / `TopTools_ShapeMapHasher`, never `IsPartner`.
- Cost: 0.44 ms per Euler count on the bracket.

### 1.4 Per-feature genus deltas

| feature | expected ΔH | measured ΔH | result |
|---|---|---|---|
| through-hole in plate | +1 | +1 | PASS |
| blind hole (depth 3 of 5) | 0 | 0 | PASS |
| "blind" pocket accidentally too deep (6 > 5) | 0 | +1 | **caught** |
| 2 through-holes in one feature | +2 | +2 | PASS |
| countersink on an existing hole | 0 | 0 | PASS |
| 2nd through-hole **crossing** the 1st | +1 (naive) | **+2** | naive rule wrong |
| 2nd through-hole not crossing | +1 | +1 | PASS |
| fillet all edges of holed plate | 0 | 0 | PASS |
| slot splitting the plate in two | 0 | 0 | PASS: solids 1→2, shells 1→2 |
| bracket E, G, W1, K1, W2, K2, C, S, F | 0,0,+1,0,+1,0,+1,+1,0 | same | PASS at all 20 sweep points |

**Surprise.** "A through-hole adds +1 to H" holds only when the hole is disjoint from existing tunnels. A through-hole that crosses an existing through-hole adds +2: a block with two crossing bores has genus 3. In general ΔH = (new tunnel openings) − (connected tunnel systems merged) + …, which is not a constant of the feature. A split into two parts shows up as ΔS = +1 (and +1 solid), with ΔH = 0.

---

## 2. Q2: Operation history for structural references. Verdict: yes for creator roles; partially overall

### 2.1 What the kernel provides (OCP probes)

| OCCT API | DSL role it supports | Result |
|---|---|---|
| `BRepPrimAPI_MakePrism::FirstShape / LastShape` | `E.cap(START)`, `E.cap(END)` | ✓ one face each |
| `MakePrism::Generated(sketch edge)` | `E.side(from=sketch.edge(X))` | ✓ exactly 1 face per edge |
| `MakePrism::Generated(sketch vertex)` | `E.lateral_edge(from=sketch.vertex(X))` | ✓ 1 edge per vertex (used for `inner_corner`) |
| `BRepAlgoAPI_Cut::Modified(tool face)` | `H.wall` (tool faces surviving into result) | ✓ |
| `BRepAlgoAPI_Cut::IsDeleted(tool cap)` | tool caps that vanish | ✓ correct |
| `BRepAlgoAPI_Cut::Generated(face)` | `H.rim(on=face)`: section edges | ✓ returns the 2 circle edges (+ vertices) |
| `BRepFilletAPI_MakeFillet::Generated(edge)` | `F.blend(from=edge)`, `F.created()` | ✓ 1 blend face per edge |
| `BRepFilletAPI_MakeFillet::IsDeleted(untouched edge)` | ledger propagation | ✗ **returns True for edges still present, unchanged** |

The fillet `IsDeleted` bug showed up in the bracket on all 7 untouched lateral edges. The ledger therefore never trusts `IsDeleted`. It infers deletion as "not in `Modified` and not present in the result map". build123d 0.13's own `ShapeHistory.from_algorithm` makes the same choice, with the same justification in its comments.

**build123d's own surface** (0.13: a `ShapeHistory` wrapper over `BRepTools_History`, plus `Select.LAST` / `Select.NEW`) is *coarser*:

- After extruding a boss, `faces(Select.LAST)` returns 2 faces, with no cap/side distinction.
- After a fillet, `faces(Select.NEW)` returns the 4 blends, with no per-edge source.

It answers "faces created by fillet F" but not "end cap of E" or "side from sketch edge X". Its builders also run `ShapeUpgrade_UnifySameDomain` (`clean`) by default, which merges faces and must be chained into history; build123d does this, but I did not test it here. **Conclusion:** structural roles need OCP-level access to each operation's maker object. The compiler should drive OCP directly, or wrap build123d's `Solid` operations while keeping the maker.

### 2.2 Prototype reference layer

`refs.py` is 83 non-blank lines and handles creation tags, propagation, cardinality and policies. Tagging inside the model adds roughly 20 lines out of 186 in `bracket.py`.

- Each tracked face or edge carries a `Tag(feature, role, source)` and a genealogy of `(op, modified|splitN)` events.
- After every operation the ledger is carried forward with `Modified()` plus result-map presence.
- `resolve(feature, role, source, card=one()|exactly(n)|at_least(n), policy=propagate_all|error_on_split)` returns a set and raises `CardinalityError` on a count mismatch.
- Identity throughout is `IsSame`. `IsPartner` would conflate START and END caps, which share a TShape (§1.3).

Resolved after E → G (fuse) → W/K/C/S (5 cuts + 2 countersink cuts) → F (fillet), at d=200, t=5:

| reference | n | geometry (outward normal / axis) | genealogy |
|---|---|---|---|
| E.cap(START) / E.cap(END) | 1 / 1 | Plane −X / +X | F modified |
| E.side(wall) | 1 | Plane −Y | W1, W2, C modified |
| E.side(mount) | 1 | Plane +Y | G, W1, K1, W2, K2, C, F modified |
| E.side(shelf) | 1 | Plane +Z | S modified |
| E.side(arm_under) | 1 | Plane −Z | G, S, F modified |
| E.side(arm_tip), E.side(leg_end) | 1, 1 | +Y, −Z | untouched |
| G.side(hypotenuse) | 1 | (0, .707, −.707) | untouched |
| G.cap(START/END) | 1 / 1 | −X / +X | F modified |
| W1.wall, W2.wall, C.wall, S.wall | 1 each | Cylinder ∥Y, ∥Y, ∥Y, ∥Z | own cut (+K for W) |
| K1.countersink, K2.countersink | 1 each | Cone ∥Y | own cut |
| **E.lateral_edge(inner)** (input to F) | **exactly(2)** | split by the gusset (`G: split2`) | consumed by F |
| F.blend(E.lateral_edge(inner)) | **exactly(2)** | Cylinder ∥X | — |

The fillet's input reference shows `inner_corner` being split by the gusset into two edges. That is the expected behaviour under a `propagate_all` policy, and the DSL must let the author declare it as `exactly(2)`. An `error_on_split` policy would (correctly) reject it.

### 2.3 Edit-stability harness

Sweep: shelf_depth ∈ {150, 175, 200, 250, 300} × t ∈ {4, 5, 6, 8}, 20 rebuilds. For every one of the 18 references the harness checked:

- cardinality;
- the geometric descriptor (surface type + outward normal or axis);
- the full event genealogy;
- per-feature ΔH;
- validity;
- (V, E, F, R, S, H);
- the topology-only adjacency hash.

**Result: 20/20 points fully stable.** All references resolved with identical cardinality, descriptors and genealogy. (V, E, F, R, S, H) was (34, 51, 19, 8, 1, 4) everywhere, with one topology-only hash, `6dbbca6a7ca1…`. The whole sweep runs in about 1 s.

**Negative controls**, which must fail:

| edit | outcome |
|---|---|
| `shelf_hole_u` 0.75 → 0.4 (shelf screw now lands on the gusset, so the hole becomes blind) | **Caught only by ΔH**: S gives ΔH = 0, not +1. `S.wall` still resolves `one()`, so a reference check alone would have missed it. |
| t=4, countersink Ø9 → Ø14 (countersink swallows the screw bore) | **Caught by cardinality**: `W1.wall` and `W2.wall` expected 1, got 0. |
| shelf_depth 120 | Refused by the layout precondition (no room below the gusset). This is a design-rule failure, not a kernel failure. |

### 2.4 Split ordering (the coarse part)

The plate's top face was split into 2–4 fragments by grooves. `Modified(top)` returned fragments in an order that is **deterministic** and was ascending in the plate's local x across rotations and groove-insertion orders. **However, the same plate drawn from a different sketch start vertex returns the fragments in the reverse order**: start vertex 0 or 3 gives ascending order, 1 or 2 gives descending, and the same holds for either winding. The order follows the face's internal parameterisation, which is an incidental authoring choice. This is direct evidence for §3.4's ban on identity or ordinal references to contingent fragments. Fragments can be referenced only as a set, or selected by an explicit geometric predicate with a tolerance.

---

## 3. Q3: Determinism. Verdict: yes on this machine and build; STEP needs canonicalisation

Six models: bracket(200, 5), bracket(300, 8), box+hole, sphere+hole, filleted box, and a 100×100×5 plate with a 10×10 hole grid cut in **one** boolean (to exercise the parallel BOP paths). The test ran:

- in-process: N=20 per model × parallel off/on;
- 6 separate processes × parallel off/on (distinct `PYTHONHASHSEED` and ASLR layouts), 2 builds each.

That gives 64 builds per model. The table shows the number of **distinct** values across all 64:

| model | (V,E,F,R,S,H) | adj hash (geom) | adj hash (topo) | **BRep bytes** | STEP, timestamp stripped | **STEP canonical** | STEP via build123d | STEP raw | volume | ms/build |
|---|---|---|---|---|---|---|---|---|---|---|
| bracket(200,5) | 1 | 1 | 1 | **1** | 40 | **1** | 1 | 64 | 1 | 33 |
| bracket(300,8) | 1 | 1 | 1 | **1** | 42 | **1** | 1 | 64 | 1 | 33 |
| box+hole | 1 | 1 | 1 | **1** | 42 | **1** | 1 | 64 | 1 | 1.2 |
| sphere+hole | 1 | 1 | 1 | **1** | 42 | **1** | 1 | 64 | 1 | 1.1 |
| filleted box | 1 | 1 | 1 | **1** | 42 | **1** | 1 | 64 | 1 | 3.3 |
| plate 10×10 holes | 1 | 1 | 1 | **1** | 42 | **1** | 1 | 64 | 1 | 62 → 46 |

- **BRep text (`BRepTools::Write`) is byte-identical** across all 64 builds of every model. That covers in-process repeats, separate processes, and parallel BOP off and on. Parallel mode demonstrably ran: the 100-hole cut went from 62 ms to 46 ms. Pointer-hash map iteration order (ASLR) did not leak into the output.
- **STEP has two sources of variation, not one:**
  1. the `FILE_NAME` timestamp, which was expected;
  2. **`PRODUCT('Open CASCADE STEP translator 8.0 <n>')`, where `<n>` is a per-process counter of `STEPControl_Writer` transfers.** Stripping only the timestamp still gives 20 distinct files in 20 in-process writes, although the files agree across processes for the same write index.

  Canonicalising both (`topo.canonical_step`) gives 1 distinct file. build123d's `export_step` uses the XCAF path with named labels and doesn't have the counter; only its timestamp needs stripping. The obvious fix, `write.step.product.name`, no longer exists in OCCT 8.
- **Signature design note.** The adjacency hash with rounded face areas (`adj` geom) changes whenever a parameter changes, so it identifies a specific *geometry*. A hash on surface type, wire count and edge curve types only (`adj_topo`) is constant across the edit sweep, so it identifies a *topology*. Both are needed: geom for "same DSL → identical result", topo for "an edit didn't flip topology".

**Nondeterminism found:** none in the kernel output. The only variations were STEP header and product metadata.

---

## 4. Implications for `docs/dsl.md`

**Keep**
- §3.4 structural references with (feature, role, source) and declared cardinality. Everything we tried resolved and was edit-stable.
- §3.4 "no identity references to contingent entities". This is now backed by evidence: fragment order flips with the sketch start vertex (§2.4).
- §5.2 the Euler check, and §5.4 storing (V, E, F, R, S, H) plus a hash. Both are cheap (< 2 ms) and caught real errors.
- §5.7 the stability harness. It ran in about 1 s for 20 parameter points and detected both negative controls.
- §6.2 OCCT via OCP behind a backend interface. Nothing in this spike argues against it.

**Change**
- §5.2: replace "seam and degenerate edges must be calibrated" with the explicit rule:
  > Count V, E, F over `TopExp::MapShapes` with `TopTools_ShapeMapHasher` (TShape + Location, orientation ignored; seam edges count once); exclude edges with `BRep_Tool::Degenerated` (poles, apexes, **and fillet vertex-blend corners**); R = Σ(wires − 1); S = shells, including internal void shells. Never de-duplicate by TShape alone: `MakePrism` caps share a TShape within one solid.
- §5.3: "a through-hole changes H by exactly +1" is only true when the new tunnel is disjoint from existing ones. The rule should be **"expected ΔH is declared by the feature and computed by its lowering given its interactions"**. For example, a hole lowering asserts +1 only if its tool is disjoint from existing hole tools, or the author declares an interaction. A mismatch is a check failure with a clear message ("hole crosses W1: ΔH=+2"), not a silent pass. Also state that ΔH checks catch faults that reference checks miss: the blind-on-gusset case in §2.3.
- §5.4: specify **two** hashes, a geometric one (rounded areas) and a topology-only one, and say which comparison uses which. Specify the hash precisely as WL over the face-adjacency graph, with seam self-loops, degenerated edges skipped, sha256 rather than language `hash()`, and sorted multisets.
- §6.2 table, last row: "Parallel Boolean modes may break determinism" was not observed on OCCT 8.0.1. Keep "pin version; verify in CI", but parallel mode need not be disabled on these grounds alone. Re-test on Linux/x86 before relaxing it globally.
- architecture §7 "canonical serialization": use **BRep text** as the canonical textual form. STEP needs canonicalisation of `FILE_NAME` and of the `PRODUCT` translator counter, or should be written via XCAF with explicit names.

**Add**
- §3.4 role vocabulary confirmed for OCCT: `extrude.cap(START|END)`, `extrude.side(from=sketch.edge)`, `extrude.lateral_edge(from=sketch.vertex)`, `boolean.tool_face(role)` (e.g. `hole.wall`, `hole.countersink`), `boolean.section_edges(on=face)` via `Generated(face)`, `fillet.blend(from=edge)` / `fillet.created()`. Not yet tested: revolve, shell or offset (`MakeThickSolid` history), chamfer, loft, sweep, draft, pattern.
- §3.4: split/merge policy must be declarable on *any* reference, not only named exports. `inner_corner` is split by the gusset and needs `exactly(2)` with `propagate_all`.
- §3.4: "Resolved references return shapes oriented as in the result solid." History lists return faces in arbitrary orientation, and the harness had to look faces up in the solid to get outward normals.
- §6.2: "The reference layer **must not trust `IsDeleted`**. Deletion is inferred from Modified plus result presence. `BRepFilletAPI_MakeFillet::IsDeleted` reports untouched edges as deleted."
- §6.2: the compiler needs each operation's OCP maker object. build123d's `Select.LAST` / `Select.NEW` (`ShapeHistory`) lacks role granularity, so wrap at OCP level or keep the maker.
- §7 open risks: delete risk 3 ("counting conventions untested"), since it is resolved. Narrow risk 5: build123d 0.13 does have history (`ShapeHistory` over `BRepTools_History`) but not role-level, and it was dated 2026, so it is new API.

## 5. Remaining risks / not tested

- **Single platform.** Everything ran on one Mac (arm64), one OCCT build (8.0.1 via cadquery-ocp wheels), one Python. Cross-platform (Linux x86_64 CI) and cross-version byte identity of BRep output is untested and is the most likely place for differences to appear.
- Parallel mode was exercised only through BOP (`SetRunParallel` / `SetParallelMode`). Fillet, offset and meshing parallel paths were not exercised.
- History was tested for prism, fuse, cut and fillet only. Not tested: revolve (periodic seams in history), `MakeThickSolid` (shell), chamfer, loft, sweep, draft, or build123d's `clean()` (UnifySameDomain) merges.
- Only one bracket topology was swept. No parameter range made the gusset or fillet change topology, so a topology-changing edit inside the "valid" range was not observed. The negative controls were constructed deliberately.
- Fillet robustness was not stress-tested: large radii, fillets meeting holes, variable radius.
- The Euler check covers manifold solids only. Non-manifold results and compounds of solids were not tested beyond the 2-box demo.
- The geometric adjacency hash rounds areas to 6 significant figures. A result near a rounding boundary could hash differently across platforms, so use the topo hash plus tolerance comparisons there.

## 6. Suggested next spikes

1. **Cross-platform determinism.** Run `q3_determinism.py` in Linux x86_64 and Linux arm64 containers with the same lockfile, and compare the BRep hashes to the macOS ones.
2. **History coverage for the trusted primitives.** Revolve, shell (`MakeThickSolid`), chamfer, loft, sweep, draft and linear/circular pattern, each with a role table like §2.1 plus an edit sweep.
3. **ΔH from lowering.** Compute expected ΔH from tool interference (disjoint vs intersecting tunnels) inside the hole and pattern packages, and decide how authors declare intentional intersections.
4. **build123d integration path.** Decide whether the compiler emits build123d (readable, `clean()` merges faces) or raw OCP (full history), and prototype keeping the maker object through build123d's `Solid` operations.
5. **FeatureScript parity.** Express the same 18 references as FeatureScript queries with `evaluateQueryCount` guards on the same bracket, and diff the cardinalities.

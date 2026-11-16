# Spike 02: operation history for the remaining operations

*Run 2026-11-15/16, unattended. All numbers come from `results/run_all.log` and `results/q{1,2,3,4}.json`, produced by `python run_all.py`. Nothing outside `spikes/02-operation-history/` was edited. The recommended doc changes in §8 are proposals only.*

Spike 01 validated history-based structural references for extrude, boolean cut, hole and fillet. This spike extends the same evidence to revolve, chamfer, shell/thick solid, loft, sweep, draft, linear and circular pattern, mirror, and build123d's `clean()` (`ShapeUpgrade_UnifySameDomain`, "USD" below).

## Verdicts

| operation (OCP builder) | structural roles | invariants (Euler + BRepCheck) | expected ΔH / ΔS | edit stability (Q2) | determinism (Q3) |
|---|---|---|---|---|---|
| **Revolve** (`BRepPrimAPI_MakeRevol`) | **Supported, with one workaround.** Caps, side per profile edge, circle edge per profile vertex. A full 360° revolve drops `Generated()` for profile edges perpendicular to the axis; `MakeRevol.Revol().Shape(edge)` recovers them. | Hold, including seam edges (360°: 2 seams). | Creator: ΔS=+1. H=0 for a partial revolve; H=+1 for a full revolve of a region off the axis; H=0 if the region touches the axis. | 16/16 points as declared. Topology changes only at 360° (caps vanish, H 0→1), as declared. | Byte-identical |
| **Chamfer** (`BRepFilletAPI_MakeChamfer`) | **Supported.** One face per input edge (`Generated(edge)`); a corner face per vertex where ≥3 chamfers meet (`Generated(vertex)`). **`IsDeleted` is wrong** (10 false positives), exactly as with fillet. | Hold | ΔH=0, ΔS=0 | 18/18 built points as declared. A chamfer that would consume a face **fails loudly** (6 of 24 points). | Byte-identical |
| **Shell / thick solid** (`BRepOffsetAPI_MakeThickSolid`) | **Supported:** offset face per face (`Generated(face)`); rim per opening (`Modified(opening)`); arc-join faces per edge/vertex for outward offsets (`Generated(edge/vertex)`). **Partial:** with no openings it builds an *offset solid*, not a hollow; faces are reachable only through `Generated`, and edges have no history. A real hollow needs offset + cut. | Hold. **But a collapsing shell returns an invalid shape without raising** (Euler also fails), or a null shape. | ΔH=0. ΔS=0 with openings; ΔS=+1 for the offset+cut void. | 16/19 points. The 3 failures are all collapse (t ≥ half the wall): 2 silently invalid, 1 null. | **Not byte-identical** for join-mode offsets (outward, or no openings): the BRep differs on every build. Topology, geometry and role geometry are identical. Inward shells with openings are byte-identical. |
| **Loft** (`BRepOffsetAPI_ThruSections`) | **Supported:** caps (`FirstShape/LastShape`) and sides per section edge (`Generated(edge)`). **Partial:** a ruled multi-section loft returns all spans for one edge (no per-span role from history); incompatible sections (square→circle) are split by OCCT, and `GeneratedFace` returns null for a split edge. | Hold | Creator: ΔS=+1, H=0 | 27/27 as declared. Equal sections turn the sides planar, which flips the topology-only hash (a surface-type change). | Byte-identical |
| **Sweep** (`MakePipe`, `MakePipeShell`) | **Supported:** caps; side per profile edge (one face per spine edge); per (profile edge, spine edge) through `MakePipe.Generated(spineEdge, profileEdge)`. `MakePipeShell` has only the set-level role. Spine edges must come from the wire (`MakeWire` may copy them). | Hold, including closed spines and torus-like sweeps. **A self-intersecting sweep passes Euler; only BRepCheck catches it.** | Creator: ΔS=+1. H=0 on an open spine; H=+1 on a closed spine. | 28/30. The 2 failures are self-intersecting sweeps (profile half-width > bend radius), flagged invalid. | Byte-identical |
| **Draft** (`BRepOffsetAPI_DraftAngle`) | **Partial.** Drafted faces come back through **`Generated(face)`, not `Modified`**, so spike 01's ledger loses them; neighbours come back through `Modified`. **No edge or vertex history at all.** Edges must be re-derived from face references (`edges_between`). | Hold | ΔH=0, ΔS=0 | 10/10 built points as declared, using face refs plus derived edges. Past the collapse angle the kernel **fails loudly**. | Byte-identical |
| **Linear / circular pattern** (placed tool copies + one boolean) | **Supported** as `instance(k).<tool role>`, provided each instance is a **separate tool** in one boolean. **Unsupported and dangerous:** instances packed in one compound tool. If they overlap, the result is wrong but valid: nothing is cut, extra solids appear, and BRepCheck and Euler both pass. | Hold (tool-list path) | ΔH = Σ over instances of each tunnel's contribution, computed from interactions. Overlapping instances, an instance off the part, or a ring that splits the disc (ΔS=+1) all change it. | Every deviation (24/36, 12/16, 8/12 as declared) is a legitimate topology change, or the compound path. All were caught by ΔH, ΔS or cardinality. | Byte-identical |
| **Mirror** (`BRepBuilderAPI_Transform` + fuse) | **Supported:** `image(of=ref)` through `ModifiedShape`, then carried through the fuse. Faces on the mirror plane vanish when the halves touch, and coplanar halves stay split until `clean()`. | Hold | ΔH and ΔS from interactions: disjoint gives ΔS=+1; touching or overlapping gives 0. | 6/10. The 4 deviations are overlapping halves (split faces), which are legitimate. | Byte-identical |
| **`clean()` / UnifySameDomain** | **History is complete and correct** (`History()` is a `BRepTools_History`; 0 disagreements in 6 cases). When nothing merges, sub-shape identity is fully preserved. When faces merge, two references alias one face; `Ledger2` records a `merged` event, and `error_on_merge` rejects it. | Hold | ΔF ≤ 0; H and S unchanged | n/a (deterministic transform) | Byte-identical |

**Bottom line.** Every operation exposes usable creator roles through OCP history. The workarounds are a revolve fallback, following `Generated` for draft and offset, and re-deriving edges from faces. The Euler counting rule from spike 01 needed **no refinement**: it held on all 29 models and on 192 of the 193 sweep points that built. The one failure was a collapsed shell, which was also BRepCheck-invalid. The new risks are elsewhere: (1) **silent kernel failures** (collapsing shells, and the valid-but-wrong compound boolean), which only ΔS, volume or validity checks catch; and (2) **byte-level nondeterminism in `BRepOffset` join mode**, which breaks "BRep text is canonical" for those operations.

---

## 0. Environment and layout

| Item | Value |
|---|---|
| Machine | macOS 26.6.2, Apple Silicon (arm64). Same machine as spike 01. |
| Python / venv | 3.12.9, repo-root `.venv` (spike 01's) |
| build123d / OCP / OCCT | 0.13.0 / `cadquery-ocp-novtk` 8.0.1.1 / **8.0.1** |
| Packages added | **None.** Only spike 01's `requirements.lock.txt`. |

**Code.** Spike 01's `topo.py` and `refs.py` are **imported, not copied**. `common.py` appends `../01-occt-feasibility` to `sys.path`. It appends rather than inserts because spike 01 also has a `q3_determinism.py`, and the local module must win the name clash.

| file | contents |
|---|---|
| `common.py` | Named sketch polygons; result-presence map; **`audit_history`**, which checks a maker's `Generated/Modified/IsDeleted` against the result and classifies disagreements; `coverage` (faces no role reaches); geometric descriptors; **`Ledger2`**, spike 01's ledger plus `follow_generated` and **merge detection** / `error_on_merge`; `HistoryAdapter` for `BRepTools_History` |
| `ops.py` | One parametric raw-OCP model per operation. Each returns an `OpRun`: result, the roles captured from the maker, the **declared** cardinalities and ΔH/ΔS, and the base-body ledger propagated through the op. `DEFAULTS` registers 29 models. |
| `q1_roles.py` | Role tables, history audit, coverage, invariants |
| `q2_stability.py` | 17 parameter sweeps, 202 points (193 built) |
| `q3_determinism.py` | In-process and cross-process rebuilds of all 29 models |
| `q4_clean.py` | USD history and reference survival |
| `run_all.py` | Entry point, about 40 s: `../../.venv/bin/python run_all.py > results/run_all.log` |
| `test_spike.py` | **85 pytest regression tests** pinning each finding, about 6 s: `../../.venv/bin/python -m pytest -q` |

**Method notes.**

- **Base body.** "E" is a 40×30×20 block extruded from a named rectangle a(0,0) b(40,0) c(40,30) d(0,30). It has `E.cap(START|END)`, `E.side(a-b|b-c|c-d|d-a)` and `E.lateral_edge(a..d)`, tagged as in spike 01.
- **History audit** (`common.audit_history`). It checks every input sub-shape against the result. A disagreement between `IsDeleted` and "absent and no `Modified` image in the result" is classified as one of three kinds:
  - **false_deleted**: the kernel says deleted, but the shape is in the result. This is a kernel bug, as with the fillet in spike 01.
  - **consumed**: the shape is absent and the kernel says not deleted, but `Generated` images exist. This is benign: creator ops consume sketch entities, and draft and offset report their images through `Generated`.
  - **missed_delete**: the shape is absent, with no image of either kind, and the kernel says not deleted. In draft this is exactly the missing edge and vertex history.
- **Coverage.** Coverage counts the result faces that no role or propagated base reference reaches. It is **0 on all 29 models**. Every face of every result is nameable structurally, given the roles below.
- **Declared vs observed.** The harness compares what an author would declare (cardinality, ΔH, ΔS) with what the kernel produced. A Q2 point is *as declared* when Euler, validity, ΔH, ΔS, every role cardinality and every base reference all match.

---

## 1. Per-operation evidence (Q1 + Q2)

Full role tables are in `results/run_all.log` ("Q1 role tables"). Descriptors show the surface type plus the outward normal or axis, oriented as in the result.

### 1.1 Revolve

Profile: rectangle `bottom / outer / top / inner` in the XZ plane, r ∈ [r_in, 10], z ∈ [0, 4], revolved about Z.

| role | API | partial (θ<360) | full (θ=360) | full, profile on axis |
|---|---|---|---|---|
| `cap(START)`, `cap(END)` | `FirstShape/LastShape` | 1 each | **absent**: `FirstShape` IsSame `LastShape`, and neither is in the result | absent |
| `side(from=edge)` | `Generated(edge)` | 1 each | `outer`/`inner`: 1. **`bottom`/`top`: `Generated` is empty and `IsDeleted` is True, although the swept faces are in the result.** | the edge on the axis gives no face (declared 0) |
| fallback | `MakeRevol.Revol().Shape(edge)` | not needed | returns the planar annulus that **is** in the result | same |
| `circle_edge(from=vertex)` | `Generated(vertex)` | 1 each | 1 each | 0 for vertices on the axis |

- (V,E,F,R,S,H) is (8,12,6,0,1,0) for a partial revolve, **(4,6,4,2,1,1)** for a full one (2 seam edges, annular faces with inner loops), and (2,3,3,0,1,0) for a full revolve on the axis. A slanted top (cone face) behaves the same; only the perpendicular edge needs the fallback.
- The gap is specific to the full revolve, perhaps because OCCT rebuilds planar faces that would otherwise carry a seam. θ=359.9 needs no workaround. Both caps of a 180° revolve correctly report outward normal −Y.
- Sweep θ ∈ {15, 90, 180, 270, 345, 359.9, 360} × r_in ∈ {0, 5}, plus slanted tops: **16/16 as declared**, genealogy constant within each of the 6 topology classes.

### 1.2 Chamfer

- One face per input edge (`Generated(edge)`), including derived input edges such as `edge(E.side(a-b), E.cap(END))` (see §7).
- Chamfering all 12 edges creates **8 corner triangles that come from `Generated(vertex)`**. Without that role, 8 of 26 faces were unnamed. Two-distance chamfers (`Add(d1, d2, edge, face)`) behave the same.
- **`IsDeleted` gives 10 false positives** on the two-edge chamfer: untouched edges are reported as deleted. This is the same defect as `MakeFillet` in spike 01, so the "never trust `IsDeleted`" rule extends to all of `BRepFilletAPI`.
- The base references survive with `modified` events. `E.lateral_edge(a)`, the chamfered edge, is consumed (declared 0).
- Sweeps:
  - d ∈ 0.5…25 on two edges: 8/8 built points as declared; d ≥ 20 (the block height) **raises**.
  - "Ridge" (both long top edges, so `E.cap(END)` shrinks to nothing at d=15): d ≤ 14.99 is fine and `E.cap(END)` stays `one()`; **d=15 and 16 raise**. OCCT does not produce the "face consumed" topology change. It refuses, so the expected topology change surfaces as an error, not as a cardinality change.
  - All 12 edges: d ≥ 10 raises.

### 1.3 Shell / thick solid

| role | API | result |
|---|---|---|
| `offset(from=face)` | `Generated(face)` | 1 per kept face. Inward (t<0) gives the inner wall; outward (t>0) gives the outer skin, while the originals become the inner wall. |
| `rim(opening=face)` | `Modified(opening face)` | 1 per opening: the annular rim face (R=1 for a single opening). **A reference to the opening face therefore propagates to the rim** (genealogy `SH: modified`). |
| `join(from=edge)`, `join(at=vertex)` | `Generated(edge)`, `Generated(vertex)` | Outward arc joins: 8 cylinders and 4 spheres on the open-top block. Without them, 12 of 23 faces were unnamed. |
| `void(from=face)` (offset + cut) | `MakeOffsetShape.Generated(face)` → `Cut.Modified` | 1 per face; ΔS=+1 |

- **`MakeThickSolidByJoin` with an empty opening list does not make a hollow.** It returns the inward offset solid: S=1, volume 14 976 = 36·26·16. Its faces are reachable only through `Generated`, which needs `Ledger2(follow_generated)`, and its edges have no history. A true closed hollow needs `MakeOffsetShape` plus `Cut`; that gives (16,24,12,0,**2**,0), and all six `void(from=…)` roles resolve.
- The cylinder cup works the same way: seam edges, offset cylinder via `Generated`.
- **Silent collapse.**
  - The open-top shell at t=−15 (half the 30 mm width) returns a shape with 2 shells that is **invalid, with non-integer Euler H, and no exception**.
  - The closed void at t=10 is invalid; at t=12 the kernel returns a **null** shape without raising.
  - Validity and Euler catch these only if they actually run after every trusted primitive.
- Sweeps: open top t ∈ {−0.5…−15, +2}, 7/8; two openings, 5/5; closed void t ∈ {0.5…12}, 4/5 built plus 1 null. The outward t=+2 point is a different topology class (arc joins) that is still as declared.

### 1.4 Loft

- `cap(START|END)` = `FirstShape/LastShape`. `side(from=section k edge)` = `Generated(edge)`; the same faces are reachable from every section's corresponding edge.
- **Ruled 3-section loft:** `Generated(edge)` returns **both spans** (n=2) for every section's edge. History offers no per-span role. A span can only be selected by derivation, e.g. "the side adjacent to `cap(START)`".
- **Incompatible sections** (square → square → circle): OCCT splits the circle into 4 and then **splits edge `b-c` once more in every section**, giving `side(from=s0.b-c)` n=2 and `side(from=s2.circle)` n=5. `GeneratedFace(b-c)` returns **null** (it is single-face), while `Generated` returns both pieces. The split choice is deterministic but is an internal rule, so declare these as `at_least(1)`, or require compatible sections.
- Sweeps:
  - s1 ∈ {4…30} × twist ∈ {0, 15, 45}: 15/15.
  - 3 sections, smooth or ruled × z1: 6/6.
  - Square → circle: 6/6.
  - s1=20 with twist 0 (identical sections) produces **planar** sides instead of B-splines. That flips the topology-only hash, because surface type is in its node label, even though (V,E,F,R,S,H) is unchanged.

### 1.5 Sweep

- `MakePipe`: `cap(START|END)` = `FirstShape/LastShape`, which are absent on a closed spine. `side(from=profile edge)` has **one face per spine edge** (n=2 on a line+arc spine). `Generated(spineEdge, profileEdge)` gives **exactly one face per (profile edge, spine edge)**.
  - The spine edges must be taken from the wire with `BRepTools_WireExplorer`. `BRepBuilderAPI_MakeWire` copied the arc edge, so passing the original arc raised "Edge not in the Spine".
- `MakePipeShell` (corrected Frenet and Frenet): same caps and set-level sides, but no two-argument `Generated`.
- Closed spine (a circle): no caps, (4,8,4,0,1,**1**) with 4 seams; a circular profile gives a torus (1,2,1,0,1,1). Euler holds with no refinement.
- Sweeps: bend radius {5…40} × profile width {2, 6, 12} × {pipe, pipeshell}, 22/24; closed spine × {rect, circle} × width, 6/6.
  - **The two failures are self-intersecting sweeps** (half-width 6 > bend radius 5). Euler passes and (V,E,F,R,S,H) is the same as the good sweeps; only **BRepCheck** flags them.

### 1.6 Draft

- Drafting all four sides of E by 5° about z=0, pulling +Z:
  - **Drafted faces come back through `Generated(face)`; `Modified(face)` is empty**, and so is `IsDeleted`. The undrafted caps come back through `Modified`.
  - **Spike 01's ledger, which follows `Modified` and presence only, loses all four `E.side` references** (count 0). `Ledger2(follow_generated=True)` keeps them (`regenerated`).
- **No edge or vertex history.** All 12 edges and 8 vertices are "missed_delete": absent, no images, not deleted. `E.lateral_edge(*)` therefore cannot propagate.
  - **Workaround:** re-derive each edge as `edges_between(E.side(prev), E.side(next))` from the face references. This gives exactly 1 edge at every sweep point.
- Sweep angle ∈ {0.5…36.8, −5, −20}: **10/10 built points as declared**. At 37° and 40°, past the 36.87° collapse of the top face, the kernel **raises**.

### 1.7 Linear and circular pattern

- The model is a hole tool (Ø6) with instance k as a placed copy (`BRepBuilderAPI_Transform(copy=False)`, shared TShape, own Location), cut from E (linear) or from a Ø40 disc (circular). The role is `instance(k).wall` = `Cut.Modified(instance k wall)`.
  - k is the pattern's own declared index. It is an intent-level parameter, not a kernel ordinal.
  - Identity with `IsSame` keeps shared-TShape instances distinct, as spike 01 predicted.
- **Three ways to combine instances were compared:**

| combine | disjoint instances | overlapping instances (pitch 5 < Ø6) |
|---|---|---|
| `tool_list`: one boolean, each instance a separate tool | correct; ΔH=n | correct: the instances merge into one slot (ΔH=1); walls may split (see below) |
| `sequential`: one cut per instance | correct, identical result | identical to `tool_list` |
| `compound`: one boolean, all instances in **one compound tool** | correct | **Wrong.** For linear holes: volume stays 24 000 (nothing cut), with 2–4 solids. **BRepCheck says valid and Euler passes**; even the instance-wall roles resolve `one()` each. Only **ΔS=+2…+4**, the base-cap cardinality (`split4`) and the volume reveal it. Circular holes with n=12 give ΔS=+12. With n=11, and with overlapping fused bosses, the result is also BRepCheck-invalid. |

  The compound case matches OCCT's rule that a boolean argument must not self-interfere. Our harness hit it naturally, which makes it the most dangerous finding of the spike.
- **Legitimate topology changes**, all detected (tool-list path):
  - n=4 at pitch 12: instance 3 (x=44) lies entirely off the 40 mm block, so `instance(3).wall` is 0 and ΔH=3, not 4.
  - Overlapping linear holes: ΔH=1 for any n.
  - A ring of 11 or 12 overlapping holes cuts the disc **into two solids** (ΔS=+1), and each wall is split into 3 faces.
- **Seam-dependent splits.** With two overlapping holes, `instance(0).wall` is 1 face but `instance(1).wall` is **2 faces**. This is consistent with the cylinder's seam (at +X) being removed with the overlap on instance 0 but surviving mid-arc on instance 1. Whether a periodic face splits therefore depends on where the seam happens to sit. It is another contingent split, and `clean()` merges it back (§4).
- Bosses (fused): `instance(k).side` and `instance(k).top` resolve 1 each when disjoint. When they overlap, the coplanar tops split into shared pieces until `clean()`.

### 1.8 Mirror

- `BRepBuilderAPI_Transform` with a mirror `gp_Trsf` gives `image(of=ref)` = `ModifiedShape(ref)` for every face (orientation is handled, and the result is valid). The images are tagged `M.*` and carried through the fuse with the ledger.
- **Touching** (plane through `E.side(p-q)`): `E.side(p-q)` and its image become internal and are deleted (declared 0). The other coplanar pairs (caps, `o-p`, `q-r`) remain **two faces each** until `clean()`.
- **Disjoint** (gap 5): 2 solids, ΔS=+1, everything 1:1.
- **Overlapping** (gap −1, −5): coplanar faces split into three pieces (original-only, shared, image-only), so `image(of=…)` resolves to 2 faces including the shared one. After `clean()` everything is 1 face again, with `merged` events.
- Sweep gap ∈ {−5, −1, 0, 1, 5} × clean: 6/10 as declared. All 4 deviations are the overlap cases above, which are legitimate.

---

## 2. Invariants: Euler–Poincaré and ΔH / ΔS

- **The spike-01 counting rule needed no refinement.** Seams appear in revolves (2), closed sweeps (4), the torus sweep (2), cylinder cups and hole walls. Every seam counts once under `TopTools_ShapeMapHasher`, and H came out integral and correct everywhere.
- **Degenerated edges:** none were produced by these ops. That includes a full revolve of a profile touching the axis: OCCT emits no pole edges for a cylinder with planar ends.
- **"Necessary, not sufficient" now has concrete examples.** Each of these passed some checks and failed others:

| fault | Euler | BRepCheck | ΔH / ΔS / volume |
|---|---|---|---|
| self-intersecting sweep | **passes** | fails | unchanged |
| collapsing shell (t=−15) | fails (H non-integer) | fails | ΔS=+1 |
| closed void at t=10 | passes | fails | — |
| overlapping instances in one compound tool | **passes** | **passes** | **ΔS=+2…+12; volume unchanged** |

  The last row is the strongest argument yet for computing ΔS, not only ΔH, from intent. A volume or "material removed > 0" sanity check would also have caught it.
- **ΔH/ΔS rules observed**, to be declared by each primitive:

| op | ΔH | ΔS |
|---|---|---|
| revolve (creator) | 0 partial; +1 per full revolve of a region disjoint from the axis; 0 if the region touches the axis | +1 |
| loft, open sweep (creator) | 0 | +1 |
| closed-spine sweep (creator) | +1 | +1 |
| chamfer, draft, shell with openings | 0 | 0 |
| shell with no openings (offset + cut) | 0 | +1 (void shell) |
| pattern of holes | Σ per-instance contributions: +1 for a disjoint through-tunnel, 0 if off the part, merged groups count once; can split the part (ΔS>0) | computed |
| pattern of bosses | 0 | 0 unless disjoint from the body |
| mirror + fuse | from interaction; 0 for the convex L-body tested | 0 touching or overlapping; +1 disjoint |
| `clean()` | 0 | 0 (F and E decrease) |

---

## 3. Determinism (Q3)

All 29 models were rebuilt 10× in-process (5 with parallel BOP off, 5 on) plus in 4 separate processes × 2 builds (distinct `PYTHONHASHSEED`, parallel alternating): 18 builds per model, 5 processes. The comparison covered BRep text, (V,E,F,R,S,H), both adjacency hashes, an **index role fingerprint** (each role's positions in the result's `TopExp` map, plus the base ledger and its genealogy) and an **order-free role-geometry fingerprint** (each role's rounded centroid and area).

| result | models |
|---|---|
| **1 distinct value for every key** | 26 of 29, including every revolve, chamfer, loft, sweep, draft, pattern, mirror and `mirror.fuse_clean`, and the inward shells with openings |
| **BRep bytes and index fingerprint vary; signature, geometry and role geometry do not** | `shell.no_openings` (18 distinct BRep in 18 builds), `shell.open_top_outward` (18/18), `shell.closed_void` (5/18) |

The second row was isolated with parallel mode off, single-threaded, in one process:

- `BRepOffsetAPI_MakeOffsetShape::PerformByJoin` (±2) gives **12 distinct BRep files in 12 builds**. `MakeThickSolid` with no openings or outward thickness behaves the same way. `PerformBySimple` and inward `MakeThickSolid` with openings give 1 file in 12.
- The differences are in **sub-shape order and curve parameterisations**: the face order by centroid differed in 8 of 8 builds, and the sorted line multisets differ too. Volume is equal to 1e-9; the signature and the per-role centroid and area are identical.
- **References are still stable:** each role resolves to the geometrically identical face on every build. **"BRep text is the canonical serialization" is false for join-mode offsets.** The likely cause is pointer-keyed map iteration inside BRepOffset; this is not confirmed.
- A downstream boolean (the closed void) reduces the variation but does not remove it: 5 distinct files.

Build times (median): 1–2 ms for revolve and sweep, 5–15 ms for loft, draft and mirror, 15–37 ms for shell, chamfer and patterns, 75 ms for 12-edge chamfer.

---

## 4. `clean()` / UnifySameDomain (Q4)

build123d 0.13 runs `ShapeUpgrade_UnifySameDomain(shape, UnifyEdges=True, UnifyFaces=True, ConcatBSplines=True)` with `AllowInternalEdges(False)` **after every boolean by default** (`SkipClean.clean`), and chains the result into its `ShapeHistory` through `ShapeHistory.from_unify`. Here it was run on raw OCP with the same settings. `History()` (a `BRepTools_History`) was wrapped in `HistoryAdapter` and fed to `Ledger2`.

| case | (V,E,F,R,S,H) before → after | sub-shapes kept IsSame | history audit | reference outcome |
|---|---|---|---|---|
| plain block (nothing to merge) | unchanged | 6/6 F, 12/12 E, 8/8 V | clean | all 10 refs unchanged, no events |
| **spike-01 bracket** | (34,51,19,8,1,4) unchanged | 19/19, 51/51, 34/34 | clean | **all 18 references resolve with their declared cardinality** |
| mirror + fuse | (20,32,14,…) → (16,24,10,0,1,0) | 2/14 faces | clean | `E.cap(START)` and `M.cap(START)` now **IsSame one face**: event `merged`; `error_on_merge` rejects it. Unmerged faces that clean() still rebuilt (`E.side(r-s)`) get a plain `modified`, so presence alone would have lost them. |
| two 180° revolves fused | (8,16,8,0,1,1) → (4,6,4,2,1,1) | 0/8 faces | clean | half-cylinders merged **across the seam** into periodic faces; all 6 refs `merged` |
| overlapping holes, sequential | wall n=2 → 1 | 4/9 | clean | the seam-split `instance(1).wall` is merged back to 1 face (`merged`) |
| line+arc sweep | (12,20,10,…) → (12,18,8,…) | 6/10 | clean | the coplanar planar sides along the line and the arc are **merged**: `side(from=a-b, along=spine0)` and `along=spine1` alias one face. The plane + cylinder pairs stay separate. |

"Clean" in the audit column means `false_deleted = consumed = missed_delete = modified_not_in_result = 0`.

**Answers.**

1. **Does it provide history?** Yes. `History()` gives `Modified` and `IsRemoved`, and it was **complete and correct in every case**. It is the best-behaved history object in this spike.
2. **Can references survive merging?** Yes, mechanically: every reference still resolves. Semantically, though, two references that were distinct now **alias one face**, and cardinalities can *decrease*: a split resolves to `one()` again, and per-segment sweep roles collapse. Merge detection must therefore be a ledger feature. It is not in spike 01's `refs.py`; `Ledger2` adds it in about 15 lines.
3. **Forbid, wrap, or always run?** The recommendation is to **wrap it and always run it**, as an explicit core step after booleans, patterns and mirrors, with history chained into the ledger. Never let it run implicitly inside build123d. The reasons:
   - It is a no-op on sub-shape identity when nothing merges (the bracket).
   - It is deterministic.
   - It restores the "one logical face, one B-rep face" canonical form that authors expect, and that Onshape/Parasolid produce for coplanar unions. That last point is not verified in this spike.
   - It *repairs* contingent splits, such as seam splits and the coplanar halves of a mirror.

   Forbidding it would leave mirror and pattern results full of coplanar fragments that are themselves contingent. Running it implicitly hides the merge events that policies need.

   The costs: references that the author intends to be distinct can merge (the sweep segments), so `error_on_merge` must be available per reference, and the DSL should warn when a declared `one()` reference resolves to a face shared with another reference.

---

## 5. Surprises

1. **Full revolve: `Generated()` is empty, and `IsDeleted()` is True, for profile edges perpendicular to the axis**, yet their faces are in the result. Workaround: `MakeRevol.Revol().Shape(edge)`, checked for presence. Pinned in `test_full_revolve_drops_generated_for_axis_normal_edges`.
2. **Draft reports drafted faces through `Generated`, not `Modified`, and gives no edge or vertex history.** A Modified-only ledger loses every drafted face. Workaround: `follow_generated` (face→face, same type) plus edges re-derived from face references.
3. **`IsDeleted` is wrong for chamfer too** (10 false positives), so treat it as broken for all of `BRepFilletAPI`.
4. **`MakeThickSolid` with no openings is an offset, not a hollow.** A hollow needs offset + cut. A reference to an opening face lands on the rim.
5. **Overlapping pattern instances packed in one compound tool produce a valid, Euler-consistent, completely wrong solid** that cuts nothing. Workaround: always pass instances as separate tools (`SetTools` with a list), and check ΔS and volume.
6. **Collapsing shells return invalid or null shapes without raising.** Chamfer and draft overreach, by contrast, raise. Failure modes differ per primitive, so validity must run after each one.
7. **`BRepOffset` join mode is not byte-deterministic**, even single-threaded and in-process; only order and parameterisation change.
8. **`BRepBuilderAPI_MakeWire` copies edges.** The spine edge passed in was "not in the Spine", so take edges from the built wire.
9. **Seam position decides whether a trimmed periodic face splits** (the overlapping-hole walls). This is another contingent split; `clean()` repairs it.
10. **Loft with incompatible sections splits edges by an internal rule** (`b-c` in every section), and `GeneratedFace` silently returns null for a split edge.
11. **Equal loft sections produce planar sides.** That changes the topology-only hash with no real topology change, so surface type should probably not be part of the "topology" hash (§8).

---

## 6. Role vocabulary proposal (for `docs/dsl.md` §3.4 / §4.3)

Notation: `X.role(args)` resolves through the OCP API shown. The *card.* column is what the primitive declares by default; the author may override it.

| op | role | resolves via | card. | notes |
|---|---|---|---|---|
| **revolve** | `R.cap(START\|END)` | `FirstShape/LastShape` | one() | **compile error** if referenced on a full revolve |
| | `R.side(from=sketch.edge)` | `Generated(edge)`; fallback `Revol().Shape(edge)` when the revolve is full | one() | exactly(0) for an edge on the axis (detect from sketch) |
| | `R.circle_edge(from=sketch.vertex)` | `Generated(vertex)` | one() | exactly(0) for a vertex on the axis |
| **chamfer** | `C.face(from=edge_ref)` | `Generated(edge)` | one() per edge | `C.created()` = union |
| | `C.corner(at=vertex_ref)` | `Generated(vertex)` | one() where ≥3 chamfers meet | the same is probably true for fillet corner patches (untested) |
| **shell** | `Sh.offset(from=face_ref)` | `Generated(face)` | one() | inner wall if t<0, outer skin if t>0 |
| | `Sh.rim(opening=face_ref)` | `Modified(face)` | one() | refs to the opening face continue onto the rim (document it, or force `error_on_modify`) |
| | `Sh.join(from=edge_ref)`, `Sh.join(at=vertex_ref)` | `Generated(edge\|vertex)` | one() | outward or arc joins only |
| | `Sh.void(from=face_ref)` | offset `Generated` → cut `Modified` | one() | closed hollow = offset + cut |
| **loft** | `L.cap(START\|END)` | `FirstShape/LastShape` | one() | solid lofts with closed sections |
| | `L.side(from=section[k].edge)` | `Generated(edge)` | exactly(spans) | spans = n_sections−1 if ruled, else 1; **at_least(1)** if the sections are incompatible. Per-span selection only by derivation (adjacent to a cap or section). |
| **sweep** | `S.cap(START\|END)` | `FirstShape/LastShape` | one() | compile error on a closed spine |
| | `S.side(from=profile.edge)` | `Generated(edge)` | exactly(n_spine_edges) | |
| | `S.side(from=profile.edge, along=spine.edge)` | `MakePipe.Generated(spineEdge, profileEdge)` | one() | MakePipe only; spine edges taken from the built wire; **may merge under clean()** where adjacent segments are coplanar |
| **draft** | `D.face(from=face_ref)` | **`Generated(face)`** | one() | other faces carry on by `Modified`; **no edge roles**: derive edges |
| **pattern** | `P.instance(k).<tool role>` | instance-k copy's role through the boolean's `Modified` | one() if disjoint | k is a declared index, not an ordinal; one boolean with a tool *list*; overlap or off-part change cardinality and ΔH, and must be declared |
| **mirror** | `M.image(of=ref)` | `Transform.ModifiedShape(ref)` → fuse `Modified` | one() | exactly(0) for a ref lying on the mirror plane when joined; aliases its original after clean() |
| **clean** | (no new roles) | `History().Modified/IsRemoved` | — | emits `merged` events; `error_on_merge` per reference |
| **derived** (all ops) | `edges_between(face_ref, face_ref)` | shared edges of two resolved faces | one() | **first-class**: it is the only way to name edges after draft or offset, and it was used here for chamfer inputs too |

---

## 7. Workarounds the reference layer needs (beyond spike 01)

1. **Follow `Generated` for face→face (same shape type) when `Modified` is empty and the shape is absent** (`Ledger2.propagate(follow_generated=True)`). This is needed for draft and offset. Keep it opt-in per primitive: for booleans, `Generated(face)` returns section *edges* (spike 01), which the same-type filter already excludes.
2. **Merge detection:** a result shape reached from ≥2 distinct pre-op shapes produces a `merged` event, which `error_on_merge` can reject.
3. **Derived edge references** (`edges_between`) are the standard way to reach edges whose history the kernel drops.
4. **Per-op fallbacks:** `Revol().Shape(edge)` for a full revolve; `WireExplorer` spine edges for sweeps.
5. **Never pack possibly-overlapping tools into one compound.** Booleans take a list of tools.

---

## 8. Recommended doc changes (not applied; for the next design session)

**`docs/dsl.md`**

- **§3.4 References.**
  - Replace the "validated in spike 01" list with the §6 table, or a pointer to it. Keep "creator roles only".
  - Add **derived references**: `edges_between(face_ref, face_ref)` and similar intersections of structural references count as structural. They are mandatory for edges after draft and offset.
  - Add that **a pattern instance index is a declared index, not an ordinal**.
  - Make `error_on_merge` concrete: merges come from `clean()`, coplanar fuses and mirrors. Two references that alias one face are a warning by default.
  - Add a sentence that **references to an opening face of a shell continue onto the rim**, unless a policy forbids it.
- **§4.3 Trusted primitives.**
  - Add per-primitive declarations (roles, ΔH, ΔS from §2/§6).
  - Add **failure-mode classes**, each needing a post-check:
    - loud (chamfer and draft overreach raise);
    - silently invalid (shell collapse, self-intersecting sweep);
    - **silently wrong but valid** (overlapping tools in one compound argument).
  - State that "trusted" requires validity, ΔH/ΔS and a volume-sign check after *every* primitive.
- **§5.2.** The counting rule is unchanged. Add that it was confirmed on revolve, sweep and torus seams with no refinement, and add the "passes Euler, fails BRepCheck" and "passes both, fails ΔS" examples to "necessary, not sufficient".
- **§5.3.** Add the §2 ΔH/ΔS table. Pattern lowering must compute ΔH and ΔS from instance–body and instance–instance interactions (off-part, overlap, ring split). **ΔS is as important as ΔH**: it was the only invariant that caught the compound-tool error.
- **§5.4.**
  - **Qualify "BRep text is canonical"**: byte identity holds for 26/29 models, but **not for `BRepOffset` join mode**. For those, compare (V,E,F,R,S,H), the adjacency hashes and an **order-free role-geometry fingerprint** instead. Alternatively, write a canonicalising serializer; this is an open item.
  - Consider dropping surface type from the topology-only hash, or making it a separate hash: equal loft sections flip it with no topology change.
- **§6.2 OCCT weakness table.** Add rows:
  - `IsDeleted` is unreliable for chamfer as well as fillet.
  - Draft reports images through `Generated` and gives no edge history.
  - A full revolve's `Generated` gap.
  - `MakeThickSolid` with no openings is an offset.
  - Collapsing offsets return invalid or null shapes without raising.
  - A compound tool must not self-overlap.
  - BRepOffset join-mode BRep bytes are nondeterministic.
  - `MakeWire` copies edges.
- **§7 risk 5.** Narrow it to the untested items in §9 below. History is now validated for revolve, chamfer, shell, loft, sweep, draft, pattern, mirror and `clean()`.
- **§3.5 / engine:** state the `clean()` decision: run it explicitly after boolean-like ops, history-chained, never implicitly through build123d.

**`CLAUDE.md` "OCCT gotchas"** (proposed additions): never trust `IsDeleted` for any `BRepFilletAPI` maker; draft and offset images come through `Generated` and have no edge history; full-revolve `Generated` gap and its fallback; never pack overlapping tools into one compound; BRepOffset join mode is not byte-deterministic; take spine edges from the built wire.

**`docs/explore-further.md` and the README index:** add a spike-02 status line, and point the "history coverage" thread at this file.

---

## 9. Remaining risks and untested items

- **Single platform again** (macOS arm64, OCCT 8.0.1). The BRepOffset nondeterminism may differ elsewhere, and its root cause was not identified.
- **Not tested at all:** fillet corner patches through `Generated(vertex)` (by analogy with chamfer only); distance-angle chamfers; chamfers or drafts on curved faces or next to fillets; drafts with only some faces drafted, or with a neutral plane away from a cap; shell with `GeomAbs_Intersection` joins or per-face thickness; shells of loft or sweep bodies; lofts with point sections, guide curves, or closed (periodic) lofts; sweeps with auxiliary spines, binormal mode, scaling laws, multiple profiles, or non-G1 spines (`SetTransitionMode`); **feature mirror and feature patterns** (patterns of fillets, of non-boolean features, along curves); revolve used as a cut or boss on an existing body (only standalone revolves were tested; the boolean part is spike 01's territory); revolves of profiles crossing the axis; USD with non-default tolerances or `AllowInternalEdges(True)`; the effect of `ConcatBSplines` on loft and sweep B-spline edges.
- **Edge roles** were checked for revolve (circle edges), spike-01 lateral edges, derived edges and chamfer inputs only. Most ops' edge-level genealogy was not audited role by role. The audit does cover all input edges for IsDeleted consistency.
- **Fixed models.** Each op was tested on one body family: a block, an L-body, a disc, a rectangle or circle profile. Sweeps covered one to three parameters each (202 points in total). No sweep exercised the same reference across a chain of several of these ops.
- **The compound-tool failure** was found for cut and fuse with overlapping cylinders. Whether OCCT ever *warns* (`HasWarnings`) was not checked. It should be, since a warning would be a cheap guard.
- **FeatureScript parity** for the new roles is untested. Onshape's queries for loft and sweep side faces and for draft are likely to differ.
- **`clean()` semantics vs Onshape:** the claim that Onshape/Parasolid merge coplanar faces on union is from general knowledge and was not verified here.

# DSL mathematical foundations: primary-source review

*Consolidated report, 2026-11-15. Scope: [`docs/explore-further.md`](../docs/explore-further.md) item 1. Built from four parallel research notes in [`research_notes/DSL mathematical foundations/`](../research_notes/DSL%20mathematical%20foundations/):*

- [`euler-operators-brep-topology.md`](../research_notes/DSL%20mathematical%20foundations/euler-operators-brep-topology.md)
- [`solid-modeling-theory.md`](../research_notes/DSL%20mathematical%20foundations/solid-modeling-theory.md)
- [`geometry-axioms-constraints-transforms.md`](../research_notes/DSL%20mathematical%20foundations/geometry-axioms-constraints-transforms.md)
- [`persistent-naming.md`](../research_notes/DSL%20mathematical%20foundations/persistent-naming.md)

**Status labels used throughout:**
- **Confirmed**: the claim was read in the primary source, or in an authoritative secondary source where marked "(secondary)".
- **Corrected**: the claim was wrong in a stated way; the correct version is given.
- **Unverified**: no adequate source was seen. Treat it as background knowledge.

During consolidation the bibliographic data of key disputed references was re-checked against Crossref, and the DOIs in the reference list were resolved there.

> **Corrections (2026-11-16).** Errata from the fresh-eyes review ([`Fresh eyes review.md`](Fresh%20eyes%20review.md), MATH-01, MATH-02). The body below is left as written.
>
> - **Laman (§5.3, §7.2 item 5).** Laman / Pollaczek-Geiringer counting characterizes generic rigidity of 2D *bar-joint* frameworks, i.e. distance constraints only. It does not cover CAD sketches, which mix distance with angle, incidence, parallelism and tangency and are non-generic by design. Bouma et al.'s normalization to distance + angle does not restore the theorem. Mixed direction–length frameworks have their own counts (Servatius & Whiteley, *SIAM J. Discrete Math.* 12(1), 1999). Use structural counting only as a heuristic, and numeric Jacobian rank at a witness configuration (Michelucci & Foufou, *CAD* 2006) as the source of truth. "Laman-style counting" in §7.2 should be read that way. See [`docs/dsl.md` §5.5](../docs/dsl.md#5-invariants-checked-on-every-compiled-solution).
> - **Euler–Poincaré (§3.7 item 1c, §7.2 item 2).** As implemented in dipm, H is solved from the formula, not measured. The check "holds with an integer H ≥ 0" can then only fail when V − E + F − R is odd or H < 0: it is a parity and integrality test. The diagnostic power is in the per-feature ΔH/ΔS assertions (§3.7 item 2), which compare against an independent expectation. A real genus check would compute H independently, e.g. via the first Betti number.

---

## 1. Executive summary

1. **The "five Euler operators" claim is right, but only in a narrower sense than stated.**
   - The relation for closed, orientable 2-manifold solids is **V − E + F − R = 2(S − H)**: R = inner loops (rings), S = shells, H = genus.
   - The basis {MVFS, MEV, MEF, KEMR, KFMRH} (with inverses) is linearly independent. It is also an exact basis of the *integer lattice* of count changes that keep the relation. We re-derived this by hand.
   - The deep result is **Mäntylä 1984** (CVGIP 26(1):45–60), not the 1988 book. It says every valid manifold topology can be reached by a sequence of *applicable* operators, and every such sequence yields a valid one. Its exact theorem text could not be read (paywalled).
   - Euler operators begin with **Baumgart 1972**, who called them "Euler primitives". **Braid, Hillyard & Stroud** is normally cited as **1980**.
   - The guarantee is **topological only**. The formula is "necessary but not sufficient" for B-rep validity, and geometry must be checked separately.
2. **Euler operators belong in the DSL as an *invariant and signature layer*, not as the user-facing alphabet.** OpenCascade (our target) has no Euler-operator API; it builds topology wholesale and validates with `BRepCheck_Analyzer`. Three practical wins:
   - an Euler–Poincaré check on every compiled solid;
   - a per-feature **genus assertion**: a through-hole adds exactly 1 to H, a blind hole adds 0;
   - a **topological signature**: counts plus a canonical face-adjacency hash, used for determinism and deduplication.
3. **Requicha 1980 gives the clearest "provable core" target.**
   - With **bounded primitives, rigid motions and regularized ∪*, ∩*, −*** (no complement), every syntactically correct tree denotes a valid solid (r-set). Validity "reduces to a parsing problem".
   - Planar-profile extrude and revolve fit within that guarantee.
   - General sweeps, lofts, shells, offsets and fillets do not. Requicha: "general validity conditions for sweep representations are unknown".
4. **For sketches, the core can be points + distance + angle + an explicit branch/orientation selector.**
   - Bouma et al. normalize the whole common CAD constraint vocabulary to distance + angle.
   - Restricting to ruler-and-compass (quadratic) steps matches Tarski's CG(n) and Owen's solver class (Owen's method underlies D-Cubed DCM).
   - Determinism needs **explicit root selection**, because well-constrained sketches have exponentially many solutions.
5. **Reflection is a sound single transform generator (Cartan–Dieudonné).** Projective geometric algebra makes it algebraically uniform. Compile reflection words back to native rotate/translate/pattern features.
6. **Persistent naming converges on one pattern across all sources:** an *evolution log* (create / modify / generate / delete / split / merge) plus re-resolution on rebuild. For the DSL:
   - reference only **invariant** entities (creator feature + role + source);
   - give every query a declared **cardinality**, failing loudly on mismatch;
   - make geometric tie-breaks set-valued and tolerance-explicit;
   - give named exports split/merge policies.
7. **F-rep / R-functions are a good secondary representation and a poor core** for a B-rep/STEP/FeatureScript target. They lose exact faces and edges, named topology and analytic surfaces.

---

## 2. Verified-claims table

Covers the claims made before this pass, from background knowledge.

| # | Prior claim | Status | Correct statement / nuance | Primary source |
|---|---|---|---|---|
| 1 | Euler operators: Braid/Hillyard/Stroud **1978**; Mäntylä **1988** | **Corrected** | They originate with Baumgart 1972 ("Euler primitives"). BHS is usually cited as 1980 (Brodlie ed.); a 1978 preprint is plausible but unverified. The completeness result is Mäntylä **1984**; the 1988 book is the textbook exposition. | Baumgart AIM-179 (1972) and SAIL files (read); Mäntylä 1984, Crossref-confirmed |
| 2 | **Five independent** Euler operators | **Confirmed, narrowly** | Six counts (V, E, F, H, R, S) with one linear relation leave a 5-dimensional space. {MVFS, MEV, MEF, KEMR, KFMRH} is a basis of the integer lattice (re-computed). "Five" depends on the parametrization: Weiler's five-operator set uses context-dependent operators. | Computed; Patrikalakis MIT 2.158J notes (secondary) |
| 3 | Euler operators are **complete for valid manifold topology** | **Confirmed (secondary); exact theorem unverified** | Reported as "Euler operators form a complete set of modeling primitives for manifold solids". The class is closed orientable 2-manifold boundaries (Mäntylä's "plane models"). The theorem is structural, not a consequence of the formula alone. | Mäntylä 1984 (not read); MTU and MIT notes (secondary) |
| 4 | Completeness is **"via the Euler–Poincaré formula"** | **Corrected** | The formula is *necessary but not sufficient* for validity. It explains why there are five operators, not why they are complete. | Patrikalakis 2003 (secondary); Baumgart: Eulerian polyhedra "do not necessarily correspond to … a solid" |
| 5 | Euler operators guarantee topology, not geometry | **Confirmed** | OCCT itself separates topological from geometric checks (`BRepCheck_Analyzer(S, GeomControls)`). | OCCT refman (read) |
| 6 | Non-manifold topology needs different machinery (Weiler radial-edge) | **Confirmed (secondary)** | "The Euler-Poincaré formula is no longer valid for NTM topologies." Weiler's minimal set: M-MR, M-SV, M-E, M-F, K-E. Radial-edge has 11 element types. | Weiler 1986 thesis (not read); Patrikalakis 2003 (secondary) |
| 7 | Kernels use Euler operators internally | **Mostly unverified** | OCCT: no Euler API found (topology built wholesale). Parasolid: `PK_EDGE_euler_*` / `PK_FACE_euler_*` functions appear in a 2009 teaching deck (snippet only). ACIS: no public docs found. Internal use in Booleans or blends is proprietary everywhere. | OCCT docs (read); others unverified |
| 8 | Requicha 1980 defined **r-sets** | **Confirmed, with nuance** | "bounded, closed, regular, and semianalytic" subsets of E³. First defined in Requicha's PAP TM-28 (1977); the 1980 Surveys paper summarizes. | Requicha 1980 (read in full) |
| 9 | Requicha 1980 defined **regularized Booleans** | **Corrected (attribution)** | X op* Y = closure(interior(X op Y)). Regular closed sets forming a Boolean algebra is classical topology (Kuratowski). Requicha credits the solid-modeling use to TM-25 (1977), TM-27 (1978) and Tilove & Requicha 1980 (CAD 12(5)). Tilove's 1980 IEEE TC paper is set-membership classification, not regularization. | Requicha 1980 (read) |
| 10 | Representation properties: **validity, completeness, uniqueness** | **Corrected (incomplete)** | Four formal properties: domain, validity, completeness (= unambiguity), uniqueness. Three informal ones: conciseness, ease of creation, efficacy. "Completeness neither implies nor is implied by uniqueness." | Requicha 1980 §1.3–1.5 (read) |
| 11 | F-rep, **Pasko et al. 1995** | **Corrected (title)** | The title ends "…concepts, implementation and **applications**", *The Visual Computer* 11(8):429–446, DOI 10.1007/BF02464333 (Crossref). | Crossref; Shapiro 2007 (read) |
| 12 | **Rvachev R-functions** | **Confirmed** | A function whose sign depends only on its arguments' signs. Standard R₀: x₁ + x₂ ± √(x₁² + x₂²). There is a completeness theory (Rvachev 1967/1974). No sufficiently complete system can be built from + and × alone. | Shapiro 2007, *Acta Numerica* (read) |
| 13 | **Tarski**: points + betweenness + equidistance; complete and decidable | **Confirmed** | Quantifier elimination around 1930, so complete, decidable and consistent. Models are Cartesian spaces over real closed fields. Reduced EG(n) is 10 axioms + 1 schema; there is no single canonical axiom count. | Tarski & Givant 1999 (read) |
| 14 | **Pieri 1908**: single primitive relation | **Confirmed and sharpened** | The ternary relation "b and c are equidistant from a", in a 24-axiom system for 3D geometry. Equidistance alone also suffices (betweenness is definable from it). Tarski calls such systems "involved and unnatural". | Tarski & Givant 1999 §3, §5 (read) |
| 15 | **Gupta 1965** proved the axioms **independent** | **Corrected** | Gupta mainly showed that Ax.6 and Ax.18 are *derivable* (redundant). 8 of the remaining axioms of FG(2) are independent; Ax.1, Ax.3 and Ax.7₁ were open (Szczerba later settled Ax.7₁ in a variant). | Tarski & Givant 1999 §2, §5 (read) |
| 16 | **Mohr–Mascheroni** (compass alone) | **Confirmed (secondary)** | Mohr 1672; Mascheroni 1797; Hjelmslev 1928. Inspiration only. | Wikipedia + citations |
| 17 | **Poncelet–Steiner** (straightedge + one circle with its centre) | **Confirmed (secondary)** | Poncelet 1822; Steiner 1833. The centre cannot be dropped. | Wikipedia + citations |
| 18 | **Laman 1970**: 2D generic rigidity by counting | **Confirmed**, priority corrected | \|E\| = 2\|V\| − 3 and every k-vertex subgraph (k ≥ 2) has ≤ 2k − 3 edges. **Pollaczek-Geiringer 1927** has priority. | Laman, Crossref-confirmed; secondary for content |
| 19 | 3D rigidity is open | **Confirmed (as of Jan 2026)** | Maxwell counting is necessary but not sufficient (double banana). No combinatorial characterization exists for d ≥ 3. Body-bar (Tay 1984) and body-hinge (Katoh & Tanigawa 2011) are solved, and body-and-CAD for 20 of 21 constraint types (Lee-St.John & Sidman). | Katoh & Tanigawa 2011; arXiv:1210.0451; arXiv:2601.19460 |
| 20 | **Cartan–Dieudonné**: reflections generate isometries | **Confirmed (secondary)**; affine corollary unverified | At most n reflections for O(n) (char ≠ 2). "Euclidean isometries of ℝⁿ need at most n+1 reflections" has a valid short proof (in the notes) but no source was located. | Wikipedia (citing Gallier, Lam); Cartan 1938 not read |

---

## 3. Euler operators and B-rep topology (main focus)

### 3.1 The Euler–Poincaré relation

For a B-rep whose shells are closed, orientable 2-manifolds:

> **V − E + F − R = 2(S − H)**
> V vertices, E edges, F faces, R rings (inner loops), S shells, H genus (handles, i.e. through-holes).

Equivalent forms, writing L for all loops (one outer loop per face plus the rings):
- V − E + 2F − L = 2(S − H)
- V − E + F = R + 2(S − H)

Source: Patrikalakis, MIT 2.158J lecture notes (secondary). Baumgart's original, without rings, is "F−E+V = 2*B−2*H" (read from his SAIL files).

**Naming hazard.** Some sources (e.g. Wikipedia's Eastman-lineage table) use **H for holes-in-faces, meaning rings**, not genus. Our docs and code should say `genus`, `rings` and `shells` explicitly.

**Necessary, not sufficient.** The MIT notes say "Euler equation is a necessary but not sufficient condition for validity of a B-rep". A model with correct counts can still be combinatorially wrong (e.g. mis-linked loops) and geometrically wrong.

### 3.2 History and attribution

| Who | When | What | Status |
|---|---|---|---|
| Baumgart | 1972 (Stanford AIM-179); 1975 AFIPS NCC | Winged-edge structure, plus "Euler primitives" MKBFV, MKEV, MKFE, KLFE, KLEV, KLVE, ESPLIT, GLUE, UNGLUE. "Inspired by Coxeter's proof of Euler's formula." He notes strict Euler adherence "would require only four primitives". | Confirmed (his own files) |
| Eastman & Weiler | 1979 (CMU report) | Specified the operators systematically (MBFLV, MEV, MEFL, MEKL, KFLEVB, KFLEVMG) in GLIDE | Secondary only |
| Braid, Hillyard & Stroud | 1980 (Brodlie ed., Academic Press, pp. 123–141) | Stepwise construction of polyhedra (BUILD group, the Cambridge lineage behind Romulus, Parasolid and ACIS) | Citation secondary; content unverified |
| Mäntylä & Sulonen | 1982, IEEE CG&A 2(7):17–31 | GWB, a solid modeler built on Euler operators | Citation confirmed (Crossref) |
| Mäntylä | 1984, CVGIP 26(1):45–60 | "A note on the modeling space of Euler operators": the completeness result | Citation confirmed; theorem text unverified |
| Wilson | 1985, IEEE CG&A 5(8) | "Euler formulas and geometric modeling" | Citation secondary |
| Mäntylä | 1988 book | *An Introduction to Solid Modeling*: half-edge data structure, GWB | Citation secondary |

### 3.3 The operator basis

Coordinates are (V, E, F, H, R, S). Each operator has a dot product of 0 with the relation's normal vector (1, −1, 1, 2, −1, −2), so it preserves the relation.

| Operator | Meaning | ΔV | ΔE | ΔF | ΔH | ΔR | ΔS | Inverse |
|---|---|---|---|---|---|---|---|---|
| MVFS | make vertex, face, shell (initial "skeletal" solid) | +1 | 0 | +1 | 0 | 0 | +1 | KVFS |
| MEV | make edge + vertex | +1 | +1 | 0 | 0 | 0 | 0 | KEV |
| MEF | make edge + face (split a face) | 0 | +1 | +1 | 0 | 0 | 0 | KEF |
| KEMR | kill edge, make ring | 0 | −1 | 0 | 0 | +1 | 0 | MEKR |
| KFMRH | kill face, make ring + hole (genus) | 0 | 0 | −1 | +1 | +1 | 0 | MFKRH |

**What has been established, and how:**
- **Count-level independence and spanning** (computed, re-checked in consolidation).
  - The 5×5 minors of the operator matrix are ±(entries of the normal vector), with gcd 1.
  - So the five vectors have rank 5, span the solution space, and form a **basis of the integer lattice**.
  - Any integer count change that respects Euler–Poincaré is a *unique* integer combination of the five. That part is linear algebra.
- **Structural completeness and soundness** (Mäntylä 1984; secondary paraphrase). Every manifold "plane model" can be built from MVFS by a finite sequence of *applicable* operators and torn down by inverses, and every applicable sequence yields a member of the class.
  - This is the non-trivial content.
  - The exact hypotheses (orientability, multiply-connected faces, multiple shells) and the proof technique are **unverified**.
  - Reading the paper (Elsevier, DOI below) is the top follow-up item.
- **Names.** The operator names (mvfs, mev, mef, kemr, kfmrh) follow Mäntylä/GWB as commonly reported. Checking them against the 1988 book is still outstanding.

**Non-uniqueness of bases.** Weiler's set as taught at MIT is also five operators (MSFLV, MEV, ME, GLUE, KE). ME and GLUE are context-dependent: ME acts as mefl, mekl or meksfl depending on where it is applied. "The five Euler operators" is therefore a fact about the dimension of the count space, not a canonical vocabulary.

### 3.4 Data structures and non-manifold extensions

- **Manifold structures.**
  - Winged-edge (Baumgart).
  - Half-edge (Mäntylä/GWB; later Kettner 1999, CGAL `HalfedgeDS`, unverified detail).
  - BRepNet's "coedges", Parasolid's "fins" and OCCT's oriented edges in wires are all half-edge-like oriented edge-uses.
- **Non-manifold structures.**
  - Weiler's radial-edge structure (RPI thesis 1986; book chapter 1988) uses face-, loop-, edge- and vertex-uses and radial ordering around edges.
  - Other lines: Gürsöz & Prinz (vertex/node-based, 1989); Rossignac & O'Connor's SGC (1989); Masuda's cell-complex operators (CAD 25(2), 1993); Yamaguchi & Kimura's coupling entities (IEEE CG&A 1995).
- **The manifold formula fails** for non-manifold topology. Masuda's generalized formula is reported as v − e + (f − r) − (V − Vh + Vc) = C − Ch + Cc, but this is **unverified**.
- **Relevance.** OCCT supports non-manifold compounds, so intent-layer intermediates (sheets, wires, contact faces) may be non-manifold. Apply the manifold Euler check only at **solid checkpoints**.

### 3.5 Topology vs. geometry validity

Every source agrees that Euler-consistency says nothing about:
- self-intersection;
- whether faces lie on their surfaces;
- whether edges are consistent with their faces' p-curves (OCCT's `SameParameter`);
- tolerances.

Requicha 1980 §2.7.2 adds that B-rep validity has both combinatorial and metric conditions. The metric ones are "computationally unpleasant", and topology and geometry "are not independent": moving one vertex can invalidate a solid.

OCCT encodes the split directly:
- `BRepCheck_Analyzer(S, GeomControls=false)` checks topology only.
- With `true` it adds checks such as `SelfIntersectingWire`, `InvalidCurveOnSurface` and `InvalidSameParameterFlag`.

### 3.6 How kernels handle it

| Kernel | Topology model | Euler operators? | Validation | Status |
|---|---|---|---|---|
| **OpenCascade** | `TopoDS_Shape` = reference to a shared `TShape` + orientation + location. Types: COMPOUND, COMPSOLID, SOLID, SHELL, FACE, WIRE, EDGE, VERTEX. Mixed-dimensional (non-manifold) allowed. | None found. Built by `BRep_Builder`, `BRepBuilderAPI_*`, `BRepPrimAPI_*`, `BRepAlgoAPI_*`. | `BRepCheck_Analyzer`, `ShapeAnalysis`, `ShapeFix`, `ShapeUpgrade` | Confirmed (docs); "no Euler layer" is absence of evidence |
| **Parasolid** | body / region / shell / face / loop / fin / edge / vertex; edges classed by fin count | `PK_EDGE_euler_*`, `PK_FACE_euler_*` exposed (e.g. split, slit, make_ring_loop) | `PK_BODY_check` (unverified) | Secondary snippet only |
| **ACIS** | (not researched in depth) | No public docs found | Has validity checking per product pages | Unverified |
| **Onshape** (on Parasolid) | Not exposed | No Euler ops in FeatureScript | n/a | Unverified |

### 3.7 What Euler topology offers us in practice

1. **Validity invariant (adopt).** For every compiled solid, check:
   - (a) `BRepCheck_Analyzer` with geometric controls passes;
   - (b) shells are closed (no free edges; `ShapeAnalysis_FreeBounds`);
   - (c) V − E + F − R = 2(S − H) holds with an integer H ≥ 0.

   Count with `TopTools_IndexedMapOfShape`, which ignores orientation. R = Σ_faces (wires − 1).

   **Caveat, reasoned during consolidation but not run** (OCP was not installed here):
   - OCCT's periodic surfaces use *seam edges* (one edge used twice by the same face), and spheres and cones have *degenerated edges* at the poles.
   - Counting all edges gives a sphere 2 − 3 + 1 = 0, which is wrong. Excluding degenerated edges gives 2 − 1 + 1 = 2.
   - With seams counted once and degenerated edges excluded, the cylinder (2 − 3 + 3 = 2) and the torus (1 − 2 + 1 = 0, H = 1) come out right.
   - **Calibrate on box, cylinder, cone, sphere and torus before trusting the check.**
2. **Genus and ring deltas as intent checks (adopt; our inference, not a published practice).**
   - Intent like "4 through-holes" implies ΔH = +4 on the plate; a blind pocket implies ΔH = 0.
   - A per-feature ΔH assertion cheaply and deterministically catches blind-vs-through mistakes and accidental break-throughs (e.g. a pocket deeper than the plate).
3. **Canonical topological signature (adopt).**
   - Store (V, E, F, R, S, H) plus a canonical hash of the face-adjacency graph with every compiled solution. Faces are labelled by surface type; adjacencies by curve type and convexity.
   - The tuple is a fast pre-filter; graph canonical labelling (nauty-style) gives exact topological equality.
   - Gives architecture §7's "same DSL → identical geometry" a float-free topological half, and supports deduplication.
   - Requicha's split of non-uniqueness into **permutational** and **positional** is the right vocabulary for what canonicalization must remove.
4. **Persistent naming substrate (indirect).** Euler operators give exact birth/death records per entity, but OCCT does not expose Euler steps. In practice we get coarser genealogy from OCCT's history API (§6). Chiyokura's DESIGNBASE reportedly used Euler-op logs for undo/redo (unverified).
5. **Tokenization / training target (research bet, not a dependency).**
   - None of the B-rep generators found tokenize Euler-operator sequences: SolidGen 2022/23 (vertices → edges → faces with pointer networks), BrepGen 2024 (diffusion over a face/edge tree), HoLa, BrepGPT, BrepARG.
   - Euler sequences would give **validity at every prefix** (grammar-constrained decoding) with a tiny vocabulary. But they are highly non-unique (needing a canonical order) and carry no geometry.
   - For mesh → history reverse engineering, they fit the *mesh → topology* stage. Recovering *design history* is a feature-level problem (DeepCAD-style command sequences).
   - "No precedent" rests on a limited search.

**Verdict for the core.** Euler operators are the strongest proven "minimal, orthogonal, complete" result in solid modeling, but they are complete for **topology**, not for **designs**. Using them as the DSL alphabet would mean writing our own kernel, and would give the verbosity Requicha warns of: B-reps are "an order of magnitude longer" than CSG. Cite them as the precedent for "small grounded basis + derived operators", and use them as invariants.

---

## 4. Solid-modeling theory: Requicha, regularized Booleans, sweeps, F-rep

### 4.1 Requicha's framework (Requicha 1980, read in full)

- **r-sets.** Solids are modeled as bounded, closed regular (X = closure(interior X)), semianalytic subsets of E³. They are "curved polyhedra with well-behaved boundaries", need not be connected, and may have through-holes.
- **Representation scheme.** A relation s: M → R, where R is the syntactically correct representations (a grammar's language) and V ⊆ R the *valid* ones (the image of the domain D).
  - *Unambiguous / complete*: s⁻¹ is a function.
  - *Unique*: s is a function.
  - Neither implies the other.
  - Non-uniqueness is either **permutational** (reordered substructure) or **positional** (congruent copies placed differently).
- **Design target, verbatim:** "design representation schemes in which essentially all syntactically correct representations are valid … thereby reducing validity checking to a parsing problem."

### 4.2 Regularized Booleans

- **Definition.** X op* Y = k i(X op Y), with c*X = k i c X.
- **Closure.** Regular sets with these operators form a Boolean algebra. Regular semialgebraic and semianalytic sets are closed under them, and bounded members are r-sets.
- **Why.** Regularization removes "dangling" faces and edges, e.g. where two touching blocks are intersected.
- **Complement must be excluded from bounded CSG,** "because it destroys boundedness".
- **In practice.** Kernels compute in floating point with tolerances. No provably robust Boolean algorithm is known (Hoffmann, Hopcroft & Karasick 1989; a Purdue dissertation c.1992). So theory justifies validating the *program*, and practice still requires validating the *result* (§3.7).
- Which Booleans OCCT regularizes by default (e.g. General Fuse can keep non-regular results) is **unverified**.

### 4.3 Representation schemes and conversions

Requicha's six families (Table 1): primitive instancing, spatial enumeration, cell decomposition, CSG, sweeps, B-rep.

- **CSG** is unambiguous but not unique.
  - With **bounded primitives**, "any CSG tree is a valid representation of an r-set if the primitive leaves are valid". This holds even for parametric (generic) trees.
  - With general halfspaces, boundedness becomes hard to verify.
- **CSG → B-rep** ("boundary evaluation") is exact but nontrivial (Requicha & Voelcker 1985, *Proc. IEEE* 73(1); set membership classification, Tilove 1980).
- **B-rep → CSG** needs **separating halfspaces** beyond the face halfspaces. The minimal set is non-unique (Shapiro & Vossler 1991, 1993; Shapiro 2007 Thm 6). Recovering CSG or history from STEP will therefore be heuristic.
- **Translational and rotational sweeps** of planar regions are unambiguous and convert to B-rep "simply".
- **General sweeps:** "the least understood … general validity conditions … are unknown". Sweeping a curve along a curve can produce dangling edges.
  - Later theory (Blackmore & Leu's sweep differential equation, 1990; SEDE 1997) characterizes envelopes but gives no simple closure theorem.
  - Martin & Stephenson 1990, Wang & Wang 1986 and Ghosh 1993 were **not found** and remain unverified.

### 4.4 F-rep and R-functions

- **R-function** (Shapiro 2007 Def. 1): f is an R-function if sign(f(x)) = Φ(sign(x₁), …, sign(xₙ)) for some Boolean Φ.
  - Standard family: R_α = (x₁ + x₂ ± √(x₁² + x₂² − 2αx₁x₂)) / (1 + α).
  - α = 1 gives min/max (not differentiable on the diagonal). α = 0 gives R₀, analytic except at the origin. R₀ᵐ is Cᵐ.
- **Completeness.** Rvachev 1967/1974: a system is "sufficiently complete" if its companion logic functions are complete, and any closed-set Boolean formula becomes a single inequality.
  - The hard part is the inverse problem: finding the formula for a given B-rep.
  - Optimized formulas may be "not properly signed" (zero at interior points).
- **F-rep** (Pasko et al. 1995): f ≥ 0 inside. Set operations, blends, offsets, sweeps and deformations all return real functions, so the representation is closed and there is no validity check at all.
  - But boundedness, regularity and proper signing are not guaranteed.
  - Boundary recovery yields meshes (marching cubes, dual contouring), not CAD B-reps. We found no source on F-rep → exact STEP-quality B-rep.

### 4.5 Candidate minimal solid cores

| Core | Valid by construction | B-rep / STEP export | Persistent refs | Role for us |
|---|---|---|---|---|
| (a) Algebraic halfspaces + ∪*, ∩*, −* | Only if boundedness is proven (hard) | Exact if halfspaces are kernel-native surfaces | Faces ↔ halfspaces | Canonical *normal form* for equivalence, not authoring |
| (b) Bounded primitives + rigid motions + regularized Booleans | **Yes (parse-level)** | Exact (`BRepPrimAPI` + `BRepAlgoAPI`) | Clear primitive-face provenance | **Core** |
| (c) Planar profile + extrude / revolve (+ Booleans) | Yes, if the profile is a valid 2D r-set and the revolve doesn't cross its axis | Exact and simple | Faces = profile edge × sweep: the classic basis of naming | **Core** (matches CadQuery, build123d and FeatureScript idioms) |
| (c′) Path sweep, loft, shell, offset, fillet, draft | No known closure theorem | Exact but kernel-dependent | Contingent topology | **Trusted primitives** in the intent layer, with runtime checks |
| (d) F-rep / SDF | Always (total functions); bounds and signing not guaranteed | **Lossy** (mesh only) | None native | Secondary: preview, interference, lattices, analysis |

---

## 5. Geometry axioms, constructions, constraints, transforms

### 5.1 Axioms (Tarski & Givant 1999, read)

- **Tarski's elementary geometry:**
  - one sort (points) and two primitives, **betweenness B** (affine) and **equidistance ≡** (metric);
  - complete, decidable and constructively consistent via quantifier elimination (around 1930; decision method published as RAND 1948, revised 1951);
  - models are exactly the Cartesian spaces over real closed fields.
- **The continuity principle sets the model class:**
  - full first-order schema → real closed fields (EG);
  - a single **Circle Axiom** → Euclidean ordered fields = **ruler-and-compass geometry (CG)**;
  - neither → Pythagorean fields;
  - second-order → ℝⁿ (FG).
- **Single-primitive systems exist** (Pieri 1908's ternary "b and c equidistant from a"; ≡ alone), but are "involved and unnatural". This directly supports the core/intent split: minimal for proof, rich for people.
- **Gupta 1965** is mainly a *dependence* result (Ax.6 and Ax.18 derivable), with partial independence; see table row 15.
- **Hilbert 1899** primitives were not checked (unverified).

**Implication.** Decidability is not operationally useful: decision procedures are doubly exponential. **Constructibility** is. Restricting core sketch steps to ruler-and-compass placements means every solution lives in a Euclidean field and is reachable by quadratic solves.

### 5.2 Constructions

Mohr–Mascheroni and Poncelet–Steiner are confirmed (secondary). They show that constructibility is robust to the choice of tools. They are inspiration only. Of note: Mascheroni's method relies heavily on **reflections**, which echoes §5.4.

### 5.3 Rigidity and constraint solving

- **2D.** Laman / Pollaczek-Geiringer counting exactly characterizes *generic* minimal rigidity of bar-joint (distance) frameworks. Non-generic (special-position) configurations can still defeat it, so pair counting with a numeric Jacobian-rank check at actual values.
- **3D.** Point-distance counting is unreliable (double banana), and no characterization is known (Dewar, arXiv Jan 2026, refutes the latest candidate).
  - **Body-based** models are solved: body-bar (Tay), body-hinge (Katoh & Tanigawa 2011), and **body-and-cad** for 20 of 21 CAD constraint types (Lee-St.John & Sidman 2012/13).
  - Assemblies should therefore be modeled as constrained bodies.
- **CAD solvers.**
  - **Owen 1991** (SMA '91, pp. 397–407): triconnected decomposition with ruler-and-compass algebraic solving. Complete for ruler-and-compass-constructible point configurations with algebraically independent distances. It is the method behind D-Cubed DCM (per Bouma et al.).
  - **Bouma, Fudos, Hoffmann, Cai & Paige 1995** (CAD 27(6):487–501):
    - normalize every common constraint (incidence, tangency, concentricity, parallel, perpendicular…) to **distance + angle** (e.g. incidence is distance 0);
    - solve bottom-up by cluster merging;
    - name the **root identification problem**: "a well-constrained geometric constraint problem has an exponential number of solutions", so "more needs to be communicated".
  - **Fudos & Hoffmann 1997** (TOG): two-phase analyze-then-construct.
  - **Hoffmann, Lomonosov & Sitharam 2001** (JSC, two parts): decomposition–recombination planners.
  - **SolveSpace:** symbolic equations solved by modified Newton, least squares when under-constrained.
  - **FreeCAD planegcs:** BFGS, Levenberg–Marquardt and DogLeg, plus QR of the Jacobian to report DOFs and redundant or conflicting constraints (read from source).
  - Onshape is listed as a D-Cubed licensee, but whether its sketcher uses DCM is unverified.

### 5.4 Transforms

- **Cartan–Dieudonné:** every element of O(n) is a product of at most n reflections (secondary). Every isometry of ℝⁿ is then a product of at most n+1 reflections (short proof in the notes; citation not located, Gallier 2001 is the likely source).
- **Reflection words:**

  | Transform | Reflections |
  |---|---|
  | Mirror | 1 |
  | Rotation | 2, in intersecting planes, at half the angle |
  | Translation | 2, in parallel planes, at half the distance |
  | Glide | 3 |
  | Screw | 4 |

- **Projective GA** (Gunn 2011, 2016) represents every Euclidean isometry, direct or indirect, as a versor sandwich product, which is literally a product of reflections. Versors give a **canonical form for transform equality** (up to sign).
- No CAD kernel or constraint solver was found using GA internally.

---

## 6. Persistent naming / topological references

### 6.1 The problem and the literature

**Definition.** Kripac 1997: identify faces, edges and vertices "in such a way that the same entities can still be identified after the models have been re-evaluated". The canonical example (Agbodan 2003; Cardot 2019): a slot splits face f into f1 and f2, a later feature references f2, then an edit means f is never split.

**Three families:**
1. **Topological history / genealogy.** Kripac's face graph; OCCT TNaming; FreeCAD's element map; Cardot's G-map rules.
2. **Generative / semantic names.** Chen & Hoffmann 1995; Capoyleas, Chen & Hoffmann 1996: creating feature + source entity + minimal topological context + orientation. Bidarra et al. 2005 reference persistent *feature* faces instead of boundary faces.
3. **Geometric predicates.** build123d selectors; Onshape `qClosestTo` etc. Usually layered over history.

**Key distinction (Agbodan, Marcheix, Pierra & Thabaud 2003):**
- **Invariant entities** are fixed by the structure of the operation, "independently of involved values". Examples: the end cap of an extrude, the side face from profile edge e.
- **Contingent entities** are fragments produced by later collisions.
- Every scheme becomes heuristic, and fails, on contingent entities:
  - Kripac's swapped matches and "piece loss";
  - Chen's unexplained thresholds and failure under symmetry;
  - FreeCAD's split index following OCCT's reporting order, which moved a fillet to the other edge.

**Shared evolution algebra.** Across sources the event types are effectively standard:
- OCCT: PRIMITIVE / GENERATED / MODIFY / DELETE (+ SELECTED);
- Cardot: Creation / Deletion / Fusion / Modification / NoEffect / Split;
- Kripac: create / split / merge / delete.

### 6.2 Production systems

- **Onshape FeatureScript** (docs read):
  - **Ids:** hierarchical feature `Id`s that "must reflect creation history"; `unstableIdComponent` for loop indices.
  - **Creator queries:** `qCreatedBy` with defined split and merge semantics. Split pieces are "created by" both the original creator and the splitting operation; merged entities by all creators plus the merge.
  - **Role queries:** `qCapEntity`, `qNonCapEntity`, `qSplitBy`.
  - **Tracking:** `startTracking`, `makeRobustQuery`.
  - **Attributes:** `setAttribute` / `qHasAttribute`.
  - **Geometric ties are set-valued:** `qClosestTo` and `qLargest` return all entities within tolerance.
  - **Hazards:** query order is "deterministic but arbitrary", and a single-entity parameter given several entities silently "takes the first".
- **OpenCascade.**
  - OCAF `TNaming_NamedShape` and `TNaming_Selector` store a recipe for finding a sub-shape and re-`Solve()` it after rebuild, or fail.
  - Lower down, `BRepBuilderAPI_MakeShape::Generated/Modified/IsDeleted` and `BRepTools_History` record vertex/edge/face/solid relations and compose with `Merge()`.
- **FreeCAD 1.0** (Nov 2024) shipped realthunder's mapped element names built from OCCT maker history (e.g. `Face6;:M2;FUS;:T1:5:F`).
  - Weak points: ordinal split indices; long names; about 30% recompute overhead in one test.
  - The FreeCAD wiki frames it as a mitigation.
- **build123d:** selectors return **unordered** `ShapeList`s (sort, group and filter to narrow). Current docs add a per-operation history (`Select.LAST` / `Select.NEW`) and `topo_path` provenance; the version that introduced these is unverified.

### 6.3 Relation to Euler operators

Each Euler operator has an exact birth/death signature, so a model built from Euler steps would have exact, free genealogy. The closest published analogue is Cardot et al. 2019, which derives persistent ids from elementary graph-rewriting rules on G-maps.

There is no evidence that Kripac or commercial systems derive names from Euler-op logs. Industrial kernels report only coarse generated/modified/deleted maps, with splits as "modified into {a, b}" in no canonical order. **That gap is exactly where tie-breaking rules are needed.**

---

## 7. What this offers our DSL core

### 7.1 Adopt as core primitives

**Solids:**
- bounded primitives (box, cylinder, cone, sphere, torus);
- **planar-profile extrude and revolve** (revolve must not cross its axis);
- rigid motions;
- regularized **union / intersection / difference**, with no complement;
- validity of any core tree reduces to parse checks plus a valid-profile check (Requicha).

**Sketches:**
- points, lines, circles and arcs;
- core relations: **distance, angle, and an orientation/side predicate**;
- incidence = distance 0; parallel and perpendicular = angle 0° and 90°; tangency and concentricity are distances (Bouma et al.).

**Core sketch steps** are ruler-and-compass placements (CG(n)), each carrying an **explicit branch tag**: side, ccw/cw, near/far. Non-quadratic cases (splines, some chains) go through a marked numeric escape hatch with a deterministic seed.

**Transforms:** `reflect(plane)` as the generator. Mirror, rotate, translate, linear and circular pattern, and symmetric are intent forms that lower to reflection words or to the cyclic group they generate. Compare transforms canonically as PGA versors. Emit native rotate/translate/pattern features when compiling to OCCT or FeatureScript; never emit long mirror chains.

**References:** invariant-entity queries only:
- `E.cap(END)`, `E.side(from=sketch.edge("top"))`, `F.created()`, `B.split(front)`;
- resolved through OCCT history, recorded as (feature id, role, source);
- feature ids hierarchical and history-shaped.

### 7.2 Adopt as invariants and checks

**Checked on every compiled solution:**
1. **Result validity:** `BRepCheck_Analyzer` (geometric controls on); closed shells; positive volume.
2. **Euler–Poincaré:** V − E + F − R = 2(S − H) at solid checkpoints, with integer H ≥ 0. Calibrate the seam/degenerated-edge counting rules on primitives first.
3. **Per-feature topological deltas** (ΔH, ΔR, ΔS) derived from intent: a through-hole adds exactly 1 to H; a blind feature adds 0; "split into two parts" adds 1 to S, or adds a solid.
4. **Topological signature** stored with each solution: (V, E, F, R, S, H) plus a canonical face-adjacency hash, alongside the pinned kernel and library versions (arch. §7).
5. **Sketch well-constrainedness:**
   - compile-time structural DOF / Laman-style counting;
   - evaluation-time Jacobian rank, redundancy and conflict detection (as planegcs does);
   - for assemblies, body-based counting (body-and-cad).
6. **Reference determinism:**
   - every query declares its cardinality (`one()`, `exactly(n)`, `at_least(n)`), and a mismatch is a compile error;
   - geometric predicates carry explicit tolerances and are set-valued on ties;
   - ordinal indices are never used;
   - when compiling to FeatureScript, emit `evaluateQueryCount` guards and never `qNthElement`.
7. **Stability harness:** perturb each design parameter across its declared range, rebuild, and assert that each reference keeps its cardinality and its (feature, role, source) genealogy. This is our own inference; no source prescribes it.

### 7.3 Treat as trusted primitives (intent layer, runtime-checked)

These have no closure theorem but are indispensable:
- fillet, chamfer, shell/offset, draft, path sweep, loft, thicken;
- hole (a semantic composite: a revolve-cut, or a cylinder subtraction, plus tags).

Each must:
- declare its expected topological deltas and the roles of the entities it creates (e.g. a fillet creates `blend` faces generated from each input edge);
- be followed by the validity checks above;
- act on **named exports**: entities carrying attributes with explicit split/merge policies (`propagate_all`, `error_on_split`, `error_on_merge`).

### 7.4 Keep out of the core

- **Euler operators as authoring vocabulary.** We would need our own kernel, and the result is far too verbose.
- **F-rep** as the authoritative representation (it breaks STEP and FeatureScript fidelity and naming). Possible later use: previews, interference, lattices.
- **Halfspace CSG** for authoring. It may be used as a canonical normal form.
- **Tarski-style decidability** as a feature claim.

### 7.5 Open risks

1. **Mäntylä's exact theorem is unread.** Before citing "proven complete" in project docs, read Mäntylä 1984 (and ideally the 1988 book).
2. **Kernel robustness.** r-set closure is a theorem about exact sets. OCCT Booleans with tangent or coincident faces can fail or yield invalid shapes, so "valid by construction" holds for the *program*, not the *output*. Add a linter for near-coincident intent.
3. **OCCT counting conventions** (seam and degenerated edges, shared TShapes) can break a naive Euler check. Not yet tested here.
4. **Coarse kernel history.** Split order is unspecified, so contingent entities cannot be named stably. The DSL must forbid identity references to them, which costs some expressiveness.
5. **build123d history and provenance features may be recent.** Pin versions and check that every wrapped operation (offset, loft, sweep) reports history.
6. **Root identification.** Branch tags make sketches deterministic but add authoring burden. The intent layer (`symmetric`, `tangent(side=…)`) must fill them in automatically.
7. **3D point-distance rigidity is open.** Do not promise well-constrainedness detection for free 3D point constraints.
8. **Parasolid internals** (Onshape) are undocumented. FeatureScript export must rely on its query semantics, not on matching OCCT genealogy.

---

## 8. Cross-check notes (consolidation)

- **Consistent across notes.** The Euler and persistent-naming notes agree on the Parasolid `PK_*_euler_*` evidence (one secondary snippet each), on OCCT's history API as the practical genealogy source, and on the evolution-event algebra. The solid-modeling and Euler notes agree that a two-layer check is needed: theory/topology plus geometric/result checks.
- **Upgraded in consolidation:**
  - Mäntylä & Sulonen 1982 (GWB) was unverified in the Euler note but confirmed by Crossref in the naming note.
  - Owen 1991's DOI 10.1145/112515.112573 and Bouma et al. 1995's CAD 27(6):487–501 were both unverified in the geometry note; Crossref confirmed them.
- **Corrected in consolidation:**
  - Shapiro 2007 *Acta Numerica* is **16:239–303**, DOI 10.1017/S096249290631001X. The solid-modeling note had 1–65 and a guessed DOI.
  - The alternative Pasko DOI 10.1007/s003710050034 does not resolve. 10.1007/BF02464333 is correct.
- **Corrections from the naming note:** Chen & Hoffmann "Towards feature attachment" is CAD **27(9)**; the 27(12) paper is "On editability…". Cardot et al. 2019 is in *CAD & Applications*. Agbodan's co-author is **Thabaud**.
- **Not contradicted, but under-sourced:** "no Euler layer in OCCT", "no Euler-op tokenization in ML", and "no GA in CAD kernels" are all absence-of-evidence findings.

---

## 9. References (primary sources; DOIs Crossref-resolved where given)

**B-rep topology and Euler operators**
- Baumgart, B. G. (1972). *Winged Edge Polyhedron Representation*. Stanford AI Memo AIM-179. https://purl.stanford.edu/tz289cy2950 ; working files https://www.saildart.org/EULER.5[OLD,BGB]
- Baumgart, B. G. (1975). A polyhedron representation for computer vision. *AFIPS NCC* 44:589–596. https://doi.org/10.1145/1499949.1500071
- Eastman, C. M. & Weiler, K. J. (1979). *Geometric modeling using the Euler operators*. CMU Institute of Physical Planning, Res. Rep. 78. https://kilthub.cmu.edu/articles/journal_contribution/Geometric_modeling_using_the_Euler_operators/6605963
- Braid, I. C., Hillyard, R. C. & Stroud, I. A. (1980). Stepwise construction of polyhedra in geometric modelling. In K. W. Brodlie (ed.), *Mathematical Methods in Computer Graphics and Design*, Academic Press, pp. 123–141.
- Mäntylä, M. & Sulonen, R. (1982). GWB: a solid modeler with Euler operators. *IEEE CG&A* 2(7):17–31. https://doi.org/10.1109/MCG.1982.1674396
- Mäntylä, M. (1984). A note on the modeling space of Euler operators. *Computer Vision, Graphics, and Image Processing* 26(1):45–60. https://doi.org/10.1016/0734-189X(84)90129-4
- Wilson, P. R. (1985). Euler formulas and geometric modeling. *IEEE CG&A* 5(8):45–60.
- Weiler, K. (1985). Edge-based data structures for solid modeling in curved-surface environments. *IEEE CG&A* 5(1):21–40.
- Weiler, K. (1986). *Topological Structures for Geometric Modeling*. PhD thesis, Rensselaer Polytechnic Institute.
- Weiler, K. (1988). The radial edge structure. In Wozny, McLaughlin & Encarnação (eds.), *Geometric Modeling for CAD Applications*, North-Holland.
- Mäntylä, M. (1988). *An Introduction to Solid Modeling*. Computer Science Press. ISBN 0-88175-108-1.
- Chiyokura, H. (1988). *Solid Modelling with DESIGNBASE*. Addison-Wesley.
- Gürsöz, E. L. & Prinz, F. B. (1989). Node-based representation of non-manifold surface boundaries. In *Geometric Modeling for Product Engineering*, North-Holland.
- Rossignac, J. & O'Connor, M. (1989). SGC: a dimension-independent model for pointsets with internal structures and incomplete boundaries. Same volume, pp. 145–180.
- Masuda, H. (1993). Topological operators and Boolean operations for complex-based nonmanifold geometric models. *Computer-Aided Design* 25(2):119–129. https://doi.org/10.1016/0010-4485(93)90097-8
- Yamaguchi, Y. & Kimura, F. (1995). Nonmanifold topology based on coupling entities. *IEEE CG&A* 15(1):42–50.
- Patrikalakis, N. M. (2003). MIT 2.158J *Computational Geometry*, Lectures 14–15 (secondary). https://ocw.mit.edu/courses/2-158j-computational-geometry-spring-2003/f04f923ac8e0af56d19095b4de8dea3c_lecnotes14_fixed.pdf
- Open Cascade. *Modeling Data* user guide. https://occt3d.com/dev/doc/overview/html/occt_user_guides__modeling_data.html ; `BRepCheck_Analyzer` https://occt3d.com/dev/doc/refman/html/class_b_rep_check___analyzer.html
- Jayaraman, P. K. et al. (2023). SolidGen: an autoregressive model for direct B-rep synthesis. *TMLR*. arXiv:2203.13944.
- Xu, X. et al. (2024). BrepGen: a B-rep generative diffusion model with structured latent geometry. *ACM TOG* 43(4). arXiv:2401.15563.

**Solid-modeling theory**
- Requicha, A. A. G. (1980). Representations for rigid solids: theory, methods, and systems. *ACM Computing Surveys* 12(4):437–464. https://doi.org/10.1145/356827.356833
- Requicha, A. A. G. (1977). Mathematical models of rigid solid objects. PAP TM-28, Univ. of Rochester.
- Requicha, A. A. G. & Tilove, R. B. (1978). Mathematical foundations of constructive solid geometry: general topology of closed regular sets. PAP TM-27.
- Tilove, R. B. & Requicha, A. A. G. (1980). Closure of Boolean operations on geometric entities. *Computer-Aided Design* 12(5):219–220.
- Tilove, R. B. (1980). Set membership classification: a unified approach to geometric intersection problems. *IEEE Trans. Computers* C-29(10):874–883.
- Requicha, A. A. G. & Voelcker, H. B. (1985). Boolean operations in solid modeling: boundary evaluation and merging algorithms. *Proc. IEEE* 73(1):30–44. https://doi.org/10.1109/PROC.1985.13108
- Shapiro, V. & Vossler, D. L. (1991). Construction and optimization of CSG representations. *Computer-Aided Design* 23(1):4–20.
- Shapiro, V. & Vossler, D. L. (1993). Separation for boundary to CSG conversion. *ACM TOG* 12(1):35–55.
- Shapiro, V. (1994). Real functions for representation of rigid solids. *CAGD* 11(2):153–175.
- Shapiro, V. (2007). Semi-analytic geometry with R-functions. *Acta Numerica* 16:239–303. https://doi.org/10.1017/S096249290631001X (author PDF: https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
- Rvachev, V. L. (1963). On analytical description of some geometric objects. *Doklady AN SSSR* 153(4):765–768; monographs 1967, 1974, 1982 (Naukova Dumka).
- Pasko, A., Adzhiev, V., Sourin, A. & Savchenko, V. (1995). Function representation in geometric modeling: concepts, implementation and applications. *The Visual Computer* 11(8):429–446. https://doi.org/10.1007/BF02464333
- Hart, J. C. (1996). Sphere tracing. *The Visual Computer* 12(10):527–545. https://doi.org/10.1007/s003710050084
- Keeter, M. J. (2020). Massively parallel rendering of complex closed-form implicit surfaces. *ACM TOG* 39(4):141. https://doi.org/10.1145/3386569.3392429
- Ju, T., Losasso, F., Schaefer, S. & Warren, J. (2002). Dual contouring of Hermite data. *ACM TOG* 21(3):339–346.
- Blackmore, D., Leu, M. C. & Wang, L. P. (1997). The sweep-envelope differential equation algorithm and its application to NC machining verification. *Computer-Aided Design* 29(9):629–637.
- Hoffmann, C. M. (1989). *Geometric and Solid Modeling: An Introduction*. Morgan Kaufmann.

**Geometry axioms, constraints, transforms**
- Tarski, A. & Givant, S. (1999). Tarski's system of geometry. *Bulletin of Symbolic Logic* 5(2):175–214. https://doi.org/10.2307/421089
- Tarski, A. (1951). *A Decision Method for Elementary Algebra and Geometry* (2nd ed.). Univ. of California Press (RAND R-109, 1948).
- Tarski, A. (1959). What is elementary geometry? In Henkin, Suppes & Tarski (eds.), *The Axiomatic Method*, North-Holland, 16–29.
- Pieri, M. (1908). La geometria elementare istituita sulle nozioni 'punto' e 'sfera'. *Mem. Mat. Fis. Soc. Ital. Sci.* 15:345–450. Translation in Marchisotto & Smith (2007), *The Legacy of Mario Pieri*, Birkhäuser.
- Gupta, H. N. (1965). *Contributions to the Axiomatic Foundations of Geometry*. PhD thesis, UC Berkeley.
- Schwabhäuser, W., Szmielew, W. & Tarski, A. (1983). *Metamathematische Methoden in der Geometrie*. Springer.
- Mohr, G. (1672). *Euclides Danicus*. Mascheroni, L. (1797). *La Geometria del Compasso*. Steiner, J. (1833). *Die geometrischen Constructionen…*. Berlin.
- Pollaczek-Geiringer, H. (1927). Über die Gliederung ebener Fachwerke. *ZAMM* 7(1):58–72. https://doi.org/10.1002/zamm.19270070107
- Laman, G. (1970). On graphs and rigidity of plane skeletal structures. *J. Engineering Mathematics* 4(4):331–340. https://doi.org/10.1007/BF01534980
- Katoh, N. & Tanigawa, S. (2011). A proof of the molecular conjecture. *Discrete & Computational Geometry* 45(4):647–700. https://doi.org/10.1007/s00454-011-9348-6
- Lee-St.John, A. & Sidman, J. (2013). Combinatorics and the rigidity of CAD systems. *Computer-Aided Design* (SPM 2012). arXiv:1210.0451.
- Dewar, S. (2026). A counter-example to Baranyai's combinatorial characterisation for 3-rigidity. arXiv:2601.19460 (preprint).
- Owen, J. C. (1991). Algebraic solution for geometry from dimensional constraints. *Proc. ACM SMA '91*, 397–407. https://doi.org/10.1145/112515.112573
- Bouma, W., Fudos, I., Hoffmann, C. M., Cai, J. & Paige, R. (1995). Geometric constraint solver. *Computer-Aided Design* 27(6):487–501. https://doi.org/10.1016/0010-4485(94)00013-4 (TR version: https://docs.lib.purdue.edu/cstech/1068)
- Fudos, I. & Hoffmann, C. M. (1997). A graph-constructive approach to solving systems of geometric constraints. *ACM TOG* 16(2):179–216. https://doi.org/10.1145/248210.248223
- Hoffmann, C. M., Lomonosov, A. & Sitharam, M. (2001). Decomposition plans for geometric constraint systems, Parts I & II. *J. Symbolic Computation* 31(4):367–408, 409–427. https://doi.org/10.1006/jsco.2000.0403
- SolveSpace technical notes, https://solvespace.com/tech.pl ; FreeCAD planegcs `GCS.h`, https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/Sketcher/App/planegcs/GCS.h
- Gunn, C. (2011). On the homogeneous model of Euclidean geometry. arXiv:1101.4542. Gunn, C. (2016). Geometric algebras for Euclidean geometry. *Adv. Appl. Clifford Algebras*. https://doi.org/10.1007/s00006-016-0647-0
- Cartan, É. (1938). *Leçons sur la théorie des spineurs*. Dieudonné, J. (1948). *Sur les groupes classiques*. (Not read.)

**Persistent naming**
- Rossignac, J. R. (1990). Issues on feature-based editing and interrogation of solid models. *Computers & Graphics* 14(2):149–172. https://doi.org/10.1016/0097-8493(90)90029-W
- Hoffmann, C. M. & Juan, R. (1993). EREP: an editable high-level representation for geometric design and analysis. Purdue TR CER-92-24.
- Chen, X. & Hoffmann, C. M. (1995). Towards feature attachment. *Computer-Aided Design* 27(9):695–702. https://doi.org/10.1016/0010-4485(94)00027-B
- Chen, X. & Hoffmann, C. M. (1995). On editability of feature-based design. *Computer-Aided Design* 27(12):905–914. https://doi.org/10.1016/0010-4485(95)00013-5
- Capoyleas, V., Chen, X. & Hoffmann, C. M. (1996). Generic naming in generative, constraint-based design. *Computer-Aided Design* 28(1):17–26. https://doi.org/10.1016/0010-4485(95)00014-3
- Kripac, J. (1997). A mechanism for persistently naming topological entities in history-based parametric solid models. *Computer-Aided Design* 29(2):113–122. https://doi.org/10.1016/S0010-4485(96)00040-1
- Wu, J., Zhang, T., Zhang, X. & Zhou, J. (2001). A face based mechanism for naming, recording and retrieving topological entities. *Computer-Aided Design* 33(10):687–698. https://doi.org/10.1016/S0010-4485(00)00099-3
- Marcheix, D. & Pierra, G. (2002). A survey of the persistent naming problem. *Proc. ACM SMA*, 13–22. https://doi.org/10.1145/566282.566288
- Bidarra, R. & Bronsvoort, W. F. (2002). Persistent naming through persistent entities. *GMP 2002*. https://doi.org/10.1109/GMAP.2002.1027515
- Agbodan, D., Marcheix, D., Pierra, G. & Thabaud, C. (2003). A topological entity matching technique for geometric parametric models. *SMI 2003*, 235–244. https://doi.org/10.1109/SMI.2003.1199623 (PDF: https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf)
- Bidarra, R., Nyirenda, P. J. & Bronsvoort, W. F. (2005). A feature-based solution to the persistent naming problem. *CAD & Applications* 2(1–4):517–526. https://doi.org/10.1080/16864360.2005.10738401
- Farjana, S. H. & Han, S. (2018). Mechanisms of persistent identification of topological entities in CAD systems: a review. *Alexandria Engineering Journal* 57(4):2837–2849. https://doi.org/10.1016/j.aej.2018.01.007
- Cardot, A., Marcheix, D., Skapin, X., Arnould, A. & Belhaouari, H. (2019). Persistent naming based on graph transformation rules to reevaluate parametric specification. *CAD & Applications* 16(5):985–1002. https://doi.org/10.14733/cadaps.2019.985-1002
- Onshape FeatureScript Standard Library: https://cad.onshape.com/FsDoc/library.html
- OCCT OCAF user guide (TNaming): https://dev.opencascade.org/doc/overview/html/occt_user_guides__ocaf.html ; `BRepTools_History`: https://occt3d.com/dev/doc/refman/html/class_b_rep_tools___history.html
- realthunder, *Topological Naming Algorithm*: https://github.com/realthunder/FreeCAD_assembly3/wiki/Topological-Naming-Algorithm ; FreeCAD wiki: https://wiki.freecad.org/Topological_naming_problem/en
- build123d, *Topology Selection and Exploration*: https://build123d.readthedocs.io/en/latest/topology_selection.html

---

## 10. Follow-ups (highest value first)

1. **Read Mäntylä 1984** (and chapters 9–11 of the 1988 book) to pin down the exact completeness statement, its hypotheses and the operator names.
2. **Prototype the Euler / BRepCheck validity check** on OCCT primitives (box, cylinder, cone, sphere, torus, plate with N through-holes) to settle the seam/degenerated-edge counting rules.
3. **Prototype history-anchored references** in build123d/OCP using `BRepTools_History`. Check which operations report history, and from which pinned version.
4. **Read Braid, Hillyard & Stroud 1980, Eastman & Weiler 1979, Kripac 1997 and Marcheix & Pierra 2002** in full (library access).
5. **Confirm Parasolid's `PK_*_euler_*` and attribute split/merge (`PK_ATTDEF`) behaviour** from Siemens documentation, if any licence access exists.

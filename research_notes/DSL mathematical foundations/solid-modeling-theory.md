# Solid-Modeling Theory (r-sets, representation schemes, regularized Booleans, sweeps, F-rep)

*Research pass 2026-11-15. One of four parallel notes. The others cover Euler operators and B-rep topology, geometry axioms and constraints, and persistent naming; those topics are left to them here.*

**Verification legend.**
- **VERIFIED**: I read the claim in the primary source text.
- **VERIFIED (secondary)**: I saw the claim stated in an authoritative secondary source, such as Shapiro's 2007 survey and its reference list, or a publisher or indexing record.
- **UNVERIFIED**: the claim comes from memory or search snippets only.

**Two primary sources were read in full text.**
- **Requicha 1980**, from a scanned PDF with a text layer, mirrored at <https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf>.
- **Shapiro 2007**, *Semi-Analytic Geometry with R-Functions*, from the author's PDF at <https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf>.

---

## Summary

- **Requicha's 1980 framework is confirmed, with one correction to the prior claim.**
  - Requicha models solids as **r-sets**: bounded, closed regular, semianalytic subsets of E³.
  - A **representation scheme** is a relation s: M → R from abstract solids to finite symbol structures.
  - It has four **formal properties**: **domain**, **validity**, **completeness (= unambiguity)** and **uniqueness**.
  - It has three **informal properties**: **conciseness**, **ease of creation** and **efficacy in the context of applications**.
  - Uniqueness is distinct from completeness. Requicha says explicitly that "Completeness neither implies nor is implied by uniqueness."
- **Regularized set operations are defined as X op* Y = k i (X op Y)**, where k is closure and i is interior.
  - Regular sets with these operations form a Boolean algebra. Requicha cites Kuratowski 1976 for this, so it is classical topology.
  - Requicha credits the solid-modeling use of these operations to three sources: Requicha & Voelcker 1977 (TM-25), Requicha & Tilove 1978 (TM-27) and Tilove & Requicha 1980 (CAD 12(5)).
  - Tilove's 1980 *IEEE TC* paper is the **set membership classification** algorithm. It is not the paper that introduced regularization.
- **The key result for a DSL core:** CSG over **bounded** r-set primitives with general regularized ∪*, ∩*, −* and rigid motions is **valid by construction**.
  - Validity then reduces to "parsing", meaning syntax checks plus valid primitive parameters.
  - With **unbounded halfspaces** or **complement**, that guarantee is lost.
  - Requicha also calls **general sweeps** "the least understood" scheme, with "general validity conditions … unknown".
- **R-functions (Rvachev, 1963 onward) are real functions whose sign depends only on the signs of their arguments.** This lets any Boolean set formula become a single inequality f ≥ 0.
  - The standard system is R_α: (x₁ + x₂ ± √(x₁² + x₂² − 2αx₁x₂)) / (1+α). R₀ = x₁ + x₂ ± √(x₁² + x₂²) is analytic everywhere except the origin.
  - No sufficiently complete system can be built from + and × alone (Rvachev 1967).
  - F-rep (Pasko, Adzhiev, Sourin & Savchenko 1995) builds a modeling language on these functions, closed under its operations.
- **What F-rep costs for B-rep or STEP export:** an exact face, edge and vertex structure; named topology for persistent references; and exact analytic and NURBS surfaces.
  - Getting a boundary back needs polygonization (marching cubes, dual contouring) or fitting, which gives a mesh, not a CAD B-rep.
  - So F-rep fits poorly as the core for a DSL that compiles to OCCT or FeatureScript.

## Verdict on prior claims

| Prior claim | Verdict | Correction / nuance |
|---|---|---|
| "Requicha (1980) defined r-sets and regularized Booleans and the properties of a representation scheme (validity, completeness, uniqueness)" | **Mostly correct; needs precision.** VERIFIED | (1) r-sets were first defined in Requicha's TM-28 (Nov 1977). The 1980 Surveys paper summarizes and popularizes them. (2) Regular closed sets and their Boolean algebra predate solid modeling (Kuratowski). Regularized operations in solid modeling are credited to Requicha & Voelcker TM-25 (1977), Requicha & Tilove TM-27 (1978) and Tilove & Requicha 1980. (3) The formal properties are **four**: domain, validity, completeness/unambiguity and uniqueness. There are also **three** informal ones: conciseness, ease of creation and efficacy. (4) "Validity" belongs to *representations*: the range V ⊆ R. It is not a closure property of the scheme. (5) Completeness ≠ uniqueness. |
| "F-rep / Rvachev R-functions (Pasko et al. 1995)" | **Correct with a title fix.** VERIFIED (secondary) | The title is "Function representation in geometric modeling: concepts, implementation and **applications**" (not "computational experiments"), *The Visual Computer* 11(8):429–446, 1995. R-functions are Rvachev's (first paper 1963, Doklady AN SSSR 153(4)). Shapiro's 1988 Cornell report brought them to English-language CAD. Pasko et al. built F-rep and later HyperFun on them. |

---

## Q1. Requicha 1980: exact definitions

### Takeaway
Requicha formalized solids as r-sets and representation schemes as relations s: M → R. He defined unambiguity (s⁻¹ is a function) and uniqueness (s is a function) as independent properties. Validity means membership in the range V. The supporting mathematics is in Rochester PAP technical memos 25, 27 and 28 (1977–78).

### Cited Findings
- **Desired properties of an abstract solid (§1.2).** VERIFIED. [Requicha 1980, p. 440](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  1. Rigidity.
  2. Homogeneous three-dimensionality: "a solid's boundary cannot have isolated or 'dangling' portions".
  3. Finiteness.
  4. Closure under rigid motions and certain Boolean operations.
  5. Finite describability.
  6. Boundary determinism.
- **Definition of r-sets.** VERIFIED. [Requicha 1980, p. 440](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - "suitable models for solids are (congruence classes of) subsets of E³ that are bounded, closed, regular, and semianalytic; we call such sets r-sets."
  - The detailed argument is deferred to REQU77b, the TM-28 memo.
  - Footnote 2: "Because each r-set determines uniquely a congruence class, a solid can be modeled by a single r-set."
- **Character of r-sets.** VERIFIED. [Requicha 1980, pp. 440–441](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - "R-sets are topological polyhedra … curved polyhedra with well-behaved boundaries".
  - They "need not be connected" and may have through holes.
- **Regularity and regularized operations (Appendix).** VERIFIED. [Requicha 1980, Appendix p. 461](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - X is a closed regular set if X = kiX, with k = closure and i = interior, citing [KURA76].
  - X ∪* Y = ki(X ∪ Y); X ∩* Y = ki(X ∩ Y); X −* Y = ki(X − Y); c*X = kicX.
  - "The regular subsets of W, together with the regularized set operators, form a Boolean algebra [KURA76, REQU78]."
- **Semialgebraic and semianalytic sets (Appendix).** VERIFIED. [Requicha 1980, Appendix pp. 461–462](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - A semialgebraic set is a finite Boolean combination of sets {F_i(x,y,z) ≤ 0} with F_i polynomial. Semianalytic sets are the same with F_i analytic.
  - "The class of regular semialgebraic sets is closed under regularized set operations; similar results hold for semianalytic sets [HIRO74]."
  - The "regularized Boolean class" defined by a collection {H_i} of regular semianalytic sets is every finite regularized combination of them. If all H_i are bounded, every member is an r-set.
- **Who is credited for regularized operations.** VERIFIED. [Requicha 1980, p. 441](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - r-sets "are not algebraically closed" under conventional Booleans, "but they are closed under the so-called regularized set intersection, union, and difference [REQU77c, REQU78, TILO80b]".
  - The reference list resolves these as follows:
    - REQU77c = Requicha & Voelcker, "Constructive solid geometry", PAP Tech. Memo 25, Nov 1977.
    - REQU78 = Requicha & Tilove, "Mathematical foundations of constructive solid geometry: General topology of regular closed sets", PAP Tech. Memo 27, March 1978.
    - TILO80b = Tilove & Requicha, "Closure of Boolean operations on geometric entities", *Computer-Aided Design* 12(5):219–220, Sept 1980.
  - TILO80a = Tilove, "Set membership classification: A unified approach to geometric intersection problems", *IEEE Trans. Computers* C-29(10):874–883, Oct 1980. It is cited for classification and boundary evaluation, not for defining regularization.
  - TM-28 = Requicha, "Mathematical models of rigid solid objects", PAP Tech. Memo 28, Univ. of Rochester, Nov 1977.
- **Representation scheme (§1.3).** VERIFIED. [Requicha 1980, pp. 441–442](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - "A representation scheme is defined formally as a relation s: M → R."
  - The domain is D. The range V is the image of D, and "Any representation in the range V is said to be valid".
  - R is the space of syntactically correct representations, "a language generated by some grammar". Representations may be graphs, not only strings.
- **Unambiguity, completeness and uniqueness, verbatim.** VERIFIED. [Requicha 1980, p. 442](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - "A representation r in V is unambiguous or complete if it corresponds to a single object (if the set s⁻¹(r) is a single-element subset {m} of D). It is unique if its corresponding objects do not admit representations other than r in the scheme (if s(s⁻¹(r)) = {r})."
  - The scheme is unambiguous or complete if s⁻¹ is a function, and unique if s is a function.
  - "Completeness neither implies nor is implied by uniqueness. An unambiguous and unique representation scheme establishes a one-to-one correspondence between its domain and range."
- **Formal properties (§1.4).** VERIFIED. [Requicha 1980, pp. 442–443](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - 1.4.1 Domain is the descriptive power.
  - 1.4.2 Validity. "The cleanest approach is to design representation schemes in which essentially all syntactically correct representations are valid … thereby reducing validity checking to a parsing problem."
  - 1.4.3 Completeness.
  - 1.4.4 Uniqueness, which matters for equality testing. The two sources of non-uniqueness are **permutational** (substructures reordered) and **positional** (congruent copies placed differently).
- **Informal properties (§1.5).** VERIFIED. [Requicha 1980, pp. 443–444](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - 1.5.1 Conciseness.
  - 1.5.2 Ease of creation.
  - 1.5.3 Efficacy in the context of applications.
  - The paper concludes that "no single object representation scheme is uniformly 'best'" and that GMSs will hold multiple representations, with a consistency requirement (§1.6).

### Inferences
- Requicha's "reducing validity checking to a parsing problem" is a direct design target for the DSL's core.
- Requicha's "permutational vs positional non-uniqueness" is a ready vocabulary for the DSL's canonicalization and dedup goals.

### Gaps
- I did not obtain TM-27 or TM-28 themselves. Their content is known only through the 1980 paper's citations.

---

## Q2. Regularized Boolean operations

### Takeaway
Regularization closes the r-set class under ∪, ∩ and −. It does this by removing lower-dimensional "dangling" faces, edges and points that ordinary set operations create, for example when two blocks touch face-to-face and are intersected.

### Cited Findings
- **Dangling portions.** VERIFIED. [Requicha 1980, Fig. 3, p. 441](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - "The regularized intersection of two r-sets is an r-set, but their conventional intersection need not be regular". The figure shows a "dangling face".
  - Fig. 2a (p. 440) shows a non-regular closed set whose "boundary has dangling portions that are not adjacent to the set's interior".
- **Closure of the r-set class.** VERIFIED. [Requicha 1980, Appendix](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - Regular sets form a Boolean algebra under the regularized operators.
  - Bounded members of a regularized Boolean class are r-sets.
- **Complement is excluded from bounded CSG.** VERIFIED. [Requicha 1980, p. 449](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - CSG validity would fail "if CSG trees were allowed to contain the regularized complement because it destroys boundedness."
- **Point membership classification.** VERIFIED. [Requicha 1980, p. 457](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - It answers whether a point is in the interior, on the boundary or outside a solid. It underlies PADL boundary evaluation (Tilove 1980).
- **R-function analogue of regularization.** VERIFIED. [Shapiro 2007, §4](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - R-negation "behaves more like the pseudo-complement (defined as the closure of the complement) than the usual complement".
  - Rvachev's Theorem 3 does not strictly cover set difference.

### Inferences
- In theory, every Boolean on r-sets yields an r-set, so a kernel never needs to represent non-manifold "dangling" debris from a regularized Boolean.
- In practice, OCCT's BRepAlgoAPI and others approximate regularization with tolerances. See Q7.

### Gaps
- I did not verify which operations OCCT, Parasolid or ACIS regularize by default. For example, OCCT's General Fuse can keep non-regular results.

---

## Q3. Taxonomy of representation schemes and conversions

### Takeaway
Requicha's six families are pure primitive instancing, spatial occupancy enumeration, cell decomposition, CSG, sweeping and boundary representation. Each has a characteristic profile of ambiguity, uniqueness and validity. CSG → B-rep ("boundary evaluation") is exact but nontrivial. B-rep → CSG needs **separating halfspaces** beyond the face halfspaces (Shapiro & Vossler).

### Cited Findings
- **The six families.** VERIFIED. [Requicha 1980, §2.2–2.7 and Table 1](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - **Primitive instancing** (§2.2) is "unambiguous, unique, easy to validate, concise, and easy to use", but works only for domains "small enough to be covered by a small catalog of families".
  - **Spatial enumeration** (§2.3) is unambiguous and unique except for positional non-uniqueness, and easy to validate, but verbose.
  - **Cell decomposition** (§2.4) is "unambiguous but nonunique. Validity is computationally" expensive.
  - **CSG** (§2.5.2) is "unambiguous but not unique".
  - **Translational and rotational sweeps** (§2.6.1) are "unambiguous but not unique, and their domains are limited to objects with translational or rotational symmetry".
  - **B-rep** (§2.7.2) is "unambiguous if faces are represented unambiguously, but generally they are not unique". Completeness rests on the theorem that "an r-set is defined unambiguously by its boundary".
- **CSG definition, grammar and parametric objects.** VERIFIED. [Requicha 1980, §2.5, pp. 448–449](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - CSG trees are ordered binary trees. Interior nodes are rigid motions or regularized ∪*, ∩*, −*. Leaves are primitives or motion arguments.
  - "CSG trees with uninstantiated parameters can be used to represent generic objects (also called procedure-, macro-, or parametric-objects …). The validity of such generic-object representations also may be ensured easily."
- **Bounded primitives versus halfspaces.** VERIFIED. [Requicha 1980, p. 449](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - With bounded primitives, "any CSG tree is a valid representation of an r-set if the primitive leaves are valid … validity … may be ensured essentially at the syntactical level".
  - With "general halfspaces", trees "may represent unbounded sets and therefore be invalid. Boundedness … generally is difficult to verify."
  - The domain of a CSG scheme depends on its underlying halfspaces, "loosely, on the available surfaces". Two schemes with different primitives can have the same domain.
  - Halfspace schemes are less concise: the 3-block example needs at least 9 planar halfspaces.
- **Restricted CSG ("glue").** VERIFIED. [Requicha 1980, §2.5.3, p. 450](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - Restricting operators to make boundary evaluation easier has costs: user inconvenience, "Lack of closure", difficulty ensuring validity, and inadequacy for interference checking.
- **B-rep validity has combinatorial and metric conditions.** VERIFIED. [Requicha 1980, §2.7.2, p. 454](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - The metric conditions (faces disjoint or meeting at a common edge or vertex) are "computationally unpleasant".
  - Topology and geometry "are not independent": moving a vertex can invalidate the solid.
  - B-reps are "verbose, an order of magnitude longer than corresponding CSG representations" (§2.7.3).
- **Conversions.** VERIFIED. [Requicha 1980, §2.10, pp. 456–457](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - Translational and rotational sweep → B-rep is "simple" because bounding edges of the 2-D set map to faces.
  - "Exact conversion of CSG to boundary representations ('boundary evaluation' …) requires nontrivial algorithms", based on set membership classification.
  - B-rep → CSG ("inverse boundary evaluation") is cited only to Popplestone 1975.
- **Requicha & Voelcker 1985.** VERIFIED (secondary: abstract and index record). [Search record](https://scilit.com/publications/bdee1968f4f08194b790da1210380d85)
  - "Boolean operations in solid modeling: Boundary evaluation and merging algorithms", *Proc. IEEE* 73(1):30–44, DOI 10.1109/PROC.1985.13108.
  - It describes the PADL boundary evaluation algorithms using set membership classification and neighborhood manipulation.
- **B-rep → CSG theory.** VERIFIED. [Shapiro 2007, §5, Theorem 6](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - "Let Ω be a solid, {∂Ω_i} a set of faces in the boundary representation, and H a set of halfspaces induced from the faces. Suppose that the interior of every face ∂Ω_i is separated from the rest of the surface (ω_i = 0) \ ∂Ω_i by a family G of linear halfspaces … Then Ω is describable by H ∪ G."
  - Face halfspaces alone may not suffice. For degree-k primitives, separators may need degree ≥ k/2.
  - "Shapiro and Vossler (1993) used the above results to design and implement a fully automated procedure for constructing set representations for solids bounded by second-degree surfaces."
  - A minimal G is "non-unique".
- **Bibliographic details for Shapiro & Vossler.** VERIFIED (secondary: Shapiro 2007 reference list).
  - 1991a: "Construction and optimization of CSG representations", *Computer-Aided Design* 23(1):4–20.
  - 1991b: "Efficient CSG representations of two-dimensional solids", *ASME J. Mech. Design* 113:292–305.
  - 1993: "Separation for boundary to CSG conversion", *ACM TOG* 12(1):35–55.
- **General semialgebraic set → CSG.** VERIFIED. [Shapiro 2007, §5](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - Algorithms exist (Basu, Pollack & Roy), but "none of these algorithms is practical enough to deal with realistic engineering problems".
- **Requicha & Voelcker 1982 and 1983.** UNVERIFIED.
  - 1982: "Solid modeling: a historical summary and contemporary assessment", *IEEE CG&A* 2(2):9–24.
  - 1983: "Solid modeling: current status and research directions", *IEEE CG&A* 3(7):25–37.

### Inferences
- The DSL's "intent → core" lowering resembles Requicha's "multiple consistent representations". The intent layer is a concise, unique-ish scheme; the core or B-rep is the evaluated, verbose scheme.
- B-rep → CSG is possible in principle but non-unique and costly. Recovering editable history from STEP will likely need heuristics.

### Gaps
- I could not read Requicha & Voelcker 1985 in full.

---

## Q4. Sweeps and Minkowski sums as generators

### Takeaway
Translational and rotational sweeps of planar regions (extrude, revolve) are well behaved and convert to B-rep easily. General sweeps can produce non-regular sets, and Requicha (1980) says conditions guaranteeing an r-set were unknown. Later work (Blackmore & Leu's sweep differential equation and sweep-envelope method) characterizes swept-volume boundaries but does not give a simple closure theorem.

### Cited Findings
- **Translational sweep as a product.** VERIFIED. [Requicha 1980, §2.6, pp. 450–451](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - "sweeping is the least understood, in a theoretical sense, of all the schemes … general validity conditions for sweep representations are unknown."
  - Translational sweep is the Cartesian product A × B (footnote 8).
  - General sweeps are S = f(A × B) for a mapping f: A × B → E³.
- **General sweeping.** VERIFIED. [Requicha 1980, §2.6.3, Fig. 11, p. 451](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - "sweeping a curve along another curve may produce a set which is not homogeneously 2-D (Note the dangling edge …). Mathematical conditions for ensuring that the resulting set is an r-set are unknown."
  - Swept volumes of moving solids serve machining (material removal) and dynamic interference checks.
  - "A major disadvantage … is the lack of known algorithms for computing properties of represented solids."
- **Blackmore & Leu.** VERIFIED (secondary: repository records).
  - They identify any smooth Euclidean motion with a first-order linear ODE, the "sweep differential equation", in "A differential equation approach to swept volumes" (1990, Proc. Rensselaer 2nd Int. Conf. on CIM, pp. 143–149). [NJIT record](https://researchwith.njit.edu/en/publications/a-differential-equation-approach-to-swept-volumes/)
  - The later sweep-envelope differential equation (SEDE) algorithm is in Blackmore, Leu & Wang 1997, *Computer-Aided Design* 29(9):629–637. [NJIT record](https://researchwith.njit.edu/en/publications/the-sweep-envelope-differential-equation-algorithm-and-its-applic/)
- **F-rep sweeps.** VERIFIED (secondary: Shapiro 2007 citation). [Shapiro 2007](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - General sweep by a moving solid has an F-rep formulation in Sourin & Pasko 1995 ("Function representation for sweeping by a moving solid", Proc. 3rd Symp. Solid Modeling).
- **Minkowski sums.** VERIFIED (secondary: MIT DSpace record and secondary descriptions). [MIT DSpace AIM-605](https://dspace.mit.edu/handle/1721.1/5684)
  - Lozano-Pérez, "Spatial Planning: A Configuration Space Approach", MIT AI Memo 605.
  - It computes configuration-space obstacles for polygons and polyhedra, built as Minkowski sums of the robot and the obstacles.
- **Journal version of Lozano-Pérez 1983.** UNVERIFIED. *IEEE Trans. Computers* C-32(2):108–120, 1983.
- **Ghosh 1993.** UNVERIFIED. "A unified computational framework for Minkowski operations", *Computers & Graphics* 17(4). Not found in search.
- **Other sweep sources, not found.** UNVERIFIED.
  - Martin & Stephenson 1990, "Sweeping of three-dimensional objects", *Computer-Aided Design* 22(4):223–234.
  - Wang & Wang 1986, "Geometric modeling for swept volume of moving solids", *IEEE CG&A* 6(12).

### Inferences
- Extrude and revolve of a valid planar region along a transverse direction are safe core operations.
  - For extrude, the result is a product of r-sets in lower dimensions.
  - For revolve, the profile must not cross the axis. This is the usual kernel restriction.
- Path sweeps, lofts and variable sections are unsafe for "valid by construction". They need runtime checks.
- The Minkowski sum of two compact regular sets is compact and regular (inference, not verified). It is the operational basis of offsets, shells and fillets as rolling-ball sweeps. B-rep kernels implement offsets with special-case surface constructions, not general Minkowski sums.

### Gaps
- I found no primary proof that the Minkowski sum is closed over r-sets (semianalyticity under Minkowski sum is plausible for semialgebraic sets via Tarski–Seidenberg).
- I found no formal closure theorem for general sweeps.

---

## Q5. F-rep and R-functions

### Takeaway
An R-function is a real function whose sign is a Boolean function of its arguments' signs. Composing a sufficiently complete system with primitive functions ω_i gives a single inequality for any set built by ∩, ∪ and (pseudo-)complement. F-rep (Pasko et al. 1995) packages this into a closed modeling language: every operation returns a continuous real function.

### Cited Findings
- **Definition 1.** VERIFIED. [Shapiro 2007, §3](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - "A function f_Φ: Rⁿ → R is an R-function if there exists a (binary) logic function Φ: Bⁿ → B satisfying the commutative diagram". That is, S₂(f_Φ(x₁…xₙ)) = Φ(S₂(x₁), …, S₂(xₙ)), where S₂ maps the sign to {0,1}.
  - Φ is the "companion function". Zero is treated as signed (±0) and belongs to both sides.
- **Standard systems.** VERIFIED. [Shapiro 2007, eqs. 3.3–3.6](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - R_α: (1/(1+α))(x₁ + x₂ ± √(x₁² + x₂² − 2αx₁x₂)), with −1 < α ≤ 1. The + sign gives disjunction; the − sign gives conjunction. The derivation comes from the law of cosines and the triangle inequality.
  - α = 1 gives min and max (R₁), which are not differentiable where x₁ = x₂.
  - α = 0 gives R₀: x₁ + x₂ ± √(x₁² + x₂²), "analytic everywhere, except at the origin".
  - R₀ᵐ: (x₁ + x₂ ± √(x₁² + x₂²))(x₁² + x₂²)^(m/2) is C^m.
  - R_p: x₁ + x₂ ± (x₁ᵖ + x₂ᵖ)^(1/p), for even p.
  - R-negation is −x.
- **Completeness results.** VERIFIED. [Shapiro 2007, §3–4](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - Theorem 1 (Rvachev 1967): a system of R-functions is sufficiently complete if its companion logic functions are complete.
  - "a sufficiently complete system of R-functions cannot be constructed using addition and multiplication alone" (Rvachev 1967).
  - Theorem 2 (Rvachev 1974, p. 62): every branch contains a continuous R-function.
  - Theorem 3 (Rvachev 1974): if Φ maps closed sets to closed sets and Ω = Φ(Ω₁…Ω_m) with Ω_i = (ω_i ≥ 0), then Ω is represented by f_Φ(ω₁…ω_m) ≥ 0. Shapiro notes the restriction to closed sets is "awkward" because difference is not strictly covered.
- **Semianalytic sets.** VERIFIED. [Shapiro 2007, §2](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - They are "defined as those sets that can be constructed as a finite Boolean combination … of sets (f_i ≥ 0), where f_i are real analytic functions", originally due to Łojasiewicz 1964.
  - The aim is "functional representations for any closed semi-analytic set". So "every semianalytic set is representable" follows directly from this definition plus Theorem 3. The hard part is the *inverse problem*: finding Φ and the ω_i from a given shape such as a B-rep (Q3).
- **Proper signing is a practical defect.** VERIFIED. [Shapiro 2007, §5](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - The function from an optimized expression "may not be properly signed". It can be zero at interior points, for example where three disks meet.
  - The fix combines the representations of Ω and of its pseudo-complement.
- **Smooth distance-like functions.** VERIFIED. [Shapiro 2007, §4.3](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - R-functions give normalized approximations of distance to an order m. The exact distance is not differentiable everywhere.
- **History.** VERIFIED. [Shapiro 2007, §1, §6](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - Rvachev's first paper: "On analytical description of some geometric objects", *Doklady AN SSSR* 153(4):765–768, 1963.
  - Monographs (all Naukova Dumka, in Russian):
    - *Geometric Applications of Logic Algebra*, 1967.
    - *Methods of Logic Algebra in Mathematical Physics*, 1974.
    - *Theory of R-functions and Some Applications*, 1982.
  - English translation of the theory: Shapiro 1988, Cornell TR (revised 1991, TR91-1219).
  - Ricci 1973 (*Computer Journal* 16(3)) first used min and max for "constructive geometry".
  - "Pasko et al. (1995) developed a powerful geometric language for computer graphics based on R-functions".
- **Shapiro 1994.** VERIFIED (secondary: Shapiro 2007 reference list). "Real functions for representation of rigid solids", *Computer-Aided Geometric Design* 11(2):153–175.
- **Shapiro 2007 itself.** VERIFIED. "Semi-Analytic Geometry with R-Functions", *Acta Numerica* 16:1–65, Cambridge UP. The PDF header shows a truncated DOI; the full DOI is UNVERIFIED (see the unverified list).
- **F-rep definition and closure.** VERIFIED (secondary: Wikipedia, citing Pasko et al. 1995). [Wikipedia: Function representation](https://en.wikipedia.org/wiki/Function_representation)
  - f(X) ≥ 0 is inside, f = 0 is the boundary, f < 0 is outside.
  - The operations are set-theoretic, blending, offsetting, projection, non-linear deformation, metamorphosis, sweeping and hypertexturing. They "yield continuous real-valued functions as output, thus guaranteeing the closure property of the representation".
  - The HyperFun language implements F-rep.
- **Pasko et al. 1995 citation.** VERIFIED (secondary: dblp, Shapiro reference list, search results). [dblp](https://dblp.dagstuhl.de/rec/journals/vc/PaskoASS95.html)
  - Pasko, A., Adzhiev, V., Sourin, A., Savchenko, V. (1995). "Function representation in geometric modeling: concepts, implementation and applications". *The Visual Computer* 11(8):429–446.
  - DOI 10.1007/BF02464333, from search snippets; see the unverified list.
- **Keeter 2020.** VERIFIED (secondary: author page and SIGGRAPH archive). [Keeter MPR](https://www.mattkeeter.com/research/mpr/)
  - "Massively Parallel Rendering of Complex Closed-Form Implicit Surfaces", *ACM TOG* 39(4), Article 141 (SIGGRAPH 2020), DOI 10.1145/3386569.3392429.
  - This is the libfive author's GPU interval-arithmetic renderer.
- **Hart 1996.** UNVERIFIED. "Sphere tracing: a geometric method for the antialiased ray tracing of implicit surfaces", *The Visual Computer* 12(10):527–545, DOI 10.1007/s003710050084.
  - Sphere tracing needs a Lipschitz bound on f, which motivates SDF-style (distance-like) functions.

### Inferences
- F-rep has an even stronger "valid by construction" property than CSG: every expression is a total function, so there is no validity check at all.
- That validity is cheap because F-rep's notion of a solid is weaker. Nothing forces boundedness, and it is regular only if functions are properly signed and non-degenerate. Requicha's boundedness and regularity guarantees have to be imposed separately.
- R₀ or R₀ᵐ operations give C^m blends "for free". This is attractive for fillet-like intent but geometrically different from a constant-radius rolling-ball fillet.

### Gaps
- I did not read the Pasko 1995 full text. Its exact operation list and its α-parameterized R-function formulas as printed in that paper are not verified there.
- I did not verify nTop's internal implicit kernel.

---

## Q6. What a minimal solid-generating core could be

### Takeaway
There are four candidate cores. Each guarantees validity at a different strength, and each suits B-rep/STEP export to a different degree.
- (a) CSG over halfspaces
- (b) bounded primitives + rigid motions + regularized Booleans
- (c) sketch + extrude/revolve(/sweep) + Booleans
- (d) F-rep

For a DSL that compiles to OCCT and FeatureScript, (b) and (c) in their safe subsets are the provable core. (a) is the theoretical floor, and (d) is an analysis or preview layer, not an export layer.

### Cited Findings
- **(a) Halfspaces.** VERIFIED. [Requicha 1980, Appendix](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf); [Shapiro 2007, §2, §5](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - By definition, every semianalytic (resp. semialgebraic) set is a finite Boolean combination of analytic (resp. algebraic) halfspaces (f ≥ 0).
  - The source for this is the definition itself, due to Łojasiewicz 1964 and given in Requicha's appendix and Shapiro 2007 §2. Shapiro 2007 §5 adds the constructive "describability" results.
  - Requicha warns that halfspace CSG loses guaranteed validity, because boundedness is hard to check, and is less concise.
- **(b) Bounded primitives.** VERIFIED. [Requicha 1980, p. 449](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - With bounded primitives and **general** regularized operators (no complement), every syntactically correct tree is a valid r-set. This holds for parametric (generic) trees too.
- **(c) Feature-based.** VERIFIED. [Requicha 1980, §2.6.1, §2.10](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - Translational and rotational sweeps are unambiguous, domain-limited, used "as a means of entering object … descriptions in GMSs based on boundary representations", and convert to B-rep simply.
  - General sweeps lack validity conditions.
- **(d) F-rep → boundary.** VERIFIED. [Shapiro 2007, §6](https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf)
  - Boundaries are recovered by marching cubes (Lorensen & Cline 1987), polygonization (Bloomenthal 1988) or continuation methods. These give piecewise-linear approximations.
- **Dual contouring.** VERIFIED (secondary: author PDF listing and SIGGRAPH archive). [Ju et al. 2002](https://www.cs.wustl.edu/~taoju/research/dualContour.pdf)
  - Ju, Losasso, Schaefer & Warren 2002, "Dual contouring of Hermite data", *ACM TOG* 21(3) (SIGGRAPH 2002).
  - It uses exact intersection points and normals to keep sharp features, but its output is still a polygon mesh.

### Inferences — candidate cores and tradeoffs

| Core | Validity by construction | Expressiveness | B-rep/STEP export | Persistent refs | Notes for DSL |
|---|---|---|---|---|---|
| (a) Halfspaces + ∪*,∩*,−* | Only if boundedness is proven, which is hard in general | Maximal: all semianalytic | Exact, via boundary evaluation, if halfspaces are kernel-native surfaces (plane, quadric, torus, NURBS) | Faces map to halfspaces, which helps naming | Elegant theory, poor ergonomics. A good *normal form* for canonicalization and equivalence, not for authoring |
| (b) Bounded primitives + rigid motions + regularized Booleans | **Yes**, at the parse level (Requicha) | Limited to the primitive set's halfspace class | Exact (OCCT BRepPrimAPI + BRepAlgoAPI) | Primitive-face provenance is clear | Best "provable" core. Add primitives to grow the domain. Intent tags attach to tree nodes |
| (c) Planar profile + extrude/revolve (+ Booleans) | Yes if the profile is a valid 2-D r-set and revolve does not cross its axis. Path sweeps and lofts need runtime checks | Matches mechanical "unsculptured" parts | Exact and simple (Requicha §2.10) | Faces map to profile edges × sweep, which is the classic basis of naming | Matches Onshape/FeatureScript and CadQuery idioms. Reduces 3-D validity to 2-D profile validity |
| (d) F-rep (R-functions/SDF) | Always (total functions), but boundedness, regularity and proper signing are not guaranteed | Very rich (blends, offsets, lattices, variable fields) | **Lossy.** Exact face/edge topology, analytic surface types, exact fillet surfaces and tolerances are lost. Only meshes or fitted surfaces come back | **None native.** The boundary has no named faces | Useful as a secondary representation for previews, interference checks, offsets and analysis. Unsuitable as the authoritative core when STEP/FeatureScript fidelity is required |

- **Recommended stance (inference).** Use a core of type (b) ∪ (c-safe): bounded primitives and planar-profile extrude/revolve, plus rigid motions and regularized ∪*, ∩*, −*.
  - Treat path-sweep, loft, shell, offset and fillet as **intent-layer operations with explicit runtime validity checks**, since theory gives no closure guarantee for them.
  - Optionally, keep a halfspace normal form (a) for canonical comparison.

### Gaps
- I found no source specifically on F-rep → *exact* B-rep (STEP-quality) reconstruction. The literature I found yields meshes.

---

## Q7. Implications for validity checks

### Takeaway
Theory says regularized Booleans on r-sets always yield r-sets, so the *mathematical* result is always valid. Kernels compute in floating point with tolerances, though, and Boolean robustness is a long-standing unsolved engineering problem. The DSL therefore still needs post-evaluation validity checks such as BRepCheck_Analyzer and an Euler–Poincaré check.

### Cited Findings
- **Validity must be automatic.** VERIFIED. [Requicha 1980, §1.4.2, p. 442](https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf)
  - "future GMSs will not be able to rely on human validation and must ensure representational validity by automatic means", either by checking after construction or by embedding constraints in the constructors.
  - Invalid representations can produce results "that appear to be credible but are in fact meaningless".
  - Requicha also notes that robustness of geometric algorithms "has not received the attention it deserves" (§1.5.3).
- **Hoffmann's textbook.** VERIFIED (secondary: book PDF table of contents seen via search snippet). [Hoffmann book PDF listing](https://softbank.iust.ac.ir/NewTechnologies/ebook/shahravi%20book/Solid%20&%20Design/Hoffman%20C.M.%20Geometric%20and%20solid%20modeling%20(1998)(344s).pdf)
  - Hoffmann, C. M. (1989), *Geometric and Solid Modeling: An Introduction*, Morgan Kaufmann. The publisher is UNVERIFIED.
  - It contains a chapter "Robust and Error-Free Geometric Operations" covering floating-point failures.
- **Hoffmann, Hopcroft & Karasick 1989.** VERIFIED (secondary: search snippet of the paper). [PDF](https://ftp1.cs.wisc.edu/pub/users/prem/for-prem/Hoffmann-Hopcroft-Karasick-1989.pdf)
  - Their polyhedral Boolean work locates the robustness problem in floating-point arithmetic. They add symbolic reasoning to resolve numerically ambiguous decisions and use floating point "when this is safe".
  - Exact title and venue UNVERIFIED: likely "Robust set operations on polyhedral solids", *IEEE CG&A* 9(6), 1989.
- **No provably robust Boolean algorithm.** VERIFIED (secondary: dissertation abstract). [Purdue dissertation record](https://docs.lib.purdue.edu/dissertations/AAI9215702)
  - "Exact arithmetic solid modeling" (Purdue, c.1992) reports that there is no known provably robust algorithm for Boolean operations on solids.

### Inferences
- **Validity has two layers.** Theory (r-set closure) justifies validating the *program*, meaning parse-level checks on the core tree as in Requicha. Practice requires validating the *result*.
  - Result checks include kernel shape checks, Euler–Poincaré consistency (covered by the B-rep topology note), positive volume, closed shells and a tolerance audit.
- **Degenerate inputs** (coplanar or tangent faces, zero-thickness contacts) are exactly where regularization matters and where kernels misbehave. The DSL linter should flag intent that yields near-coincident geometry. These are inferred risk areas, not sourced.
- **Lowering must be deterministic** and should, as an inference, pin the kernel version and tolerances. Tolerance-dependent results make "same program → same B-rep" a kernel property, not a theoretical one.

### Gaps
- I did not survey the modern robustness literature: exact predicates and EGC (Yap), Shewchuk predicates, mesh-arrangement Booleans (e.g. Zhou et al. 2016 "Mesh arrangements for solid geometry"), and OCCT fuzzy Booleans.

---

## Reference list

**Primary, read in full (VERIFIED):**
1. Requicha, A. A. G. (1980). Representations for rigid solids: theory, methods, and systems. *ACM Computing Surveys* 12(4):437–464. DOI [10.1145/356827.356833](https://doi.org/10.1145/356827.356833). Full text read at <https://lvelho.impa.br/i3d14/modtec/p437-requicha.pdf>.
2. Shapiro, V. (2007). Semi-analytic geometry with R-functions. *Acta Numerica* 16:1–65. Cambridge UP. PDF: <https://ftp.cs.wisc.edu/pub/users/prem/rfuns.pdf>. The DOI in the PDF header is truncated; the full DOI is UNVERIFIED.

**Cited via Requicha 1980's reference list (VERIFIED as citations):**
3. Requicha, A. A. G. (1977). Mathematical models of rigid solid objects. Tech. Memo 28, Production Automation Project, Univ. of Rochester, Nov 1977.
4. Requicha, A. A. G., & Voelcker, H. B. (1977). Constructive solid geometry. Tech. Memo 25, PAP, Univ. of Rochester, Nov 1977.
5. Requicha, A. A. G., & Tilove, R. B. (1978). Mathematical foundations of constructive solid geometry: general topology of regular closed sets. Tech. Memo 27, PAP, Univ. of Rochester, March 1978.
6. Tilove, R. B. (1980). Set membership classification: a unified approach to geometric intersection problems. *IEEE Trans. Computers* C-29(10):874–883.
7. Tilove, R. B., & Requicha, A. A. G. (1980). Closure of Boolean operations on geometric entities. *Computer-Aided Design* 12(5):219–220.
8. Kuratowski, K., & Mostowski, A. (1976). *Set Theory* (cited as KURA76 for regular sets forming a Boolean algebra). Exact KURA76 entry UNVERIFIED.

**Cited via Shapiro 2007's reference list (VERIFIED as citations):**
9. Rvachev, V. L. (1963). On analytical description of some geometric objects. *Doklady AN SSSR* 153(4):765–768.
10. Rvachev, V. L. (1967). *Geometric Applications of Logic Algebra*. Naukova Dumka (Russian).
11. Rvachev, V. L. (1974). *Methods of Logic Algebra in Mathematical Physics*. Naukova Dumka (Russian).
12. Rvachev, V. L. (1982). *Theory of R-functions and Some Applications*. Naukova Dumka (Russian).
13. Shapiro, V. (1988; rev. 1991). Theory of R-functions and applications: a primer. Tech. Report TR91-1219, Computer Science Dept., Cornell University.
14. Shapiro, V. (1991). *Representations of Semi-Algebraic Sets in Finite Algebras Generated by Space Decompositions*. PhD thesis, Cornell University.
15. Shapiro, V. (1994). Real functions for representation of rigid solids. *Computer-Aided Geometric Design* 11(2):153–175.
16. Shapiro, V., & Vossler, D. L. (1991a). Construction and optimization of CSG representations. *Computer-Aided Design* 23(1):4–20.
17. Shapiro, V., & Vossler, D. L. (1991b). Efficient CSG representations of two-dimensional solids. *ASME J. Mechanical Design* 113:292–305.
18. Shapiro, V., & Vossler, D. L. (1993). Separation for boundary to CSG conversion. *ACM Transactions on Graphics* 12(1):35–55.
19. Pasko, A., Adzhiev, V., Sourin, A., & Savchenko, V. (1995). Function representation in geometric modeling: concepts, implementation and applications. *The Visual Computer* 11(8):429–446. DOI 10.1007/BF02464333 (from search snippets; see the unverified list). [dblp](https://dblp.dagstuhl.de/rec/journals/vc/PaskoASS95.html)
20. Sourin, A., & Pasko, A. (1995). Function representation for sweeping by a moving solid. Proc. 3rd Symp. on Solid Modeling and Applications.
21. Łojasiewicz, S. (1964). Triangulations of semi-analytic sets. *Annali della Scuola Normale Superiore di Pisa* 18:449–474. (Shapiro's reference list prints "semi-algebraic"; the original title is "semi-analytic sets", UNVERIFIED.)
22. Ricci, A. (1973). A constructive geometry for computer graphics. *The Computer Journal* 16(3):157–160.

**Verified via index or author records (VERIFIED (secondary)):**
23. Requicha, A. A. G., & Voelcker, H. B. (1985). Boolean operations in solid modeling: boundary evaluation and merging algorithms. *Proc. IEEE* 73(1):30–44. DOI [10.1109/PROC.1985.13108](https://doi.org/10.1109/PROC.1985.13108).
24. Blackmore, D., & Leu, M. C. (1990). A differential equation approach to swept volumes. Proc. Rensselaer 2nd Int. Conf. on Computer Integrated Manufacturing, pp. 143–149. [NJIT](https://researchwith.njit.edu/en/publications/a-differential-equation-approach-to-swept-volumes/)
25. Blackmore, D., Leu, M. C., & Wang, L. P. (1997). The sweep-envelope differential equation algorithm and its application to NC machining verification. *Computer-Aided Design* 29(9):629–637. [NJIT](https://researchwith.njit.edu/en/publications/the-sweep-envelope-differential-equation-algorithm-and-its-applic/)
26. Lozano-Pérez, T. Spatial planning: a configuration space approach. MIT AI Memo 605. [DSpace](https://dspace.mit.edu/handle/1721.1/5684)
27. Keeter, M. J. (2020). Massively parallel rendering of complex closed-form implicit surfaces. *ACM TOG* 39(4), Art. 141. DOI [10.1145/3386569.3392429](https://doi.org/10.1145/3386569.3392429).
28. Ju, T., Losasso, F., Schaefer, S., & Warren, J. (2002). Dual contouring of Hermite data. *ACM TOG* 21(3):339–346 (SIGGRAPH 2002). [PDF](https://www.cs.wustl.edu/~taoju/research/dualContour.pdf)
29. Hoffmann, C. M. (1989). *Geometric and Solid Modeling: An Introduction*. Morgan Kaufmann. The publisher is UNVERIFIED; the existence of its robustness chapter is VERIFIED via the ToC snippet.
30. Hoffmann, C. M., Hopcroft, J. E., & Karasick, M. S. (1989). Robust set operations on polyhedral solids. *IEEE CG&A* 9(6). The title and venue are UNVERIFIED; the content is VERIFIED via snippet. [PDF](https://ftp1.cs.wisc.edu/pub/users/prem/for-prem/Hoffmann-Hopcroft-Karasick-1989.pdf)

## Unverified items (explicit)
- Requicha & Voelcker 1982, "Solid modeling: a historical summary and contemporary assessment", *IEEE CG&A* 2(2):9–24.
- Requicha & Voelcker 1983, "Solid modeling: current status and research directions", *IEEE CG&A* 3(7):25–37.
- Martin, R. R., & Stephenson, P. C. 1990, "Sweeping of three-dimensional objects", *CAD* 22(4):223–234. Not found in search.
- Wang, W. P., & Wang, K. K. 1986, "Geometric modeling for swept volume of moving solids", *IEEE CG&A* 6(12).
- Ghosh, P. K. 1993, "A unified computational framework for Minkowski operations", *Computers & Graphics* 17(4).
- Lozano-Pérez 1983 journal version, *IEEE Trans. Computers* C-32(2):108–120.
- Hart, J. C. 1996, "Sphere tracing…", *The Visual Computer* 12(10):527–545, DOI 10.1007/s003710050084.
- The Pasko et al. 1995 DOI 10.1007/BF02464333 (from search snippets; one source gave 10.1007/s003710050034), and that paper's internal formulas and operation list, which I did not read.
- The Shapiro 2007 Acta Numerica DOI. The PDF shows a truncated "10.1017/S0962492902…"; it is probably 10.1017/S0962492906370017.
- The claim that Minkowski sums of r-sets are r-sets (my inference).
- The default regularization behavior of OCCT, Parasolid and ACIS Booleans.
- The exact KURA76 reference in Requicha 1980.

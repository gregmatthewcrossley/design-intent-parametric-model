# Geometry axioms, constructions, constraint solving, and transforms

*Research pass, 2026-11-15. One of four parallel notes (the others cover Euler operators/B-rep, solid-modeling theory/F-rep, and persistent naming). Status tags: **VERIFIED** means I read the cited source text myself. **VERIFIED (secondary)** means I saw it only in a reliable secondary source such as Wikipedia, a vendor page, or a citing paper. **UNVERIFIED** means it comes from background knowledge and no source was seen.*

## Summary

- **Tarski's geometry.** Confirmed from the primary source (Tarski & Givant 1999). It uses one sort (points) and two primitives: ternary betweenness B and quaternary equidistance ≡. Elementary (first-order) geometry admits quantifier elimination, so it is complete and decidable. Its models are exactly Cartesian spaces over real closed fields.
- **Gupta's results, correcting a common summary.** The prior claim and Wikipedia say Gupta "proved the axioms independent". Tarski & Givant say otherwise. Gupta's thesis showed that two axioms, Ax.6 and Ax.18, are *derivable* (redundant). It also showed 8 of the remaining 11 axioms of FG(2) are independent. Independence of Ax.1, Ax.3 and Ax.7₁ was still open when Tarski & Givant wrote. Szczerba later settled Ax.7₁ in a modified system.
- **Pieri (1908).** Corrected and sharpened. His single primitive is the ternary relation "b and c are equidistant from a" (xy ≡ yz in Tarski's notation). His system for 3D full Euclidean geometry has 24 axioms. Tarski also notes that ≡ alone suffices, because betweenness is definable from it. Tarski calls such one-primitive axiomatizations "involved and unnatural".
- **Ruler-and-compass geometry has its own finite axiomatization.** Replacing the continuity schema by a single Circle Axiom gives the theory of ruler-and-compass constructions, whose models are Euclidean ordered fields. This is the most directly useful foundational fact for a sketch DSL, because it matches what graph-constructive CAD solvers (Owen/D-Cubed, Bouma–Fudos–Hoffmann) can solve with quadratic equations only.
- **Laman / Pollaczek-Geiringer.** Confirmed: the 2D generic-rigidity counting characterization has 1927 priority. In 3D, Maxwell counting is necessary but not sufficient (the double banana is the counterexample), and no combinatorial characterization exists for any d ≥ 3 as of Jan 2026. A recently proposed characterization (Baranyai, date not confirmed) was shown to be necessary only (Dewar, arXiv Jan 2026). Body-hinge/panel-hinge rigidity is solved: Katoh & Tanigawa 2011 proved the Tay–Whiteley molecular conjecture. "Body-and-cad" rigidity, covering 20 of 21 CAD constraint types, has a combinatorial characterization (Lee-St.John & Sidman 2012/13).
- **Constraint solvers.**
  - Owen 1991 (ACM SMA, pp. 397–407) does triconnected decomposition and ruler-and-compass algebraic solving. It is the basis of D-Cubed DCM, confirmed via Bouma et al.
  - Bouma et al. normalize incidence to zero-distance. Their final constraint vocabulary is only distance + angle.
  - Well-constrained problems have exponentially many solutions. Choosing one is the "root identification problem", which bears directly on determinism.
  - SolveSpace uses modified Newton, with least squares when under-constrained.
  - FreeCAD planegcs uses BFGS / Levenberg–Marquardt / DogLeg plus QR-based DOF counting and redundancy/conflict diagnosis.
- **Cartan–Dieudonné.** The linear statement is confirmed (secondary source): at most n reflections, characteristic ≠ 2. The n+1 bound for affine Euclidean isometries follows by a short argument but I found no source text for it. Gunn's projective GA (PGA) explicitly provides all Euclidean isometries, direct and indirect, as versor ("sandwich") operators.

---

## Verdict table on prior claims

| # | Prior claim | Verdict | Notes / source |
|---|---|---|---|
| 1 | Tarski: points only; primitives betweenness + equidistance | **Confirmed (VERIFIED)** | Tarski & Givant 1999 §2: "two primitive notions, the ternary relation of betweenness, B, and the quaternary relation of equidistance, ≡". In the original 1926–27 version, point equality was also a primitive; later versions treat it as logical identity. |
| 2 | Complete and decidable via RCF quantifier elimination | **Confirmed (VERIFIED)**, with nuance | Tarski proved quantifier elimination for the geometry around 1930. Completeness, decidability and a constructive consistency proof follow. The models of EG(n) are exactly the n-dimensional Cartesian spaces over real closed fields. The decision method was published as RAND R-109 (1948) and revised by the University of California Press (1951). |
| 3 | First-order continuity *schema* | **Confirmed (VERIFIED)** | Elementary geometry EG(n) uses the schema As.11 (infinitely many instances). Full geometry FG(n) uses a single second-order Ax.11. Any independent equivalent replacement of the schema must be infinite (Tarski 1959). |
| 4 | Number of axioms | **Corrected/clarified (VERIFIED)** | There is no single number. Tarski & Givant list Ax.1–Ax.24 plus variants across versions. The reduced EG(n) is Ax.1–5, Ax.7₁, Ax.8⁽ⁿ⁾, Ax.9⁽ⁿ⁾, Ax.10₁, Ax.15 and As.11: 10 axioms plus one schema. The textbook version is Schwabhäuser–Szmielew–Tarski 1983, EH(n). Wikipedia's "10 axioms and one schema" (VERIFIED secondary) agrees. |
| 5 | Pieri 1908: single primitive, an equidistance-type ternary relation | **Confirmed and sharpened (VERIFIED)** | Pieri's only primitive is the ternary relation that holds among a, b, c "if, and only if, b and c are equidistant from a". His system for full 3D geometry has 24 axioms (Tarski & Givant §3). Citation: Memorie di Matematica e di Fisica della Società Italiana delle Scienze, vol. 15 (1908), pp. 345–450. Wikipedia's Tarski page says "Pieri had only two primitive notions". Read as point + relation, that is consistent. |
| 6 | Tarski: a single ternary/quaternary relation suffices | **Confirmed (VERIFIED)** | B is definable from ≡, so ≡ alone suffices. Pieri's ternary xy ≡ yz also suffices, as do xy ≤ zu and xy ≤ yz (Tarski & Givant §5). Tarski calls such axiom sets "rather involved and unnatural". |
| 7 | Gupta 1965 proved independence of Tarski's axioms | **Corrected (VERIFIED)** | Per Tarski & Givant, Gupta showed Ax.6 (identity of betweenness) and Ax.18 (outer connectivity) are *derivable* from the rest. In FG(2), Ax.2, 4, 5, 8⁽²⁾, 9⁽²⁾, 10₁, 11 and 15 are independent. Ax.1, 3 and 7₁ were open. Szczerba proved Ax.7₁ independent in a variant with Ax.10₂. Wikipedia's phrasing ("independent except Pasch and reflexivity of congruence") is a lossy summary. Thesis: UC Berkeley, 1965, 407 pp. |
| 8 | Hilbert 1899 primitives | **UNVERIFIED** | From background: point, line, plane; incidence, betweenness, congruence (of segments and angles); second-order completeness axiom. Not checked. |
| 9 | Mohr–Mascheroni: compass alone suffices | **Confirmed (VERIFIED secondary)** | Mohr, *Euclides Danicus*, Amsterdam 1672. Mascheroni, *La Geometria del Compasso*, Pavia 1797. Hjelmslev drew renewed attention to Mohr in 1928 (Matematisk Tidsskrift B, pp. 1–7). Lines count as constructed once two points on them are. |
| 10 | Poncelet–Steiner: straightedge plus one circle with its center | **Confirmed (VERIFIED secondary)** | Poncelet 1822. Steiner 1833, *Die geometrischen Constructionen, ausgeführt mittelst der geraden Linie und eines festen Kreises* (Berlin: Dümmler). The center cannot be dropped (Hilbert's argument). |
| 11 | Laman 1970 statement + DOI | **Confirmed (VERIFIED secondary)** | J. Eng. Math. 4(4):331–340, doi:10.1007/BF01534980. The statement is |E| = 2|V| − 3 and every k-vertex subgraph (k ≥ 2) has ≤ 2k − 3 edges. |
| 12 | Pollaczek-Geiringer 1927 priority | **Confirmed (VERIFIED secondary)** | ZAMM 7(1):58–72, doi:10.1002/zamm.19270070107. |
| 13 | 3D: Maxwell 3n − 6 necessary, not sufficient; double banana; open | **Confirmed (VERIFIED secondary)**, status current to Jan 2026 | Multiple arXiv surveys. Dewar (arXiv:2601.19460, Jan 2026) shows Baranyai's recent condition is necessary but not sufficient. Background claim that no characterization is known for any d ≥ 3 is consistent with these sources. |
| 14 | Body-bar/body-hinge solved: Tay 1984, Tay–Whiteley, Katoh–Tanigawa 2011 | **Confirmed (VERIFIED secondary)** | Katoh & Tanigawa, "A Proof of the Molecular Conjecture", DCG 45(4):647–700 (2011), doi:10.1007/s00454-011-9348-6. The conjecture is Tay–Whiteley 1984. Jackson–Jordán had done the 2D case. Tay's body-bar theorem citation itself is not checked (UNVERIFIED). |
| 15 | Owen 1991, basis of D-Cubed DCM | **Confirmed (VERIFIED via Bouma et al. tech report)** | "J. Owen. Algebraic solution for geometry from dimensional constraints. In ACM Symp. Found. of Solid Modeling, pages 397–407, Austin, Tex, 1991." Bouma et al. say DCM "is a commercial constraint solver using this method" and thank John Owen of D-Cubed. DOI not confirmed (likely 10.1145/112515.112573, UNVERIFIED). |
| 16 | Bouma, Fudos, Hoffmann, Cai, Paige 1995, CAD 27(6) | **Partially verified** | I read the Purdue tech report version (CSD-TR-93-054, Aug 1993). The journal citation, CAD 27(6):487–501, 1995, is UNVERIFIED. |
| 17 | Fudos & Hoffmann 1997 ACM TOG | **Confirmed (VERIFIED secondary)** | ACM TOG 16(2):179–216, doi:10.1145/248210.248223 (Purdue CGV record, DBLP). |
| 18 | Hoffmann, Lomonosov, Sitharam 2001 JSC | **Confirmed; title corrected** | Two parts: "Decomposition Plans for Geometric Constraint Systems, Part I: Performance Measures for CAD", JSC 31(4):367–408. "…Part II: New Algorithms", JSC 31(4):409–427, doi:10.1006/jsco.2000.0403. |
| 19 | Kramer 1992 | **UNVERIFIED** | Background: G. Kramer, *Solving Geometric Constraint Systems: A Case Study in Kinematics*, MIT Press, 1992 (degrees-of-freedom analysis). Not checked. |
| 20 | Jermann/Trombettoni/Neveu/Mathis survey | **UNVERIFIED** | Not checked. |
| 21 | Sitharam, St. John, Sidman eds. 2018 Handbook | **Partially verified** | Fudos–Hoffmann–Joan-Arinyo arXiv:1608.05205 says it was accepted as a chapter in "Handbook of Geometric Constraints Principles (CRC Press)". Exact title, year and ISBN are UNVERIFIED. |
| 22 | Onshape uses D-Cubed | **Partially verified (vendor claim)** | A Siemens PLM Components blog lists Onshape as a D-Cubed licensee. It does not say which component, or that the sketcher uses it. |
| 23 | SolveSpace = numeric Newton | **Confirmed (VERIFIED)** | solvespace.com/tech.pl: constraints are symbolic equations solved by "a modified Newton's method", with least squares when not fully constrained. |
| 24 | FreeCAD planegcs = numeric + DOF/redundancy | **Confirmed (VERIFIED from source code)** | `GCS.h` declares the BFGS, LevenbergMarquardt and DogLeg algorithms, Eigen dense/sparse QR of the transposed Jacobian, `dofs`, `conflictingTags`, `redundantTags` and `partiallyRedundantTags`. |
| 25 | Cartan–Dieudonné: ≤ n reflections | **Confirmed (VERIFIED secondary)** | Wikipedia states it for nondegenerate symmetric bilinear spaces over fields of characteristic ≠ 2. Primary citations (Cartan 1938, *Leçons sur la théorie des spineurs*; Dieudonné 1948) are not checked (UNVERIFIED). |
| 26 | Corollary: Euclidean isometries of Rⁿ are ≤ n+1 reflections | **UNVERIFIED as a citation; sound as an argument** | No source text found. The proof sketch is in the Transforms section below. |
| 27 | GA/CGA/PGA as a uniform core | **Partially verified** | Gunn 2011 (arXiv:1101.4542) says "versor (sandwich) operators provide all euclidean isometries, both direct and indirect". Gunn 2016 (AACA, doi:10.1007/s00006-016-0647-0) argues PGA is the smallest structure-preserving Euclidean GA and compares it with CGA. Hestenes, Dorst–Fontijne–Mann 2007, Hestenes–Li–Rockwood 2001 and "May the Forque Be with You" are UNVERIFIED. No CAD kernel use was found. |

---

## 1. Axiomatic foundations: Tarski, Pieri, Gupta, Hilbert

### Takeaway
Elementary Euclidean geometry can be built on **one sort (points) and two relations: betweenness (affine) and equidistance (metric)**. Equidistance alone, or Pieri's ternary relation alone, also suffices but makes the axioms far uglier. The first-order theory is complete and decidable. Its strength depends on the continuity principle: the full schema gives real closed fields, the single Circle Axiom gives ruler-and-compass (Euclidean fields), and neither gives Pythagorean fields.

### Cited findings (all VERIFIED from Tarski & Givant 1999 text unless noted)
- Tarski's axiom set dates from his 1926–27 Warsaw lectures. "He proved, around 1930, that his system of geometry admits elimination of quantifiers… First, the theory is complete… Second, the theory is decidable… Third, there is a constructive consistency proof." — [Tarski & Givant 1999](https://www.math.ucla.edu/~asl/bsl/0502/0502-002.ps)
- Primitives are B (ternary) and ≡ (quaternary). In the original set, point equality was also a primitive. — ibid. §2
- Gupta's thesis showed that Ax.6 and Ax.18 can be derived from the remaining axioms, "and actually in the case of Ax.18 it is rather involved". — ibid. §2
- Independence status in FG(2): Ax.2, Ax.4, Ax.5, Ax.8⁽²⁾, Ax.9⁽²⁾, Ax.10₁, Ax.11 and Ax.15 are independent. "The independence of the three remaining axioms Ax.1, Ax.3, and Ax.7₁ is still an open question." Szczerba proved Ax.7₁ independent once Ax.10₁ is replaced by Ax.10₂. — ibid. §5
  - Names: Ax.1 is reflexivity of equidistance, Ax.3 identity of equidistance, Ax.7₁ the inner Pasch axiom.
- EG(2) with the schema is trivially *not* independent, because instances of a schema can be logically equivalent. Any independent replacement of the schema must be infinite. — ibid. §5
- Models: EG(n) has the n-dimensional Cartesian spaces over real closed fields. CG(n) (schema replaced by the Circle Axiom) has the spaces over **Euclidean ordered fields**, and is the theory of straightedge-and-compass constructions. PG(n) (no continuity) has the spaces over Pythagorean ordered fields. FG(n) has the unique model ℝⁿ. — ibid. footnote 5
- Pieri [1908]: "the axiom set of Pieri for the full 3-dimensional Euclidean geometry… consists of 24 axioms. The only primitive notion used in the system is the ternary relation which holds among points a, b, c if, and only if, b and c are equidistant from a." Tarski notes that one of Pieri's axioms alone (XXI, a Pasch form) is nearly as long as all of FG(3). — ibid. §3
- B is definable from ≡: B(xyz) ↔ ∀u (ux ≤ xy ∧ uz ≤ zy → u = y), "essentially due to Pieri". So ≡ alone suffices, but such an axiom set "would be rather involved and unnatural". Other single primitives that suffice include xy ≤ zu and xy ≤ yz. — ibid. §5
- Tarski's reason for choosing these primitives: "the former represents the affine, the latter the metric, aspect of geometry". Veblen used the same two notions. — ibid. §3
- Pieri's memoir is translated in Marchisotto & Smith, *The Legacy of Mario Pieri in Geometry and Arithmetic* (Birkhäuser 2007), ch. 3 — [Smith's book pages](https://smith-at-sfsu.net/Documents/PieriBook/Volume1/Chapter3/Chapter3.htm) (VERIFIED secondary via search snippet)
- Hilbert 1899 primitives: points, lines, planes; incidence, betweenness, congruence; second-order completeness. — UNVERIFIED

### Inferences
- The **two-relation split (affine betweenness / metric equidistance)** is the cleanest precedent for the DSL's core relational vocabulary. In practice the core needs incidence/order (affine) and distance (metric). Angle is derivable from distance among points, but it is convenient to keep it.
- Single-primitive systems (Pieri, ≡ only) show minimality is achievable but costs readability. This is direct support for the core/intent split: a minimal core is for proofs and checking, and humans write the intent layer.
- **Decidability mostly does not matter operationally for CAD.** Tarski-style decision procedures, and their practical heir cylindrical algebraic decomposition, are doubly exponential. CAD sketches are solved numerically or constructively, not by deciding sentences. What matters is the *model class*: if the core only allows ruler-and-compass steps (CG), every solution is in a Euclidean field, and closed-form quadratic solving suffices. This matches Owen's solver class (§3).

### Gaps
- Hilbert's axioms were not checked against the Grundlagen.
- I did not read Gupta's thesis or Pieri's memoir directly. Their content is taken from Tarski & Givant's account.

---

## 2. Construction minimality: Mohr–Mascheroni, Poncelet–Steiner

### Takeaway
Both results are confirmed (secondary sources). They show that ruler-and-compass constructibility is robust to the choice of tools: compass alone, or straightedge plus one fixed circle with its center, reach the same points. This is inspiration only for a CAD DSL. The useful fact is the field-theoretic one from §1: ruler-and-compass equals Euclidean fields, equals solving only quadratics.

### Cited findings
- Mohr 1672, *Euclides Danicus* (Amsterdam: J. van Velsen). Mascheroni 1797, *La Geometria del Compasso* (Pavia). Hjelmslev, Matematisk Tidsskrift B (1928) 1–7, revived Mohr's priority. A line counts as constructed when two of its points are. — [Wikipedia: Mohr–Mascheroni](https://en.wikipedia.org/wiki/Mohr%E2%80%93Mascheroni_theorem) (VERIFIED secondary)
- Poncelet–Steiner: "whatever can be constructed by straightedge and compass together can be constructed by straightedge alone", given one circle and its centre. The centre cannot be dropped (Hilbert). Steiner 1833, *Die geometrischen Constructionen, ausgeführt mittelst der geraden Linie und eines festen Kreises*, Berlin: Dümmler. — [Wikipedia: Poncelet–Steiner](https://en.wikipedia.org/wiki/Poncelet%E2%80%93Steiner_theorem) (VERIFIED secondary)
- Tarski & Givant: straightedge-and-compass geometry has the finite axiomatization CG(n) (EG(n) with the Circle Axiom in place of the schema). — [Tarski & Givant 1999](https://www.math.ucla.edu/~asl/bsl/0502/0502-002.ps) (VERIFIED)

### Inferences
- **Mascheroni's method relies mainly on reflections** of points in lines (per Wikipedia). That links naturally to §4: reflections are a natural generating operation for constructions as well as transforms.
- The "small core, provably expressive" story should cite CG(n) and Owen's completeness result, not Mohr–Mascheroni.

### Gaps
- Primary texts (Mohr, Mascheroni, Steiner, Hjelmslev) were not seen.

---

## 3. Rigidity theory and geometric constraint solving

### Takeaway
- In **2D**, DOF counting with the Laman subgraph condition exactly characterizes generic minimal rigidity for distance (bar-joint) constraints. That makes it a sound, cheap, structural well-constrainedness check.
- In **3D** point-distance systems, counting is only necessary. It can be fooled (double banana), and no combinatorial characterization is known.
- For **body-based** 3D constraint systems, which is how CAD assemblies are modeled, combinatorial characterizations exist: body-bar (Tay), body-hinge (Katoh–Tanigawa), and body-and-cad for 20 of 21 constraint types (Lee-St.John & Sidman).
- Production solvers combine graph decomposition with numeric solving. Each also has to pick one root out of exponentially many solutions ("root identification").

### Cited findings — rigidity
- Laman graphs: n vertices, 2n − 3 edges, every k-vertex subgraph ≤ 2k − 3 edges. Laman 1970, J. Eng. Math. 4(4):331–340, doi:10.1007/BF01534980. The characterization "had already been discovered in 1927 by Hilda Geiringer" (Pollaczek-Geiringer, ZAMM 7(1):58–72, doi:10.1002/zamm.19270070107). — [Wikipedia: Laman graph](https://en.wikipedia.org/wiki/Laman_graph) (VERIFIED secondary)
- In 3D, Maxwell counting is necessary but not sufficient. The double banana, two K5−e graphs sharing a non-edge pair, satisfies counting but is flexible. Several surveys call 3D characterization the biggest open problem in rigidity theory. — [Sitharam & Zhou / "Nucleation-free 3D rigidity" arXiv:1311.4859](https://arxiv.org/pdf/1311.4859); [Nixon & Ross, "One brick at a time" arXiv:1203.6623](https://arxiv.org/pdf/1203.6623) (VERIFIED secondary via search snippets)
- Dewar 2026 gives a counterexample to the converse of Baranyai's recently proposed necessary condition for 3-rigidity. — [arXiv:2601.19460](https://arxiv.org/abs/2601.19460) (VERIFIED abstract; a preprint, not peer-reviewed as far as I could tell)
- Katoh & Tanigawa, "A Proof of the Molecular Conjecture", DCG 45(4):647–700 (2011), doi:10.1007/s00454-011-9348-6. A graph is realizable as an infinitesimally rigid body-hinge framework in ℝᵈ iff it is realizable as a rigid panel-hinge framework. Conjecture by Tay & Whiteley 1984. 2D by Jackson & Jordán. — [Springer PDF](https://link.springer.com/content/pdf/10.1007/s00454-011-9348-6.pdf), [arXiv:0902.0236](https://arxiv.org/abs/0902.0236) (VERIFIED secondary via search)
- Lee-St.John & Sidman, "Combinatorics and the Rigidity of CAD Systems" (SPM'12; CAD special issue). They characterize generic minimal rigidity of **body-and-cad** frameworks for 20 of 21 CAD constraint types (all except point–point coincidence), via edge-disjoint spanning-tree partitions. It is "a basis for deterministic rigidity algorithms" without numerics. — [arXiv:1210.0451](https://arxiv.org/abs/1210.0451) (VERIFIED abstract)

### Cited findings — constraint solvers (VERIFIED from Bouma et al. TR CSD-TR-93-054 unless noted)
- **Owen 1991.** "a graph-constructive solver in which the constraint graph is analyzed for triconnected components… This procedure is recursive". It handles only "constraint configurations… that can be solved using ruler-and-compass construction steps. Algebraically, this is equivalent to solving only quadratic equations." Owen gives "a proof… that the solver is complete for ruler-and-compass constructible point configurations with prescribed distances that are algebraically independent." "DCM is a commercial constraint solver using this method." — [Bouma et al. 1993 TR](https://docs.lib.purdue.edu/cstech/1068)
- **Bouma et al.**
  - Entities: points, lines, circles, segments, arcs.
  - Constraints: distance, angle, parallelism, incidence, perpendicularity, tangency, concentricity, collinearity, radius.
  - The front end normalizes everything into "a normal form in which only distance and angle constraints are allowed… incidence constraints are translated to zero-distance constraints". Tangency becomes the distance from the circle centre to the line.
  - Their solver works bottom-up: it builds clusters, then merges them by rules (two clusters sharing two elements, or three clusters pairwise sharing one).
  - Neither their basic algorithm nor Owen's solves *all* ruler-and-compass configurations.
- **Root identification.** "a well-constrained geometric constraint problem has an exponential number of solutions." Choosing one is "the root identification problem". Their remedies are three approaches (moving elements, adding constraints, solver dialogue) plus hierarchical structuring of the constraint problem. The ambiguity "has severe consequences on the problem of communicating a generic design based on well-constrained sketches… more needs to be communicated." Existing solvers infer the intended root from the topology and coordinates of the initial sketch.
- Fudos & Hoffmann 1997, ACM TOG 16(2):179–216, doi:10.1145/248210.248223. Two-phase method: analysis of the constraint graph, then construction; handles well-, over- and under-constrained systems. — [Purdue record](https://cs.purdue.edu/cgvlab/www/publications/fudos1997graph), [DBLP](https://dblp.org/rec/journals/tog/FudosH97) (VERIFIED secondary)
- Hoffmann, Lomonosov & Sitharam 2001, decomposition–recombination (DR) planners. Part I: JSC 31(4):367–408. Part II: JSC 31(4):409–427, doi:10.1006/jsco.2000.0403. — [Purdue PDF](https://www.cs.purdue.edu/cgvlab/papers/cmh/decompJSC01b.pdf) (VERIFIED secondary)
- Fudos, Hoffmann & Joan-Arinyo (arXiv:1608.05205; chapter in the CRC Handbook of Geometric Constraint Systems Principles):
  - "a good solver may miss solutions that exist but should never report a solution that doesn't".
  - "constraint solvers used in MCAD took a quantum leap with the work by Owen". — [arXiv](https://arxiv.org/abs/1608.05205) (VERIFIED abstract/snippet)
- **SolveSpace.** Constraints are "represented as equations in a symbolic algebra system… solved numerically, by a modified Newton's method", with forward substitution for trivial equations. "If the sketch is not fully constrained, then the Jacobian is solved in a least squares sense." The initial sketch position picks among multiple solutions. — [solvespace.com/tech.pl](https://solvespace.com/tech.pl) (VERIFIED)
- **FreeCAD planegcs** (source code):
  - Algorithms: BFGS, LevenbergMarquardt, DogLeg.
  - QR decomposition of the transposed Jacobian (Eigen FullPivHouseholderQR or SparseQR) yields `dofs`, `redundantTags`, `conflictingTags` and `partiallyRedundantTags`. — [GCS.h](https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/Sketcher/App/planegcs/GCS.h) (VERIFIED)
- **D-Cubed.**
  - Siemens says 2D DCM is the most widely adopted 2D constraint solver; 3D DCM handles assemblies and kinematics.
  - A Siemens blog lists Onshape as a licensee. — [Siemens 2D DCM](https://www.siemens.com/en-us/products/plm-components/d-cubed/2d-dcm/), [PLM Components blog](https://blogs.sw.siemens.com/plm-components/geometric-constraint-solving-1-introduction/) (VERIFIED secondary; vendor claims)

### Inferences
- **DOF counting as a check.**
  - 2D sketches: Laman-style counting on a constraint graph is a sound *generic* well-constrainedness test for point/distance systems. Each entity contributes its DOF and each constraint its equation count.
  - It can still pass on non-generic (special-position) configurations. So pair it with a numeric Jacobian-rank check at the actual values, as planegcs does with QR.
  - 3D: counting alone is unreliable for point-distance systems. But if 3D constraints are modeled body-based (features and parts as rigid bodies), there is a sound combinatorial theory (body-and-cad).
- **Determinism hinges on root identification.** A deterministic compiler cannot rely on "near the initial sketch" heuristics unless the initial positions are part of the source. Options:
  - (a) Restrict the core to *constructive* sequences, where each step is a ruler-and-compass placement with an explicit branch selector (e.g. `side=left`, `orientation=ccw`). Every root is then named in the source.
  - (b) Keep declarative constraints, but require chirality/orientation tags and solve numerically from a deterministic seed.
  - Option (a) matches Owen's and Fudos–Hoffmann's construction plans and makes the core "provably grounded" in CG(n).
- **Minimal relational vocabulary for sketches.** Bouma et al. show the whole common CAD constraint vocabulary normalizes to **distance + angle** (incidence = zero distance; tangency = centre-to-line distance equal to radius; concentric = zero distance between centres), plus orientation/side to select roots. This is the CAD analogue of Tarski's B + ≡: angle stands in for affine direction, and betweenness/orientation is needed for root selection. Parallel/perpendicular are angle 0/90°. Midpoint and symmetric belong in the intent layer and lower to distance or reflection constraints.

### Gaps
- Owen 1991's DOI and full text were not seen.
- Kramer 1992 and the Jermann et al. survey were not checked.
- The Handbook's exact bibliographic data is unconfirmed.
- I found no first-party Onshape statement on its sketch solver, and no D-Cubed technical documentation of its algorithms beyond Bouma et al.'s inference.

---

## 4. Transforms: Cartan–Dieudonné and geometric algebra

### Takeaway
Reflections generate the orthogonal group: at most n reflections in a nondegenerate n-dimensional space, characteristic ≠ 2. A short argument extends this to "all Euclidean isometries of ℝⁿ are products of at most n+1 hyperplane reflections". Projective geometric algebra represents every Euclidean isometry, proper or improper, as a sandwich product with a versor, which is literally a product of reflections. So "reflection as the single transform generator" is mathematically sound and has an algebraic implementation. I found no evidence that any mainstream CAD kernel or constraint solver uses GA internally.

### Cited findings
- "every element of the orthogonal group O(V, b) is a composition of at most n reflections", for an n-dimensional non-degenerate symmetric bilinear space over a field of characteristic ≠ 2. In 3D: one reflection (a mirror), two reflections (a rotation), three reflections (an improper rotation). — [Wikipedia: Cartan–Dieudonné](https://en.wikipedia.org/wiki/Cartan%E2%80%93Dieudonn%C3%A9_theorem) (VERIFIED secondary; cites Gallier 2001, Garling 2011, Lam 2005)
- Gunn 2011, "On the Homogeneous Model of Euclidean Geometry" (extended AGACSE 2010 paper). It uses the degenerate Clifford algebra P(ℝ*ₙ,₀,₁), and "versor (sandwich) operators provide all euclidean isometries, both direct and indirect". The spin group, a double cover of the direct Euclidean group, sits in the even subalgebra. — [arXiv:1101.4542](https://arxiv.org/abs/1101.4542) (VERIFIED abstract)
- Gunn 2016, "Geometric algebras for euclidean geometry", Adv. Appl. Clifford Algebras, doi:10.1007/s00006-016-0647-0. It argues Euclidean PGA is the smallest structure-preserving Euclidean GA and compares it with CGA on kinematics and rigid-body criteria. — [arXiv:1411.6502](https://arxiv.org/abs/1411.6502) (VERIFIED abstract)

### Inference: proof sketch of the n+1 corollary (my own argument, not sourced)
Let f be an isometry of ℝⁿ. If f fixes a point p, then f is linear about p, so it is a product of at most n reflections in hyperplanes through p. Otherwise, let σ be the reflection in the perpendicular-bisector hyperplane of p and f(p). Then σ∘f fixes p, so f = σ∘(σ∘f) uses at most n+1 reflections. A pure translation uses 2 reflections, in parallel hyperplanes.

### Inferences for the DSL
- **One transform primitive.** Take `reflect(hyperplane)` as the core transform. Then:
  - `mirror` is one reflection.
  - Rotation about an axis (3D) or point (2D) is two reflections in planes or lines through it, at half the angle.
  - Translation is two reflections in parallel planes, at half the distance.
  - Glide and screw motions are three and four reflections.
  - `pattern` (linear or circular) is the group generated by one such composite, applied k times.
- The lowering keeps intent: a circular pattern is "the cyclic group generated by rotation R", and R lowers to a reflection pair. Equality of transforms becomes equality of versors up to sign, which is canonical and useful for deduplication.
- **Practical caveat.** OpenCascade (gp_Trsf), build123d/CadQuery and FeatureScript all expose matrix or rigid transforms plus native mirror/pattern features. The DSL would *compile* reflection words into those, ideally recognizing pairs to emit native rotate/translate/pattern features. Emitting a long chain of mirrors would hurt B-rep feature trees and persistent naming.
- PGA could also serve as a uniform *entity* representation: points, lines and planes as blades, with meet and join for incidence. Whether that is worth it over plain vectors and matrices is a design choice. The evidence found here is for its elegance and its kinematics use (Gunn), not for any use in CAD kernels.

### Gaps
- Primary Cartan (1938) and Dieudonné texts were not seen.
- The "n+1" bound has no citation; Gallier 2001 likely states it but was not checked.
- Hestenes, Dorst–Fontijne–Mann 2007, Hestenes–Li–Rockwood 2001 and Gunn & De Keninck's "May the Forque Be with You" were not checked.
- I searched for no evidence of GA in commercial kernels or constraint solvers, and found none. Absence is unconfirmed.

---

## Implications for a DSL core (synthesis)

1. **Relational core for sketches.** The core is points, plus one metric relation (distance) and one directional relation (angle). Root selection uses an orientation/side predicate, which is the analogue of Tarski's betweenness. Everything else in common CAD vocabularies normalizes to these, as Bouma et al. do. This mirrors Tarski's affine/metric split. A single primitive (Pieri) is possible but not worth the readability cost.
2. **Target CG(n), not EG(n).** Restrict core constructions to ruler-and-compass steps (quadratic solves). That gives closed-form, exactly reproducible solutions and Owen-style completeness for that class. Non-quadratic cases (some circle–circle–line chains, splines) go through an explicitly marked numeric escape hatch.
3. **Decidability is not a feature to advertise.** It is a theoretical comfort with no practical procedure (doubly exponential). Advertise *constructibility* and *well-constrainedness* instead.
4. **Well-constrainedness check.**
   - 2D: structural Laman/DOF counting at compile time, plus a numeric Jacobian-rank and redundancy check at evaluation, as planegcs does.
   - 3D: use body-based models, whose combinatorics are solved. Do not rely on point-distance counting.
5. **Determinism needs explicit root selection.** Every quadratic step carries a branch tag in the core. Intent-layer forms like `symmetric`, `tangent(side=…)` and `concentric` fix these tags. Without that, compiled output depends on initial guesses (Bouma et al.: "more needs to be communicated").
6. **Transforms.** `reflect` is the sole core transform generator (Cartan–Dieudonné). `mirror`, `rotate`, `translate`, `pattern` and `symmetric` are intent forms that lower to reflection words, and are canonically compared as PGA versors. When compiling to OpenCascade or FeatureScript, recognize them and re-emit native features.

---

## Reference list

**VERIFIED (text or abstract seen)**
- Tarski, A. & Givant, S. (1999). Tarski's system of geometry. *Bulletin of Symbolic Logic* 5(2):175–214. doi:10.2307/421089. PS: https://www.math.ucla.edu/~asl/bsl/0502/0502-002.ps
  - Bibliography entries VERIFIED via this paper:
  - Tarski, A. (1948/1951). *A decision method for elementary algebra and geometry*. RAND R-109; 2nd rev. ed. University of California Press, 1951.
  - Tarski, A. (1959). What is elementary geometry? In Henkin, Suppes & Tarski (eds.), *The Axiomatic Method*, North-Holland, pp. 16–29.
  - Tarski, A. (1967). *The completeness of elementary algebra and geometry*. Institut Blaise Pascal, Paris.
  - Gupta, H. N. (1965). *Contributions to the axiomatic foundations of geometry*. PhD dissertation, UC Berkeley, 407 pp.
  - Pieri, M. (1908). La geometria elementare istituita sulle nozioni 'punto' e 'sfera'. *Memorie di Matematica e di Fisica della Società Italiana delle Scienze* 15:345–450.
  - Schwabhäuser, W., Szmielew, W. & Tarski, A. (1983). *Metamathematische Methoden in der Geometrie*. Springer.
- Bouma, W., Fudos, I., Hoffmann, C. M., Cai, J. & Paige, R. (1993). A Geometric Constraint Solver. Purdue CS Tech. Rep. CSD-TR-93-054. https://docs.lib.purdue.edu/cstech/1068 (Journal version: *Computer-Aided Design* 27(6):487–501, 1995. UNVERIFIED page numbers.)
- Owen, J. C. (1991). Algebraic solution for geometry from dimensional constraints. *Proc. ACM Symp. on Foundations of Solid Modeling* (SMA '91), Austin TX, pp. 397–407. Citation verified via Bouma et al. DOI not confirmed.
- Dewar, S. (2026). A counter-example to Baranyai's combinatorial characterisation for 3-rigidity. arXiv:2601.19460. https://arxiv.org/abs/2601.19460
- Lee-St.John, A. & Sidman, J. (2012/13). Combinatorics and the rigidity of CAD systems. SPM '12 / *Computer-Aided Design* special issue. arXiv:1210.0451. https://arxiv.org/abs/1210.0451
- Fudos, I., Hoffmann, C. M. & Joan-Arinyo, R. (2016/17). Tree-decomposable and underconstrained geometric constraint problems. arXiv:1608.05205; chapter in Sitharam, St. John & Sidman (eds.), *Handbook of Geometric Constraint Systems Principles*, CRC Press. https://arxiv.org/abs/1608.05205
- Gunn, C. (2011). On the homogeneous model of Euclidean geometry. In *Guide to Geometric Algebra in Practice* (AGACSE 2010), Springer. arXiv:1101.4542. https://arxiv.org/abs/1101.4542
- Gunn, C. (2016). Geometric algebras for Euclidean geometry. *Advances in Applied Clifford Algebras*. doi:10.1007/s00006-016-0647-0. arXiv:1411.6502.
- SolveSpace technical description. https://solvespace.com/tech.pl
- FreeCAD planegcs source, `GCS.h`. https://github.com/FreeCAD/FreeCAD/blob/main/src/Mod/Sketcher/App/planegcs/GCS.h

**VERIFIED (secondary only)**
- Laman, G. (1970). On graphs and rigidity of plane skeletal structures. *J. Engineering Mathematics* 4(4):331–340. doi:10.1007/BF01534980.
- Pollaczek-Geiringer, H. (1927). Über die Gliederung ebener Fachwerke. *ZAMM* 7(1):58–72. doi:10.1002/zamm.19270070107. (Title from background; volume and pages via Wikipedia.)
- Katoh, N. & Tanigawa, S. (2011). A proof of the molecular conjecture. *Discrete & Computational Geometry* 45(4):647–700. doi:10.1007/s00454-011-9348-6. arXiv:0902.0236.
- Fudos, I. & Hoffmann, C. M. (1997). A graph-constructive approach to solving systems of geometric constraints. *ACM TOG* 16(2):179–216. doi:10.1145/248210.248223.
- Hoffmann, C. M., Lomonosov, A. & Sitharam, M. (2001). Decomposition plans for geometric constraint systems, Part I: Performance measures for CAD. *J. Symbolic Computation* 31(4):367–408. Part II: New algorithms, 31(4):409–427. doi:10.1006/jsco.2000.0403.
- Mohr, G. (1672). *Euclides Danicus*. Amsterdam: J. van Velsen.
- Mascheroni, L. (1797). *La Geometria del Compasso*. Pavia: P. Galeazzi.
- Hjelmslev, J. (1928). Matematisk Tidsskrift B, pp. 1–7.
- Steiner, J. (1833). *Die geometrischen Constructionen, ausgeführt mittelst der geraden Linie und eines festen Kreises*. Berlin: F. Dümmler.
- Marchisotto, E. A. & Smith, J. T. (2007). *The Legacy of Mario Pieri in Geometry and Arithmetic*. Birkhäuser. (ch. 3: translation of Pieri 1908)
- Siemens D-Cubed 2D DCM product page; PLM Components blog (licensee list incl. Onshape).
- Wikipedia: Tarski's axioms; Laman graph; Cartan–Dieudonné theorem; Mohr–Mascheroni theorem; Poncelet–Steiner theorem.

**UNVERIFIED (background only)**
- Hilbert, D. (1899). *Grundlagen der Geometrie*. Teubner.
- Kramer, G. A. (1992). *Solving Geometric Constraint Systems: A Case Study in Kinematics*. MIT Press.
- Jermann, C., Trombettoni, G., Neveu, B. & Mathis, P. Decomposition of geometric constraint systems: a survey. *Int. J. Computational Geometry & Applications* 16(5–6), 2006 (details unverified).
- Tay, T.-S. (1984). Rigidity of multigraphs I: linking rigid bodies in n-space. *J. Combinatorial Theory B* 36:95–112.
- Tay, T.-S. & Whiteley, W. (1984). Recent advances in the generic rigidity of structures. *Structural Topology* 9.
- Cartan, É. (1938). *Leçons sur la théorie des spineurs*. Hermann. Dieudonné, J. (1948). *Sur les groupes classiques*. Hermann.
- Gallier, J. (2001). *Geometric Methods and Applications*. Springer. (Likely source for the affine n+1 bound.)
- Hestenes, D. & Sobczyk, G. (1984). *Clifford Algebra to Geometric Calculus*. Reidel.
- Hestenes, D., Li, H. & Rockwood, A. (2001). New algebraic tools for classical geometry. In Sommer (ed.), *Geometric Computing with Clifford Algebras*, Springer.
- Dorst, L., Fontijne, D. & Mann, S. (2007). *Geometric Algebra for Computer Science*. Morgan Kaufmann.
- Gunn, C. & De Keninck, S. "May the Forque Be with You: Dynamics in PGA" (bivector.net).
- Sitharam, M., St. John, A. & Sidman, J. (eds.) (2018). *Handbook of Geometric Constraint Systems Principles*. CRC Press. Existence partially verified; year and ISBN unverified.

---

## Explicit list of unverified items
1. Hilbert's primitive notions and axiom groups.
2. Gupta's thesis content, seen only via Tarski & Givant. Pieri's memoir, seen only via Tarski & Givant and the Marchisotto–Smith listing.
3. Owen 1991 DOI and full text. The claim that DCM is *still* based on Owen's method today (Bouma et al. 1993 and Siemens marketing only).
4. Bouma et al. 1995 journal page numbers.
5. Kramer 1992; the Jermann et al. survey; the Handbook's exact title, year and ISBN.
6. Tay 1984 body-bar theorem citation details.
7. Whether Onshape's *sketcher* specifically runs D-Cubed 2D DCM. Only a vendor licensee list was seen.
8. Cartan 1938 / Dieudonné primary statements. The affine "≤ n+1 reflections" corollary has a proof sketch above but no citation.
9. Hestenes, Dorst et al., Hestenes–Li–Rockwood, "May the Forque Be with You".
10. Whether any CAD kernel or constraint solver uses geometric algebra internally. Not searched; none known.
11. Baranyai's 3D rigidity condition: seen only via Dewar's abstract; the original paper was not identified.

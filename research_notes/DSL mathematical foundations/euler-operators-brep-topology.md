# Euler operators and B-rep topology

*Research pass 2026-11-15. This is the deepest of four foundation dives. Scope: explore-further.md item 1, main focus.*

**How to read the tags.**
- **VERIFIED**: I read the statement myself in the cited source (full text, abstract, or official doc page).
- **VERIFIED (secondary)**: I read it in a reliable secondary source, such as MIT lecture notes or a bibliographic database, but not in the original.
- **COMPUTED**: I checked it by my own calculation; the method is shown.
- **UNVERIFIED**: background knowledge, or a search-snippet claim I could not open.

Several key primary sources were paywalled or blocked: Mäntylä 1984 (ScienceDirect 403), Eastman & Weiler 1979 (CMU KiltHub and the Ohio State copy both 403), Mäntylä's 1988 book (no legal full text), and Braid–Hillyard–Stroud (no full text). The exact wording of Mäntylä's completeness theorem is therefore **UNVERIFIED**. See the list at the end.

---

## Summary

- **Origin.** Baumgart introduced the winged-edge structure and the "Euler primitives" in 1972 (Stanford AIM-179). His Euler primitives preserve "F-E+V = 2*B-2*H" (B = bodies, H = handles). They include MKBFV, MEV-style MKEV, MKFE, ESPLIT, KLFE, KLEV, KLVE, GLUE and UNGLUE. **VERIFIED** from Baumgart's own SAIL files.
- **The formula.** The modern Euler–Poincaré formula for manifold solids with inner loops (rings) is V − E + F − R = 2(S − H), where H is genus. Equivalent forms are V − E + F − (L − F) = 2(S − H), with L = all loops, and V − E + F = R + 2(S − H). **VERIFIED (secondary)** in Patrikalakis's MIT notes. The notes also stress that the formula is "a necessary but not sufficient condition for validity of a B-rep" (**VERIFIED (secondary)**).
- **Why five operators.** The formula has six counts (V, E, F, H, R, S) tied by one linear equation, so the space of count-changes is 5-dimensional. I checked that the standard Mäntylä set {MVFS, MEV, MEF, KEMR, KFMRH} is linearly independent and is in fact a basis of the *integer* solution lattice. Every count-change consistent with the formula is therefore an integer combination of these five. **COMPUTED.**
- **"Five" depends on the parametrization.** Weiler's set as taught at MIT is also five (MSFLV, MEV, ME, GLUE, KE), but its operators are context-dependent: ME behaves as mefl, mekl or meksfl depending on where it is applied. **VERIFIED (secondary).**
- **Completeness.** The claim that Euler operators are complete for manifold solids is attributed to Mäntylä (1984, CVGIP). Bibliographic data **VERIFIED**: DOI 10.1016/0734-189X(84)90129-4; zbMATH keywords include "objects bounded by 2-manifold surfaces". The exact theorem text is **UNVERIFIED** (paywalled).
- **Non-manifold topology.** The manifold formula fails here. The MIT notes say: "The Euler-Poincare formula is no longer valid for NTM topologies". Weiler defined a minimal sufficient set of non-manifold operators: M-MR, M-SV, M-E, M-F, K-E. **VERIFIED (secondary).**
- **Kernels.** OpenCascade builds topology (TopoDS/TopAbs) with no Euler-operator layer that I could find. It validates with `BRepCheck_Analyzer`, which separates topological checks from geometric ones (`GeomControls`) and checks e.g. self-intersecting wires. **VERIFIED** from the official refman. Parasolid exposes `PK_EDGE_euler_*` and `PK_FACE_euler_*` functions. **VERIFIED (secondary)**, via a 2009 teaching deck seen only in a search snippet. I found no ACIS "Euler operations" documentation.
- **Machine learning.** No ML B-rep generator I found uses Euler-operator sequences as tokens. SolidGen (2022/23) predicts vertices, then edges, then faces with pointer networks over an "indexed B-rep". BrepGen (2024) uses a tree with duplicated nodes that are merged afterwards. **VERIFIED** (abstracts). Euler-operator tokenization looks like an open niche.

## Verdict on the prior claim

> Prior claim: "Euler operators (Braid, Hillyard & Stroud 1978; Mäntylä 1988) are five independent operators complete for valid manifold topology via the Euler–Poincaré formula."

**Mostly right, but it needs four corrections.**

1. **Attribution and dates are off.**
   - Euler operators originate with **Baumgart (1972)**. He called them "Euler primitives" and said they were "inspired by Coxeter's proof of Euler's formula" (**VERIFIED**).
   - Braid, Hillyard & Stroud's *Stepwise construction of polyhedra in geometric modelling* is usually cited as **1980**, in K. W. Brodlie (ed.), *Mathematical Methods in Computer Graphics and Design*, Academic Press, pp. 123–141. **VERIFIED (secondary)**, from a Springer reference list. A 1978 date probably refers to an earlier CAD Group, Cambridge report (**UNVERIFIED**).
   - The completeness *result* is **Mäntylä 1984** (CVGIP), not the 1988 book. The book is the textbook exposition (with the GWB / half-edge implementation).
2. **"Five independent" is right for counts only.** The five operators are independent and span the 5-dimensional lattice of count-changes allowed by V − E + F − R = 2(S − H) (**COMPUTED**). This is a fact about *counts*. Different authors pick different bases, and an operator's count effect can depend on context (Weiler's ME).
3. **"Complete for valid manifold topology" is narrower than it sounds.** As usually reported, the theorem says every topologically valid polyhedron in the class (closed, orientable 2-manifold boundaries, i.e. Mäntylä's "plane models") can be built by a finite sequence of Euler operators from the initial MVFS. Soundness also holds: every applicable sequence yields a member of the class. It does **not** follow from the Euler–Poincaré formula alone, which is necessary but not sufficient for validity. The proof is a constructive argument on the topological structure (**UNVERIFIED**; paper not accessed).
4. **Topology only.** The guarantee is combinatorial. It says nothing about geometric validity: self-intersection, faces lying on their surfaces, edge/vertex tolerance consistency.

**Corrected statement for our docs:**

> Euler operators, introduced by Baumgart (1972) and systematized by Braid, Hillyard & Stroud (1980), Eastman & Weiler (1979) and Mäntylä (1984; book 1988), are local topological operators that keep the Euler–Poincaré relation V − E + F − R = 2(S − H) invariant. A standard basis is MVFS, MEV, MEF, KEMR and KFMRH, together with their inverses. These five are linearly independent and span the 5-dimensional lattice of count-changes the relation allows. Mäntylä (1984) showed the operators are sound and complete for closed, orientable, 2-manifold boundary topologies: every such topology can be built (and torn down) by a finite operator sequence. The guarantee is purely topological. Geometric validity must be checked separately, and non-manifold models need a different formula and operator set (Weiler 1986; Masuda 1993; Yamaguchi & Kimura 1995).

---

## Q1. The Euler–Poincaré formula

### Takeaway
For a closed, orientable, 2-manifold B-rep with inner loops, the formula is V − E + F − R = 2(S − H). Some authors write H as G. The formula is necessary, not sufficient, for topological validity.

### Cited findings
- **Single shell** (Patrikalakis, MIT 2.158J notes, §14.6.3): "V − E + F − Li = 2(1 − G)". **VERIFIED (secondary).**
  - Li = "Number of interior loops".
  - G = "Genus, the number of closed paths on a surface which do not separate the surface into more than one region. Or, genus is the number of handles to be added to a sphere to make it homeomorphic to the object." — [Patrikalakis 2003](https://ocw.mit.edu/courses/2-158j-computational-geometry-spring-2003/f04f923ac8e0af56d19095b4de8dea3c_lecnotes14_fixed.pdf)
- **Alternative form:** "V − E + 2F − L = 2(1 − G)", using L = Lp + Li and Lp = F (one peripheral loop per face). This is the same as the brief's V − E + F − (L − F) = 2(S − H). **VERIFIED (secondary)**, same source.
- **Multiple shells:** "For multiple shelled objects (objects with cavities), the Euler equation becomes V − E + F − Li = 2(S − G)". **VERIFIED (secondary)**, same source.
- **Not sufficient:** "Euler equation is a necessary but not sufficient condition for validity of a B-rep." The notes add further conditions, e.g. all counts ≥ 0, and "If V = E = F = Li = 0 ⇒ S = 0, G = 0". **VERIFIED (secondary)**, same source.
- **Why orientability matters:** it "guarantees that the interior of a solid volume is distinguishable from its exterior". **VERIFIED (secondary)**, same source.
- **Variant form** on Wikipedia, credited to the Eastman lineage: "V – E + F = H + 2 * (S – G)", with H = holes in faces (rings). **VERIFIED (secondary)** — [Wikipedia](https://en.wikipedia.org/wiki/Euler_operator_(digital_geometry))
- **Baumgart's form** (bodies B, handles H; no rings): "F-E+V = 2*B-2*H". He defines handles as "well formed holes in a surface". **VERIFIED** — [Baumgart, SAIL EULER.5](https://www.saildart.org/EULER.5[OLD,BGB]); also in his 1975 NCC paper draft, "F-E+V=2*B-2*H between the numbers of bodies, faces, edges, vertices and handles" — [SAIL OUT[NCC,BGB]](https://www.saildart.org/OUT[NCC,BGB])

### History in brief
- Euler (1750s) gave V − E + F = 2 for convex polyhedra.
- Poincaré generalized it to the alternating sum of Betti numbers; for a closed orientable surface of genus g, χ = 2 − 2g.
- Solid-modelling forms add rings (R) and shells (S).

**UNVERIFIED** (standard mathematics; no primary source fetched).

### Inferences
- **Two names for "H".** Literature uses H for handles/genus (Baumgart, Mäntylä) and also for holes-in-faces (the Wikipedia/Eastman variant). Our docs should use explicit names: `genus`, `rings` (inner loops), `shells`.
- **What a manifold solid needs.** For OCCT (TopoDS), the applicable class is closed, orientable, 2-manifold shells. Non-manifold and open shells need other rules (Q5).

### Gaps
- I could not read the exact statement and variable names in Mäntylä's book (1988, ch. on Euler operators).

---

## Q2. Baumgart: winged edge and the first Euler operators

### Takeaway
Baumgart (1972) introduced both the winged-edge representation and a set of "Euler primitives" that preserve F − E + V = 2B − 2H. He did not use the term "Euler operators" in the documents I read. The make/kill naming pattern (MKBFV, MKEV, MKFE, KLFE, KLEV) is his.

### Cited findings
- **AIM-179 abstract**, *Winged Edge Polyhedron Representation*, Stanford AI Memo AIM-179 / STAN-CS-320, October 1972: "A winged edge polyhedron representation is stated and a set of primitives that preserve Euler's F-E+V=2 equation are explained." **VERIFIED** — [Stanford PURL](https://purl.stanford.edu/tz289cy2950)
- **"SUMMARY OF POLYHEDRON PRIMITIVES"** (Baumgart SAIL file, dated 1974-04-23; notes "under construction, Oct 1972") lists the Euler primitives:
  - MKBFV "make a body, face & vertex"
  - KLBFEV "kill a body & all its pieces"
  - MKEV "make edge & vertex"
  - MKFE "make face & edge"
  - ESPLIT "split an edge"
  - KLFE "kill face & edge leaving a face"
  - KLEV "kill edge & vertex leaving an edge"
  - KLVE "kill vertex & edge leaving a vertex"
  - GLUE "glue two faces together"
  - UNGLUE "unglue along a seam containing E"

  It says they "were inspired by Coxeter's proof of Euler's formula, section 10.3" (Coxeter, *Regular Polytopes*). It notes strict adherence to the Euler equation "would require only four primitives", and that Eulerian polyhedra "do not necessarily correspond to what we normally call a solid classical polyhedron". **VERIFIED** — [SAIL EULER.5[OLD,BGB]](https://www.saildart.org/EULER.5[OLD,BGB])
- **1975 NCC paper draft:**
  - The winged-edge structure is "the bedrock for the Euler primitives, which are an elegant set of subroutines for altering polyhedra … always maintaining the Euler relation".
  - It gives procedures ESPLIT, KLEV, MKFE(V1,FACE,V2) and KLFE.
  - It gives low-level node makers and killers (MKB/MKF/MKE/MKV, KLB/KLF/KLE/KLV).
  - It gives "wing mungers" (WING, INVERT, EVERT) and traversal (ECW/ECCW, VCW/VCCW, FCW/FCCW, OTHER, LINKED).

  **VERIFIED** — [SAIL OUT[NCC,BGB]](https://www.saildart.org/OUT[NCC,BGB])
- **Published 1975 paper:** B. G. Baumgart, "A polyhedron representation for computer vision", *AFIPS '75 National Computer Conference*, May 1975, pp. 589–596, DOI 10.1145/1499949.1500071. Bibliographic data **VERIFIED (secondary)** via search; the PDF was blocked (403).
- **Thesis:** Baumgart's 1974 Stanford PhD, *Geometric Modeling for Computer Vision* (AIM-249 / STAN-CS-74-463). **UNVERIFIED** (title seen in search; report numbers from memory).
- **Naming:** Wikipedia says the operators "are named by Baumgart … after the Euler–Poincaré characteristic". **VERIFIED (secondary)**. I did not see the literal phrase "Euler operator" in Baumgart's own texts.

### Inferences
- Baumgart's set is redundant and is not presented as a basis: it includes ESPLIT, KLVE, GLUE and UNGLUE. The "minimal basis" framing comes later (Braid et al., Eastman & Weiler, Mäntylä).
- Baumgart's GLUE/UNGLUE change genus and body count. They prefigure Mäntylä's KFMRH/MFKRH.

### Gaps
- I could not read the published AFIPS PDF or the thesis.

---

## Q3. Braid, Hillyard & Stroud: stepwise construction

### Takeaway
The paper is usually cited as Braid, I. C., Hillyard, R. C., Stroud, I. A. (1980), "Stepwise construction of polyhedra in geometric modelling", in K. W. Brodlie (ed.), *Mathematical Methods in Computer Graphics and Design*, Academic Press, London, pp. 123–141. I could not access its operator set.

### Cited findings
- **Citation** as above. **VERIFIED (secondary)**, from a reference list in a Springer chapter — [Springer ref](https://link.springer.com/chapter/10.1007/978-3-642-78291-6_1). Note: the editor's name is Brodlie; the search snippet misspelled it "Brodie".
- **Later book:** Ian Stroud's *Boundary Representation Modelling Techniques* (Springer, 2006) covers stepwise modelling and Euler operators at length. The Springer PDF was not accessible. **UNVERIFIED** beyond the title and chapter topic.

### Inferences / UNVERIFIED background
- The "1978" date likely comes from the preprint, presented at a 1978 IMA conference (**UNVERIFIED**).
- From memory: Braid et al. were the BUILD group (Cambridge CAD Group, later Shape Data → Romulus → Parasolid and ACIS lineage). They showed polyhedra can be built stepwise with operators that keep the Euler relation, using an operator set that includes rings (inner loops) and making the five-degrees-of-freedom argument explicit. **UNVERIFIED.**

### Gaps
- No full text of the paper. Exact operator names and the independence/completeness claims are unconfirmed.

---

## Q4. Mäntylä, Eastman & Weiler, Wilson, Chiyokura: completeness and the operator basis

### Takeaway
The key result is Mäntylä (1984). The basis {MVFS, MEV, MEF, KEMR, KFMRH} plus inverses is independent and spans the count lattice (COMPUTED). The paper's exact theorem wording is unverified.

### Cited findings
- **Mäntylä 1984 citation:** M. Mäntylä, "A note on the modeling space of Euler operators", *Computer Vision, Graphics, and Image Processing* 26(1):45–60, 1984. DOI [10.1016/0734-189X(84)90129-4](https://doi.org/10.1016/0734-189X(84)90129-4). zbMATH 0585.68085; keywords "modeling spaces for physical solid objects; objects bounded by 2-manifold surfaces". **VERIFIED** (bibliographic) — [MaRDI portal](https://portal.mardi4nfdi.de/wiki/Item:Q3709924); vol/pages from an arXiv reference list (secondary).
- **What the result says**, as reported secondhand: "It has been proved by Mantyla in 1984 that Euler operators form a complete set of modeling primitives for manifold solids", i.e. "every topologically valid polyhedron can be constructed from an initial polyhedron by a finite sequence of Euler operators". **VERIFIED (secondary)** — [C.-K. Shene, MTU course notes](https://pages.mtu.edu/~shene/COURSES/cs3621/NOTES/model/euler-op.html). I saw this as a search snippet; direct fetch failed on a certificate error.
- **Weiler's set** (MIT notes): "Five basic Euler operators presented below are sufficient to create any topology but others are also defined to add convenience": MSFLV, MEV, ME, GLUE, KE.
  - ME is context-dependent: mefl (+F +L +E), mekl (−L +E) or meksfl (−S −F −L +E).
  - GLUE is kflevmg (+1 genus) or kflevs (−1 shell).
  - These are "fairly low level operators" that "provide automatic topological integrity checking", and "Almost any other kind of commonly found modeling operator … can be built on top of the Euler operators, including parametric primitives and sweeps."

  **VERIFIED (secondary)** — [Patrikalakis 2003](https://ocw.mit.edu/courses/2-158j-computational-geometry-spring-2003/f04f923ac8e0af56d19095b4de8dea3c_lecnotes14_fixed.pdf)
- **Eastman & Weiler 1979**, "Geometric modeling using the Euler operators", Carnegie-Mellon University, Institute of Physical Planning (report DRC-15-2-79 / Res. Rep. 78; CMU CS repository paper 1587), May 1979.
  - The abstract (search snippet) says existing descriptions of the Euler operators lacked completeness and clear specification; the paper specifies them and implements them in GLIDE.
  - Basic operators (per Wikipedia's table credited to Eastman): MBFLV, MEV, MEFL, MEKL, KFLEVB, KFLEVMG.

  **VERIFIED (secondary).** Full text blocked (403). — [Wikipedia](https://en.wikipedia.org/wiki/Euler_operator_(digital_geometry)); [CMU KiltHub](https://kilthub.cmu.edu/articles/journal_contribution/Geometric_modeling_using_the_Euler_operators/6605963)
- **Wilson 1985:** P. R. Wilson, "Euler formulas and geometric modeling", *IEEE Computer Graphics and Applications* 5(8):45–60, August 1985. **VERIFIED (secondary)** (citation in the MIT notes); content not read.
- **Mäntylä 1988 book:** *An Introduction to Solid Modeling*, Computer Science Press, Rockville MD, ISBN 0-88175-108-1. **VERIFIED (secondary)** (citation); content not read.

### UNVERIFIED background on Mäntylä's formulation
- **Formula in the book:** v − e + f = 2(s − h) + r.
- **Operators (GWB/half-edge):** mvfs, mev, mef, kemr, kfmrh, with inverses kvfs, kev, kef, mekr, mfkrh. There are also "low-level" variants (lmev, lmef, …) and the "split-edge" and "join" utilities.
- **Mäntylä's book distinguishes:**
  - the "modeling space" of *plane models*: abstract topological polyhedra, i.e. graphs embedded on closed orientable surfaces, with faces possibly multiply connected;
  - from "realizable" solids, where geometry is added.
- **The 1984 note's content:**
  - (i) the Euler operators are **sound**: they map plane models to plane models;
  - (ii) they are **complete**: any plane model can be reduced to the empty model by a finite sequence of operators (e.g. via kef/kev/kemr…), and hence built in reverse;
  - (iii) the five operators are **independent** in the sense of the count vectors.
- **GWB:** M. Mäntylä & R. Sulonen, "GWB: A solid modeler with Euler operators", *IEEE Computer Graphics and Applications* 2(7):17–31, 1982.
- **Chiyokura:** H. Chiyokura, *Solid Modelling with DESIGNBASE: Theory and Implementation*, Addison-Wesley, 1988. Euler operators underpin DESIGNBASE. Its history-based undo/redo is implemented by recording and inverting the primitive operator sequence, an early "operation history = Euler-op log" design.

### Independence argument (COMPUTED)
- Coordinates: (V, E, F, H, R, S).
- Constraint: V − E + F − R − 2S + 2H = 0, i.e. normal vector c = (1, −1, 1, 2, −1, −2).
- **Operator vectors:**
  - MVFS (1,0,1,0,0,1)
  - MEV (1,1,0,0,0,0)
  - MEF (0,1,1,0,0,0)
  - KEMR (0,−1,0,0,1,0)
  - KFMRH (0,0,−1,1,1,0)
- Each has dot product 0 with c, so each preserves the relation.
- The six 5×5 minors are (−2, 1, 2, −1, −1, −1). These are ±c entries (Plücker coordinates of the span), with gcd 1.
- **Hence:**
  - (a) rank 5, so the five are linearly independent;
  - (b) they span the full 5-dimensional solution space;
  - (c) they form a **basis of the integer lattice**. Any integer count-change that respects Euler–Poincaré is a unique integer combination of the five.
- Count-level "completeness" is therefore easy linear algebra. The deep part of Mäntylä's theorem is that a sequence of *applicable* local operations exists for every actual topology, which is a structural statement.

### Gaps
- No access to Mäntylä 1984, so I have not seen the exact theorem statement, the definition of "plane model", or the proof technique.
- I did not check the exact operator names in Braid et al. or Eastman & Weiler from full text.

---

## Q5. Half-edge and non-manifold extensions

### Takeaway
- Half-edge (Mäntylä's GWB; later Kettner/CGAL) and winged-edge structures serve 2-manifolds.
- Non-manifold modelling needs:
  - **use-based structures:** radial-edge (Weiler 1986/88); vertex-based (Gursoz & Prinz 1989/90); coupling entities (Yamaguchi & Kimura 1995); cell complexes (Masuda 1993); SGC (Rossignac & O'Connor 1989);
  - **a different Euler-type formula and operator set:** e.g. Weiler's M-MR, M-SV, M-E, M-F, K-E.

### Cited findings
- **Radial edge:** "The radial edge data structure explicitly represents eleven topological element types." It uses face-use, loop-use, edge-use and vertex-use; "Radial ordering of faces around common edges is represented directly". **VERIFIED (secondary)** — [Patrikalakis 2003](https://ocw.mit.edu/courses/2-158j-computational-geometry-spring-2003/f04f923ac8e0af56d19095b4de8dea3c_lecnotes14_fixed.pdf)
- **Manifold formula fails; Weiler's operators:** "The Euler-Poincare formula is no longer valid for NTM topologies. NTM topology operators similar to Euler operators have been specified and defined by Weiler. A minimal sufficient set of NTM operators to construct any model are: M-MR … M-SV … M-E … M-F … K-E." **VERIFIED (secondary)**, same source.
- **Sufficiency:** "There is no complete theory available yet concerning the identification and proof of the theoretical minimal amount of topological information required to reconstruct a NTM topology. The radial edge data structure … has been proven to be sufficient and complete." **VERIFIED (secondary)**, same source (2003).
- **Weiler citations:**
  - K. Weiler, *Topological Structures for Geometric Modeling*, PhD thesis, Rensselaer Polytechnic Institute, Troy NY, 1986.
  - K. Weiler, "Edge-based data structures for solid modeling in curved-surface environments", *IEEE CG&A* 5(1):21–40, Jan 1985.

  **VERIFIED (secondary)** (MIT reference list).
  - "The radial edge structure: a topological representation for non-manifold geometric boundary modeling", in M. Wozny, H. McLaughlin, J. Encarnação (eds.), *Geometric Modeling for CAD Applications*, North-Holland, 1988, pp. 3–36. **UNVERIFIED** (page range uncertain; one snippet suggested 37–68 from memory).
- **Masuda 1993:** H. Masuda, "Topological operators and Boolean operations for complex-based nonmanifold geometric models", *Computer-Aided Design* 25(2):119–129, 1993, DOI [10.1016/0010-4485(93)90097-8](https://doi.org/10.1016/0010-4485(93)90097-8).
  - Abstract: "A mathematical framework is introduced, and the topological structure and basic topological operations are discussed on the basis of the framework."
  - Keywords include "Euler operations; cell complexes; form-feature modelling".
  - **VERIFIED (secondary)** — [MaRDI](https://portal.mardi4nfdi.de/wiki/Publication:1209190)
- **Yamaguchi & Kimura 1995:** Y. Yamaguchi, F. Kimura, "Nonmanifold topology based on coupling entities", *IEEE CG&A* 15(1):42–50, 1995. They propose a data structure and two classes of operations "focusing on neighborhood relationships and boundary information" over "cell decomposition in a 3D Euclidean space". **VERIFIED (secondary)** (abstract via search). I found no confirmation of the exact Euler–Poincaré form they use.
- **Gursoz & Prinz:** E. L. Gürsöz, F. B. Prinz, "Node-based representation of non-manifold surface boundaries in geometric modeling", in Wozny, Turner, Preiss (eds.), *Geometric Modeling for Product Engineering*, North-Holland, 1989. **VERIFIED (secondary)** (citation).
- **Rossignac & O'Connor:** "SGC: A dimension-independent model for pointsets with internal structures and incomplete boundaries", same volume, pp. 145–180, 1989. **VERIFIED (secondary)** (citation).

### UNVERIFIED background
- **Half-edge:** Mäntylä's half-edge structure in GWB/the 1988 book (solid → face → loop → half-edge → vertex). L. Kettner, "Using generic programming for designing a data structure for polyhedral surfaces", *Computational Geometry: Theory and Applications* 13(1):65–90, 1999, is the basis of the CGAL `HalfedgeDS`. A Springer chapter titled "The Halfedge Data Structure and Euler Operators" exists in *Introduction to Geometric Computing* (Ghali, 2008, DOI 10.1007/978-1-84800-115-2_27); **VERIFIED (secondary)**, title only.
- **The non-manifold formula** in the Masuda / Yamaguchi–Kimura line is the cell-complex Euler characteristic χ = Σ(−1)^k n_k, applied per dimension with corrections for regions, cavities and holes. Masuda's version is commonly given as v − e + (f − r) − (V − Vh + Vc) = C − Ch + Cc, where V = volumes, Vh = volume holes, Vc = cavities, C = complexes, Ch = complex holes, Cc = complex cavities. **UNVERIFIED** (not read).

---

## Q6. Topology versus geometry validity

### Takeaway
Euler operators and the Euler–Poincaré formula guarantee only combinatorial consistency. Geometric validity is a separate check that every kernel performs independently.

### Cited findings
- "Euler equation is a necessary but not sufficient condition for validity of a B-rep." **VERIFIED (secondary)** — Patrikalakis 2003.
- The same notes separate topology from geometry. They define topological entities with geometric conditions on top, e.g. an edge as "A finite, non-self-intersecting curve", and note that faces must not self-intersect "but they are allowed to intersect with each other" in certain representations. **VERIFIED (secondary)**, same source.
- Baumgart already warned that Eulerian polyhedra "do not necessarily correspond to what we normally call a solid classical polyhedron". **VERIFIED** — [SAIL EULER.5](https://www.saildart.org/EULER.5[OLD,BGB])
- **OCCT encodes the split explicitly.** `BRepCheck_Analyzer(S, GeomControls)`: "If False only topological informaions are checked." Geometric checks include `BRepCheck_SelfIntersectingWire`, `BRepCheck_IntersectingWires`, `BRepCheck_InvalidCurveOnSurface` and `BRepCheck_InvalidSameParameterFlag`. **VERIFIED** — [OCCT refman BRepCheck_Analyzer](https://occt3d.com/dev/doc/refman/html/class_b_rep_check___analyzer.html)

### Inferences
- Our validity invariant must have two layers:
  - (1) topological: closed oriented shells, Euler characteristic consistent with expected genus;
  - (2) geometric: BRepCheck with GeomControls=True, plus tolerances and a self-intersection check.
- An Euler-consistent solid can still be geometrically garbage.

---

## Q7. Commercial and open kernels

### Takeaway
- **OpenCascade:** a shareable, oriented, located TopoDS graph built by `BRep_Builder` / `BRepBuilderAPI_*` and the algorithms. I found no Euler-operator API. Validity comes from BRepCheck, ShapeAnalysis and ShapeFix.
- **Parasolid:** exposes explicit Euler-operator functions (secondary evidence).
- **ACIS:** I found no public documentation of an Euler-operator API.
- How any of these kernels uses Euler operators *internally* (e.g. inside Booleans) is proprietary or undocumented.

### Cited findings
- **OCCT topology** (*Modeling Data* user guide):
  - "The TopoDS_Shape class describes a reference to a shape." It "contains a reference to an underlying abstract shape, an orientation, and a local reference coordinate."
  - "A TopoDS_TShape is a description of a shape in its definition frame of reference."
  - Shape types are COMPOUND, COMPSOLID, SOLID, SHELL, FACE, WIRE, EDGE, VERTEX; SOLID is "a part of space limited by shells".
  - Topology "defines relationships between simple geometric entities". "Topological library allows you to build pure topological data structures."
  - Non-manifold support: "Due to a built-in non-manifold (or mixed-dimensional) feature" models may mix 0D–3D entities.

  **VERIFIED** — [OCCT Modeling Data guide](https://occt3d.com/dev/doc/overview/html/occt_user_guides__modeling_data.html). The first 100k of 115k characters were scanned; no mention of Euler operators or Euler characteristic.
- **BRepCheck_Analyzer:**
  - "A framework to check the overall validity of a shape"; anomalies can be corrected with ShapeAnalysis, ShapeUpgrade and ShapeFix.
  - IsValid "Returns true if no defect is detected on the shape S or any of its subshapes".
  - Criteria include edges with ≥2 vertices unless degenerate, closed wires, correctly oriented faces, closed shells for solids, and SameParameter/SameRange flags on edges in faces.

  **VERIFIED** — [OCCT refman](https://occt3d.com/dev/doc/refman/html/class_b_rep_check___analyzer.html)
- **Parasolid:**
  - Topology entities: body, region, shell, face, loop, fin (oriented edge-use), edge, vertex.
  - Edges are classed by fin count (wireframe, laminar, manifold, general).
  - Euler functions include `PK_EDGE_euler_slit`, `PK_EDGE_euler_split`, `PK_EDGE_euler_open_zip`, `PK_EDGE_euler_close_zip`, `PK_EDGE_euler_delete_with_face`, `PK_EDGE_euler_delete_ring_face`, `PK_FACE_euler_unslit`, `PK_FACE_euler_make_loop`, `PK_FACE_euler_make_ring_face`, `PK_FACE_euler_make_ring_loop`. Some change face genus.

  **VERIFIED (secondary)**, search snippets of a 2009 Parasolid deck hosted by Seoul National University OCW ([4845.pdf](https://ocw.snu.ac.kr/sites/default/files/NOTE/4845.pdf), [4844.pdf](https://ocw.snu.ac.kr/sites/default/files/NOTE/4844.pdf)). Direct fetch failed (DNS). Confirm against the Siemens PK reference.
- **ACIS:** no public "Euler operations" API documentation found. Spatial's product pages list Booleans, blending, validity checking and so on. **VERIFIED (absence in search).**

### UNVERIFIED background
- **OCCT tools:**
  - `TopExp::MapShapes` / `TopExp_Explorer` count sub-shapes (V, E, F).
  - `BRep_Builder` makes raw topology.
  - `BRepBuilderAPI_MakeEdge/Wire/Face/Shell/Solid/Sewing` build from geometry.
  - `ShapeAnalysis_FreeBounds` and `ShapeAnalysis_Shell` find free edges (open shells).
  - `BRepAlgoAPI_*` handles Booleans, with internals in BOPAlgo/IntTools (the old TopOpeBRep is deprecated).
  - None are Euler operators. Topology is created wholesale, not via operator sequences.
  - **Caution for Euler counting in OCCT:** seam edges (periodic surfaces), degenerated edges (sphere poles) and shared TShapes with different orientation mean naive V/E/F counts need care. Use `TopTools_IndexedMapOfShape` (identity ignoring orientation).
- **ACIS** (Spatial) has historically had a low-level "Euler operations" layer (the `euler` component or `api_*` topology operations) in some versions. **UNVERIFIED.**
- **Onshape:** uses Parasolid. FeatureScript exposes no Euler operators. **UNVERIFIED.**

---

## Q8. Practical uses for our DSL

### (a) Validity invariant on every compiled solid

**Proposed check (my inference):**
- for each solid: shells closed (no free edges), all faces oriented consistently, BRepCheck with geometric controls passes;
- compute V, E, F from `TopTools_IndexedMapOfShape` and R = Σ(wires per face − 1);
- assert V − E + F − R = 2(S − H) holds with H ≥ 0 integer;
- compare H against the *intent's expected genus*, e.g. a plate with 4 through-holes ⇒ genus 4.

**Grounding:**
- The formula and its non-sufficiency are VERIFIED (secondary).
- OCCT's IsValid and the GeomControls split are VERIFIED.
- The genus-as-intent-check idea is my inference. Through-holes raise genus by 1 each; blind holes don't change it (UNVERIFIED but standard topology).
- **Caveat:** OCCT seam and degenerated edges change raw counts. Calibrate on primitives (box: 8 − 12 + 6 = 2; cylinder; sphere; torus) before trusting the check. I did not run this in this pass.

### (b) Canonical topological description and graph signature
- **Basic signature:** the tuple (V, E, F, R, S, H) plus the face-adjacency graph (faces as nodes, labelled by surface type; edges as nodes or arcs, labelled by curve type and convexity). This gives a cheap invariant for dedup and solution comparison.
- **Precedent:** face-adjacency graphs are the standard ML input.
  - UV-Net: Jayaraman et al., CVPR 2021 (**UNVERIFIED** detail).
  - BRepNet: Lambourne et al., CVPR 2021. It uses "coedges", essentially half-edges, and convolution kernels defined over them. **UNVERIFIED** detail.
- **Exact comparison:** graph isomorphism / canonical labelling (e.g. nauty-style) over the labelled face-adjacency multigraph gives a canonical topological form. The Euler tuple is a fast pre-filter. This is inference.
- **Brevity.** An Euler-operator construction sequence has length ≥ V + E + F-ish. So "Euler length" measures topological size, not design-intent brevity. It is a poor definition of DSL brevity but a reasonable complexity measure for a solution. This is inference.

### (c) Euler-operator sequences as tokenization or training target
- **SolidGen** (Jayaraman, Lambourne, Desai, Willis, Sanghi, Morris; arXiv 2203.13944, 2022; *TMLR* 2023): "models the B-rep directly by predicting the vertices, edges, and faces using Transformer-based and pointer neural networks". It relies on an "indexed boundary representation" that references B-rep vertices, edges and faces in a hierarchy, which "can be inverted back into a B-rep exactly". It is limited to lines, arcs, and planar/cylindrical/conical/spherical/toroidal surfaces. **VERIFIED** (abstract via search) — [arXiv](https://arxiv.org/abs/2203.13944)
- **BrepGen** (Xu, Lambourne, Jayaraman, Wang, Willis, Furukawa; *ACM TOG* 2024, arXiv 2401.15563): a diffusion model over a tree (solid → faces → edges → vertices). Shared topology is represented by duplicated nodes merged afterwards, and it handles free-form surfaces. **VERIFIED (secondary)** — [arXiv](https://arxiv.org/abs/2401.15563)
- **Later work:**
  - HoLa (arXiv 2504.14257) learns a surface-only latent, with curves derived via a neural intersection network.
  - BrepGPT (arXiv 2511.22171) uses a "Voronoi half-patch" representation.
  - BrepARG (arXiv 2601.16771) puts face-index topology tokens in one sequence.

  **VERIFIED (secondary)** (search snippets).
- **No direct precedent.** My search found **no ML paper that tokenizes B-reps as Euler-operator sequences**. Absence in a limited search, not proof.
- **DeepCAD** (Wu, Xiao, Zheng; ICCV 2021) learns sketch-and-extrude command sequences rather than topology ops. PolyGen (Nash et al., ICML 2020) generates vertices then faces of meshes. **UNVERIFIED** details.
- **Inference: a natural niche.** Euler-op sequences are always topologically valid by construction (soundness). The vocabulary is tiny (5 ops + inverses with pointer arguments). Validity is guaranteed at every prefix, which grammar-constrained decoding can exploit.
- **Weakness.** Sequences are highly non-unique: many orders give the same solid. A canonical ordering would be needed (e.g. BFS over a canonical face labelling). Geometry still has to be attached.
- **For mesh → B-rep → history,** Euler ops are better suited to the mesh → topology stage than to recovering *design history*, which is feature-level.

---

## Operator table: count deltas

Mäntylä-style basis. Coordinates (V, E, F, H = genus/handles, R = rings/inner loops, S = shells). Invariant: V − E + F − R = 2(S − H). Names follow Mäntylä/GWB (UNVERIFIED against the book). Deltas COMPUTED to satisfy the invariant.

| Operator | Meaning | ΔV | ΔE | ΔF | ΔH | ΔR | ΔS | Inverse |
|---|---|---|---|---|---|---|---|---|
| MVFS | make vertex, face, shell (initial "skeletal" solid) | +1 | 0 | +1 | 0 | 0 | +1 | KVFS |
| MEV | make edge, vertex (split vertex / grow strut) | +1 | +1 | 0 | 0 | 0 | 0 | KEV |
| MEF | make edge, face (split a face/loop) | 0 | +1 | +1 | 0 | 0 | 0 | KEF |
| KEMR | kill edge, make ring (split loop into outer + inner) | 0 | −1 | 0 | 0 | +1 | 0 | MEKR |
| KFMRH | kill face, make ring & hole (glue face into another face's ring → through-hole) | 0 | 0 | −1 | +1 | +1 | 0 | MFKRH |

Notes:
- Baumgart's GLUE/UNGLUE and Weiler's GLUE are not in this basis. The kflevmg variant raises genus by 1 and is a composite of the basis. The kflevs variant merges two shells (ΔS = −1) and corresponds to the shell-merging use of KFMRH, i.e. ΔF = −1, ΔR = +1, ΔS = −1, ΔH = 0. That is another lattice vector, a combination of the basis. (COMPUTED that it satisfies the invariant: −1 − 1 = 2(−1).)
- **Weiler/MIT variant** (Patrikalakis Table 14.6; VERIFIED secondary). Coordinates (S, F, L, E, V, G), where L counts all loops:
  - MSFLV: S+1, F+1, L+1, V+1
  - MEV: E+1, V+1
  - ME: mefl F+1 L+1 E+1 | mekl L−1 E+1 | meksfl S−1 F−1 L−1 E+1
  - GLUE: kflevmg F−2 L−2 E−ne V−nv G+1 | kflevs S−1 F−2 L−2 E−ne V−nv
  - KE: inverse of ME
- **Weiler non-manifold minimal set** (VERIFIED secondary): M-MR (model and initial region), M-SV (shell + vertex), M-E, M-F, K-E.

---

## Implications for the DSL core

1. **Euler operators are the wrong level for the user-facing core, and the right level for the validity layer.** Our core alphabet (sketch/extrude/revolve/boolean…) works on geometry-bearing solids. OCCT builds topology wholesale, not by Euler steps. Lowering the DSL to Euler ops would mean writing our own kernel. Recommendation:
   - adopt the **Euler–Poincaré relation and BRepCheck as compile-time invariants**;
   - do *not* adopt Euler ops as the core alphabet.
2. **The provable-core analogy holds only partially.** Euler ops are a *proven sound and complete* basis for a *topological* modelling space. The intent-layer → core lowering could cite this as the precedent for "small grounded basis + derived operators". Chiyokura and the MIT notes both describe higher operators (primitives, sweeps) built on Euler ops. The completeness of our geometric core needs its own argument (Requicha r-sets; covered by other notes).
3. **Genus as a first-class intent check.** Intent like "through-hole", "pass-through", "4 mounting holes" implies a predictable ΔH (and ΔR on the faces involved). Checking ΔH per feature is a cheap, deterministic topological assertion: "this hole feature must increase genus by exactly 1". It catches blind-vs-through mistakes and accidental breakthroughs.
4. **Canonical topological signature** for determinism (architecture §7) and dedup:
   - (V, E, F, R, S, H), plus a canonical labelled face-adjacency graph hash;
   - store it with every compiled solution next to the kernel version;
   - this gives "same DSL ⇒ identical topology" an equality check independent of float noise.
5. **Persistent naming.** Euler-op logs give each entity a creation event (Chiyokura's history/undo idea). That is the essence of history-based naming. In our OCCT target we get this from `BRepBuilderAPI_MakeShape::Generated/Modified/IsDeleted` histories (UNVERIFIED API detail), not from Euler ops.
6. **ML / tokenization (reverse-engineering direction).**
   - Euler-op sequences are an under-explored, validity-by-construction token set (no precedent found).
   - Pair them with SolidGen-style pointer networks.
   - Treat it as a research bet, not a dependency.
7. **Non-manifold intermediates.** OCCT allows non-manifold compounds, so intent-layer intermediates (sheet bodies, wire frames, contact faces) may be non-manifold. The validity invariant should be applied only at "solid" checkpoints. Use Weiler/Masuda-style rules if we ever need non-manifold validity.

---

## References

**Primary (read)**
- Baumgart, B. G. (1972). *Winged Edge Polyhedron Representation*. Stanford AI Memo AIM-179 (STAN-CS-320), Oct 1972. https://purl.stanford.edu/tz289cy2950 (abstract read)
- Baumgart, B. G. (c. 1972–74). "Summary of Polyhedron Primitives", SAIL file EULER.5[OLD,BGB]. https://www.saildart.org/EULER.5[OLD,BGB] (read)
- Baumgart, B. G. (1975). "A polyhedron representation for computer vision". *AFIPS '75 NCC*, pp. 589–596. DOI [10.1145/1499949.1500071](https://doi.org/10.1145/1499949.1500071). Draft read at https://www.saildart.org/OUT[NCC,BGB]; published PDF https://www.cs.jhu.edu/~misha/Fall25/Readings/Baumgart75.pdf (blocked).
- Open Cascade. *Modeling Data* user guide. https://occt3d.com/dev/doc/overview/html/occt_user_guides__modeling_data.html (read)
- Open Cascade. `BRepCheck_Analyzer` class reference. https://occt3d.com/dev/doc/refman/html/class_b_rep_check___analyzer.html (read)
- Jayaraman, P. K., et al. (2022/2023). "SolidGen: An Autoregressive Model for Direct B-rep Synthesis". *TMLR* 2023; arXiv:2203.13944. https://arxiv.org/abs/2203.13944 (abstract)
- Xu, X., Lambourne, J. G., Jayaraman, P. K., Wang, Z., Willis, K. D. D., Furukawa, Y. (2024). "BrepGen: A B-rep Generative Diffusion Model with Structured Latent Geometry". *ACM TOG* 43(4); arXiv:2401.15563. https://arxiv.org/abs/2401.15563 (abstract)

**Secondary (read)**
- Patrikalakis, N. M. (2003). *Computational Geometry, Lectures 14 and 15* (MIT 2.158J). https://ocw.mit.edu/courses/2-158j-computational-geometry-spring-2003/f04f923ac8e0af56d19095b4de8dea3c_lecnotes14_fixed.pdf
- Wikipedia. "Euler operator (digital geometry)". https://en.wikipedia.org/wiki/Euler_operator_(digital_geometry)
- Shene, C.-K. "Euler Operators", MTU CS3621 notes. https://pages.mtu.edu/~shene/COURSES/cs3621/NOTES/model/euler-op.html (snippet only)
- MaRDI portal, entries for Mäntylä 1984 and Masuda 1993. https://portal.mardi4nfdi.de/wiki/Item:Q3709924 ; https://portal.mardi4nfdi.de/wiki/Publication:1209190

**Cited, not read (bibliographic data verified where marked)**
- Braid, I. C., Hillyard, R. C., Stroud, I. A. (1980). "Stepwise construction of polyhedra in geometric modelling". In K. W. Brodlie (ed.), *Mathematical Methods in Computer Graphics and Design*, Academic Press, London, pp. 123–141. (secondary-verified citation)
- Eastman, C. M., Weiler, K. J. (1979). *Geometric modeling using the Euler operators*. Carnegie-Mellon University, Institute of Physical Planning, DRC-15-2-79 / Res. Rep. 78. https://kilthub.cmu.edu/articles/journal_contribution/Geometric_modeling_using_the_Euler_operators/6605963
- Mäntylä, M. (1984). "A note on the modeling space of Euler operators". *Computer Vision, Graphics, and Image Processing* 26(1):45–60. DOI [10.1016/0734-189X(84)90129-4](https://doi.org/10.1016/0734-189X(84)90129-4)
- Mäntylä, M. (1988). *An Introduction to Solid Modeling*. Computer Science Press, Rockville MD. ISBN 0-88175-108-1.
- Mäntylä, M., Sulonen, R. (1982). "GWB: A solid modeler with Euler operators". *IEEE CG&A* 2(7):17–31. (UNVERIFIED details)
- Wilson, P. R. (1985). "Euler formulas and geometric modeling". *IEEE CG&A* 5(8):45–60.
- Weiler, K. (1985). "Edge-based data structures for solid modeling in curved-surface environments". *IEEE CG&A* 5(1):21–40.
- Weiler, K. (1986). *Topological Structures for Geometric Modeling*. PhD thesis, Rensselaer Polytechnic Institute.
- Weiler, K. (1988). "The radial edge structure: a topological representation for non-manifold geometric boundary modeling". In Wozny, McLaughlin, Encarnação (eds.), *Geometric Modeling for CAD Applications*, North-Holland. (pages UNVERIFIED)
- Gürsöz, E. L., Prinz, F. B. (1989). "Node-based representation of non-manifold surface boundaries in geometric modeling". In Wozny, Turner, Preiss (eds.), *Geometric Modeling for Product Engineering*, North-Holland.
- Rossignac, J., O'Connor, M. (1989). "SGC: A dimension-independent model for pointsets with internal structures and incomplete boundaries". Same volume, pp. 145–180.
- Masuda, H. (1993). "Topological operators and Boolean operations for complex-based nonmanifold geometric models". *Computer-Aided Design* 25(2):119–129. DOI [10.1016/0010-4485(93)90097-8](https://doi.org/10.1016/0010-4485(93)90097-8)
- Yamaguchi, Y., Kimura, F. (1995). "Nonmanifold topology based on coupling entities". *IEEE CG&A* 15(1):42–50.
- Chiyokura, H. (1988). *Solid Modelling with DESIGNBASE: Theory and Implementation*. Addison-Wesley. (UNVERIFIED details)
- Kettner, L. (1999). "Using generic programming for designing a data structure for polyhedral surfaces". *Computational Geometry* 13(1):65–90. (UNVERIFIED)
- Hoffmann, C. M. (1989). *Geometric and Solid Modeling: An Introduction*. Morgan Kaufmann.
- Stroud, I. (2006). *Boundary Representation Modelling Techniques*. Springer.
- Parasolid Euler-operator teaching deck (2009), Seoul National University OCW. https://ocw.snu.ac.kr/sites/default/files/NOTE/4845.pdf (snippet only)
- Lambourne, J. G., et al. (2021). "BRepNet: A topological message passing system for solid models". CVPR 2021. (UNVERIFIED)
- Jayaraman, P. K., et al. (2021). "UV-Net: Learning from boundary representations". CVPR 2021. (UNVERIFIED)
- Wu, R., Xiao, C., Zheng, C. (2021). "DeepCAD: A deep generative network for computer-aided design models". ICCV 2021. (UNVERIFIED)
- Nash, C., et al. (2020). "PolyGen: An autoregressive generative model of 3D meshes". ICML 2020. (UNVERIFIED)

---

## Explicit list of unverified items

1. The exact theorem statement, the definition of "plane models", and the proof method in Mäntylä 1984. Only the bibliographic data and a secondary paraphrase ("complete set of modeling primitives for manifold solids") were seen.
2. Mäntylä's operator names (mvfs, mev, mef, kemr, kfmrh and inverses) and formula form v − e + f = 2(s − h) + r as printed in the 1988 book.
3. The operator set and wording in Braid, Hillyard & Stroud (1980), and whether a 1978 preprint exists.
4. The full text of Eastman & Weiler 1979. The operator list is only via Wikipedia's table.
5. The content of GWB (Mäntylä & Sulonen 1982) and Chiyokura's DESIGNBASE, including undo via inverse Euler ops.
6. The page range of Weiler 1988, and the exact non-manifold Euler formulas of Masuda 1993 and Yamaguchi & Kimura 1995.
7. Parasolid `PK_*_euler_*` function names and semantics (2009 teaching deck seen in search snippets only), and whether Parasolid uses them internally in Booleans/blends.
8. Whether ACIS has a public Euler-operator API. Not found.
9. That OCCT has no Euler-operator layer. Based on absence in the Modeling Data guide (first 100k chars) and my background knowledge.
10. OCCT counting caveats (seam/degenerated edges) and the history API (`Generated/Modified/IsDeleted`).
11. Details of BRepNet, UV-Net, DeepCAD and PolyGen. The absence of Euler-op tokenization in ML literature is based on a limited search.
12. The history of Euler's and Poincaré's formulas.

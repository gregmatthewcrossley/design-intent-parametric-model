# Persistent Naming / Topological References in History-Based CAD

Researcher notes, part of a 4-part pass on DSL mathematical foundations. Sibling notes cover Euler operators/B-rep topology, solid-modeling theory and geometry axioms/constraints. Links to Euler operators are flagged where they matter.

Tags: **[VERIFIED]** means I read the primary source text (full text, official docs page, or Crossref metadata for bibliographic facts). **[VERIFIED-secondary]** means the claim is confirmed only through a secondary source that quotes or describes the primary. **[UNVERIFIED]** means the claim comes from memory or a search snippet only.

---

## Summary

- **The problem.** A history-based model stores operations whose parameters point at faces, edges and vertices of earlier states. When it is rebuilt with new parameters, topology can split, merge, vanish or appear, so a stored reference has to be *named* when the model is built and *matched* when it is rebuilt. Agbodan et al. (2003) and Cardot et al. (2019) both frame it this way, with the same textbook example: a slot splits face f into f1 and f2, a later feature references f2, then an edit means f is never split. [VERIFIED]
- **Three families of naming scheme exist.**
  - *Topological history or genealogy.* Kripac's face graph, OCCT TNaming, FreeCAD/realthunder's element map, Onshape's internal ids, and Cardot's G-map rule tracking.
  - *Generative or semantic names.* Chen/Hoffmann/Capoyleas name an entity by the feature that created it plus the source entity, then disambiguate with topological context and orientation. Bidarra et al. go further and drop boundary-face names entirely in favour of *feature faces*.
  - *Geometric or predicate selection.* build123d filters and sorts, Onshape's `qClosestTo` and `qParallelPlanes`. These are usually layered over history (hybrid).
- **Failure modes recur across schemes.** The literature and the docs keep naming the same ones: splits (one name maps to n entities), merges (n names map to one entity), deletion (the referenced entity disappears), ambiguous matches under symmetry, order-dependent indices (FreeCAD's `;:M2` index depends on the order OCCT reports results), and thresholds or approximate matches that silently pick the wrong entity (Agbodan's critique of Chen and Kripac). [VERIFIED]
- **What production systems converge on.** Onshape (a) names every operation with a hierarchical `Id` that must mirror creation history, (b) resolves references through lazily evaluated *queries*, of which `qCreatedBy`, `qCapEntity`/`qNonCapEntity`, `qSplitBy`, `startTracking` and attributes are history-based, (c) defines exactly how splits and merges propagate creator ids, and (d) documents the evaluation order of `qNthElement` and `evaluateQuery` as "deterministic but arbitrary". [VERIFIED]
- **Recommendation for our DSL.** References should be *semantic queries* over creator-feature and role, using an OCCT history record (`BRepBuilderAPI_MakeShape::Generated/Modified/IsDeleted`, `BRepTools_History`) as the primary mechanism. Geometric predicates come second and need explicit tolerance and tie rules. Every query must declare its expected cardinality and fail loudly otherwise, and stability should be checked by perturbing parameters in a test harness.

---

## Q1. Primary literature: naming schemes and their failure modes

### Takeaway
The literature divides into two families. *Generic or generative naming* (Chen, Hoffmann, Capoyleas) names an entity by the operation that created it plus its source entity and topological context. *Topological-history graphs with matching* (Kripac, then Agbodan/Marcheix/Pierra, then Cardot) record the face splits, merges and deletions and match old entities to new ones on rebuild. Both need heuristics when topology changes, and the approximations they make are their main failure mode. Bidarra et al. argue that boundary-entity naming can only ever solve a fraction of the problem, and propose referencing persistent *feature* faces instead.

### Cited Findings

**Bibliography.** All DOIs were confirmed through Crossref metadata; the full Crossref entries are in the reference list. [VERIFIED for bibliographic data]
- Kripac, J. (1997). CAD 29(2):113–122, DOI 10.1016/S0010-4485(96)00040-1. An earlier version appeared at ACM SMA '95, pp. 21–30, DOI 10.1145/218013.218024.
- Chen, X. & Hoffmann, C.M. (1995). "Towards feature attachment." CAD 27(9):695–702, DOI 10.1016/0010-4485(94)00027-B. **Note:** this is CAD 27(9), *not* 27(12). The CAD 27(12) paper is "On editability of feature-based design", pp. 905–914, DOI 10.1016/0010-4485(95)00013-5.
- Capoyleas, V., Chen, X. & Hoffmann, C.M. (1996). "Generic naming in generative, constraint-based design." CAD 28(1):17–26, DOI 10.1016/0010-4485(95)00014-3.
- Marcheix, D. & Pierra, G. (2002). "A survey of the persistent naming problem." Proc. 7th ACM SMA, pp. 13–22, DOI 10.1145/566282.566288.
- Bidarra, R., Nyirenda, P.J. & Bronsvoort, W.F. (2005). CAD&A 2(1–4):517–526, DOI 10.1080/16864360.2005.10738401.
- Wu, J., Zhang, T., Zhang, X. & Zhou, J. (2001). "A face based mechanism for naming, recording and retrieving topological entities." CAD 33(10):687–698, DOI 10.1016/S0010-4485(00)00099-3.
- Agbodan, D., Marcheix, D., Pierra, G. & **Thabaud**, C. (2003). "A topological entity matching technique for geometric parametric models." Shape Modeling International 2003, pp. 235–244, DOI 10.1109/SMI.2003.1199623. **Note:** the fourth author is Thabaud, not "Thiebaut".
- Cardot, A., Marcheix, D., Skapin, X., Arnould, A. & Belhaouari, H. (2019). "Persistent naming based on graph transformation rules to reevaluate parametric specification." **Computer-Aided Design & Applications** (not *Computer-Aided Design*) 16(5):985–1002, DOI 10.14733/cadaps.2019.985-1002.
- Farjana, S.H. & Han, S. (2018). "Mechanisms of persistent identification of topological entities in CAD systems: a review." Alexandria Engineering Journal 57(4):2837–2849, DOI 10.1016/j.aej.2018.01.007.

**Content of the papers**
- Kripac's problem statement: "One of the fundamental problems in history-based parametric solid modelling systems is to identify topological entities (faces, edges, vertices) of solid models in such a way that the same entities can still be identified after the models have been re-evaluated." [VERIFIED-secondary: the abstract as shown on a bibliographic record] — [record](https://data.zhenzhi.com/details/1/871973047)
- How Agbodan et al. describe Kripac's system:
  - It is an API with "a table of correspondence between an entity of the initial model and one or more entities of the reevaluated model".
  - It uses "an interesting graph structure for identification of any topological entities based on face history (creations, splits, merges and deletions of faces)".
  - Its matching is *global*, which costs space and time, and it keeps a copy of the model at every step. [VERIFIED, Agbodan full text] — [Agbodan et al. 2003 PDF](https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf)
- Failure modes Agbodan et al. demonstrate in Kripac's matching:
  - *Swapped matching.* When a slot splits a face, matching by "longest common face cycle" in the topological neighbourhood maps Fa→Fy and Fb→Fx, the wrong way round. A later operation that takes Fa as input then receives the wrong face.
  - *"Piece loss".* The backward-forward graph search can skip faces, so face J is "lost".
  - Kripac's model "does not allow to record that a selected mapping was only approximated as it uses a discrete metrics". [VERIFIED] — [Agbodan et al. 2003](https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf)
- How Agbodan et al. describe Chen's approach (EREP plus a naming schema):
  - Entities generated by extrusion or revolution are "named by reference to the corresponding source entity of the extruded 2D contour and the constructive gesture".
  - Entities created by collisions are described by "its origin, either a source entity or an intersection of source faces, its smallest unambiguous topological context and its local orientation".
  - Names on curved domains need extra geometric information, namely edge orientation relative to the extrusion direction.
  - Matching compares topological neighbourhoods against a threshold. The weaknesses: the threshold is unexplained, the matching is local, and it is "very sensitive to the subdivision of the topological neighborhood".
  - Chen covered only sweep, blend and fillet features, and the approach works "when there are not too many symmetries in the model". [VERIFIED] — [Agbodan et al. 2003](https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf)
- Agbodan et al.'s own model:
  - **Invariant entities** are "completely and unambiguously characterized by the structure of a constructive gesture and its input parameters, independently of involved values". Examples are the end face of a swept block and the lateral shell of a slot.
  - **Contingent entities** "result from an interaction between the pre-existing geometric model and invariant entities".
  - A *face graph* records creation, split and deletion of faces. Invariant faces are named by a unique topological traversal; contingent faces get an iterative number.
  - For an extrusion, each resulting entity "corresponds to the cartesian product between a topological entity of the profile and a topological entity of the path".
  - Matching is global and per step, based on weighted topological neighbourhoods, and is implemented on Open CASCADE. [VERIFIED] — [Agbodan et al. 2003](https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf)
- Agbodan et al. trace the line of work to "the pioneer work of Hoffmann and Juan [EREP]", cited as Purdue Tech Report CER-92-24, 1993. [VERIFIED as citation]
- Cardot et al.:
  - Restate the problem with the slot example. The first slot is shortened, so "f is not split and neither f1 nor f2 are created", yet the second slot still references f2. "Persistent naming should enable both unambiguous identification of initial model entities and consistent matching between initial and reevaluated model entities".
  - Classify orbit evolutions as **Creation, Deletion, Fusion (merge), Modification, NoEffect, Split**.
  - Track "only entities that are actually referenced in the parametric specification ... and only during the reevaluation phase". [VERIFIED full text] — [Cardot et al. 2019](https://www.cad-journal.net/files/vol_16/CAD_16(5)_2019_985-1002.pdf)
- Bidarra et al. (abstract, via search summary): persistent naming schemes "solve only a fraction" of the problem. They propose "to use the names of persistent feature faces, instead of the names of boundary faces, every time a reference to a face is required". [VERIFIED-secondary: search summary of the TU Delft abstract; the PDF host was unreachable] — [TU Delft record](https://publications.graphics.tudelft.nl/papers/626)

### Inferences
- The splits, merges and deletions that Kripac's face graph records are the same evolution categories as Cardot's (Creation/Deletion/Fusion/Modification/Split) and OCCT's (PRIMITIVE/GENERATED/MODIFY/DELETE). The field has effectively standardised on a small *evolution algebra*.
- The "invariant vs. contingent" distinction is the key design lesson. A DSL should only let users reference *invariant* entities, those defined by an operation's structure such as "cap face of extrude E" or "side face from sketch edge e". Contingent entities, the fragments produced by later collisions, are where every scheme becomes heuristic.

### Gaps
- I did not read the Kripac, Chen–Hoffmann, Capoyleas, Marcheix–Pierra, Wu or Farjana–Han full texts. They are paywalled, and the TU Delft host for Bidarra et al. was unreachable. Claims about them come from Agbodan et al.'s and Cardot et al.'s critiques and from abstracts.

---

## Q2. Onshape FeatureScript query model

### Takeaway
Onshape references geometry through lazily evaluated `Query` values, anchored to hierarchical feature `Id`s that must mirror creation history. `qCreatedBy` has a precisely documented semantics for splits and merges. Positional selection (`qNthElement`, `evaluateQuery` order) is documented as "deterministic but arbitrary", which is why it is fragile. `startTracking` and `makeRobustQuery` expose the history tracking directly.

### Cited Findings
All findings below are [VERIFIED] from the [FeatureScript Standard Library docs](https://cad.onshape.com/FsDoc/library.html).
- **`qCreatedBy(featureId, entityType)`**
  - "An entity is 'created by' an operation if the entity was added to the context as part of that operation. Entities modified, but not created, by an operation are not returned by this query."
  - "If an entity is split (as in a split part operation), the resulting entities are 'created by' both the original entity's creator and the split part operation."
  - "If two entities are merged (as in a union of coincident faces), that entity is 'created by' the creators of each merged entity, as well as the merging operation itself."
- **`qNthElement(queryToFilter, n)`**: "The order of entities resolved by a query is deterministic but arbitrary." No explicit "discouraged" warning appears on the page. The fragility follows from this sentence plus the `evaluateQuery` note below.
- **`evaluateQuery`**
  - Returns "exactly one transient query for each matching entity at the time of the call. If the context is modified, the returned queries may become invalid".
  - "The order of entities returned by this function is arbitrary (and generally not predictable) except in the case of a qUnion query."
- **Set operators.** "qUnion is guaranteed to preserve order". "qIntersection preserves the order of the first subquery". "qSubtraction preserves the order of query1".
- **Role-based queries.** `qCapEntity(featureId, capType, entityType)` returns "start/end cap vertex, edge, and face entities created by featureId. Cap entities are produced by extrude, revolve, sweep, loft and thicken features". `qNonCapEntity` returns the side entities. `qSplitBy(featureId, entityType, backBody)` returns the front or back side of a split, defined relative to the tool's normal.
- **Geometric filters**
  - `qGeometry(query, GeometryType)`, `qParallelPlanes`, `qOwnedByBody`.
  - `qClosestTo` and `qFarthestAlong`: "In the case of a tie, resolves to all entities within TOLERANCE.zeroLength."
  - `qLargest`: "Multiple entities may be returned if they tie within tolerance."
  - So ties return *sets*, not an arbitrary pick.
- **Tracking queries**
  - `startTracking(context, subquery | sketchId, sketchEntityId)` "Generates a tracking query, which will evaluate to entities derived from subquery in features between startTracking and when query is evaluated". Example: tracking sketch "line0" through an extrude yields "a face and two edges (top and bottom) corresponding to line0".
  - `startTrackingIdentity` produces entities "inheriting the identity" of the subquery.
  - `makeRobustQuery` "Generates query robust to identity-preserving changes". `makeRobustQueriesBatched(..., followSplitMerge)` optionally follows "through splits and merges".
- **Ids**
  - "The full id hierarchy must reflect creation history. That is, each Id (including parents) must refer to a contiguous region of operations on the context." The docs show a loop that reuses `id + "extrude"` failing.
  - `ANY_ID` ("*") is a wildcard, for example `qCreatedBy(id + ANY_ID + "fillet")`.
  - `unstableIdComponent` "Marks a given id component as 'unstable' causing queries to treat it as a wildcard ... such as an index into the results of an evaluated query". `setExternalDisambiguation` exists for such cases.
- **Attributes.** `setAttribute` attaches named data to entities and `qHasAttribute(name)` queries it back. This is another way to name entities explicitly.
- **Operations that take one entity:** "When an operation parameter that requires one entity receives a query that resolves to multiple entities, it takes the first resolved entity."
- **Other lookups.** `qDependency` returns "the true dependency" (for example the profile edges of an extruded body). `lastModifyingOperationId` returns the id of the operation that created or last modified an entity. `qUniqueVertices` picks "the vertex with the lowest deterministic ID".

### Inferences
- Onshape's model maps almost directly onto our DSL:
  - A feature id plays the role of a DSL node name.
  - `qCapEntity` and `qNonCapEntity` are role queries.
  - `startTracking` is "generated by sketch edge e".
  - Attributes are named exports.
- The silent "takes the first resolved entity" rule is a hazard. When the DSL compiles to FeatureScript, it should emit a cardinality check (`evaluateQueryCount`) before any single-entity parameter.

### Gaps
- I could not find the separate "Queries" or "Ids" tutorial page; one guessed URL returned 404. I also did not find an Onshape blog post describing its internal naming algorithm. The internals behind the queries (how the kernel tracks persistent ids) remain undocumented publicly as far as I found.

---

## Q3. FreeCAD TNP work (realthunder element map → FreeCAD 1.0)

### Takeaway
realthunder's algorithm gives every sub-element a *mapped element name* made from its history, built from OCCT's `Generated` and `Modified` maker history. Splits are disambiguated by an index whose order depends on OCCT's reporting order, which the author acknowledges as a weakness. FreeCAD 1.0 (November 2024) shipped it as a mitigation, not a complete fix.

### Cited Findings
- **History source.** The algorithm uses "the modeling history" from OCCT's `BRepBuilderAPI_MakeShape` (`Generated`/`Modified`), wrapped behind `TopoShape::Mapper`. `BRepBuilderAPI_Sewing` and `BRepOffsetAPI_ThruSections` need special handling. [VERIFIED] — [realthunder wiki: Topological Naming Algorithm](https://github.com/realthunder/FreeCAD_assembly3/wiki/Topological-Naming-Algorithm)
- **`TopoShape::makESHAPE()` runs four steps:**
  1. Copy names of unchanged elements.
  2. Name generated and modified elements through the Mapper.
  3. Name unnamed sub-elements from a named parent (`;:U`).
  4. Name remaining elements from their named children (`;:L`). [VERIFIED] — same source
- **Name format.** Example: `Face6;:M2;FUS;:T1:5:F`, read as follows. [VERIFIED] — same source
  - `Face6` is the source element.
  - `;:M`, `;:G` or `;:MG` marks modified, generated or both.
  - `2` is the index for splits or multiple outputs.
  - `FUS` is the opcode.
  - `;:T<tag>:<len>:<type>` gives the owner tag, the source-name length and the element type.
  - Merges list extra sources in brackets after `;:M(`.
  - Long names are hashed.
- **Acknowledged limitations** [VERIFIED] — same source:
  - When a mapped element disappears or is renamed, fillet and similar features raise an invalid-link error. Guessing a replacement is left to the editing tool and is described as unreliable.
  - The split index depends on OCCT's reporting order; in the wiki's example a fillet moved to the other split edge.
  - Names grow long.
  - A non-formal test measured overhead: recompute time 40 s → 52 s, file size 17.8 → 22.6 MiB.
- **FreeCAD 1.0** is "the first stable release of FreeCAD to feature this new naming algorithm". The wiki says its first purpose is to avoid making things worse, not to fix every case, and recommends datum objects and best practices for robust models. [VERIFIED-secondary: search summary of the wiki; a direct fetch was blocked by bot protection] — [FreeCAD wiki: Topological naming problem](https://wiki.freecad.org/Topological_naming_problem/en); release coverage at [Hackaday 2024-11-20](https://hackaday.com/2024/11/20/freecad-version-1-0-released)

### Inferences
- The FreeCAD approach is the closest existing proof that OCCT's history API is enough to build genealogy names. Its weakest point, ordinal split indices, is exactly where our DSL should refuse to guess and demand a geometric tie-breaker or raise an error.

### Gaps
- I did not verify the FreeCAD source paths for the merged code (`src/App/ElementMap*`, `TopoShapeExpansion.cpp`) or the exact 1.0 release notes. The claims about which feature types remain fragile in 1.0 come from community comments only and are excluded.

---

## Q4. OpenCascade TNaming / OCAF and the history API; build123d

### Takeaway
OCCT provides two layers:
- *OCAF TNaming.* `TNaming_NamedShape` holds old/new shape pairs with an evolution tag. `TNaming_Selector` stores a "name" (a recipe for re-finding a sub-shape) and re-solves it after a rebuild.
- *Raw maker history.* `BRepBuilderAPI_MakeShape::Generated/Modified/IsDeleted` and `BRepTools_History`.

build123d's current docs show a per-operation history record (`Select.LAST`/`Select.NEW`) plus selector provenance (`topo_path`), layered on unordered `ShapeList`s that must be sorted, grouped or filtered.

### Cited Findings
All OCCT findings below are [VERIFIED] from the [OCCT OCAF User Guide](https://dev.opencascade.org/doc/overview/html/occt_user_guides__ocaf.html).
- **Evolution types**
  - "PRIMITIVE – newly created topology, with no previous history".
  - "GENERATED – ... the new shape is created from a low-level old shape (a prism face from an edge, for example)".
  - "MODIFY – the new shape is a modified old shape".
  - "DELETE – the new shape is empty ... the old shape topology is deleted".
  - "SELECTED – ... has no effect on the history".
  - "Only pairs of shapes with equal evolution can be stored in one named shape."
- **TNaming_Selector**
  - Creates "a unique description (data structure) of how to find the selected topology using as resources: the given context shape ... its evolution and naming structure".
  - After rebuild: "it is necessary to call method TNaming_Selector::Solve. If the naming structure ... is correct, the selector automatically updates the selected sub-shape ..., else it fails."
- **Fuse example.** After two boxes are fused, a sub-shape "can be identified unambiguously by name type and set of labels": "face F1' as a modification of face F11", "face F1'' as generation of face F12", "edges as an intersection of two contiguous faces", "vertices as an intersection of three contiguous faces".
- **BRepTools_History** [VERIFIED] — [OCCT reference: BRepTools_History](https://occt3d.com/dev/doc/refman/html/class_b_rep_tools___history.html)
  - Keeps generated, modified and removed relations between input shapes and output shapes.
  - "The relations are kept only for shapes of types vertex, edge, face, and solid."
  - An input cannot be both removed and modified. A removed shape may still generate shapes; in the fillet example an edge generates faces and is then removed.
  - A shape cannot be both generated and modified from the same input.
  - Every output is either an input or derived from one.
  - `Merge()` composes sequential histories (S→T then T→Q gives S→Q).
- **build123d topology selection** [VERIFIED] — [build123d docs: Topology Selection and Exploration (latest)](https://build123d.readthedocs.io/en/latest/topology_selection.html)
  - Selectors return a `ShapeList`, and "a ShapeList from a selector is unordered". Users narrow results with `sort_by`, `group_by` and `filter_by` (plus `>`, `<`, `>>`, `<<` and `|`).
  - **History:** "Every operation — a boolean, a fillet, a chamfer, a 2D fillet, a join of connected edges — keeps a record" that "travels with the shape the operation returns".
  - `Select.LAST` returns features the last operation created or brought in. `Select.NEW` returns "only the features that existed in no input in any form".
  - A shape that no operation produced has no record, and asking it for `Select.LAST` or `Select.NEW` raises an error. The older `new_edges()` compared geometrically.
  - **Provenance:** `topo_path`, `topo_parent` and `topo_owner` record the selection route. Selecting an edge directly from a solid "records no face, so an operation that needs one must say so rather than guess".
  - The page does not discuss topological naming or stability across parameter edits.

### Inferences
- `BRepTools_History` gives a compiler written over build123d/OCP everything it needs to give each entity a "creator feature + role + source" name at compile time, the way FreeCAD does. Composing histories with `Merge` yields a whole-model genealogy.
- The `Select.NEW` and `Select.LAST` record in build123d is a per-step history, not a persistent name across rebuilds, so the DSL must still re-resolve queries on every rebuild.
- The docs page is "latest", so the history and provenance features may postdate older build123d releases. The DSL must pin the version (architecture §7).

### Gaps
- I did not confirm which build123d version introduced `Select.NEW`, the history record or `topo_path`. I also did not check whether every operation build123d wraps (for example offset, loft or sweep) reports history.
- The class pages for `BRepBuilderAPI_MakeShape::Generated/Modified/IsDeleted` were not fetched separately. Those methods are described in the realthunder wiki and are standard OCCT, [VERIFIED-secondary].

---

## Q5. Other approaches (Parasolid/CATIA/SolidWorks, Rossignac, EREP, recent work)

### Takeaway
Commercial kernels mostly handle naming internally, through attributes that carry per-attribute split and merge policies, and the internals are proprietary. I found no openly accessible official Parasolid documentation of attribute split and merge behaviour. The academic roots are Rossignac (1990) and Hoffmann & Juan's EREP (1993). Recent work continues the G-map/graph-rule line (Cardot 2019, a 2024 Jerboa follow-up) and hierarchical naming (a 2023 Chinese paper). I found no credible 2020s machine-learning "TNP" paper.

### Cited Findings
- Rossignac, J.R. (1990). "Issues on feature-based editing and interrogation of solid models." Computers & Graphics 14(2):149–172, DOI 10.1016/0097-8493(90)90029-W. [VERIFIED bibliographic data only]
- Hoffmann, C.M. & Juan, R. (1993). "EREP: an editable high-level representation for geometric design and analysis." Purdue Tech Report CER-92-24. [VERIFIED as cited in Agbodan 2003]
- Agbodan et al. describe EREP as "an unevaluated, high-level, generative, textual representation, independent of any underlying core modeler", which "stores all entities by name". [VERIFIED] — [Agbodan et al. 2003](https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf)
- The analogous attribute-policy pattern, documented for PTC Creo Elements/Direct rather than Parasolid: user-defined attributes have `:on-split` and `:on-merge` options such as `:copy` and `:detach`. CGAL combinatorial-map cell attributes are templated on `OnMerge` and `OnSplit` functors. [VERIFIED-secondary: search snippets] — [PTC user_atts](https://support.ptc.com/help/creo_elements_direct/r20.7.0.0/advanced_documentation/integration_kit/reference/user_atts.html), [CGAL Cell_attribute](https://doc.cgal.org/Manual/4.0/doc_html/cgal_manual/Combinatorial_map_ref/Class_Cell_attribute.html)
- Onshape's `setAttribute` and `qHasAttribute` are the documented attribute mechanism in a production system. [VERIFIED] — [FsDoc](https://cad.onshape.com/FsDoc/library.html)
- Recent work:
  - A 2024 Jerboa/G-map paper tracks only the entities the specification references. [UNVERIFIED: search snippet; the ZCU host was unreachable] — [ZCU B17-2024](https://dspace5old.zcu.cz/bitstream/11025/57384/1/B17-2024.pdf)
  - A 2023 JCAD&CG paper proposes hierarchical naming to resolve reference ambiguity. [UNVERIFIED: snippet] — [jcad.cn](https://www.jcad.cn/cn/article/doi/10.3724/SP.J.1089.2023.2023-00023)
  - Farjana, Han & Mun (2016) apply persistent identification to macro-parametric model exchange, JCDE 3(2):161–177, DOI 10.1016/j.jcde.2016.01.001. [VERIFIED bibliographic data]
  - Marcheix (2005), "A persistent naming of shells", CAD/CG'05, DOI 10.1109/CAD-CG.2005.12. [VERIFIED bibliographic data]
  - Bidarra & Bronsvoort (2002), "Persistent naming through persistent entities", GMP 2002, DOI 10.1109/GMAP.2002.1027515. [VERIFIED bibliographic data]

### Inferences
- Attribute propagation with explicit split and merge policies is a clean model for *named exports* in our DSL. A user-named face carries a tag, and every operation must state what happens to that tag when the face splits or merges: copy to all fragments, or error.

### Gaps
- Parasolid attribute-definition docs (the `PK_ATTDEF` split, merge and transform behaviours) are behind Siemens' licence; not found.
- SolidWorks and CATIA internal persistent IDs are undocumented publicly; not found.
- I found no 2020s ML paper actually titled "Rethinking the topological naming problem". If one exists, I did not locate it.

---

## Q6. Relation to Euler operators and entity genealogy

### Takeaway
Every history mechanism above is an *evolution log* over a small set of event types: create, delete, modify, split, merge. Elementary topological operators map naturally onto these events. Cardot et al. derive naming directly from elementary graph-transformation rules on G-maps (creation, deletion, split, triangulation, extrusion), which is the closest published analogue to "naming via Euler operators". I found no evidence that Kripac's scheme is built on Mäntylä-style Euler operators. It records face-level events.

### Cited Findings
- Kripac's face graph records "creations, splits, merges and deletions of faces". [VERIFIED-secondary via Agbodan 2003] — [PDF](https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf)
- Agbodan's face graph records "creation, split, deletion" per constructive gesture. Each node is a face "which exists or has existed in the model. All the faces without outgoing historical links exist in the geometry." [VERIFIED] — same
- Cardot et al.:
  - "Each modeling operation is formally defined as a rule applied on a G-Map", and Jerboa "ensures by design that the topological consistency ... is maintained after each rule".
  - Orbit evolution types are Creation, Deletion, Fusion, Modification, NoEffect, Split.
  - Persistent ids of darts are derived "using the information returned by transformation rules".
  - "Currently, Jerboa only provides the use of elementary rules, such as object creation or deletion, split of topological entities, triangulation, extrusion". [VERIFIED] — [Cardot et al. 2019](https://www.cad-journal.net/files/vol_16/CAD_16(5)_2019_985-1002.pdf)
- OCCT's evolution enum (PRIMITIVE/GENERATED/MODIFY/DELETE) and `BRepTools_History` (generated/modified/removed) are the same algebra at the B-rep level. [VERIFIED] — see Q4
- Mäntylä's Euler-operator modeler: Mäntylä, M. & Sulonen, R. (1982). "GWB: A Solid Modeler with Euler Operators." IEEE CG&A 2(7):17–31, DOI 10.1109/MCG.1982.1674396. [VERIFIED bibliographic data; content belongs to the sibling Euler-operator notes]
- Parasolid exposes Euler-level operators such as `PK_EDGE_euler_split` and `PK_VERTEX_euler_merge_edges`. [UNVERIFIED: search snippet of a course slide deck] — [SNU slides](https://ocw.snu.ac.kr/sites/default/files/NOTE/4845.pdf)

### Inferences
- Each Euler operator (for example MEV, MEF, KEMR, and their inverses) has an exact birth/death signature: it makes or kills a known number of vertices, edges, faces and loops. If high-level features were compiled to Euler sequences, genealogy would be exact and free, because every entity's birth record would be "the k-th entity made by op j of feature F".
- Industrial kernels (OCCT booleans and fillets) are not exposed as Euler sequences. They report coarse generated/modified/deleted maps, so the DSL inherits coarse genealogy. Splits in particular are reported as "modified into {a, b}" without a canonical order.
- That gap, between exact Euler-level birth records and coarse kernel history, is exactly where tie-breaking rules are needed (see Q7).

### Gaps
- I have no primary source showing a commercial system deriving persistent names from Euler-operator logs. This is an inference, not a documented practice.

---

## Q7. What a DSL must do to make references deterministic

### Takeaway
Combine four layers:
1. **Semantic, history-anchored queries** (creator feature + role + source sketch entity), the "invariant entities".
2. **Geometric predicates** with explicit tolerances and *set-valued* tie semantics.
3. **Mandatory cardinality assertions**, so a query that resolves to the wrong count is a compile error, never a silent "first".
4. **Named exports** with explicit split and merge policies.

Validate them with parameter-perturbation stability tests on a pinned kernel.

### Cited Findings (grounding)
- *Reference only invariant entities.* Invariant entities are characterised "by the structure of a constructive gesture and its input parameters, independently of involved values". [VERIFIED] — [Agbodan 2003](https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf). Bidarra et al. likewise reference persistent *feature* faces. [VERIFIED-secondary] — [TU Delft](https://publications.graphics.tudelft.nl/papers/626)
- *Role queries exist in production.* Onshape's `qCapEntity`, `qNonCapEntity`, `qSplitBy` and `startTracking(sketch, entity)`. Chen names extruded entities "by reference to the corresponding source entity of the extruded 2D contour and the constructive gesture". [VERIFIED] — [FsDoc](https://cad.onshape.com/FsDoc/library.html), [Agbodan 2003](https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf)
- *Positional and evaluation order are unsafe.* Onshape documents that order is "deterministic but arbitrary". build123d says `ShapeList`s are unordered. FreeCAD's split index depends on OCCT's reporting order and, in the wiki's example, made a fillet move to the other edge. [VERIFIED] — see Q2–Q4
- *Ties must be set-valued.* `qClosestTo`, `qFarthestAlong` and `qLargest` return all entities within tolerance on a tie. [VERIFIED] — [FsDoc](https://cad.onshape.com/FsDoc/library.html)
- *Never silently take the first.* Onshape does exactly this for single-entity parameters: it "takes the first resolved entity". This is a documented hazard. [VERIFIED] — [FsDoc](https://cad.onshape.com/FsDoc/library.html)
- *Fail rather than guess.* `TNaming_Selector::Solve` "else it fails". FreeCAD raises an invalid-link error and leaves guessing to the user. build123d provenance says an operation that needs a face "must say so rather than guess". [VERIFIED] — see Q3–Q4
- *Approximate matches poison later steps.* Kripac cannot record that a mapping "was only approximated". [VERIFIED] — [Agbodan 2003](https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf)
- *Ids must mirror history.* Onshape requires each `Id` to cover a contiguous region of operations, and supports `unstableIdComponent` for loop indices. [VERIFIED] — [FsDoc](https://cad.onshape.com/FsDoc/library.html)

### Inferences (recommendations; see the full list below)
- See the "Recommendations for our DSL" section.

### Gaps
- No source I found gives a formal stability test methodology (parameter perturbation). That recommendation is my own engineering inference, motivated by the reevaluation scenarios in Agbodan and Cardot.

---

## Comparison table of naming approaches

| Approach | Mechanism | Strengths | Failure modes | Source |
|---|---|---|---|---|
| Kripac 1997 (Topological ID System) | Face history graph (create/split/merge/delete) plus a correspondence table; global matching by topological neighbourhood | Global matching; handles one-to-many maps | Wrong matching under splits (Fa↔Fy swap); "piece loss" in the graph search; cannot record approximate matches; stores a model copy per step | Agbodan 2003 critique [VERIFIED-secondary] |
| Chen / Capoyleas / Hoffmann 1995–96 (generic naming, EREP) | Name = creating gesture + source entity, plus minimal topological context plus feature orientation; threshold-based matching | Introduced topological context and orientation as name parts; detailed ambiguity analysis | Unexplained thresholds; local matching; sensitive to how the neighbourhood is subdivided; limited to sweep, blend and fillet; breaks under symmetry | Agbodan 2003 [VERIFIED-secondary] |
| Agbodan/Marcheix/Pierra 2003 | Invariant vs. contingent entities; face graph; weighted neighbourhood with global per-step matching | Separates structural (invariant) names from collision (contingent) ones | Contingent entities still need heuristic matching | Agbodan 2003 [VERIFIED] |
| Bidarra/Nyirenda/Bronsvoort 2005 | Reference persistent *feature* faces instead of boundary faces; declarative feature model | Avoids most of the boundary-naming problem | Needs a semantic feature model, not a plain B-rep history | TU Delft abstract [VERIFIED-secondary] |
| Cardot et al. 2019 (Jerboa/G-maps) | Persistent ids of darts derived from graph-rule application; evolution types Creation/Deletion/Fusion/Modification/NoEffect/Split; tracks only referenced entities | Dimension-independent; formal; low overhead | Only elementary rules so far; bulletin boards written by hand | Cardot 2019 [VERIFIED] |
| OCCT TNaming/OCAF | NamedShape old/new pairs with evolution (PRIMITIVE/GENERATED/MODIFY/DELETE/SELECTED); Selector name with `Solve()` | Kernel-native; names intersection edges and vertices by their adjacent faces | `Solve` fails if the name is invalid; requires an OCAF document framework | OCCT OCAF guide [VERIFIED] |
| FreeCAD 1.0 / realthunder | Mapped element names from OCCT maker history (`;:M`/`;:G`, index, opcode, tag) | Works across all Part operations; traceable genealogy | Split index follows OCCT's reporting order; long names; ~30% recompute overhead in one test; invalid link on disappearance | realthunder wiki [VERIFIED] |
| Onshape FeatureScript | Hierarchical Ids, lazy queries, `qCreatedBy` with split/merge rules, cap/non-cap roles, tracking queries, attributes | Precise semantics; role queries; set-valued ties | `qNthElement` and evaluation order are arbitrary; single-entity parameters silently take the first | FsDoc [VERIFIED] |
| build123d (CadQuery-like) | Geometric selectors plus sort/group/filter, plus a per-operation history record (`Select.LAST`/`NEW`) and `topo_path` provenance | Concise; expressive geometric predicates | Lists are unordered; positional indexing after a sort can change when topology changes; no persistent names across rebuilds | build123d docs [VERIFIED] |
| Attribute propagation (Parasolid, Creo Elements/Direct, CGAL) | Tags on entities with per-attribute on-split and on-merge policies | Explicit user-defined names survive operations | Policy is needed for every event; Parasolid specifics are closed | PTC/CGAL [VERIFIED-secondary]; Parasolid [UNVERIFIED] |

---

## Recommendations for our DSL

1. **Primary references are semantic and history-anchored.** For example `E.cap(END)`, `E.side(from=sketch.edge("top"))`, `F.faces_created()` or `B.split(front)`. They resolve through the OCCT history API (`BRepBuilderAPI_MakeShape::Generated/Modified/IsDeleted`, composed with `BRepTools_History::Merge`), and the DSL records them as (feature id, role, source) triples. *Grounding:* invariant entities (Agbodan 2003); Onshape `qCapEntity`, `qNonCapEntity`, `startTracking`; FreeCAD's use of OCCT history.
2. **Feature ids are hierarchical, deterministic and history-shaped,** following Onshape's contiguity rule. Generated sub-ids such as pattern instances or loop indices are marked unstable and never referenced positionally. *Grounding:* FsDoc `Id` and `unstableIdComponent`.
3. **Geometric predicates are second-class but allowed,** for example `plate.face(normal=-Y)`. Each predicate has an explicit tolerance and is set-valued on ties: it never picks "the first". If a predicate is used to break a tie, the DSL requires a total order with a stated tolerance, for example "farthest along +X, then +Y". *Grounding:* Onshape tie semantics; arch. §7 "no float-sensitive tie-breaking without explicit tolerance rules".
4. **Every query declares its expected cardinality,** as `exactly(n)`, `at_least(n)` or `one()`. Any mismatch is a compile error that names the query, the candidate set and the creating feature. No silent "first resolved", and no ordinal indices. *Grounding:* the Onshape first-entity hazard; TNaming `Solve` failing; FreeCAD's invalid link; build123d's "must say so rather than guess".
5. **Named exports are attributes with a policy.** A skeleton's exported `mount_face` is tagged when it is created. Each downstream operation applies a split/merge policy (`propagate_all`, `error_on_split`, `error_on_merge`). On rebuild, the export resolves only if the policy is satisfied. *Grounding:* attribute split/merge policies (PTC, CGAL); Onshape `setAttribute`/`qHasAttribute`; Bidarra's persistent feature faces.
6. **Never reference contingent entities by identity.** Fragments created by later collisions are reached only through a predicate over a semantic parent, for example "the fragment of `E.cap(END)` nearest point p, exactly one". Never through a stored index. *Grounding:* Agbodan's invariant/contingent distinction; Kripac's swap failure.
7. **Stability tests.** For each solution, perturb every design parameter (±ε and across its declared range), rebuild, and assert that every query keeps its cardinality and that its resolved entity keeps the same (feature, role, source) genealogy. Flag any reference whose resolution changes. *Grounding:* the reevaluation scenarios in Agbodan Fig. 1 and Cardot Fig. 1. The methodology itself is my inference.
8. **Pin the kernel and the library.** Pin the OCCT version (history ordering can differ between versions) and the build123d version (history and provenance features are recent). Record both with every solution. *Grounding:* arch. §7; FreeCAD's split order depends on OCCT's reporting.
9. **Compiling to FeatureScript.** Map semantic references to `qCreatedBy`, `qCapEntity`, `qNonCapEntity`, `startTracking` and `qHasAttribute`. Emit `evaluateQueryCount` checks before single-entity parameters, and never emit `qNthElement`. *Grounding:* FsDoc.

---

## Reference list

Primary literature. DOIs confirmed via Crossref.
- Kripac, J. (1997). A mechanism for persistently naming topological entities in history-based parametric solid models. *Computer-Aided Design* 29(2):113–122. https://doi.org/10.1016/S0010-4485(96)00040-1. Conference version: *Proc. 3rd ACM SMA* (1995) 21–30, https://doi.org/10.1145/218013.218024
- Chen, X. & Hoffmann, C.M. (1995). Towards feature attachment. *Computer-Aided Design* 27(9):695–702. https://doi.org/10.1016/0010-4485(94)00027-B
- Chen, X. & Hoffmann, C.M. (1995). On editability of feature-based design. *Computer-Aided Design* 27(12):905–914. https://doi.org/10.1016/0010-4485(95)00013-5
- Capoyleas, V., Chen, X. & Hoffmann, C.M. (1996). Generic naming in generative, constraint-based design. *Computer-Aided Design* 28(1):17–26. https://doi.org/10.1016/0010-4485(95)00014-3
- Marcheix, D. & Pierra, G. (2002). A survey of the persistent naming problem. *Proc. 7th ACM SMA*, 13–22. https://doi.org/10.1145/566282.566288
- Bidarra, R. & Bronsvoort, W.F. (2002). Persistent naming through persistent entities. *GMP 2002*, 233–240. https://doi.org/10.1109/GMAP.2002.1027515
- Bidarra, R., Nyirenda, P.J. & Bronsvoort, W.F. (2005). A feature-based solution to the persistent naming problem. *Computer-Aided Design & Applications* 2(1–4):517–526. https://doi.org/10.1080/16864360.2005.10738401
- Wu, J., Zhang, T., Zhang, X. & Zhou, J. (2001). A face based mechanism for naming, recording and retrieving topological entities. *Computer-Aided Design* 33(10):687–698. https://doi.org/10.1016/S0010-4485(00)00099-3
- Agbodan, D., Marcheix, D., Pierra, G. & Thabaud, C. (2003). A topological entity matching technique for geometric parametric models. *Shape Modeling International 2003*, 235–244. https://doi.org/10.1109/SMI.2003.1199623. Full text: https://www.lias-lab.fr/publications/7076/2003-ICSMA-AGBODAN.pdf
- Marcheix, D. (2005). A persistent naming of shells. *CAD/CG'05*, 259–268. https://doi.org/10.1109/CAD-CG.2005.12
- Baba-ali, M., Marcheix, D. & Skapin, X. (2009). An edge matching technique for non-planar face intersections in geometric parametric models. *IEEE SMI 2009*, 201–208. https://doi.org/10.1109/SMI.2009.5170149
- Cardot, A., Marcheix, D., Skapin, X., Arnould, A. & Belhaouari, H. (2019). Persistent naming based on graph transformation rules to reevaluate parametric specification. *Computer-Aided Design & Applications* 16(5):985–1002. https://doi.org/10.14733/cadaps.2019.985-1002 (open access PDF: https://www.cad-journal.net/files/vol_16/CAD_16(5)_2019_985-1002.pdf)
- Farjana, S.H. & Han, S. (2018). Mechanisms of persistent identification of topological entities in CAD systems: a review. *Alexandria Engineering Journal* 57(4):2837–2849. https://doi.org/10.1016/j.aej.2018.01.007
- Farjana, S.H., Han, S. & Mun, D. (2016). Implementation of persistent identification of topological entities based on macro-parametrics approach. *J. Computational Design and Engineering* 3(2):161–177. https://doi.org/10.1016/j.jcde.2016.01.001
- Rossignac, J.R. (1990). Issues on feature-based editing and interrogation of solid models. *Computers & Graphics* 14(2):149–172. https://doi.org/10.1016/0097-8493(90)90029-W
- Hoffmann, C.M. & Juan, R. (1993). EREP: an editable high-level representation for geometric design and analysis. Purdue University Tech. Report CER-92-24. No DOI; see also Hoffmann, "EREP Project Overview", *CAD Systems Development* (1997), https://doi.org/10.1007/978-3-642-60718-9_3
- Mäntylä, M. & Sulonen, R. (1982). GWB: A solid modeler with Euler operators. *IEEE CG&A* 2(7):17–31. https://doi.org/10.1109/MCG.1982.1674396

Official documentation and design write-ups
- Onshape FeatureScript Standard Library (query.fs, Id, attributes, tracking): https://cad.onshape.com/FsDoc/library.html (accessed 2026-11-15)
- OCCT OCAF User Guide (TNaming section): https://dev.opencascade.org/doc/overview/html/occt_user_guides__ocaf.html
- OCCT reference, BRepTools_History: https://occt3d.com/dev/doc/refman/html/class_b_rep_tools___history.html
- build123d, Topology Selection and Exploration (latest): https://build123d.readthedocs.io/en/latest/topology_selection.html
- realthunder, Topological Naming Algorithm (GitHub wiki): https://github.com/realthunder/FreeCAD_assembly3/wiki/Topological-Naming-Algorithm
- FreeCAD wiki, Topological naming problem: https://wiki.freecad.org/Topological_naming_problem/en
- PTC Creo Elements/Direct, User-Defined Attributes: https://support.ptc.com/help/creo_elements_direct/r20.7.0.0/advanced_documentation/integration_kit/reference/user_atts.html

---

## Explicit list of UNVERIFIED or partially verified items

1. **Kripac (1997) content.** The full text was not read. The abstract was seen only via a bibliographic record, and the mechanism comes from Agbodan's description.
2. **Chen–Hoffmann and Capoyleas content.** Known only through Agbodan's description; the full texts were not read.
3. **Marcheix & Pierra (2002) survey content.** Only the bibliographic data is confirmed; the abstract and text were not seen.
4. **Bidarra et al. (2005).** The abstract is known only through a search summary, because the TU Delft PDF host was unreachable.
5. **Wu et al. (2001) and Farjana & Han (2018).** Only the bibliographic data is verified; their content and classification were not read.
6. **Rossignac (1990) and Hoffmann & Juan EREP (1993).** Only the bibliographic data and citations are verified, not their content.
7. **FreeCAD 1.0 wiki statements.** Seen only via a search summary (the site blocked fetching). The details of the FreeCAD-merged code and release notes were not checked.
8. **Parasolid attribute split/merge behaviour (`PK_ATTDEF`) and SolidWorks/CATIA persistent IDs.** No official source found.
9. **Parasolid Euler functions (`PK_EDGE_euler_split` etc.).** Seen only in a search snippet of a university slide deck.
10. **2024 Jerboa follow-up (ZCU) and 2023 JCAD&CG hierarchical naming paper.** Search snippets only; the hosts were unreachable or not fetched.
11. **2020s "Rethinking the topological naming problem" / ML work.** Not found. It may not exist.
12. **Onshape internal naming algorithm or blog write-up.** Not found. Only the FeatureScript API semantics are verified.
13. **build123d.** Which release introduced the history record and `topo_path`, and whether all operations report history, is not verified.
14. **"`qNthElement` is discouraged".** Not stated in the docs. The docs say only that the order is "deterministic but arbitrary". The discouragement is an inference.
15. **Stability-test methodology (Recommendation 7).** My own inference; no source found that prescribes it.

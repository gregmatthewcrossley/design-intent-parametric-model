# From-scratch generative models for parametric CAD, and lessons for a neutral sketch+feature DSL

Compiled 2026-11-15. Repo metadata (licenses, stars, last push) was pulled from the GitHub API on that date. Items marked **[unverified this session]** come from the researcher's prior knowledge of the primary paper and were not re-fetched; check them before relying on them. Everything else has a source fetched or searched in this session.

---

## 1. What each from-scratch work contributed (venue/year, representation, architecture, data, results, code/license, limits)

### Takeaway
The lineage runs along two tracks. The first generates **construction sequences**: sketch-and-extrude (DeepCAD to SkexGen to HNC-CAD to TransCAD/GenCAD) and constrained 2D sketches (SketchGraphs to SketchGen / CAD-as-Language / Vitruvion to AutoConstrain). The second generates **B-reps directly** (SolidGen to BrepGen to DTGBrepGen/BrepDiff/HoLa/BrepGPT to AutoBrep/BrepARG to ParaCAD/TG-Diff in 2026). Sequence models produce editable but expressively narrow (sketch+extrude) output. B-rep models cover free-form geometry but produce dumb solids with no feature history or constraints. Almost all released code and weights are **non-commercial** (GPL-for-research + no-commercial clause, CC BY-NC, or CC BY-NC-SA). DeepCAD, SkexGen, SketchGraphs, BrepDiff and AutoBrep are the main MIT exceptions.

### Cited Findings

**Sequence track (sketch + extrude)**
- **DeepCAD** (Wu, Xiao, Zheng; ICCV 2021). There are 6 command types (line, arc, circle, loop start, extrude, EOS). Each command carries a fixed 16-slot parameter vector [x, y, α, f, r, θ, φ, γ, px, py, pz, s, e1, e2, b, u], with unused slots set to −1. Sequences are padded to 60 commands, shapes are normalized to a 2×2×2 cube, and continuous parameters are quantized to 256 levels (8-bit) — [DeepCAD paper (ar5iv)](https://ar5iv.labs.arxiv.org/html/2105.09492)
  - Dataset: 178,238 sketch+extrude models from the Onshape models behind ABC. Designs with any other operation were discarded. Split 90/5/5 — [DeepCAD](https://ar5iv.labs.arxiv.org/html/2105.09492)
  - Architecture: a non-autoregressive Transformer autoencoder (4 layers, 8 heads, 256-d latent) plus a latent WGAN-GP for generation. Trained 1000 epochs at batch size 512 — [DeepCAD](https://ar5iv.labs.arxiv.org/html/2105.09492)
  - Results: autoencoding ACC_cmd 99.50%, ACC_param 97.98% (within 3 quantization levels), median CD 0.752×10⁻³, invalid 2.72%. A regression (unquantized) variant was worse (CD 2.142, invalid 4.32%), which supports quantizing parameters. Generation COV 78.13, MMD 1.45, JSD 3.76 — [DeepCAD](https://ar5iv.labs.arxiv.org/html/2105.09492)
  - Limits stated by the authors: only line/arc/circle (about 92% of curves); fillet etc. left out because they need B-rep references; "cannot guarantee topological soundness"; failure rises with sequence length — [DeepCAD](https://ar5iv.labs.arxiv.org/html/2105.09492)
  - Code: MIT, about 843 stars, last push 2024-04 (repo now at rundiwu/DeepCAD) — [GitHub API](https://github.com/ChrisWu1997/DeepCAD)
- **SkexGen** (Xu et al.; ICML 2022). An autoregressive Transformer with disentangled codebooks for topology, geometry and extrude. Code is MIT (about 149 stars, last push 2023-05) — [GitHub](https://github.com/samxuxiang/SkexGen). Representation details (quantized sketch/extrude tokens, three VQ codebooks, trained on DeepCAD data) are **[unverified this session]**.
- **HNC-CAD, Hierarchical Neural Coding** (Xu et al.; ICML 2023). A three-level tree of neural codes (global part arrangement down to local curve geometry). It uses a VQ-VAE variant with "masked skip connection" and two cascaded autoregressive transformers, which enables conditional generation and CAD autocompletion — [arXiv 2307.00149](https://arxiv.org/abs/2307.00149). Its license forbids commercial use; research use follows GPL v3 — [hnc-cad LICENSE](https://github.com/samxuxiang/hnc-cad)
- **TransCAD** (Dupont, Cherenkova, Mallis, Gusev, Kacem, Aouada; ECCV 2024). An end-to-end hierarchical transformer that infers a CAD sequence from a point cloud. The decoder works in two layers (sequence-level, then loop/op-level) and adds a "loop refiner" that regresses sketch primitive parameters. Evaluated on DeepCAD and Fusion360. It proposes a new metric, mean Average Precision of CAD Sequence — [ECVA](https://ecva.net/papers/eccv_2024/papers_ECCV/html/7791_ECCV_2024_paper.php), [arXiv 2407.12702](https://bohrium.dp.tech/paper/arxiv/2407.12702). No official code repo was found. Note: the GitHub repo "Macro-parametrics/TransCAD" is an unrelated older neutral CAD translator (see §5).
- **GenCAD** (Alam & Ahmed; TMLR 2025). Image-conditioned CAD sequence generation with a contrastive representation and diffusion priors, on the DeepCAD command format. Code, data and checkpoints are released, but the repo has **no license file** (about 3.9k stars) — [GitHub](https://github.com/ferdous-alam/GenCAD)
- **Text2CAD** (Khan et al.; NeurIPS 2024 spotlight). Text-to-sequence on DeepCAD-style sequences. Code is under a "Text2CAD Community License", CC BY-NC-SA 4.0 — [GitHub](https://github.com/SadilKhan/Text2CAD)
- **CAD-Recode** (ICCV 2025). Point cloud to CadQuery Python code. This is an LLM fine-tune, not trained from scratch, but it marks the shift from token DSLs to code. License is CC BY-NC 4.0 — [GitHub](https://github.com/filaPro/cad-recode)

**Sketch / constraint track**
- **SketchGraphs** (Seff et al.; ICML 2020 workshop). Described as "a dataset of 15 million CAD sketches with geometric constraint graphs" (from Onshape). Code is MIT; last push 2021 — [GitHub](https://github.com/PrincetonLIPS/SketchGraphs)
- **Vitruvion** (Seff, Zhou, Richardson, Adams; ICLR 2022). Autoregressive generation of primitives, then constraints that reference earlier primitives. Outputs match CAD constraint graphs and "may be directly imported, solved, and edited". It can be conditioned on partial sketches and hand-drawn images. Trained on SketchGraphs — [arXiv 2109.14124](https://arxiv.org/abs/2109.14124). The repo has code, data and model download scripts but **no LICENSE file** — [GitHub](https://github.com/PrincetonLIPS/vitruvion)
- **SketchGen** (Para et al.; NeurIPS 2021). Generates constrained CAD sketches. The repo exists, with no license and a minimal README — [GitHub](https://github.com/wamiq-reyaz/sketchgen)
- **Computer-Aided Design as Language** (Ganin, Bartunov, Li, Keller, Saliceti; NeurIPS 2021). A general language model over sketches serialized with "an off-the-shelf data serialization protocol". Evaluated on unconditional synthesis and image-to-sketch — [arXiv 2105.02769](https://arxiv.org/abs/2105.02769). The following details are **[unverified this session]**: protobuf serialization, an Onshape dataset of about 4.7M sketches, a Transformer with pointer outputs for constraint references, and that the dataset and code were not publicly released by DeepMind.
- **AutoConstrain / design alignment** (Casey et al., Autodesk; ICCV 2025). Starts from Vitruvion and applies RL and preference optimization with a constraint solver as the reward. RLOO and GRPO fully constrain 93.05% and 91.59% of sketches, versus 8.87% for the base model and 34.24% for SFT, with fewer over-constrained or unsolvable sketches — [arXiv 2504.13178](https://arxiv.org/abs/2504.13178), [Autodesk Research](https://www.research.autodesk.com/?p=6753)

**Datasets / environments**
- **Fusion 360 Gallery Dataset** (Willis et al.; SIGGRAPH 2021). The Dataset License allows use "only for non-commercial research purposes" — [LICENSE.md](https://github.com/AutodeskAILab/Fusion360GalleryDataset). The reconstruction subset has about 8,625 sketch+extrude sequences plus the Fusion 360 Gym environment for program synthesis via interactive reconstruction **[counts unverified this session]**.
- **ABC-1M (deduplicated)** is released on Hugging Face by Autodesk and used to train AutoBrep — [AutoBrep README](https://github.com/AutodeskAILab/AutoBrep)
- **BRepNet** (Autodesk) code is CC BY-NC-SA 4.0. **JoinABLe** has a LICENSE file whose text could not be decoded in this session — [BRepNet](https://github.com/AutodeskAILab/BRepNet)

**Direct B-rep track**
- **SolidGen** (Jayaraman et al.; TMLR Feb 2023, arXiv Mar 2022). Introduces the "Indexed Boundary Representation", which references vertices, edges and faces in a hierarchy. Autoregressive Transformers with pointer networks predict vertices, then edges, then faces, with no sketch-extrude supervision. It can be conditioned on class, image or voxels — [arXiv 2203.13944](https://arxiv.org/abs/2203.13944). No official code was found. Restriction to prismatic/analytic surfaces is **[unverified this session]**.
- **BrepGen** (Xu et al.; SIGGRAPH 2024). Diffusion over a hierarchical tree of faces, edges and vertices. Each node holds a bounding box and a latent shape code. Topology is implicit in duplicated nodes, which are detected and merged. Claimed first to handle free-form and doubly-curved surfaces. Contributes a new furniture dataset — [arXiv 2401.15563](https://arxiv.org/abs/2401.15563). License: no commercial use; GPL v3 for research (code, data, weights) — [BrepGen LICENSE](https://github.com/samxuxiang/BrepGen)
- **DTGBrepGen** (Li et al.; CVPR 2025). Decouples topology and geometry. Transformers generate edge-face and edge-vertex adjacency, then geometry is generated as B-spline control points. Trained on 4×A800 80GB for about 3 days per dataset. Pretrained weights are on Google Drive; the repo has **no license** — [GitHub](https://github.com/jinli99/DTGBrepGen)
- **BrepDiff** (SIGGRAPH 2025). Code is MIT — [GitHub](https://github.com/brepdiff/brepdiff). **HoLa** (ACM TOG 44(4) 2025), **BrepGPT** (Voronoi half-patch; ACM TOG 44(6) 2025) and **BrepGiff** (CVPR 2025) are listed in BrepARG's related work — [BrepARG](https://arxiv.org/html/2601.16771v2). TG-Diff reports that HoLa had no public code — [TG-Diff](https://arxiv.org/html/2607.21928)
- **AutoBrep** (Xu, Jayaraman, Lambourne, Liu, Malpure, Meltzer; SIGGRAPH Asia 2025; arXiv Dec 2025). A decoder-only Transformer generates one unified token sequence. Geometry is encoded as bounding boxes plus FSQ-encoded UV-grid shape codes, topology as reference tokens, in BFS order over the face adjacency graph. It supports autocompletion and a complexity control (easy/medium/hard). Trained on ABC-1M. Code is **MIT** and checkpoints are on Hugging Face — [GitHub](https://github.com/AutodeskAILab/AutoBrep), [arXiv 2512.03018](https://arxiv.org/abs/2512.03018)
- **BrepARG** (arXiv 2601.16771, v2 Mar 2026). Uses a holistic token sequence:
  - Tokens: faces sampled on a 32×32 UV grid and edges at 32 points go through a shared VQ-VAE (4 codes each; codebook 4,096 for DeepCAD, 8,192 for ABC). Bounding boxes are quantized to 2,048 levels per coordinate. Face-index tokens carry topology. Faces are ordered by DFS. Face blocks are 11 tokens and edge blocks 12.
  - Architecture: an 8-layer, 256-d decoder-only Transformer.
  - Validity: DeepCAD 87.60% versus DTGBrepGen 79.80%, BrepGen 68.23%, BrepDiff 62.83%, DeepCAD 58.10%. ABC 67.54% versus DTGBrepGen 57.59%.
  - Source: [arXiv 2601.16771v2](https://arxiv.org/html/2601.16771v2). Code at github.com/123qiang06/BrepARG (license not checked).
- **TG-Diff** (arXiv 2607.21928, July 2026). D3PM discrete diffusion over the surface adjacency matrix, then a topology-conditioned DiT over 16×16 UV-grid surface latents. Edges and vertices are recovered by surface intersection, with fitting to analytic surfaces or B-splines — [arXiv 2607.21928](https://arxiv.org/html/2607.21928). Unconditional results:

  | Method | DeepCAD COV | DeepCAD Valid | ABC Valid |
  |---|---|---|---|
  | TG-Diff | 77.9 | 85.6% | 61.4% |
  | DTGBrepGen | 73.9 | 75.6% | 52.9% |
  | BrepDiff | 73.5 | 59.3% | 30.1% |
  | BrepGen | 71.7 | 50.5% | 41.4% |
- **ParaCAD** (Qin et al.; arXiv 2607.17093, July 2026). Point-cloud-conditioned autoregressive B-rep generation with "surface-centric tokenization". Each face is tokenized by exact surface type and continuous parameters with a constrained UV domain. Edges and vertices are recovered by surface intersection. Claims better precision and watertightness than point-sampled baselines — [arXiv 2607.17093](https://arxiv.org/abs/2607.17093)
- Other 2026 items found but not read: "Towards Valid B-Rep Generation: Training-Free Wireframe Anomaly Detection and Repair" (arXiv 2608.04955); "Learn the Solid, Not the File" (arXiv 2609.11573); CADENA stepwise reverse engineering (arXiv 2608.00799) — [search results](https://arxiv.org/html/2608.04955v1), [2609.11573](https://arxiv.org/pdf/2609.11573), [2608.00799](https://arxiv.org/pdf/2608.00799)
- **Surveys:** "Geometric Deep Learning for CAD: A Survey" (Heidari & Iosifidis, arXiv 2402.17695, v2 Jul 2025) — [arXiv](https://arxiv.org/pdf/2402.17695). "A Survey on Deep Learning in 3D CAD Reconstruction" (Applied Sciences 15(12), Jun 2025) notes that generation models use extrusion operations "to avoid the direct generation of B-rep" — [MDPI](https://mdpi.com/2076-3417/15/12/6681)

### Inferences
- The field has largely moved its from-scratch effort to direct B-rep generation (2024 to 2026), with validity on DeepCAD-scale data now about 85–88%. Sequence-from-scratch research has mostly been overtaken by LLM-to-code approaches (CAD-Recode, Text2CAD, etc.).
- Validity numbers are not comparable across papers. BrepGen's validity is 68.23% in the BrepARG paper and 50.5% in the TG-Diff paper; the difference comes from different validity checks and post-processing.

### Gaps
- Exact metrics for SkexGen, HNC-CAD, Vitruvion, SolidGen and CAD-as-Language were not fetched (only abstract pages were reachable). AutoBrep's numbers were not in its abstract.
- The licenses of BrepARG, JoinABLe and TransCAD were not confirmed. No TransCAD (ECCV) or SolidGen official code was found.

---

## 2. Tokenization / representation, and limits of sketch-and-extrude

### Takeaway
Sequence models use a small command vocabulary with fixed-width parameter slots, quantized to 8 bits (256 levels) in a normalized frame. B-rep models quantize bounding boxes (up to 2,048 levels) and compress surface and curve shape with VQ or FSQ codes over UV grids. Sketch+extrude-only representations exclude fillets, chamfers, shells, patterns, revolves and sweeps, because those operations need references to B-rep entities that do not yet exist in the token stream.

### Cited Findings
- DeepCAD's 16-slot parameter vector (with −1 for unused slots), 256-level quantization, 60-command cap and 2×2×2 normalization; quantized beats regressed parameters (CD 0.752 versus 2.142) — [DeepCAD](https://ar5iv.labs.arxiv.org/html/2105.09492)
- DeepCAD's data excluded every model that used anything beyond sketch+extrude. The authors explicitly defer fillets because they "need B-rep reference" — [DeepCAD](https://ar5iv.labs.arxiv.org/html/2105.09492)
- Survey observation: generation models use extrusion "to avoid the direct generation of B-rep" — [MDPI survey](https://mdpi.com/2076-3417/15/12/6681)
- B-rep tokenization choices:
  - BrepARG: 2,048-level bounding-box quantization plus VQ codes over 32×32 UV grids — [BrepARG](https://arxiv.org/html/2601.16771v2)
  - AutoBrep: FSQ shape codes plus bounding boxes plus topology reference tokens in BFS order — [AutoBrep](https://github.com/AutodeskAILab/AutoBrep)
  - ParaCAD: exact analytic surface type plus continuous parameters, which avoids lossy point grids — [ParaCAD](https://arxiv.org/abs/2607.17093)
  - BrepGen: duplicated-node implicit topology — [BrepGen](https://arxiv.org/abs/2401.15563)
- Longer sequences fail more often, and the long-tailed length distribution biases models toward short, simple parts — [DeepCAD](https://ar5iv.labs.arxiv.org/html/2105.09492)

### Inferences
- A DSL that wants fillet, chamfer, shell or pattern needs a way to reference generated topology: by query (e.g., "edges created by feature 3 that are convex") rather than by index. Learned token streams have so far avoided this problem rather than solved it.
- Grid/VQ geometry codes lose exact analytic intent (a cylinder becomes an approximately cylindrical patch). ParaCAD's 2026 return to exact surface types suggests kernel-native primitives are worth keeping in a DSL.

### Gaps
- No primary-source quantification found of what fraction of real-world Onshape/Fusion models use non-extrude features. DeepCAD says only that such models were discarded, without the discard rate in the fetched text.

---

## 3. Constraints and design intent

### Takeaway
Only the 2D-sketch line of work (SketchGraphs, SketchGen, CAD-as-Language, Vitruvion, AutoConstrain) generates or infers geometric and dimensional constraints. The 3D sequence models (DeepCAD and successors) and all B-rep generators output fixed coordinates with no constraints. Constraints are represented as a graph: primitives are nodes and constraints are (hyper)edges referencing earlier primitives by pointer.

### Cited Findings
- SketchGraphs frames sketches as geometric constraint graphs (15M from Onshape) — [SketchGraphs](https://github.com/PrincetonLIPS/SketchGraphs)
- Vitruvion generates primitives first, then constraints that point to earlier primitives. The output imports into CAD software and can be "solved, and edited" — [Vitruvion](https://arxiv.org/abs/2109.14124)
- Under supervised training alone, the Vitruvion base model fully constrains only 8.87% of sketches (SFT 34.24%). Solver-feedback RL raises this to about 92–93%. Autodesk calls the problem of matching design intent under edits "design alignment" and treats it as open — [arXiv 2504.13178](https://arxiv.org/abs/2504.13178)

### Inferences
- In real data, sketches are mostly under-constrained, so imitation learning reproduces under-constraint. A solver in the loop (as reward or validation) is the proven fix. A DSL should make the "fully constrained / DOF remaining" status checkable at compile time.

### Gaps
- No from-scratch 3D sequence model was found that generates feature-level design intent (references, equations, configurations) beyond sketch constraints.

---

## 4. Robustness to parameter edits (edit stability)

### Takeaway
Direct evidence is thin. The only quantitative work found measures sketch constraint completeness and solvability (AutoConstrain). No paper found benchmarks whether generated 3D feature models rebuild validly when their parameters are perturbed.

### Cited Findings
- AutoConstrain reports fewer over-constrained or unsolvable sketches and stable geometry after alignment, and ran a professional-designer human study comparing constraint quality across variants — [arXiv 2504.13178](https://arxiv.org/abs/2504.13178), [Autodesk Research](https://www.research.autodesk.com/?p=6753)
- DeepCAD's sequence outputs have a 2.7–3.3% invalid rate even in reconstruction, with no topological guarantee — [DeepCAD](https://ar5iv.labs.arxiv.org/html/2105.09492)
- B-rep generators report 50–88% validity on DeepCAD and 41–67% on ABC, and are not editable parametrically at all — [TG-Diff](https://arxiv.org/html/2607.21928), [BrepARG](https://arxiv.org/html/2601.16771v2)

### Inferences
- An "edit-stability" metric (perturb each parameter by ±k%, rebuild, then check validity, topology preservation and reference survival) is an open benchmark opportunity. It would be a distinctive evaluation for a DSL-based system.

### Gaps
- No primary source found for a 3D re-parameterization robustness benchmark of generated CAD.

---

## 5. Practical guidance for a kernel-neutral sketch+feature DSL

### Takeaway
The models suggest four practices: keep a small typed command vocabulary with quantized/normalized parameters; reference earlier entities by ID or pointer; add solver/kernel-in-the-loop validation; and avoid index-based topological references. Commercial-friendly reuse of the learned artifacts is mostly blocked by NC licenses. Neutral CAD exchange via "macro" command sets (the earlier TransCAD/MPA project) is a precedent for a vendor-neutral feature language.

### Cited Findings
- **Fixed-width parameter slots with an unused sentinel** work well for learning: DeepCAD reaches 99.5% command and 98% parameter accuracy — [DeepCAD](https://ar5iv.labs.arxiv.org/html/2105.09492)
- **Pointer references to earlier entities** are used both for sketch constraints (Vitruvion) and for B-rep topology (SolidGen's indexed B-rep; AutoBrep's topology reference tokens) — [Vitruvion](https://arxiv.org/abs/2109.14124), [SolidGen](https://arxiv.org/abs/2203.13944), [AutoBrep](https://github.com/AutodeskAILab/AutoBrep)
- **Code as the DSL:** CAD-Recode targets CadQuery Python, which rides on OpenCascade — [CAD-Recode](https://github.com/filaPro/cad-recode)
- **Kernel tooling:** DTGBrepGen and other Autodesk-lineage repos depend on OCCWL, Autodesk's OpenCascade wrapper — [DTGBrepGen README](https://github.com/jinli99/DTGBrepGen)
- **Neutral feature exchange precedent:** TransCAD (Macro-Parametrics Approach) translates models between commercial CAD systems using "macro files", i.e., per-system modeling-command sets. It is built on the commercial ACIS/HOOPS kernels — [Macro-parametrics/TransCAD](https://github.com/Macro-parametrics/TransCAD)
- **Licensing:**

  | Terms | Works |
  |---|---|
  | MIT | DeepCAD, SkexGen, SketchGraphs, BrepDiff, AutoBrep |
  | GPL-v3 research use, no commercial use | HNC-CAD, BrepGen |
  | CC BY-NC | CAD-Recode |
  | CC BY-NC-SA | Text2CAD, BRepNet |
  | No license file | Vitruvion, GenCAD, DTGBrepGen, SketchGen |
  | Non-commercial research only (dataset) | Fusion 360 Gallery dataset |

  Sources: [GitHub API, 2026-11-15](https://github.com/AutodeskAILab/AutoBrep), [Fusion360 LICENSE](https://github.com/AutodeskAILab/Fusion360GalleryDataset)

### Inferences
- **Topological references:** do not emit raw face or edge indices for fillet, chamfer or shell. Use semantic queries tied to the creating feature (Onshape FeatureScript query style), so references survive regeneration. This is the persistent-naming problem that DeepCAD sidestepped by excluding such features.
- **Kernel independence:** compile the DSL to CadQuery or build123d (OpenCascade) for validation and training data, and keep the IR independent of the kernel so it can also target FeatureScript. The MPA approach shows the per-target "macro" translation layer.
- **Solver in the loop:** keep a constraint solver and a kernel rebuild in the loop as validity checks and as RL rewards (AutoConstrain shows a large gain).
- **Training data:** treat quantization (8-bit in a normalized frame) as a training-time encoding only. The DSL itself should carry real units and named parameters or equations.
- **Licensing:** models with NC terms are usable for research baselines only. For product use, MIT AutoBrep/DeepCAD/SkexGen or retraining on permissively licensed data is required. Note that ABC/Onshape-derived data has its own terms (not checked here).

### Gaps
- Primary sources on the persistent-naming problem (FreeCAD TNP, Onshape query semantics) and on build123d/CadQuery design were not fetched in this session. They are presumably covered by an adjacent researcher.

---

## 6. Data and compute requirements

### Takeaway
These models are small by modern standards: tens to a few hundred million parameters, trained on 80k–1M shapes, in 1–3 days on 4 GPUs. The binding constraint is clean, licensed data, not compute.

### Cited Findings
- **DeepCAD:** 178k sequences; 1000 epochs at batch size 512 (GPU hours not given in the fetched text) — [DeepCAD](https://ar5iv.labs.arxiv.org/html/2105.09492)
- **DTGBrepGen:** 4×A800 80GB, about 3 days per dataset — [README](https://github.com/jinli99/DTGBrepGen)
- **BrepARG:** about 1.2 days on 4×H20 (VQ-VAE about 12 h plus sequence model about 17 h), with 1.5 s per B-rep on an RTX 4090 — [BrepARG](https://arxiv.org/html/2601.16771v2)
- **Baseline training time and inference speed** (from BrepARG's comparison) — [BrepARG](https://arxiv.org/html/2601.16771v2):

  | Model | Training | Inference per sample |
  |---|---|---|
  | BrepGen | 7.5 days | 8.4 s |
  | DTGBrepGen | 3.0 days | 3.6 s |
  | BrepDiff | 1.8 days | 8.3 s |
- **TG-Diff:** 4×RTX 3090; 82M parameters versus DTGBrepGen 145M and BrepGen 292M. Training sets were DeepCAD 84k, ABC 293k and Furniture 1.3k shapes — [TG-Diff](https://arxiv.org/html/2607.21928)
- **AutoBrep:** trained on deduplicated ABC-1M — [README](https://github.com/AutodeskAILab/AutoBrep)

### Inferences
- A from-scratch DSL model at the DeepCAD/SkexGen scale is feasible on a single multi-GPU node. Converting enough real feature-rich models into the DSL is the harder part.

### Gaps
- GPU-hour figures for SkexGen, HNC-CAD, Vitruvion, SolidGen and AutoBrep were not retrieved.

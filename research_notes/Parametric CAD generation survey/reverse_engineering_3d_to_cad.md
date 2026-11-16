# Reverse Engineering Parametric CAD Construction Histories from 3D Geometry (point clouds, meshes, scans, B-reps)

*Notes compiled 2026-11-15. Sources were checked through roughly mid-November 2026. Numbers come from primary papers unless marked otherwise. Items tagged **[unverified this session]** come from background knowledge and were not re-checked against the source in this session (budget cap of about 15 tool calls). The report writer should treat them as lower confidence.*

**Metric conventions used below:** CD is Chamfer distance, reported ×10³ on unit-normalized shapes unless stated otherwise. IoU is volumetric IoU in %. IR is invalidity ratio in %, meaning the share of outputs that fail to produce a valid solid. "Med." means median.

---

## Q1. What did the major point-cloud/mesh → CAD-history methods each contribute?

### Takeaway
The field moved through four stages:
1. Segment-and-fit primitives: ParSeNet, Point2Cyl, ComplexGen, NVD-Net, Point2CAD.
2. Self-supervised sketch-extrude fitting: ExtrudeNet, SECAD-Net.
3. Supervised autoregressive command-sequence transformers trained on DeepCAD: DeepCAD, MultiCAD, TransCAD, CAD-SIGNet.
4. LLM decoders that emit CadQuery Python, trained on procedurally generated data and then RL-tuned: CAD-Recode (ICCV 2025) and cadrille (ICLR 2026 Oral).

Since 2026 the frontier has shifted to stepwise/agentic mesh→CAD with richer operations (CADFit, CADENA, StepCAD). In head-to-head tables, the procedurally trained LLM code generators dominate the DeepCAD, Fusion360 and CC3D benchmarks.

### Cited Findings

**Primitive / B-rep-patch recovery (gives surfaces, not a feature history)**
- **ParSeNet** (ECCV 2020). Decomposes point clouds into parametric surface patches (plane, sphere, cylinder, cone, open/closed B-spline) using segmentation plus differentiable fitting. Code: `Hippogriff/parsenet-codebase`; the GitHub API reports **no license file** (verified via `gh api`, last push 2020-09) — [arXiv 2003.12181](https://arxiv.org/abs/2003.12181) **[paper details unverified this session]**; [repo](https://github.com/Hippogriff/parsenet-codebase)
- **ComplexGen** (SIGGRAPH 2022, Guo et al.). Predicts a B-rep "chain complex" from point clouds: corners, curves, patches, and their topology. Trained and evaluated on ABC. Output is a B-rep with no history — [arXiv 2205.14573](https://arxiv.org/abs/2205.14573) **[unverified this session; repo license not checked; `cvlab-epfl/ComplexGen` 404s]**
- **NVD-Net** ("neural Voronoi diagram", not "vertex distance"). Predicts a Voronoi diagram from a point cloud or distance field via binary classification. Then extracts B-rep surfaces, curves, vertices, and connectivity. Evaluated on ABC with ground-truth B-reps — [arXiv 2406.05261](https://arxiv.org/html/2406.05261v1). Venue and license not verified; guessed repo paths 404'd.
- **Point2CAD** (CVPR 2024). Hybrid analytic-neural surface fitting that reconstructs B-rep topology from point clouds. Reported SOTA on ABC. Code `prs-eth/point2cad` is **Apache-2.0** (verified) — [HF papers 2312.04962](https://huggingface.co/papers/2312.04962); [repo](https://github.com/prs-eth/point2cad)
- **Point2Primitive** (2025). Partitions the point cloud into per-extrusion clusters and predicts extrusion primitives directly, instead of SDF sketches — [arXiv 2505.02043](https://arxiv.org/html/2505.02043v3)

**Extrusion-cylinder / self-supervised sketch-extrude**
- **Point2Cyl** (CVPR 2022, Uy et al.). Segments a point cloud into "extrusion cylinders": it predicts per-point segment membership, base/barrel labels, and normals, then recovers the extrusion axis, 2D sketch (implicit), and extent. Code is **MIT** (verified) — [repo](https://github.com/mikacuy/point2cyl). In CAD-Recode's comparison it scores DeepCAD Med. CD 4.27 / IoU 73.8 / IR 3.9 and Fusion360 Med. CD 4.18 / IoU 67.5 / IR 3.2, trained on 35k DeepCAD shapes — [CAD-Recode Table 1](https://arxiv.org/html/2412.14042)
- **ExtrudeNet** (ECCV 2022, Ren et al.). Unsupervised. Learns sketch (closed Bézier/SDF) plus extrude primitives combined with Boolean ops, from point clouds — [arXiv 2209.15632](https://arxiv.org/abs/2209.15632) **[unverified this session; repo/license not located]**
- **SECAD-Net** (CVPR 2023, Li et al.). Self-supervised. Learns 2D sketch SDFs plus extrusion cylinders and unions them to reconstruct voxel/point input, without ground-truth sequences. Code `BunnySoCrazy/SECAD-Net` is **MIT** (verified, last push 2025-10) — [repo](https://github.com/BunnySoCrazy/SECAD-Net); [arXiv 2303.10613](https://arxiv.org/abs/2303.10613) **[paper details unverified]**

**Supervised command-sequence models (DeepCAD vocabulary: line/arc/circle + extrude)**
- **DeepCAD** (ICCV 2021, Wu et al.). Transformer autoencoder over sketch-extrude command sequences. It also introduced the DeepCAD dataset (~178k Onshape models, ABC-derived). A PointNet++ encoder mapped into its latent space gives the standard "point cloud → CAD" baseline. Code is **MIT** (verified) — [repo](https://github.com/ChrisWu1997/DeepCAD). Baseline numbers: DeepCAD Mean CD 42.5, Med. CD 9.64, IoU 46.7, IR 7.1; Fusion360 Mean CD 330, Med. CD 89.2, IoU 39.9, IR 25.2; CC3D Med. CD 263, IR 12.7 — [CAD-Recode Tables 1–2](https://arxiv.org/html/2412.14042)
- **MultiCAD** (Ma et al., 2023). Contrastive multimodal (point cloud ↔ sequence) representation learning. DeepCAD Med. CD 8.09, IR 11.5; Fusion360 Med. CD 42.2, IR 16.5 — [CAD-Recode Table 1](https://arxiv.org/html/2412.14042). The cadrille table prints "8.09 / 11.5 / —" in the CD/IoU/IR columns, which appears to be a column shift: 11.5 is IR, not IoU — [cadrille Table 1](https://arxiv.org/html/2505.22914)
- **HNC-CAD** (hierarchical neural coding). DeepCAD Med. CD 8.64 / IoU 65.3 / IR 5.6; Fusion360 36.8 / 63.5 / 7.3 — [CAD-Recode Table 1](https://arxiv.org/html/2412.14042)
- **PrismCAD**. DeepCAD Med. CD 4.28 / IoU 72.1 / IR 16.2 — [CAD-Recode Table 1](https://arxiv.org/html/2412.14042)
- **TransCAD** (ECCV 2024, Dupont et al.). Hierarchical transformer: a loop/sketch-level, then extrusion-level decoder from point clouds. Proposes **mean Average Precision of CAD Sequence** as a new metric — [ECCV 2024 poster](https://eccv2024.ecva.net/virtual/2024/poster/1688). Scores DeepCAD Mean CD 32.3 / Med. 4.51 / IoU 65.5 / IR 1.1 and Fusion360 78.6 / 33.4 / 60.2 / 2.4 — [CAD-Recode Table 1](https://arxiv.org/html/2412.14042)
- **CAD-Diffuser**. DeepCAD Med. CD 3.02 / IoU 74.3 / IR 1.5; Fusion360 3.85 / 63.2 / 1.7 — [CAD-Recode Table 1](https://arxiv.org/html/2412.14042)
- **CAD-SIGNet** (CVPR 2024, Khan et al., SnT Luxembourg). Autoregressive layer-wise sketch/extrude inference. "Sketch-instance guided attention" restricts cross-attention to points inside each sketch's bounding box. Generates several candidates and picks the one with lowest CD to the input — [arXiv 2402.17678](https://arxiv.org/html/2402.17678v1). Scores DeepCAD Mean CD 3.43 / Med. 0.28 / IoU 77.6 / IR 0.9; Fusion360 7.37 / 0.48 / 65.6 / 1.6; CC3D 14.82 / 2.90 / 42.6 / 2.5 — [CAD-Recode Tables 1–2](https://arxiv.org/html/2412.14042). Without test-time sampling, cadrille re-reports it as DeepCAD 0.29/77.3/5.0, Fusion360 0.70/58.4/9.3, CC3D 4.42/39.1/15.5 (Med. CD/IoU/IR) — [cadrille Table 3](https://arxiv.org/html/2505.22914). Repo/license not located.

**LLM-as-decoder, CAD-as-code**
- **CAD-Recode** (ICCV 2025, Rukhovich et al., Univ. Luxembourg):
  - Method: point cloud → CadQuery Python. Uses a lightweight point projector plus Qwen2-1.5B (original tokenizer and one added linear layer) — [repo](https://github.com/filaPro/cad-recode)
  - Training data: purely **procedural**. Sketches are 3–8 random circles or rotated rectangles combined by union/cut, extruded on canonical planes, translated and unioned, quantized to a [-100,100] grid, validated with `BRepCheck_Analyzer`, and deduplicated. The text says 1M sequences; the tables say "11M", and the paper doesn't explain the gap. It contains no human-designed models — [arXiv 2412.14042](https://arxiv.org/html/2412.14042)
  - Results trained on its procedural set (with test-time sampling): DeepCAD Mean CD 0.30 / Med. 0.16 / IoU 92.0 / IR 0.4; Fusion360 0.35 / 0.15 / 87.8 / 0.5; CC3D 0.76 / 0.31 / 74.2 / 0.3. Trained on DeepCAD-160k only, it gets DeepCAD IoU 80.7 and Fusion360 IoU 67.6, which shows the procedural data drives most of the gain — [same](https://arxiv.org/html/2412.14042)
  - Downstream: feeding CAD-Recode output to GPT-4o gives 76.5% on SGP-Bench CAD-QA (1000 tasks), vs 63.2% via CAD-SIGNet and 42.3% for PointLLM. Code editing is shown only qualitatively, with GPT-4o exposing parameters as sliders — [same](https://arxiv.org/html/2412.14042)
  - Release: weights v1 and v1.5 (March 2025) on HF, plus a demo Space. GitHub license is reported as **NOASSERTION** (a custom LICENSE.md; the type wasn't readable via API) — [repo](https://github.com/filaPro/cad-recode)
- **cadrille** (arXiv 2505.22914, **ICLR 2026 Oral**; Kolodiazhnyi, …, Rukhovich):
  - Method: a VLM (Qwen2-VL-based) taking point cloud, multi-view image, or text → CadQuery. SFT on CAD-Recode procedural data plus Text2CAD-annotated DeepCAD, then **online RL (Dr. CPPO: Dr. GRPO + CPPO, G=16 → top-4 by |advantage|)**. Reward is 10·IoU minus 10 for invalid code. RL uses only *unannotated* DeepCAD/Fusion360 training inputs (hard examples with mean reward < 7.5) — [arXiv HTML](https://arxiv.org/html/2505.22914)
  - Point-cloud results after RL (Med. CD / IoU / IR): DeepCAD 0.17 / 90.2 / 0.0; Fusion360 0.17 / 85.0 / 0.2; CC3D 0.47 / 67.9 / 0.2. Its own re-run of CAD-Recode without test-time sampling: CC3D 0.54 / 60.5 / 9.8 — [same](https://arxiv.org/html/2505.22914)
  - Image results after RL: DeepCAD 0.17 / 92.2 / 0.0; Fusion360 0.17 / 84.6 / 0.0; CC3D 0.57 / 65.0 / 0.1 — [same](https://arxiv.org/html/2505.22914)
  - Release: code `col14m/cadrille` is **Apache-2.0** (verified, last push 2026-09-01) — [repo](https://github.com/col14m/cadrille)

**2026 stepwise / richer-operation mesh→CAD**
- **CADFit** (arXiv 2605.01171, May 2026; MIT + Siemens):
  - Method: optimization-based mesh→CadQuery. Fits extrude/revolve candidates with one-sided Chamfer, assembles them by IoU-guided backward pruning and residual union/cut, filters sketches with a DINO-based prior, and recovers fillets/chamfers by IoU line search — [arXiv HTML](https://arxiv.org/html/2605.01171v1)
  - Results (IoU fraction / CD / IR): DeepCAD-hard-300 0.960 / 0.016 / 0.000; Fusion360-300 0.917 / 0.017 / 0.000; ABC Hard (151–1500 faces) 0.547 vs CAD-Recode 0.333 and cadrille 0.086. In this out-of-distribution setting cadrille collapses on Fusion360 (IoU 0.092, IR 0.46) while CAD-Recode holds at 0.761 — [same](https://arxiv.org/html/2605.01171v1)
  - Release: no code or license stated.
- **CADENA: Stepwise CAD Reverse Engineering** (arXiv 2608.00799, Aug 2026). Mesh → parametric CAD program, one operation at a time, comparing the target against the current partial geometry each step. Introduces CADENA-Bench (mechanical-part categories). Claims to beat prior methods on CADENA-Bench, DeepCAD, Fusion360, and MCB. Code `github.com/zhemdi/cadena`, weights `huggingface.co/kulibinai/cadena`, benchmark on HF. Numbers not in the abstract — [arXiv](https://arxiv.org/abs/2608.00799)
- **StepCAD** (arXiv 2610.03799, Oct 2026; Nehme & Ahmed, MIT). State-conditioned LLM policy plus IoU-guided tree search with local edits. Introduces **ARCADE-1.5M** (1.5M executable programs, up to 150+ ops, 12.5M state-action transitions). Claims "up to 87.2% relative IoU improvement over the strongest evaluated baseline". Release not stated — [arXiv](https://arxiv.org/abs/2610.03799). The search snippet listed extrude, revolve, loft, sweep, fillet, chamfer, shell, and mirror as dataset ops — [arXiv PDF](https://arxiv.org/pdf/2610.03799)
- **Extrusion Segmentation Strategy** (arXiv 2605.08971, May 2026; TU Braunschweig). Splits DeepCAD sequences at each extrude, trains a single-extrusion model on partial point clouds, then concatenates. On complex models: command accuracy 58.10→77.71%, parameter accuracy 69.94→82.50%, Med. CD 10.92→2.07, IR 32.02→12.03% — [arXiv HTML](https://arxiv.org/html/2605.08971)
- **Pointer-CAD** (arXiv 2603.04337, 2026). LLM command sequences that use pointers to select B-rep edges/faces, extending to chamfer/fillet — [arXiv PDF](https://arxiv.org/pdf/2603.04337)
- **Img2CADSeq** (arXiv 2605.13293, 2026). Image → point cloud (intermediate) → CAD sequence via diffusion — [arXiv](https://arxiv.org/html/2605.13293v1)

**Fusion 360 Gallery reconstruction (B-rep → sketch-extrude)**
- **Fusion 360 Gallery** (Willis et al., SIGGRAPH/TOG 2021). Defines a sketch-and-extrude programming language and releases 8,625 human design sequences. Poses "recovering a CAD program from a target geometry" as neurally guided program synthesis — [arXiv 2010.02392](https://arxiv.org/abs/2010.02392)
  - Method detail: the agent picks face-extrude actions on the target B-rep (start face, end face, operation) with a GNN (MPN) policy plus search (random/beam/best-first). Evaluated by IoU and "exact reconstruction" rate **[method detail from background knowledge; numbers not verified this session]**
  - License: the dataset repo has a custom (NOASSERTION) license — [repo](https://github.com/AutodeskAILab/Fusion360GalleryDataset)

### Inferences
- Benchmark numbers aren't comparable across papers without checking the protocol. CAD-Recode's own table uses test-time sampling, which gives IR 0.4 on DeepCAD. Re-run by cadrille without sampling, CAD-Recode's IR is 3.1, and CAD-SIGNet's IR is 0.9 vs 5.0 by the same mechanism.
- The DeepCAD/Fusion360 numbers are close to saturated: Med. CD ≈ 0.17 and IoU ≈ 85–92%. The 2026 papers now evaluate on hardest-subset, ABC-hard, MCB, or new benchmarks (CADENA-Bench, ARCADE).
- CADFit's results suggest cadrille's RL gains don't transfer to out-of-distribution meshes (Fusion360 IoU 0.092 in CADFit's run). This conflicts with cadrille's own Fusion360 IoU of 85.0. The likely causes are a protocol difference (mesh vs sampled points, hardest subset, normalization). Treat this as an open conflict.

### Gaps
- ExtrudeNet, SECAD-Net, ComplexGen, ParSeNet, and NVD-Net headline numbers weren't re-fetched; they report on their own ABC/DeepCAD splits, often with different metrics.
- I didn't find repos or licenses for CAD-SIGNet, TransCAD, ExtrudeNet, NVD-Net, or ComplexGen.
- CADENA and StepCAD headline tables weren't retrieved.
- The text of CAD-Recode's custom LICENSE.md wasn't read; it may be non-commercial.

---

## Q2. Inferring a feature history from a B-rep (STEP): feature recognition / "un-defeaturing"

### Takeaway
Classical machining-feature recognition (graph/AAG, hint-based, volume decomposition) identifies *features* such as holes, pockets, and slots, but not an ordered parametric history. Learned B-rep methods either label faces by operation/step (CADOps-Net, BRepNet, BRepFormer, BRepMAE) or predict full sequences (CADParser, Fusion 360 Gallery agents). Rule-based history synthesis from STEP exists, but only as early, non-peer-reviewed open source.

### Cited Findings
- Han, Pratt & Regli, "Manufacturing feature recognition from solid models: a status report" (2000), names three dominant technologies: graph-based algorithms, volumetric decomposition, and hint-based geometric reasoning — [NIST](https://www.nist.gov/node/744276)
- Joshi & Chang's Attributed Adjacency Graph represents faces as nodes and edges as arcs with convexity attributes. It is limited to predefined feature-pattern graphs, struggles with interacting or general features (e.g., an n-sided pocket), and is computationally costly. Hint-based extensions add minimal condition subgraphs for interacting features — [Wikipedia: Feature recognition](https://en.wikipedia.org/wiki/Feature_recognition); [Critical Review of FR Techniques](https://researchgate.net/profile/Ramy-Harik-2/publication/338437468_A_Critical_Review_of_Feature_Recognition_Techniques/links/5f045f0492851c52d61de263/A-Critical-Review-of-Feature-Recognition-Techniques.pdf)
- A later review classifies approaches as logic rules, graph-based, volume decomposition, hint-based, neural network, and hybrid — [Critical Review](https://researchgate.net/profile/Ramy-Harik-2/publication/338437468_A_Critical_Review_of_Feature_Recognition_Techniques/links/5f045f0492851c52d61de263/A-Critical-Review-of-Feature-Recognition-Techniques.pdf)
- **CADParser** (IJCAI 2023). Graph encoder over the B-rep plus a sequence decoder that predicts the command sequence. Comes with a ~40k-model dataset that has construction sequences — [IJCAI](https://ijcai.org/proceedings/2023/200)
- **CADOps-Net** (2022). Segments B-rep faces by operation type and construction step, using SolidWorks construction-history labels (CC3D-Ops) — [arXiv 2208.10555](https://arxiv.org/html/2208.10555v1)
- **BRepNet** (CVPR 2021, Autodesk). Topological message passing for face segmentation into modeling operations. Custom license (NOASSERTION) — [repo](https://github.com/AutodeskAILab/BRepNet)
- **BRepFormer** (2025) is a transformer for B-rep geometric feature recognition — [arXiv 2504.07378](https://arxiv.org/pdf/2504.07378). **BRepMAE** (2026) is a self-supervised masked autoencoder for machining feature recognition — [arXiv 2602.22701](https://arxiv.org/html/2602.22701v1)
- **Dassault patent US 11436795**, "Learning a neural network for inference of editable feature trees". Infers editable feature trees from a history-free discrete shape — [USPTO](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11436795)
- **Vingt-ds/cad-history-recovery** is an in-development, deterministic, rule-based pipeline: B-rep/STEP → replayable construction sequence. It explicitly does *not* claim to recover the designer's original history — [GitHub](https://github.com/Vingt-ds/cad-history-recovery)
- **Zero-to-CAD** (arXiv 2604.24479, Apr 2026; Autodesk-affiliated authors incl. P. K. Jayaraman). Argues that direct B-rep generation yields valid geometry without history, which limits editability. A 2B model trained only on agentically synthesized programs reconstructs human-designed B-rep geometry — [arXiv PDF](https://arxiv.org/pdf/2604.24479)
- **Fusion 360 Gallery reconstruction** is B-rep → sketch-extrude sequence via face-extrude actions — [arXiv 2010.02392](https://arxiv.org/abs/2010.02392)

### Inferences
- For STEP input, a practical hybrid is: (1) classical or learned feature recognition removes fillets, chamfers, holes, and patterns ("defeaturing"); (2) the remaining prismatic core is reconstructed as sketch-extrude/revolve with a CAD-Recode-style generator or rule-based synthesis; (3) the removed features are re-applied as explicit ops. CADFit's post-hoc fillet/chamfer line search does a mesh-side analogue of this.
- Point-cloud methods can consume B-rep input by sampling points. They throw away exact topology, though, so B-rep-native methods should reach better exactness.

### Gaps
- No peer-reviewed 2025–2026 STEP→full-history method with standard benchmark numbers was found.
- Commercial "feature recognition" tools (e.g., in Siemens NX, SolidWorks FeatureWorks, CADfix) weren't investigated.

---

## Q3. Noise, partial scans, and operations beyond sketch-and-extrude

### Takeaway
Robustness mostly comes from training-time Gaussian noise plus CC3D evaluation. No standardized partial-scan ablation was found in CAD-Recode. Coverage is extending from extrude-only (2021–2025) to revolve, fillet, chamfer, and even loft, sweep, and shell (2026).

### Cited Findings
- CAD-Recode adds Gaussian noise (σ=0.01) with p=0.5 during training. CC3D (surface noise, smoothed edges, missing parts) is its only real-scan test; there is no dedicated noise or partial-scan ablation. Its stated limitations are: no revolution or fillet; failures on sub-quantization features and B-spline geometry; and mean CD is sensitive to outliers — [arXiv 2412.14042](https://arxiv.org/html/2412.14042)
- CC3D accuracy drops for every method. CAD-SIGNet goes from IoU 77.6 on DeepCAD to 42.6 on CC3D; CAD-Recode from 92.0 to 74.2 — [CAD-Recode](https://arxiv.org/html/2412.14042). cadrille's RL lifts CC3D point-cloud IoU from 61.8 to 67.9 and cuts IR from 5.9 to 0.2 — [cadrille](https://arxiv.org/html/2505.22914)
- CADFit supports extrude, revolve, fillet, chamfer, union, and cut. It leaves loft, sweep, and patterns to future work, and fails on curved surfaces without stable planar sketches — [CADFit](https://arxiv.org/html/2605.01171v1)
- Pointer-CAD adds fillet/chamfer through pointer-based edge selection — [arXiv 2603.04337](https://arxiv.org/pdf/2603.04337). StepCAD's dataset reportedly includes revolve, loft, sweep, fillet, chamfer, shell, and mirror — [arXiv PDF](https://arxiv.org/pdf/2610.03799). BrepGPT notes that sequence methods mostly lack loft, sweep, fillet, and chamfer — [arXiv 2511.22171](https://arxiv.org/pdf/2511.22171)
- Segmenting by extrusion improves complex-model reconstruction substantially (Q1). This points to partial-cloud-to-sub-sequence training as a robustness tool — [arXiv 2605.08971](https://arxiv.org/html/2605.08971)

### Inferences
- Holes and patterns are rarely first-class operations in learned methods. They get encoded as cut-extrudes repeated N times, which loses design intent (hole spec, pattern count/spacing).

### Gaps
- No quantitative partial-scan benchmark (e.g., single-view occlusion) was found for the main methods.

---

## Q4. Standard metrics and SOTA numbers

### Takeaway
The standard metrics are mean/median CD (×10³), IoU (%), and IR (%). Older sequence papers also report command/parameter accuracy, and TransCAD adds mAP-of-sequence. As of Nov 2026, the best published point-cloud numbers are: DeepCAD Med. CD ≈ 0.16–0.17, IoU 90–92%; Fusion360 Med. CD ≈ 0.15–0.17, IoU 85–88%; CC3D Med. CD 0.31–0.47, IoU 68–74%.

### Cited Findings
**DeepCAD** (point cloud):
- CAD-Recode with test-time sampling: Mean CD 0.30 / Med. 0.16 / IoU 92.0 / IR 0.4 — [CAD-Recode](https://arxiv.org/html/2412.14042)
- cadrille (Dr. CPPO, no sampling): Med. 0.17 / IoU 90.2 / IR 0.0 — [cadrille](https://arxiv.org/html/2505.22914)

**Fusion360:**
- CAD-Recode: 0.35 / 0.15 / 87.8 / 0.5
- cadrille: 0.17 / 85.0 / 0.2

**CC3D (real scans, 2,973 clouds):**
- CAD-Recode: 0.76 / 0.31 / 74.2 / 0.3
- cadrille: 0.47 / 67.9 / 0.2 (CD and IoU computed under cadrille's protocol)

**Other metrics:**
- Command/parameter accuracy (Extrusion Segmentation paper): ACC_cmd 81.89%, ACC_param 84.25% overall on DeepCAD with the single-extrusion model — [arXiv 2605.08971](https://arxiv.org/html/2605.08971)
- TransCAD's mAP-of-CAD-sequence — [ECCV 2024](https://eccv2024.ecva.net/virtual/2024/poster/1688)
- Harder mesh benchmarks (CADFit protocol): DeepCAD-300-hardest IoU 0.960, Fusion360 0.917, ABC-Hard 0.547 — [CADFit](https://arxiv.org/html/2605.01171v1)

### Inferences
- The CAD-Recode and cadrille numbers on CC3D aren't directly comparable: the protocols differ and cadrille's table re-runs CAD-Recode at IoU 60.5. Under cadrille's protocol, cadrille RL is SOTA. CAD-Recode's self-reported 74.2 uses test-time sampling.

### Gaps
- No public leaderboard reconciles the protocols. Papers with Code (cited in the CAD-Recode README) shut down in 2025, which is my background knowledge, not verified this session.

---

## Q5. Reverse engineering as a data engine for multimodal design-intent models

### Takeaway
Yes, and this is now the dominant strategy. Procedural or agentic program synthesis (CAD-Recode 1M, Zero-to-CAD 1M, ARCADE-1.5M) already provides paired (geometry ↔ program) data that beats human-data training. Reverse-engineering models can then pseudo-label unannotated meshes or STEP files, with execution plus IoU as the filter. That is exactly how cadrille's RL uses unannotated inputs.

### Cited Findings
- CAD-Recode trained on procedural data vs DeepCAD-160k: DeepCAD IoU 92.0 vs 80.7, Fusion360 87.8 vs 67.6 — [CAD-Recode](https://arxiv.org/html/2412.14042)
- cadrille's RL needs only geometry, with no sequence labels. Its reward is computed by executing the generated code and measuring IoU against the input — [cadrille](https://arxiv.org/html/2505.22914)
- Zero-to-CAD synthesizes about 1M executable sequences beyond sketch-extrude via an LLM agent in a CAD execution loop, and releases 100k. A VLM trained on it beats GPT-5.2 on multi-view-image → CAD, with no real history data — [arXiv 2604.24479](https://arxiv.org/abs/2604.24479)
- StepCAD's ARCADE-1.5M provides 12.5M intermediate state-action pairs, i.e. supervision for stepwise design processes — [arXiv 2610.03799](https://arxiv.org/abs/2610.03799)
- Outputs as CadQuery code are LLM-readable. GPT-4o answered 76.5% of CAD-QA questions from CAD-Recode output and could parameterize it — [CAD-Recode](https://arxiv.org/html/2412.14042)

### Inferences
- A viable engine is: mesh/STEP corpus (ABC, Thingi10k, scans) → reverse-engineer (CAD-Recode/cadrille/CADFit) → execute and keep only high-IoU outputs → paired (mesh, render, code) triples. The caveat is that recovered histories are *plausible*, not the *designer's* intent. Quantization, primitive bias, and missing semantic dimensions or constraints mean "design intent" labels need a separate source or refactoring step.
- Licensing gates reuse:
  - Apache-2.0: cadrille, Point2CAD
  - MIT: DeepCAD, Point2Cyl, SECAD-Net
  - Custom / need review: CAD-Recode, Fusion 360 Gallery, BRepNet

### Gaps
- No paper was found that quantifies how pseudo-labeled reverse-engineered histories compare to true human histories for downstream design-intent learning.

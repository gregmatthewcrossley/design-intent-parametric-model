# Datasets, Benchmarks, Metrics, and Tooling for Parametric CAD Generation (as of Nov 2026)

Method note: about 16 tool calls. I checked licenses against primary sources (LICENSE files, HF cards, dataset pages, Onshape ToU) wherever I could. Items marked "[unverified this session]" come from background knowledge and were not confirmed against a source here. The report writer should treat them as leads to check, not facts.

## Datasets: contents, sizes, licenses, availability

### Takeaway
No large, real-world dataset with sketch and feature histories is cleanly licensed for commercial use. Licenses fall into three groups:
- **Onshape-derived (ABC, DeepCAD, SketchGraphs, CADFS, Omni-CAD, Text2CAD's geometry):** creators keep copyright. Onshape's ToU does grant a broad "use without restriction" license on free-plan public documents.
- **Autodesk Fusion 360 Gallery:** strictly non-commercial research only.
- **Recent ML datasets (Text2CAD, CAD-Recode):** CC BY-NC(-SA).

For a solo builder, CAD-Recode (1M synthetic CadQuery programs) plus DeepCAD/Text2CAD is the de facto SFT recipe. Every piece of it is non-commercial or carries an inherited-copyright caveat.

### Cited Findings

**ABC (2019)**
- About 1M CAD models from Onshape. Formats: meta YAML, STEP, Parasolid, STL, "feat" (surface patches and curves), OBJ with normals and curvature, renders, stats, and the original Onshape FeatureScript (`ofs`).
- meta, step, para and stl2 are always available. Data comes in 10k-model chunks fetched with wget/curl, with MD5 checksums.
- License: "The copyright of the CAD models is owned by their creators", with a pointer to Onshape ToU 1.g.ii. No warranties.
- [ABC dataset page](https://deep-geometry.github.io/abc-dataset/)

**Onshape ToU, section 1(g)(ii)**
- For public documents owned by free-plan users (created on or after Aug 7, 2018, or earlier without a LICENSE tab), the customer "grants a worldwide, royalty-free and non-exclusive license to any End User or third party ... to use the intellectual property contained in Customer's Public Document without restriction". This includes copying, modifying and selling.
- Documents with a LICENSE tab that reserves greater rights keep those rights.
- Section 4(b)(9) prohibits "any robot, spider, scraper or other automated means to access the Service" and "any data mining, data gathering or extraction method".
- The ToU has no clause that explicitly mentions ML or AI training.
- [Onshape Terms of Use](https://www.onshape.com/en/legal/terms-of-use)

**SketchGraphs (2020)**
- 15M sketches from real Onshape models, stored as geometric constraint graphs (nodes are primitives, edges are constraints).
- Downloads: raw JSON is 128 zstd tar shards (about 43 GB). Construction sequences are `sg_all.npy` (about 15 GB). Filtered train/val/test splits (`sg_t16_*.npy`) are also hosted at sketchgraphs.cs.princeton.edu.
- License: code is MIT. For data, "original creators of the CAD sketches hold the copyright", with a pointer to Onshape ToU.
- [SketchGraphs GitHub](https://github.com/PrincetonLIPS/SketchGraphs)

**DeepCAD (2021)**
- About 170k sketch+extrude designs derived from ABC/Onshape. Sketch and extrude only. [CADFS paper](https://arxiv.org/html/2605.01925)
- cadrille's split uses about 160k train and 8,046 test samples. [cadrille paper](https://arxiv.org/html/2505.22914)
- The data license was not checked this session (see Gaps).

**Fusion 360 Gallery (Autodesk, 2020–2021)**
- Reconstruction subset: 8,625 human sketch+extrude design sequences, plus the Fusion 360 Gym environment. Segmentation subset: faces labeled by the modeling operation that created them (Extrude, Fillet, Chamfer, ...). Assembly and joint subsets also exist. [GitHub](https://www.github.com/AutodeskAILab/Fusion360GalleryDataset)
- License: "non-commercial research purposes" only.
  - You may not redistribute the full dataset; you may only point others to the repo.
  - Modified portions may be shared non-commercially under the same restrictions.
  - You may not try to link models back to their creators.
  - Autodesk may terminate the license or cut off access at any time.
  - [Fusion 360 Gallery LICENSE](https://github.com/AutodeskAILab/Fusion360GalleryDataset/blob/master/LICENSE.md)
- cadrille uses 6,900 Fusion360 training samples (unannotated, for RL) and 1,725 test samples. [cadrille paper](https://arxiv.org/html/2505.22914)

**Text2CAD (NeurIPS 2024 Spotlight)**
- Text annotations on DeepCAD models at four levels: L0 abstract, L1 beginner, L2 intermediate, L3 expert.
- v1.0 was annotated with LLaVA-NeXT and Mixtral-8x7B. Files: CSV 1.1 GB, JSON, RGB images 48 GB, depth images 37 GB.
- v1.1 was annotated with Qwen2-VL 14B and Qwen2.5-72B. It adds description and keyword columns and 397 GB of RGB images. Its split is filtered to about 5% cuboid and cylinder models.
- `cad_seq.zip` (579 MB) holds the CAD vectors. Total storage is 605 GB.
- License: **CC BY-NC-SA 4.0**, gated on Hugging Face.
- [HF SadilKhan/Text2CAD](https://huggingface.co/datasets/SadilKhan/Text2CAD); [GitHub](https://github.com/SadilKhan/Text2CAD)

**CAD-Recode (ICCV 2025)**
- About 1M synthetic, procedurally generated sketch-extrude programs in CadQuery Python, plus a validation set of about 1k.
- A v1.5 release exists. One derivative counts 982,847 programs in v1.5.
- License on HF: **cc-by-nc-4.0**.
- [HF filapro/cad-recode-v1.5](https://huggingface.co/datasets/filapro/cad-recode-v1.5/blame/main/README.md); [arXiv 2412.14042](https://arxiv.org/pdf/2412.14042.pdf); [AI4Manufacturing/w_cad2](https://huggingface.co/datasets/AI4Manufacturing/w_cad2)

**cadrille (2025)**
- Code is Apache-2.0. It trains on CAD-Recode plus Text2CAD/DeepCAD; the SFT mix is about 1.17M examples. [CADFS paper](https://arxiv.org/html/2605.01925)
- RL code is not released, but SFT and RL checkpoints are on HF. [cadrille GitHub](https://github.com/col14m/cadrille)

**CC3D**
- The cadrille evaluation set has 2,973 point clouds sampled from real scans of CAD models, with noise, missing parts and smoothed edges. It covers revolve, chamfer and fillet operations. Used for testing only. [cadrille paper](https://arxiv.org/html/2505.22914)

**Omni-CAD (CAD-MLLM)**
- About 450k instances (453,220 after augmentation), drawn from ABC and processed DeepCAD-style. Each instance has text, multi-view images, point clouds and command sequences. [arXiv 2411.04954](https://arxiv.org/html/2411.04954v3)
- cadrille reports more than 27k Omni-CAD test samples. [cadrille paper](https://arxiv.org/html/2505.22914)

**CADParser**
- About 40k designs, augmented from about 6.8k base designs, with 5 operations. [CADFS paper](https://arxiv.org/html/2605.01925)

**CADFS (arXiv 2605.01925, May 2026). The most important new dataset.**
- About 451k real Onshape designs reconstructed as executable FeatureScript programs and verified by re-execution. About 15% failed verification and were dropped. The fine-tuning set is about 405k programs of at most 8,192 tokens.
- 15 operations:
  - sketch, extrude, revolve, sweep, loft, construction plane
  - fillet, chamfer
  - shell, hole, boolean, delete body
  - circular pattern, mirror, transform
- Also includes LLM-written descriptions (annotator plus reviewer LLMs), multi-view images and point clouds.
- Availability is claimed at voyleg.github.io/cadfs. The paper states no dataset license.
- Results: on DeepCAD text-conditioned generation, CD improves 40% and ECD 64% over cadrille. Adding bounding-box conditioning improves CD by 76% and cuts IR by 36%.
- [CADFS arXiv](https://arxiv.org/html/2605.01925)

**MFCAD / MFCAD++**
- MFCAD++ is a set of B-rep STEP models with a machining-feature class label on every face. It extends MFCAD (Cao et al.) and was built for Hierarchical CADNet (CAD journal, 2022), with a 70/15/15 split.
  - [QUB Pure record](https://pure.qub.ac.uk/en/datasets/mfcad-dataset-dataset-for-paper-hierarchical-cadnet-learning-from/)
- MFCAD is cited as 15,488 solids. [AI4Manufacturing/w_cad1](https://huggingface.co/datasets/AI4Manufacturing/w_cad1)
- These are B-reps with no feature history, so they suit segmentation and recognition rather than generation.

**Other 2026 releases**
- VisCAD (arXiv 2609.03811), a multimodal industrial CAD foundation-model suite. [arXiv](https://arxiv.org/pdf/2609.03811)
- CADENA, stepwise CAD reverse engineering (arXiv 2608.00799). [arXiv](https://arxiv.org/pdf/2608.00799)
- Details for both were not read.

### Inferences
- Onshape-derived data (ABC, DeepCAD, SketchGraphs, Text2CAD geometry, Omni-CAD, CADFS) sits in a gray zone. Free-plan public docs carry a broad "without restriction" IP license to third parties, which arguably covers ML training. Two caveats:
  - Docs with LICENSE tabs or from paid accounts may reserve rights.
  - Collecting new data by crawling Onshape violates the anti-scraping clause in 4(b)(9).
  - Reusing existing academic dumps avoids your own scraping, but the curators' added layers (annotations, CC BY-NC-SA) still bind you.
- A commercial-intent builder should treat Fusion 360 Gallery, Text2CAD and CAD-Recode as research-only. The cleanest commercial path is to regenerate a CAD-Recode-style procedural dataset with your own generator, which is cheap.
- CADFS is the first large real dataset beyond sketch+extrude. FeatureScript, though, ties execution to Onshape. Re-execution needs the Onshape API, which has paid or limited quotas (see below).

### Gaps
Not verified this session:
- DeepCAD's data license.
- License and download status for Omni-CAD, CADFS, MFCAD++ (and its exact count of about 59.6k), and CC3D-Ops.
- Thingi10k: my background knowledge is per-object licenses.
- Objaverse-CAD, CADBench/CAD-Bench, Text2CQ, OpenECAD: no time to check.
- Fusion 360 Gallery subset sizes beyond reconstruction (segmentation about 35k parts; assembly about 8.2k assemblies) are [unverified this session].

## Benchmarks and metrics

### Takeaway
The standard reconstruction protocol is median Chamfer Distance (×10³), volumetric IoU, and Invalidity Ratio (IR) on the DeepCAD, Fusion360 and CC3D test sets. Generative work adds MMD, COV and JSD. Code- and text-oriented benchmarks (CADPrompt, Text2CAD-Bench, BenchCAD) measure geometry after execution plus LLM- or VLM-judged fidelity. Current SOTA nearly saturates DeepCAD (IoU about 90–92%, IR about 0%). CC3D and real-world or industrial benchmarks remain hard.

### Cited Findings
- cadrille's evaluation computes IoU, invalidity ratio and Chamfer distance. [cadrille GitHub](https://github.com/col14m/cadrille)
- Point-cloud results (CD ×10⁻³ / IoU % / IR %). [cadrille paper](https://arxiv.org/html/2505.22914)

  | Model | DeepCAD | Fusion360 | CC3D |
  |---|---|---|---|
  | CAD-Recode | 0.18 / 87.1 / 3.1 | 0.19 / 79.1 / 5.0 | 0.54 / 60.5 / 9.8 |
  | cadrille SFT | 0.18 / 87.1 / 2.1 | 0.19 / 79.8 / 2.8 | 0.54 / 61.8 / 5.9 |
  | + DPO | 0.18 / 88.1 / 0.7 | 0.19 / 80.9 / 1.3 | 0.54 / 61.3 / 2.6 |
  | + Dr. CPPO (online RL) | 0.17 / 90.2 / 0.0 | 0.17 / 85.0 / 0.2 | 0.47 / 67.9 / 0.2 |

- Multi-view image input with Dr. CPPO reaches IoU 92.2 (DeepCAD), 84.6 (Fusion360) and 65.0 (CC3D). [cadrille paper](https://arxiv.org/html/2505.22914)
- cadrille's RL reward is 10 × IoU, or −10 for invalid code. It mines hard examples (mean SFT reward below 7.5), giving about 50k DeepCAD and 3k Fusion360 inputs. [cadrille paper](https://arxiv.org/html/2505.22914)
- CADFS metrics:
  - geometry: CD, Edge Chamfer Distance (ECD), Normal Consistency
  - distribution: MMD, COV, JSD
  - validity: IR
  - topology: Segment Error, Dangling Edge Length, Self-Intersection Ratio, Flux Enclosure Error
  - [CADFS](https://arxiv.org/html/2605.01925)
- Text2CAD evaluation runs through `Evaluation/eval_seq.py`. [Text2CAD GitHub](https://github.com/SadilKhan/Text2CAD)
- CADPrompt (ICLR 2025, CADCodeVerify): 200 objects, each with images, STL, ground-truth CadQuery code and a natural-language prompt. Objects come from Wu et al. 2021. Data is at github.com/Kamel773/CAD_Code_Generation; license not found. [arXiv 2410.05340](https://arxiv.org/html/2410.05340v2)
- Text2CAD-Bench (arXiv 2605.18430): 600 parametric models in 4 difficulty levels, deliberately including chamfers, fillets, sweeps and lofts. [arXiv](https://arxiv.org/html/2605.18430v1)
- BenchCAD (arXiv 2605.10865)
  - Contents: 17,900 execution-verified CadQuery programs across 106 industrial part families, such as bevel gears, springs and twist drills.
  - Tasks: VQA, code QA, image-to-code and instruction-guided code editing.
  - Findings: frontier models recover coarse geometry but replace sweeps, lofts and twist-extrudes with sketch-extrude. RL and fine-tuning do not generalize to unseen families.
  - License not stated.
  - [arXiv](https://arxiv.org/abs/2605.10865)
- Other 2026 benchmarks not read in depth:
  - RealCADBench (industrial design intents, arXiv 2609.03773)
  - CADWorld (computer-use, long-horizon CAD, arXiv 2609.16251)
  - [RealCADBench](https://arxiv.org/pdf/2609.03773); [CADWorld](https://arxiv.org/pdf/2609.16251)

### Inferences
- A minimal evaluation suite for a solo builder:
  - IR, median CD and IoU on the DeepCAD and Fusion360 test splits, for comparability.
  - CC3D for robustness.
  - One 2026 code benchmark (BenchCAD or Text2CAD-Bench) for richer features and editing.
- Add an edit-robustness test (change a parameter, re-execute, check validity) because none of the standard metrics captures design intent.
- Command and parameter accuracy and command F1 (the DeepCAD and Text2CAD style) suit token-sequence representations but carry over poorly to code. Execute-and-compare-geometry is now dominant.

### Gaps
- Exact Text2CAD metric definitions (F1 on primitives, parameter accuracy, GPT-4V judge) were not confirmed this session.
- Human or LLM-judge protocols were not extracted.
- "CAD-Bench" and "CADBench" (BlenderLLM) were not checked.

## Synthetic data generation and transfer

### Takeaway
Procedural CadQuery generation (CAD-Recode) is enough to reach SOTA on DeepCAD and Fusion360 without training on their geometry. Transfer to real, noisy data (CC3D) is clearly weaker. Online RL with an execution and IoU reward on unannotated real meshes closes much of the gap.

### Cited Findings
- SFT on CAD-Recode alone reaches IoU 87.1% on DeepCAD but only 60.5% on CC3D, with about 10% invalid outputs. RL on unannotated DeepCAD and Fusion360 meshes raises CC3D IoU to 67.9% and cuts IR to 0.2%. [cadrille paper](https://arxiv.org/html/2505.22914)
- CADFS shows that real-data diversity matters. Ablations show the FeatureScript representation, the extended 15-operation set and the new annotations each improve results. [CADFS](https://arxiv.org/html/2605.01925)
- BenchCAD finds weak generalization to unseen part families even after fine-tuning and RL. [BenchCAD](https://arxiv.org/abs/2605.10865)

### Inferences
- Recommended recipe:
  - Write your own procedural generator for commercial cleanliness.
  - SFT on it.
  - RL with an execution reward (IoU plus a validity penalty) on whatever unlabeled meshes or B-reps you can license.
- Augment beyond sketch-extrude (revolve, fillet, shell, patterns), since benchmarks show models collapse to extrudes.

### Gaps
- LLM-written CAD code datasets (e.g., Text2CQ, CAD-Coder) and their verification rates were not checked this session.

## Kernels, languages, and tooling for a headless compile-and-check loop

### Takeaway
For a fast, local, batchable loop, OCCT via CadQuery or build123d (Python, pip or conda installable) is the established choice. Most 2025–2026 papers (CAD-Recode, cadrille, BenchCAD, CADPrompt) use CadQuery. Onshape and FeatureScript give real-CAD fidelity (CADFS) but have API quotas and ToS limits. Zoo's KCL engine is proprietary and cloud-hosted.

### Cited Findings
- **Onshape API**
  - Annual call caps: 2,500 per year on Education Student and Educator plans, 10,000 on EDU Enterprise. Standard is listed as 2,500 per user.
  - Calls from the browser and API Explorer also count. Per-endpoint rate limits return HTTP 429. Once the cap is exhausted, requests are rejected for the rest of the year.
  - The policy was documented October 10, 2025.
  - [Onshape API Limits](https://onshape-public.github.io/docs/auth/limits); [Onshape EDU plans](https://www.onshape.com/en/education/plans); [Onshape forum](https://forum.onshape.com/discussion/27916/api-limits)
- **Onshape ToU** bans automated scraping and data mining (4(b)(9)). [Onshape ToU](https://www.onshape.com/en/legal/terms-of-use)
- **Zoo**
  - The Design Studio app (formerly the KittyCAD Modeling App) is open source; the repo is listed as MIT.
  - The geometry engine is not open source. The app streams video frames from a hosted engine over WebSockets.
  - [Zoo FAQ](https://zoo.dev/docs/faq); [KittyCAD GitHub](https://github.com/kittycad); [KCL intro](https://docs.zoo.dev/research/introducing-kcl)
- **CadQuery** is the target language of CAD-Recode, CADPrompt and BenchCAD. [CAD-Recode](https://arxiv.org/pdf/2412.14042.pdf); [BenchCAD](https://arxiv.org/abs/2605.10865)

### Inferences (licenses and properties below are [unverified this session], from background knowledge)
- **Kernels and CAD languages**
  - OCCT: LGPL-2.1 with an exception.
  - CadQuery: Apache-2.0.
  - build123d: Apache-2.0, OCCT-based, more Pythonic, with algebra and builder modes.
  - OpenSCAD: GPL-2. CSG only with no B-rep or fillets. Fast with the Manifold backend.
  - FreeCAD: LGPL. Headless via `freecadcmd`. It ships the planegcs sketch solver and is heavier per process.
  - Manifold: Apache-2.0. Mesh booleans only, no B-rep.
  - truck (Rust, Apache-2.0) and Fornjot (Rust): experimental B-rep kernels. Not production-ready for fillets and shells.
  - SolidWorks API: Windows/COM, needs a paid license, not headless-friendly.
  - Parasolid: commercial license via Siemens, not available to hobbyists.
- **Constraint solvers**
  - SolveSpace libslvs (GPL-3) and FreeCAD's planegcs are the open 2D solvers. planegcs has a WASM/npm port.
- **Recommended loop**
  - CadQuery or build123d in a multiprocessing worker pool with a per-sample timeout.
  - Validity check: OCCT `BRepCheck_Analyzer`, solid count, and positive volume.
  - Tessellate, sample points, compute CD and IoU (IoU by voxelizing the mesh, or via OCCT boolean common volume).
- **Multimodal rendering**
  - OCCT HLR (`HLRBRep_Algo` / `HLRBRep_PolyAlgo`) gives orthographic hidden-line drawings. build123d exposes `project_to_viewport` for SVG.
  - pyrender, Blender or trimesh produce shaded images.

### Gaps
- Tool licenses and maintenance status (OCCT 7.9/8.0 releases, CadQuery/build123d 2026 activity, Fornjot status) were not verified this session.
- KCL's language license was not confirmed.
- Onshape commercial-plan API quotas and whether ToU 1.g.ii covers ML training were not confirmed with Onshape; the ToU is silent on AI.
- No throughput benchmarks (programs per second) were found comparing CadQuery, build123d, OpenSCAD+Manifold and FreeCAD.

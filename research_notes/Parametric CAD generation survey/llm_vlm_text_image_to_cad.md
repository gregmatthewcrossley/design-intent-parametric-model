# LLM/VLM-based Parametric CAD Generation from Text, Images/Sketches and Engineering Drawings (2023–2026)

Notes compiled 2026-11-15. All dates are arXiv first-submission or venue dates as stated in sources. Numbers are self-reported by each paper unless marked otherwise. Benchmarks, normalizations and splits differ across papers, so cross-paper numbers are generally **not** directly comparable. License and star data came from the GitHub API on 2026-11-15.

## Q1. What does each major work do? (per-work fact sheets)

### Takeaway
The field has moved in two steps. First came task-specific transformers and MLLMs that emit DeepCAD-style command tokens (Text2CAD, CAD-MLLM, CAD-Llama, FlexCAD). Then, from about 2025, pretrained (V)LMs started emitting executable Python CAD code, mostly CadQuery (CAD-Recode, cadrille, Text-to-CadQuery, CAD-Coder), using SFT followed by RL with geometric rewards. Most models sit between 0.1B and 8B parameters, mostly Qwen2/2.5(-VL), and are trained and evaluated almost entirely on DeepCAD/Fusion360 sketch-and-extrude parts.

### Cited Findings

**Text2CAD (Khan et al., NeurIPS 2024 Spotlight)** — text → DeepCAD-style sketch/extrude sequence
- The GitHub repo is titled "[NeurIPS'24 Spotlight] Text2CAD: Generating Sequential CAD Designs from Beginner-to-Expert Level Text Prompts". Its license is "Text2CAD Community License Agreement" (custom; GitHub reports NOASSERTION), and it has about 495 stars — [GitHub SadilKhan/Text2CAD](https://github.com/SadilKhan/Text2CAD)
- It is a transformer trained from scratch, not a pretrained LLM. Text-to-CadQuery reports its size as 363M and its results on the Text2CAD test set as median CD×10³ 0.370, mean CD×10³ 26.417, IR 3.5%, and Gemini-judge 58.80% — [Text-to-CadQuery arXiv 2505.06507](https://arxiv.org/pdf/2505.06507)
- As a baseline in cadrille (DeepCAD test, text input) it scores CD 0.37, IoU 71.5%, IR 3.7% — [cadrille v3](https://arxiv.org/html/2505.22914v3)
- CAD-Coder's table reports Text2CAD at mean CD×10³ 29.29, median 0.37, IR 3.75% — [CAD-Coder NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/file/564a224e88f2490f3c1deaae877d37e3-Paper-Conference.pdf)
- Its text annotations on about 150–170K DeepCAD models are the de facto text-to-CAD training set reused by Text-to-CadQuery, CAD-Coder and cadrille. CAD-Coder uses "all 150K training descriptions and geometries from Text2CAD" for GRPO — [CAD-Coder](https://proceedings.neurips.cc/paper_files/paper/2025/file/564a224e88f2490f3c1deaae877d37e3-Paper-Conference.pdf); cadrille uses about 160k DeepCAD (Text2CAD version) samples — [cadrille v3](https://arxiv.org/html/2505.22914v3)

**CAD-MLLM (arXiv 2411.04954, Nov 2024)** — text, image and/or point cloud → DeepCAD command sequence
- **Base model:** Vicuna-7B with LoRA. Images go through a frozen DINOv2 encoder with a perceiver and projection layer. Points go through a frozen Michelangelo encoder with a linear projection.
- **Output:** 16-variable vectorized sketch-extrude commands.
- **Data:** It introduces the Omni-CAD dataset: about 275,717 models, expanded to 453,220 by taking intermediate extrusion states. Captions come from InternVL2-26B, and each model has 8 views plus point clouds.
- **Compute:** 16× H800 80GB, 20 epochs, about 47 h.
- **Point-input results:** CD 1.85 vs 4.51 for DeepCAD and F-score 90.88 vs 71.83. NVDNet has better CD (0.82) but worse topology.
- **Image-input results:** CD 3.77 vs 5.38 for InstantMesh.
- **Text-input results:** a user study only.
- **Stated limitations:** text lacks absolute dimensions, so outputs match in shape but not in size. Thin structures and dangling edges fail.
- **Availability:** No explicit code or data release is stated in the v1 paper.
- Source: [CAD-MLLM arXiv HTML](https://arxiv.org/html/2411.04954v1)

**CAD-Llama (arXiv 2505.04481; the survey lists it as CVPR 2025)** — text → "Structured Parametric CAD Code" (SPCC), a Python-like DSL
- **Base model:** LLaMA3-8B.
- **SPCC format:** a hierarchical Python-like code with named components and descriptions, 8-bit quantized coordinates, and angles in degrees.
- **Data:** DeepCAD, de-duplicated from about 178K to about 100K models, annotated by GPT-4o in two stages (about 70M tokens).
- **Training:** stage 1 is full-FT "SPCC-adaptive pretraining" and stage 2 is LoRA instruction tuning (rank 256).
- **Compute:** 4× A100, 38 + 12 GPU-hours.
- **Text-to-CAD results:** ACC_T 84.72 vs 69.91 for Text2CAD and 20.03 for GPT-4. MCD 10.53 vs 20.64 for Text2CAD.
- **Other results:** unconditional generation success ratio 99.9%. Cross-dataset Fusion360 ACC_T 78.35.
- **Availability:** code not stated.
- **Failure cases:** parameter errors and text/command mismatch.
- Sources: [CAD-Llama arXiv HTML](https://arxiv.org/html/2505.04481v2); venue per [LLMs for CAD survey](https://dl.acm.org/doi/10.1145/3787499)

**FlexCAD (ICLR 2025, arXiv 2411.05823)** — controllable/masked CAD generation by fine-tuned LLMs
- It describes itself as "unified and versatile controllable CAD generation with fine-tuned large language models" — [LLMs for CAD survey](https://dl.acm.org/doi/10.1145/3787499)
- Code is released at microsoft/FlexCAD under the MIT license — [GitHub microsoft/FlexCAD](https://github.com/microsoft/FlexCAD)
- Base model size and numbers were not verified in this pass (see Gaps).

**CAD-Recode (Rukhovich et al., ICCV 2025; arXiv 2412.14042, Dec 2024)** — point cloud → CadQuery Python
- **Architecture:** Qwen2-1.5B plus a lightweight trainable point-cloud projector (Fourier encoding, then linear layer). A 0.5B ablation also exists.
- **Data:** 1M procedurally generated CadQuery programs (lines, arcs and circles plus boxes and cylinders).
- **Results:** It reports "10× lower Chamfer Distance and over 20% higher IoU" on DeepCAD/Fusion360 while training only on synthetic data. The output code can be handed to GPT-4o for editing and CAD QA.
- Sources: [project page](https://cad-recode.github.io); [arXiv 2412.14042](https://arxiv.org/pdf/2412.14042.pdf); [ICCV supplement](https://openaccess.thecvf.com/content/ICCV2025/supplemental/Rukhovich_CAD-Recode_Reverse_Engineering_ICCV_2025_supplemental.pdf)
- **Headline numbers (as cadrille baseline, CD / IoU% / IR%):** DeepCAD 0.18 / 87.1 / 3.1; Fusion360 0.19 / 79.1 / 5.0; CC3D (real scans) 0.54 / 60.5 / 9.8 — [cadrille v3](https://arxiv.org/html/2505.22914v3)
- **Availability:** code license is CC BY-NC 4.0 (non-commercial). Models v1 and v1.5 and datasets v1 and v1.5 are on Hugging Face (filapro/cad-recode, filapro/cad-recode-v1.5), v1.5 released March 2025 — [GitHub filaPro/cad-recode](https://github.com/filaPro/cad-recode)

**cadrille (Kolodiazhnyi et al., arXiv 2505.22914, May 2025; v3 Feb 2026 retitled "Multimodal CAD Reconstruction with Reinforcement Learning")** — point cloud, multi-view images, or text → CadQuery
- **Base model:** Qwen2-VL-2B. Points enter through a CAD-Recode-style linear projection.
- **SFT:** on Text2CAD/DeepCAD (about 160k) plus CAD-Recode 1M procedural programs. 120k steps, lr 2e-4, batch 8×4 accumulation, on a single H100.
- **RL:** on DeepCAD/Fusion360 training meshes without CAD annotations, keeping only "hard" examples (mean reward below 7.5).
- **Methods compared:** offline DPO (5 samples, β=0.3) vs online "Dr. CPPO" (Dr. GRPO plus CPPO, group 16, keep 4). RL ran on 8× H100.
- **Reward:** 10 × IoU with the GT mesh, and −10 for invalid code.
- **Results after RL (CD / IoU% / IR%):**
  - Points: DeepCAD 0.17 / 90.2 / 0.0; Fusion360 0.17 / 85.0 / 0.2; CC3D 0.47 / 67.9 / 0.2
  - Multi-view images: DeepCAD 0.17 / 92.2 / 0.0; Fusion360 0.17 / 84.6 / 0.0; CC3D 0.57 / 65.0 / 0.1
  - Text (SFT only): DeepCAD CD 0.21, IoU 81.1, IR 1.4
- **Inference:** about 2 s per sample (points or images), 3.9 s (text).
- Source: [cadrille v3](https://arxiv.org/html/2505.22914v3)
- **Availability:** code under Apache-2.0. SFT and RL weights are on Hugging Face (maksimko123/cadrille, maksimko123/cadrille-rl). The README says "We don't provide RL fine-tuning code for now" — [GitHub col14m/cadrille](https://github.com/col14m/cadrille)

**Text-to-CadQuery (arXiv 2505.06507, May 2025)** — text → CadQuery
- **Data:** It adds 170K CadQuery annotations to Text2CAD. These were generated by Gemini 2.0 Flash from minimal JSON, with an execute-and-fix loop plus a visual comparison check that reached about 85% executable. The whole annotation run took 9 h and cost $170.
- **Models fine-tuned:** CodeGPT-small 124M, GPT-2 medium 355M and large 774M, Gemma3-1B, Qwen2.5-3B (all full SFT), and Mistral-7B (LoRA). All ran on 1–2× A100 80GB, with the longest run (Mistral-7B) at 33 h. By comparison, the Text2CAD transformer took 2 days on 1× A100 from scratch.
- **Best model (Qwen2.5-3B):** median CD×10³ 0.191, mean 10.229, IR 6.5%, Gemini-judge 69.30%, vs Text2CAD at 0.370 / 26.417 / 3.5% / 58.80%. Mistral-7B LoRA has the lowest IR (1.32%) but lower accuracy, which the authors attribute to insufficient data.
- **GPT-4.1-mini fine-tuned on a 10k subset:** 0% IR, with accuracy around the 7B model's.
- **Open models zero-shot:** most failed to produce valid CadQuery during annotation trials.
- Source: [arXiv 2505.06507](https://arxiv.org/pdf/2505.06507)
- **Availability:** repo at Text-to-CadQuery/Text-to-CadQuery. GitHub reports no license file — [GitHub](https://github.com/Text-to-CadQuery/Text-to-CadQuery)

**CAD-Coder (Guan et al., NeurIPS 2025; arXiv 2505.19713)** — text → CadQuery with chain-of-thought (CoT) and GRPO
- **Base model:** Qwen2.5-7B-Instruct.
- **Data:** The pipeline has DeepSeek-V3 synthesize CadQuery candidates for Text2CAD items, then keeps the lowest-CD executable script. This gives 110K text–CadQuery–mesh triplets, of which 8K are "high-quality" SFT samples, plus 1.5K CoT cold-start samples.
- **Training:** SFT for 3 epochs (lr 1e-5, batch 64, about 7 h), then GRPO (verl) for 1 epoch over 150K Text2CAD descriptions. GRPO used batch 384, k=8, KL β=0.001, and took **146 h**. Everything ran on 8× A800 80GB.
- **Reward:** piecewise linear on Chamfer distance (1.0 if CD<1e-5, 0 if CD>0.5 or the code fails, 0.01 at CD=0.5), plus a regex format reward for CoT tags.
- **Main results (mean CD×10³ / median / IR%):**
  - CAD-Coder: 6.54 / 0.17 / 1.45
  - Text2CAD: 29.29 / 0.37 / 3.75
  - GPT-4o: 143.5 / 40.96 / 70.5
  - Claude-3.7-sonnet: 186.53 / 134.16 / 47.03
  - DeepSeek-V3: 186.69 / 107.57 / 51.96
  - Qwen2.5-72B: 209.41 / 153.81 / 82.64
  - Qwen2.5-7B: 202.35 / 169.86 / 98.83
- **Ablation (mean / median CD×10³, IR%):**
  - SFT only: 74.55 / 0.33, IR 5.33%
  - GRPO without SFT: 76.20 / 0.95
  - SFT+GRPO without CoT: 17.34 / 0.20, IR 4.95%
  - Full: 6.54 / 0.17, IR 1.45%
- **SFT data quality:** 8K high-quality samples beat 70K medium-quality ones (mean CD 6.54 vs 9.89).
- **Failure modes:** the appendix notes "reward hacking behavior, revealing limitations in handling overlapping features and tight geometric…" constraints.
- Source: [CAD-Coder NeurIPS 2025 paper](https://proceedings.neurips.cc/paper_files/paper/2025/file/564a224e88f2490f3c1deaae877d37e3-Paper-Conference.pdf)
- **Availability:** repo gudo7208/CAD-Coder (no license file per GitHub API) and an HF page gudo7208/CAD-Coder — [HF](https://huggingface.co/gudo7208/CAD-Coder)
- **Naming caution:** at least three different 2025 papers are called "CAD-Coder" (2505.06507 is Text-to-CadQuery, 2505.08686 by Wang et al., and 2505.19713) — [awesome-ai4cad](https://github.com/gudo7208/awesome-ai4cad)

**CADmium (arXiv 2507.09792, Jul 2025)** — text → JSON-formatted CAD sequence
- It fine-tunes Qwen2.5-Coder-14B with LoRA on re-annotated DeepCAD text and releases fine-tuned models under Apache 2.0. It is "competitive" with Text2CAD and better on some metrics — [CADmium arXiv](https://arxiv.org/html/2507.09792v3)
- A third party (HierCAD, arXiv 2607.11339) reports CADmium ahead of Text2CAD on Arc F1 (75.68 vs 36.27) and mean CD (44.52 vs 63.47) — [HierCAD](https://arxiv.org/pdf/2607.11339)

**CADCodeVerify / CADPrompt (ICLR 2025, arXiv 2410.05340)** — prompted VLM, text → CadQuery, with a visual self-verification loop
- It is training-free. The VLM asks itself validation questions about renders of its own output and refines the code. It introduces the CADPrompt benchmark and was tested with GPT-4, Gemini 1.5 Pro and CodeLlama. A summary reports −7.30% point-cloud distance and +5.0% success rate for GPT-4 — [ICLR 2025 paper](https://proceedings.iclr.cc/paper_files/paper/2025/file/81a934cd364e18ea6fdeaf57a93c17d4-Paper-Conference.pdf); [alphaxiv summary](https://www.alphaxiv.org/abs/2410.05340)
- Repo Kamel773/CAD_Code_Generation, no license file per GitHub API — [GitHub](https://github.com/Kamel773/CAD_Code_Generation)

**Query2CAD (arXiv 2406.00144, Jun 2024)** — prompted LLM, text → FreeCAD macros
- Training-free, with a self-refinement loop. GPT-4 Turbo reaches a 53.6% first-attempt success rate — [arXiv 2406.00144](https://arxiv.org/abs/2406.00144); [GitHub](https://github.com/akshay140601/Query2CAD) (no license file)

**CAD-Assistant** — a tool-augmented VLLM planner that writes FreeCAD Python, zero-shot. No benchmark numbers were verified — [LLMs-CAD survey taxonomy](https://github.com/lichengzhanguom/LLMs-CAD-Survey-Taxonomy)

**CAD-GPT** — an MLLM generating CAD construction sequences from a single image or text, with an emphasis on spatial reasoning. No numbers were verified — [LLMs-CAD survey taxonomy](https://github.com/lichengzhanguom/LLMs-CAD-Survey-Taxonomy)

**OpenECAD (arXiv 2406.09913)** — an efficient VLM that generates editable 3D CAD code from images — [awesome-ai4cad](https://github.com/gudo7208/awesome-ai4cad). Base model and license were not verified (the repo URL tried, PolyU-HK/OpenECAD, returned 404).

**Img2CAD — two different papers share the name**
- arXiv 2408.01437: reverse engineering via "VLM-assisted conditional factorization". A VLM infers discrete global structure, then a separate model predicts continuous attributes.
- A separate "Img2CAD: Conditioned 3-D CAD Model Generation From Single Image With Structured Visual Geometry" (arXiv 2410.03417).
- Source: [awesome-ai4cad](https://github.com/gudo7208/awesome-ai4cad)

**GenCAD (arXiv 2409.16294)** — image-conditioned CAD command generation using contrastive learning and diffusion priors. It is not LLM-based — [awesome-ai4cad](https://github.com/gudo7208/awesome-ai4cad)

**Image→CadQuery with RL, 2025–2026**
- **ReCAD (AAAI 2026 oral, arXiv 2512.06328):** SFT then GRPO, base Qwen2.5-VL-7B-Instruct. ReCAD-VL image-to-CAD on DeepCAD: IoU-best 63.14 and median CD 7.45; Fusion360 54.93 — [ReCAD PDF](https://faculty.fudan.edu.cn/__local/0/D2/CC/D3026842510847F68CEB05EE848_0AE8E22B_128CCF9.pdf); venue per [awesome-ai4cad](https://github.com/gudo7208/awesome-ai4cad)
- **GACO-CAD (arXiv 2510.17157, Oct 2025):** single image → CAD. SFT, then RL with an IoU-based geometric reward (thresholds 0.4 and 0.8) plus a conciseness/length reward — [GACO-CAD](https://arxiv.org/html/2510.17157)
- **GIFT (arXiv 2603.27448, Mar 2026)** cites GACO-CAD-RL at IoU 0.864 (image + depth + normal) vs ReCAD-VL at 0.631 (image only) — [GIFT](https://arxiv.org/html/2603.27448)
- **CAD-RL (arXiv 2508.10118):** "From Intent to Execution: Multimodal Chain-of-Thought RL for Precise CAD Code Generation" — [arXiv](https://arxiv.org/pdf/2508.10118)
- **CME-CAD (CVPR 2026, arXiv 2512.23333):** heterogeneous multi-expert RL for CAD code — [arXiv](https://arxiv.org/pdf/2512.23333)
- **ConCAD (arXiv 2609.34494):** constraint-aware image-to-CAD with dual-granularity rewards. It lists ReCAD at IoU 0.723 and zero-shot Qwen3-VL-2B at 0.160 — [ConCAD](https://arxiv.org/html/2609.34494)

**Other 2025–2026 text-to-CAD works (titles/venues only, not deep-read)**
- ToolCAD (tool-using LLM with RL; arXiv 2604.07960) — [arXiv](https://arxiv.org/html/2604.07960v2)
- PR-CAD (ICLR 2026, arXiv 2604.19773) — [arXiv](https://arxiv.org/pdf/2604.19773)
- CAD-Tokenizer (ICLR 2026, 2509.21150)
- NURBGen (AAAI 2026, 2511.06194; code at SadilKhan/NURBGen)
- STEP-LLM (2601.12641; code available)
- HierCAD (2607.11339)
- ProCAD / "Clarify Before You Draw" (2602.03045)
- Test-time scaling via consensus selection (2608.09706)
- FEA-feedback self-improving agents (2605.17448)
- CADENA (stepwise reverse engineering, 2608.00799; code zhemdi/cadena)
- IndustryForge-27B (2607.28050; HF model)
- Source for the list: [awesome-ai4cad](https://github.com/gudo7208/awesome-ai4cad)

### Inferences
- The "CAD code from a pretrained LLM" paradigm, with CadQuery as the dominant target, is now the mainstream for 2025–2026 work. DSL-token approaches persist mostly as baselines or in specialized settings.
- Weights for permissively usable models are scarce. cadrille (Apache-2.0 code, HF weights) and CADmium (Apache 2.0 models) are the clearest. CAD-Recode and Text2CAD are non-commercial (CC BY-NC 4.0 and a custom/CC BY-NC-SA-style community license).

### Gaps
- FlexCAD's base model, LoRA setup and numbers were not verified here.
- CAD-GPT, CAD-Assistant and OpenECAD base models, metrics and licenses were not verified.
- No "CAD-R1" paper by that exact name was found. Related RL works are listed above instead.
- Licenses of the CAD-Coder and Text-to-CadQuery HF weights were not checked.
- Text2CAD's original paper numbers were not fetched directly; its figures above come from later papers' baseline tables.

## Q2. Which works convert engineering drawings (orthographic views, vector or raster drawings) into parametric CAD, and how well does it work?

### Takeaway
Drawing-to-CAD is less mature than point- or image-to-CAD. Early strong works were domain-restricted (cabinets made of planks), and Drawing2CAD (2025) is a non-LLM seq2seq model on vector drawings with modest gains. An LLM/VLM wave (CAD2Program, Drawing-Recode, Ortho2CAD, SOV-CAD, IterCAD) only appeared in 2025–2026, and this pass found no verified headline numbers on real-world mechanical drawings.

### Cited Findings
- **PlankAssembly (ICCV 2023, arXiv 2308.05744):** a transformer seq model that maps three orthographic line-drawing views to "shape programs" of planks for cabinet-like furniture. It is designed to be robust to noisy or incomplete drawings, unlike back-projection methods — [ICCV open access](https://openaccess.thecvf.com/content/ICCV2023/html/Hu_PlankAssembly_Robust_3D_Reconstruction_from_Three_Orthographic_Views_with_Learnt_ICCV_2023_paper.html). Code is under AGPL-3.0 — [GitHub manycore-research/PlankAssembly](https://github.com/manycore-research/PlankAssembly)
- **CAD2Program (AAAI 2025, arXiv 2412.11892):** treats a 2D CAD drawing as a raster image, regardless of its original format, and encodes it with a standard ViT. It autoregressively predicts a general-purpose text language describing 3D parametric models. It is trained on a large cabinet dataset and is "competitive" with vector-input methods while placing fewer restrictions on the input — [arXiv abstract](https://arxiv.org/abs/2412.11892). Repo license is CC-BY-SA-4.0 — [GitHub manycore-research/CAD2Program](https://github.com/manycore-research/CAD2Program)
- **Drawing2CAD (ACM MM 2025, arXiv 2508.18733):** vector engineering drawings (SVG primitives, 1–4 views) feed a dual-decoder transformer that separates command type from parameters, trained with a soft-target loss. It introduces the CAD-VGDrawing dataset of more than 150K drawing/CAD pairs.
  - MCD: 11.98 vs 12.15 for DeepCAD-vector with three views, and 10.88 vs 11.37 with four views. These are small margins.
  - Sources: [arXiv 2508.18733](https://arxiv.org/abs/2508.18733); [HF papers](https://huggingface.co/papers/2508.18733)
  - Code and data are under MIT — [GitHub lllssc/Drawing2CAD](https://github.com/lllssc/Drawing2CAD)
- **2026 drawing/orthographic works (titles only):** Drawing-Recode (arXiv 2607.27558), IterCAD (ACM MM 2026, 2608.24020), Ortho2CAD (2607.08891) and SOV-CAD (2607.04119). The list notes that Ortho2CAD and SOV-CAD use reward-based or offline RL — [awesome-ai4cad](https://github.com/gudo7208/awesome-ai4cad)
- **CadVLM (arXiv 2409.17457):** a VLM for parametric 2D sketch generation and completion at the sketch level, not full 3D — [arXiv](https://arxiv.org/pdf/2409.17457)

### Inferences
- Engineering drawings carry explicit dimensions, which text prompts lack; CAD-MLLM names missing absolute dimensions as a failure cause. Drawing input is therefore a natural fit for exact parametric output, but no surveyed work demonstrates robust extraction of dimension annotations or GD&T from real PDFs.
- The cadrille/CAD-Recode recipe (procedural CadQuery data, then render synthetic views, then a VLM with RL) is a plausible template for drawings. Drawing-Recode's name suggests exactly this, but it is unverified.

### Gaps
- No verified quantitative results for the 2026 LLM-based drawing works.
- No evidence was found of evaluation on real scanned or raster industrial drawings with dimension callouts.

## Q3. How does RL with kernel/geometry rewards compare to SFT alone? What reward designs are used?

### Takeaway
In every paper checked, RL after SFT gives large gains: invalidity drops to near zero, and IoU and CD improve substantially. Online methods (GRPO variants) beat offline DPO. RL without an SFT warm start fails. Rewards are simple: executing the CAD kernel, then IoU or Chamfer against the ground-truth mesh, plus an invalid-code penalty and sometimes format or conciseness terms.

### Cited Findings
- **cadrille:** reward = 10×IoU, −10 if the code is invalid. Online Dr. CPPO raised IoU by about 3–9 points over SFT across benchmarks and drove the invalidity ratio to about 0%. Offline DPO reduced invalidity but "barely changes accuracy", and DPO is capped by the best sampled output. The authors also note instability in point-cloud RL — [cadrille v3](https://arxiv.org/html/2505.22914v3)
- **CAD-Coder (text→CadQuery, Qwen2.5-7B):**
  - Reward: piecewise linear on Chamfer distance, plus a format reward.
  - SFT only gives mean CD×10³ 74.55. SFT+GRPO gives 17.34, and SFT+CoT+GRPO gives 6.54.
  - GRPO without SFT gives 76.20, i.e. RL needs the SFT prior.
  - IR falls from 5.33% to 1.45%.
  - Cost: GRPO took 146 h on 8× A800 vs 7 h for SFT.
  - Reward hacking was observed on overlapping features.
  - Source: [CAD-Coder NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/file/564a224e88f2490f3c1deaae877d37e3-Paper-Conference.pdf)
- **GACO-CAD:** IoU reward with lower and upper thresholds (0.4 and 0.8), plus a length/conciseness reward that favors shorter programs — [GACO-CAD](https://arxiv.org/html/2510.17157)
- **ReCAD:** GRPO after SFT on Qwen2.5-VL-7B — [ReCAD](https://faculty.fudan.edu.cn/__local/0/D2/CC/D3026842510847F68CEB05EE848_0AE8E22B_128CCF9.pdf)
- **cadrille RL data:** RL can use meshes without CAD annotations; cadrille's RL stage uses DeepCAD and Fusion360 meshes only, keeping hard examples — [cadrille v3](https://arxiv.org/html/2505.22914v3)

### Inferences
- Because geometric rewards need only a target mesh, RL opens training on unlabeled mesh/B-rep collections. This is a key data-efficiency lever over SFT, which needs paired code.
- RL wall-clock is dominated by CAD-kernel execution and mesh comparison per sample (CAD-Coder: 146 h of GRPO vs 7 h of SFT). Fast, sandboxed CadQuery/OCC execution is the practical bottleneck.

### Gaps
- No head-to-head comparison of IoU vs Chamfer as reward signal was found.
- No study was found on topology- or design-intent-aware rewards (e.g. feature count, constraint satisfaction). ConCAD's "constraint-aware dual-granularity rewards" may address this but was not read.

## Q4. How does output representation (Python CAD code vs compact DSL tokens) affect performance, data efficiency, and use of LLM pretraining?

### Takeaway
Python/CadQuery output lets small pretrained code LMs beat from-scratch DSL transformers. Even a 124M Python-pretrained model beats the 363M Text2CAD. CadQuery is also directly executable and editable by general LLMs. The trade-offs are longer sequences, and an invalid-code failure mode that must be controlled with scale or RL.

### Cited Findings
- **Text-to-CadQuery:**
  - Fine-tuned CodeGPT-small (124M, Python-pretrained) beat Text2CAD (363M DSL transformer) on all accuracy metrics, while GPT-2 medium (355M, not code-specialized) did not improve further. This is attributed to Python pretraining priors.
  - Accuracy rises with model size up to 3B. Mistral-7B LoRA lagged on accuracy (attributed to insufficient data) but had the lowest IR.
  - Source: [Text-to-CadQuery](https://arxiv.org/pdf/2505.06507)
- **Fine-tuning cost:** under 1 h for 124M and 33 h for 7B, on a single A100. Training the Text2CAD transformer from scratch took 2 days — [Text-to-CadQuery](https://arxiv.org/pdf/2505.06507)
- **CAD-Recode:** shows that CadQuery output from Qwen2-1.5B lets GPT-4o do editing and CAD QA on the result with a generic prompt — [project page](https://cad-recode.github.io)
- **CAD-Llama** sits between the two approaches: it converts DeepCAD commands into a Python-like hierarchical DSL (SPCC) with semantic component names, and reports large gains over Text2CAD (ACC_T 84.72 vs 69.91) — [CAD-Llama](https://arxiv.org/html/2505.04481v2)
- **CADmium** keeps a JSON sequence representation but uses a code LLM (Qwen2.5-Coder-14B) and reaches parity or better with Text2CAD — [CADmium](https://arxiv.org/html/2507.09792v3)
- **Zero-shot frontier LLMs** are poor at precise CadQuery. Invalidity ratios: GPT-4o 70.5%, Claude-3.7-sonnet 47.0%, Qwen2.5-7B 98.8% on Text2CAD test prompts — [CAD-Coder](https://proceedings.neurips.cc/paper_files/paper/2025/file/564a224e88f2490f3c1deaae877d37e3-Paper-Conference.pdf)

### Inferences
- For a small-compute project, Python CAD code on a 1.5–3B code-pretrained model is the most data- and compute-efficient starting point. Procedural program generation (CAD-Recode's 1M) supplies unlimited paired data.
- DSL tokens remain attractive for very compact sequences or for diffusion/VAE latent models, but they forfeit LLM pretraining and readability.

### Gaps
- No controlled study was found that holds model and data fixed and varies only the output language (CadQuery vs build123d vs OpenSCAD vs FeatureScript).
- None of the works checked targets FeatureScript or build123d (aside from a FreeCAD/OpenSCAD minority).

## Q5. What base models and compute budgets are used, and what is feasible on a few consumer/prosumer GPUs?

### Takeaway
Typical base models are Qwen2-1.5B, Qwen2-VL-2B, Qwen2.5-3B, Qwen2.5-7B, Qwen2.5-VL-7B, LLaMA3-8B, Vicuna-7B and Qwen2.5-Coder-14B (LoRA). SFT for models of 3B and under fits on a single 80GB GPU in hours to a day. The RL stages are the expensive part (8× H100/A800, days), and not all RL code is released.

### Cited Findings

| Work | Base model | Compute |
|---|---|---|
| cadrille | Qwen2-VL-2B | SFT on 1× H100 (120k steps); RL on 8× H100 — [cadrille v3](https://arxiv.org/html/2505.22914v3) |
| CAD-Coder | Qwen2.5-7B-Instruct | 8× A800 80GB; SFT 7 h; GRPO 146 h. Inference latency <1 s token generation on RTX 4090, V100, A800 and H800 with vLLM — [CAD-Coder](https://proceedings.neurips.cc/paper_files/paper/2025/file/564a224e88f2490f3c1deaae877d37e3-Paper-Conference.pdf) |
| Text-to-CadQuery | 124M–7B | 1–2× A100 80GB; ≤33 h — [Text-to-CadQuery](https://arxiv.org/pdf/2505.06507) |
| CAD-Llama | LLaMA3-8B | 4× A100; 50 GPU-hours total — [CAD-Llama](https://arxiv.org/html/2505.04481v2) |
| CAD-MLLM | Vicuna-7B LoRA | 16× H800; about 47 h — [CAD-MLLM](https://arxiv.org/html/2411.04954v1) |
| CAD-Recode | Qwen2-1.5B (0.5B ablation) | Compute not verified — [ICCV supplement](https://openaccess.thecvf.com/content/ICCV2025/supplemental/Rukhovich_CAD-Recode_Reverse_Engineering_ICCV_2025_supplemental.pdf) |
| ReCAD | Qwen2.5-VL-7B-Instruct | Not verified — [ReCAD](https://faculty.fudan.edu.cn/__local/0/D2/CC/D3026842510847F68CEB05EE848_0AE8E22B_128CCF9.pdf) |
| CADmium | Qwen2.5-Coder-14B LoRA | Not verified — [CADmium](https://arxiv.org/html/2507.09792v3) |

### Inferences
- **Feasible on 1–4 consumer/prosumer GPUs (24–48GB):**
  - LoRA/QLoRA SFT of 1.5–3B (V)LMs on CadQuery.
  - Inference with released cadrille/CAD-Recode weights.
  - Small-scale GRPO with a 2B model, given short programs and cheap CadQuery execution.
- Matching CAD-Coder's 146 h × 8 A800 GRPO run is likely out of reach, though using fewer hard examples (as cadrille does) cuts cost.

### Gaps
- No paper reported results specifically on consumer GPUs for training.
- GPU-hours for cadrille RL and CAD-Recode SFT were not found.

## Q6. Known failure modes

### Takeaway
The recurring failures are:
- Invalid/non-executable code, which zero-shot LLMs hit severely.
- Wrong absolute dimensions from text.
- Missed fine details and thin features.
- Reward hacking on overlapping features.
- Weak generalization beyond DeepCAD-style sketch-extrude parts. Accuracy drops sharply on real scans (CC3D) and is barely measured on complex mechanical parts (fillets, revolves, sweeps, patterns).

### Cited Findings
- **Real-scan generalization gap:** IoU falls from about 90% on DeepCAD to about 65–68% on CC3D for cadrille, and from 87.1 to 60.5 for CAD-Recode — [cadrille v3](https://arxiv.org/html/2505.22914v3)
- **cadrille limitations:** text-based reconstruction is the hardest and remains weak; fine details are missed; there is sim-to-real concern because training uses synthetic renders; naive mixing of DeepCAD and procedural data in SFT hurts — [cadrille v3](https://arxiv.org/html/2505.22914v3)
- **CAD-MLLM:** text lacks absolute dimensions, giving size mismatch; thin structures and fine details fail; dangling edges remain — [CAD-MLLM](https://arxiv.org/html/2411.04954v1)
- **CAD-Llama:** parameter errors and text-command mismatches — [CAD-Llama](https://arxiv.org/html/2505.04481v2)
- **CAD-Coder:** reward hacking and limitations with overlapping features and tight geometric constraints. Zero-shot LLM invalidity is 47–99% — [CAD-Coder](https://proceedings.neurips.cc/paper_files/paper/2025/file/564a224e88f2490f3c1deaae877d37e3-Paper-Conference.pdf)
- **Text-to-CadQuery:** larger models are more executable but need more data to become more accurate. GPT-4.1-mini fine-tuned had 0% IR but no accuracy gain over 7B — [Text-to-CadQuery](https://arxiv.org/pdf/2505.06507)
- **Domain:** benchmarks are predominantly DeepCAD/Fusion360 sketch-extrude parts. CAD-Recode's procedural data uses lines, arcs, circles, boxes and cylinders, and drawing works such as PlankAssembly and CAD2Program are restricted to cabinets — [CAD-Recode](https://cad-recode.github.io); [PlankAssembly](https://openaccess.thecvf.com/content/ICCV2023/html/Hu_PlankAssembly_Robust_3D_Reconstruction_from_Three_Orthographic_Views_with_Learnt_ICCV_2023_paper.html); [CAD2Program](https://arxiv.org/abs/2412.11892)
- **Metric inconsistency:** cross-paper IoU numbers use different normalizations. GIFT's IoU-best normalizes by inertia tensor and aligns principal axes, so image-to-CAD numbers across papers are not comparable — [GIFT](https://arxiv.org/html/2603.27448)

### Inferences
- Design-intent qualities are essentially unmeasured by current metrics (CD, IoU, IR, exact-match, LLM-judge). These include meaningful parameters, constraints, feature semantics, and editability under parameter change. This is a gap a design-intent project could target.

### Gaps
- No standard benchmark was found for complex industrial parts or for parametric editability/robustness under parameter perturbation.
- No verified quantitative study of hallucinated features exists beyond qualitative failure figures.

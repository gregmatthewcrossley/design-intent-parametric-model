# Agentic LLM + CAD-Kernel Systems, Commercial Landscape, and Open Problems (as of Nov 15, 2026)

Scope note: research ran Nov 15, 2026 with about 25 search/fetch calls. arXiv PDFs for RealCADBench, TOOLCAD and CADTests were too large or unreadable to fetch, so their headline numbers come from abstracts only. Several commercial claims come from trade press or competitor blogs and are flagged as such.

## 1. Agentic / tool-using approaches and measured performance (frontier LLMs + kernel/visual feedback)

### Takeaway
Prompted frontier models (GPT-5.x, Claude 4.5, Gemini 3) writing CadQuery or FreeCAD Python now clearly beat older purpose-trained text-to-CAD models on geometric fidelity for simple and medium parts. They still fail badly on advanced features (sweep, loft, shell), with invalid rates of 54–92% at the hardest levels. Kernel error retry and visual self-verification give consistent but modest gains: a few points of success rate and about 11–18% lower geometric error in CADCodeVerify. The only near-perfect results (99.8% validity in ReliCAD) come from systems that add a structured spec, a constraint solver and a verification-repair loop, not from the LLM alone.

### Cited Findings
**Visual self-verification (CADCodeVerify, ICLR 2025, arXiv 2410.05340)**
- Method: a VLM writes CadQuery, renders the result, generates and answers its own validation questions about the render, then repairs the code. Two refinement rounds were run. The benchmark is CADPrompt, with 200 NL prompts paired with expert CadQuery code. — [arXiv 2410.05340](https://arxiv.org/abs/2410.05340v1); [ICLR 2025](https://iclr.cc/virtual/2025/poster/30576)
- Table 2 (success rate / point-cloud distance / IoGT):
  - GPT-4 zero-shot: 92.0% / 0.153 / 0.935 with no refinement, and 94.0% / 0.132 / 0.941 with CADCodeVerify.
  - GPT-4 few-shot: 96.0% / 0.155 / 0.939 → 96.5% / 0.127 / 0.944.
  - Gemini few-shot: 85.0% → 85.0% success, with distance 0.171 → 0.147.
  - CodeLlama few-shot: 67.0% → 73.5% success, with distance 0.224 → 0.185.
  - The 3D-Premise baseline (image-only feedback) sometimes *lowered* success: GPT-4 few-shot went to 91.0%. — [arXiv html v1](https://arxiv.org/html/2410.05340v1)
  - Computed gains: +0.5 to +6.5 success points and 11–18% lower point-cloud distance. Weaker models gain more. — same source
- Abstract-level claim: "5.0% improvement in success rate" and "7.30% reduction in point cloud distance" for GPT-4. An earlier rendering said 5.5%. — [HF papers](https://huggingface.co/papers/2410.05340)

**Frontier-model benchmark: Text2CAD-Bench (arXiv 2605.18430, May 2026)**
- 600 human-curated CadQuery tasks across 4 levels. Each model gets up to 3 retries with the kernel error message, and the best attempt counts. — [arXiv 2605.18430](https://arxiv.org/html/2605.18430v1)
- Results on the geometric prompt, as CD×10³ / invalid rate / IoU:
  - GPT-5.2: L1 44.31 / 11.1% / 0.59, L2 60.38 / 20.0% / 0.50, L3 93.46 / 68.0% / 0.23.
  - Claude-4.5-Sonnet: L1 52.62 / 20.3% / 0.54, L2 71.66 / 43.7% / 0.48, L3 70.13 / 70.0% / 0.25.
  - DeepSeek-V3.2: L1 53.15 / 13.3% / 0.54.
  - Gemini-3-Flash: L1 66.82 / 17.7% / 0.44. Its reported L3 IR of 12.8% is anomalous and unexplained in the paper. — same
- Purpose-trained models were far worse on fidelity:
  - Text2CAD: IoU 0.08 / 0.04 / 0.04 at L1–L3, despite a low invalid rate of 2–11%. This means valid but wrong geometry.
  - CADFusion: IoU 0.03 with IR 53–70%.
  - Text2CADQuery: IoU 0.02–0.07 with IR 44–80%. — same
- Advanced features (sweep, loft, shell) cause most failures, with most models above 65% IR at L3. L4 IR ranged from 17% (Gemini) to 81% (MiniMax). — same
- Executability, geometric similarity and feature-level correctness are "largely independent." For example, GPT-5.2 leads L1–L3 on CD but scores lowest on the L4 feature-level judge. — same
- CadQuery beats DeepCAD-style command sequences as the output representation for all LLMs. — same
- Retry gains were not ablated, and multi-turn execution feedback was not explored (authors' stated limitation). — same

**Industrial benchmark: RealCADBench (arXiv 2609.03773, Sep 3, 2026)**
- 12,632 tasks from 19 factory-automation categories. Inputs are text, 2D engineering drawings, product photos and renders. Output is FreeCAD Python. A 1,770-task evaluation slice includes a 25-task assembly study. — [arXiv 2609.03773](https://arxiv.org/abs/2609.03773)
- Across six frontier models on part tasks: executability 0.565–0.812, Solid IoU 0.284–0.538, Surface IoU 0.112–0.217. No model led all metrics. — same
- Assemblies: the Codex agent with GPT-5.5 improved executability and IoU over standalone GPT-5.5 but scored 6.98 points *lower* on the rubric Judge. In other words, an agentic loop raised validity metrics but not judged design quality. — same
- Recurring failures: missing fine structures, loss of part identity, and incorrect assembly placement. — same

**Spec + kernel + verify/repair loop: ReliCAD (arXiv 2609.22325, Sep 16, 2026)**
- Pipeline: user requirements → structured spec (geometric relations, topological dependencies, feature order) → constraint-aware instructions → CAD kernel via an "agent-ready API" with constraint solving → runtime evidence → a verification-feedback loop that localizes and repairs errors. — [arXiv 2609.22325](https://arxiv.org/abs/2609.22325)
- Reported 99.8% validity and IoU 0.8753 on HistCAD generation. Baseline numbers are not in the abstract. — same

**RL-trained tool-using open models: TOOLCAD (arXiv 2604.07960, ACL 2026)**
- An interactive "CAD modeling gym" with a CAD engine providing hybrid feedback. Training uses CAD chain-of-thought SFT followed by online curriculum RL. The authors claim open LLMs reach parity with proprietary models. — [arXiv 2604.07960](https://arxiv.org/abs/2604.07960)
- Search-snippet figures from its table: GPT-4o + ReAct 62.7% average success; Qwen3-235B-A22B + ReAct 60.5%. — [TOOLCAD PDF via search](https://arxiv.org/pdf/2604.07960). These are unverified because the PDF could not be fetched.

**Test-based evaluation: CADTests / CADTestBench (arXiv 2605.07807, May 8, 2026)**
- Proposes "executable software tests that verify whether a generated CAD model satisfies" the prompt's geometric and topological requirements. These tests also serve as generation guidance, and simple test-guided baselines reportedly beat current methods. Code and data are released. — [arXiv 2605.07807](https://arxiv.org/abs/2605.07807)

**MCP servers and practitioner agent loops**
- Zoo exposes its CAD tools through a Zoo-MCP server so external agents can drive KCL. — [Zoo Zookeeper research page](https://docs.zoo.dev/research/zookeeper)
- Onshape Labs (opened Jul 2026) shipped a FeatureScript MCP Server, GA Aug 2026. This is a single-source claim from a Leo AI blog. — [getleo.ai](https://www.getleo.ai/blog/onshape-built-in-ai)
- Autodesk announced Fusion MCP servers. Details were not retrieved. — [Engineering.com AU 2026](https://www.engineering.com/au-2026-autodesks-ai-assistant-is-evolving/)
- FreeCAD + Claude via MCP: one forum user called earlier copy-paste use "mediocre" but MCP "a much different experience." — [V1E forum](https://forum.v1e.com/t/freecad-and-claude-with-mcp/54958)

### Inferences
- Kernel and visual feedback are necessary but not sufficient. They mostly fix syntax and API errors and small geometric deviations. They do not fix wrong feature strategy or advanced-feature failures. The big jumps (ReliCAD) come from adding an explicit intermediate spec and constraint solving.
- Agentic loops can game executability and IoU at the expense of holistic quality (the RealCADBench Codex result). Evaluation needs spec or test checks, not only IoU.
- For a solo builder, the cheapest strong baseline in late 2026 is a frontier model + CadQuery/FreeCAD + retries + render critique. Gains beyond that likely need structured specs, CADTests-style verifiers, or RL on a gym (TOOLCAD).

### Gaps
- I did not retrieve primary numbers for CAD-Assistant (FreeCAD tool-using VLM), Query2CAD, CADDesigner or LLM4CAD.
- I found no source reporting cost or latency per successful part for agent loops. Anecdotes: an HN user reports "several minutes of thinking" before many failures ([HN](https://news.ycombinator.com/item?id=47411437)), and SGS-1 took about 3 minutes per solid ([WorldCAD Access](https://upfrontezine.substack.com/p/whats-new-in-cad-bcc)).
- No controlled ablation isolates kernel-error retry from visual critique on 2026 frontier models.

## 2. Commercial landscape: what is shipped vs. announced

### Takeaway
As of Nov 2026, the only shipped products that generate *editable parametric* models from prompts are code-based: Zoo's Zookeeper/KCL and Adam (CadQuery/OpenSCAD). The incumbents (Autodesk, Dassault, PTC, Siemens) mostly ship assistants: help chat, AutoConstrain, drawing automation. Their generative features (Autodesk neural CAD, AutoTimeline, AutoAssemble) are announced without dates. Native B-rep generators like Spectral SGS-1 output STEP without feature trees and degrade quickly with complexity.

### Cited Findings
**Zoo (formerly KittyCAD)**
- Zookeeper is a conversational agent in Zoo Design Studio. It shipped Jan 2026 with Design Studio v1.1; one third-party source says Feb 2026. — [Zoo docs](https://docs.zoo.dev/research/zookeeper); [Zoo press](https://zoo.dev/press/zoo-introduces-zookeeper)
- Zookeeper writes and executes KCL, Zoo's geometry language, and returns a parametric solid with a feature tree. It uses engineering tools such as mass, volume and surface-area checks. — [Digital Engineering 24/7](https://www.digitalengineering247.com/article/zoo-introduces-zookeeper-agent-for-cad-design/products); [getleo.ai review](https://www.getleo.ai/blog/zoo-text-to-cad-review)
- Access: the ML-ephant API and Zoo-MCP. An enterprise pilot converts customers' proprietary CAD into KCL and fine-tunes on it. — [Zoo enterprise](https://zoo.dev/enterprise)
- KCL 3.0 / Design Studio 1.5 reportedly improve fillets and Booleans. This is a third-party claim I did not verify. — [Zoo blog](https://zoo.dev/blog)
- A competitor hands-on (Leo AI, dated May or Nov 2026) found Zoo good on simple parts (L-bracket, flanged bearing housing). A sensor enclosure with snap-fits came out with misaligned walls and non-functional snaps. The review calls Zoo output "mesh-based (STL)," which conflicts with Zoo's own feature-tree/KCL claims and probably reflects the older Text-to-CAD endpoint. — [getleo.ai comparison](https://www.getleo.ai/blog/text-to-cad-tools-comparison-guide)

**Adam**
- YC W25. $4.1M seed led by TQ Ventures. — [mezha.net](https://mezha.net/eng/news/adam-startup-raises-4-1m-to-revolutionize-ai-cad-modeling/); [Futurism Today](https://thefuturismtoday.com/startups/adam-ai-powered-cad-tool-raises-seed-funding/)
- An LLM writes CadQuery/OpenSCAD, so models are parametric via variables. Failures in the Leo AI test: complex surfacing, organic shapes and assemblies with mates. A gearbox housing failed to compile because of Booleans on non-intersecting bodies. — [getleo.ai comparison](https://www.getleo.ai/blog/text-to-cad-tools-comparison-guide)

**Spectral Labs SGS-1 (announced Sep 2025)**
- Image or mesh → B-rep STEP. The company claims it beats GPT-5 and HoLa-BRep, but its comparison shows only cases where HoLa produced valid solids. — [Spectral SGS-1](https://www.spectrallabs.ai/research/SGS-1); [AI CAD Frontier post](https://www.spectrallabs.ai/research/The-AI-CAD-Frontier)
- Independent and competitor tests:
  - Simple parts are fine.
  - Fillets lose tangency, and planar faces come out slightly warped.
  - A multi-pocket housing was "unusable."
  - Output has no feature tree. — [getleo.ai](https://www.getleo.ai/blog/text-to-cad-tools-comparison-guide)
  - A test from a 1966 drawing was "reasonable but failed," taking about 3 minutes. — [WorldCAD Access](https://upfrontezine.substack.com/p/whats-new-in-cad-bcc)
- Spectral's own view is that the code/VLM category "produces the most useful outputs for engineering," but "VLMs do not have good spatial understanding." — [AI CAD Frontier](https://www.spectrallabs.ai/research/The-AI-CAD-Frontier)

**Autodesk (status at AU 2026)**
- Live: AutoConstrain, Building Layout Explorer, and the in-product Autodesk Assistant (mainly a support chatbot). — [Engineering.com](https://www.engineering.com/au-2026-autodesks-ai-assistant-is-evolving/)
- Announced without dates:
  - Fusion AutoTimeline: imported solid → parametric feature tree.
  - AutoAssemble: finds connection points and creates constraints and a timeline.
  - Find Similar, AI CAM toolpaths, and an agentic PLM experience.
  - The standalone Assistant, with timing and pricing due in 2027.
  - Project Quill, which remains research. — same
- Neural CAD, which grew from Project Bernini (AU 2024), targets editable B-rep from text, sketches and images. The author says it was "more promise than product" in 2025 and still has a long road in 2026. — same; [Autodesk neural tech](https://www.autodesk.com/solutions/autodesk-ai/neural-technology); [DEVELOP3D](https://develop3d.com/cad/autodesks-ai-blueprint-for-cad/)

**Dassault SOLIDWORKS 2026**
- AURA is a knowledge/conversational assistant built on docs, manuals and forums, reportedly running on Mistral on Dassault's Outscale cloud. LEO is the "design companion." Both are in the Labs (beta) tab, with commercial access from 2026 FD03. — [SOLIDWORKS blog](https://blogs.solidworks.com/products/solidworks/meet-the-solidworks-ai-design-companions/); [CADimensions](https://resources.cadimensions.com/cadimensions-resources/aura-your-new-personal-design-assistant-in-solidworks-0)
- Per one review, AURA "doesn't create parts from text." — [texocad blog](https://blog.texocad.ai/posts/solidworks-aura-ai)
- AI-powered drawing creation is a separate feature. — [Introducing SOLIDWORKS 2026](https://www.solidworks.com/media/introducing-solidworks-2026)

**PTC Onshape**
- AI Advisor is embedded in the workspace and grounded in Onshape docs and the Learning Center. It explicitly does not generate designs or do generative design. — [Onshape blog](https://www.onshape.com/en/blog/ai-advisor-artificial-intelligence-cad-engineering-software); [DE247](https://www.digitalengineering247.com/article/onshape-ai-advisor-now-embedded-directly-in-the-design-environment)
- Onshape Labs plus the FeatureScript MCP Server (2026) is a single-source claim. — [getleo.ai](https://www.getleo.ai/blog/onshape-built-in-ai)

**Siemens**
- NX Design Copilot is described only as a natural-language help assistant. I found no evidence of generative geometry. — [getleo.ai comparison](https://www.getleo.ai/blog/built-in-ai-cad-plm-comparison-2026)

**Other startups and funding**
- Backflip AI (scan/mesh-to-CAD): $30M Series A (NEA, a16z), Dec 2024. — [StartupIntros](https://startupintros.com/orgs/backflip-ai)
- Leo AI: $5M seed (Flint Capital), mid-2025. Reported totals vary: $9.7M widely, $12.7M per PitchBook. — [PitchBook](https://pitchbook.com/profiles/company/539820-73); [Seedtable](https://seedtable.com/companies/leo-ai)
- Leo AI is now partly a PDM-search product and publishes competitor reviews, so it has a conflict of interest. — [getleo.ai](https://www.getleo.ai/blog/text-to-cad-tools-comparison-guide)
- One roundup claims Mach9 raised about $49M (Oct 2026 Series A), with Vizcom, Quilter and Backflip behind it. This is unverified aggregator data. — [Apollo Technical](https://www.apollotechnical.com/ai-cad-tools/)
- Autodesk notes that Backflip and CADfit already offer AutoTimeline-like solid → feature-tree conversion. — [Engineering.com](https://www.engineering.com/au-2026-autodesks-ai-assistant-is-evolving/)

### Inferences
- The commercial "parametric from prompt" space is thin and code-first (KCL, CadQuery, OpenSCAD). Incumbents are concentrating on assistive features: constraints, drawings, help, and imported-solid → feature tree.
- The niche of a reliable design-intent-preserving parametric generator for a mainstream CAD system (Onshape/Fusion/SolidWorks feature trees) appears open.
- Incumbent MCP servers (Fusion, Onshape FeatureScript) lower the barrier for frontier-model agents inside mainstream CAD.

### Gaps
- I did not research Vizcom, nTop, CADAgent, Backflip's 2026 product state, Zoo funding or Adam's 2026 product updates.
- Siemens primary sources were not found.
- No vendor publishes independent quality benchmarks. All commercial quality evidence here is anecdotal or from a competitor.

## 3. Fine-tuned open models vs. prompted frontier models vs. from-scratch models

### Takeaway
On text→CadQuery from human-curated prompts, prompted frontier LLMs beat older from-scratch and fine-tuned text-to-CAD models by a wide margin on IoU (Text2CAD-Bench: about 0.5–0.6 vs. under 0.1 at L1). Small fine-tuned VLMs do win on in-distribution image/point-cloud→code tasks (CAD-Coder, CAD-Recode). RL-trained open tool-using agents (TOOLCAD) claim parity with proprietary models.

### Cited Findings
- Text2CAD-Bench L1 IoU: GPT-5.2 0.59, Claude-4.5-Sonnet 0.54. From-scratch Text2CAD scored 0.08, and the fine-tuned Text2CADQuery and CADFusion scored 0.07 and 0.03. — [arXiv 2605.18430](https://arxiv.org/html/2605.18430v1)
- CAD-Coder (arXiv 2505.14646), an open VLM fine-tuned for image→CadQuery, reportedly beats GPT-4.5 and Qwen2.5-VL-72B and gets 100% valid code. The test was only a 100-sample GenCAD-Code subset, which is in-distribution. — [alphaxiv](https://alphaxiv.org/abs/2505.14646)
- CAD-Recode is trained on 1M procedurally generated CadQuery sequences for point cloud→code, and is compared against reverse-engineering baselines rather than LLMs. — [ICCV 2025 PDF](https://orbilu.uni.lu/bitstream/10993/67036/1/CADRecode_ICCV_2025.pdf)
- CADmium (TMLR 2026) fine-tunes Qwen2.5-Coder-14B on GPT-4.1-annotated sequences. It is competitive with or better than Text2CAD, with gains as model size grows. — [arXiv 2507.09792](https://arxiv.org/html/2507.09792v2); [TMLR](https://mlanthology.org/tmlr/2026/govindarajan2026tmlr-cadmium)
- Text-to-CadQuery fine-tunes open models (from Qwen2.5-3B up) on about 170K text–CadQuery pairs. Larger models produce more accurate and executable code. — [arXiv 2505.06507](https://arxiv.org/html/2505.06507v1)
- TOOLCAD: Qwen3-235B + ReAct scores 60.5% vs. GPT-4o + ReAct at 62.7% (snippet). After SFT + RL, the authors claim open models are comparable to proprietary ones. — [arXiv 2604.07960](https://arxiv.org/abs/2604.07960)

### Inferences
- Models trained on DeepCAD/Text2CAD-style data are biased toward the sketch-extrude distribution. They generalize poorly to human-written prompts, producing valid but wrong shapes. A from-scratch model trained on public datasets is unlikely to beat frontier prompting for a solo builder.
- Fine-tuning pays off for narrow, in-distribution input modalities (image/point cloud → code) and for distilling agent behavior into a cheaper open model via RL on a kernel gym.

### Gaps
- I found no published head-to-head that reports cost per valid part or dimensional-correctness accuracy, as opposed to CD/IoU, across all three paradigms.

## 4. Open problems (evidence-backed)

### Takeaway
The unsolved core is everything beyond "a solid that looks right":
- correct feature strategy for advanced operations
- design-intent and constraint capture that survives edits
- assemblies and mates
- grounding of exact dimensions from drawings and photos
- evaluation metrics that measure intent rather than IoU

### Cited Findings
- **Advanced features:** sweep, loft and shell drive invalid rates above 65% at L3 for most frontier models. — [Text2CAD-Bench](https://arxiv.org/html/2605.18430v1)
- **Evaluation beyond geometry:**
  - Executability, geometric similarity and feature-level understanding are decoupled, and execution rate "overstates performance." — [Text2CAD-Bench](https://arxiv.org/html/2605.18430v1)
  - RealCADBench argues execution alone does not capture quality. — [RealCADBench](https://arxiv.org/abs/2609.03773)
  - CADTests proposes requirement-level executable tests. — [CADTests](https://arxiv.org/abs/2605.07807)
- **Assemblies and mates:**
  - Incorrect assembly placement and loss of part identity. — [RealCADBench](https://arxiv.org/abs/2609.03773)
  - Adam fails on assemblies with mates. — [getleo.ai](https://www.getleo.ai/blog/text-to-cad-tools-comparison-guide)
  - Autodesk AutoAssemble is still unreleased. — [Engineering.com](https://www.engineering.com/au-2026-autodesks-ai-assistant-is-evolving/)
- **Fine detail and multimodal grounding:**
  - Missing fine structures from drawings and photos; Surface IoU stays at or below 0.217. — [RealCADBench](https://arxiv.org/abs/2609.03773)
  - "VLMs do not have good spatial understanding." — [Spectral](https://www.spectrallabs.ai/research/The-AI-CAD-Frontier)
- **Design intent and reliability:** the stochastic LLM vs. deterministic CAD mismatch limits "design-intent preservation." ReliCAD's answer is explicit specs plus constraint solving. — [ReliCAD](https://arxiv.org/abs/2609.22325)
- **Data scarcity and quality:** the DeepCAD dataset has many duplicates and little diversity. — [Spectral](https://www.spectrallabs.ai/research/The-AI-CAD-Frontier)
- **Converting legacy solids into editable history:** AutoTimeline, Backflip and CADfit exist, which shows demand, but no robust public solution has been shown. — [Engineering.com](https://www.engineering.com/au-2026-autodesks-ai-assistant-is-evolving/)
- **B-rep quality of native generators:** non-tangent fillets and warped planar faces cause problems in assemblies. — [getleo.ai](https://www.getleo.ai/blog/text-to-cad-tools-comparison-guide)
- **Practitioner reality:**
  - Works for simple prismatic parts, but fails on complex geometry, constraints and assemblies. — [texocad blog](https://blog.texocad.ai/posts/llm-cad-generation) (vendor blog)
  - Hallucinated FreeCAD API calls and wrong argument order. — [texocad FreeCAD post](https://blog.texocad.ai/posts/freecad-ai-macro)
  - An HN user designing an enclosure: most attempts fail after minutes, and successful ones get aspects wrong. — [HN](https://news.ycombinator.com/item?id=47411437)
  - Positive reports come mostly from simple or architectural parts (an HN church tower, a Japanese blog using Opus 5.5 + FreeCAD MCP). — [HN](https://news.ycombinator.com/item?id=47365299); [note.com](https://note.com/teruemon/n/nd9dd34affe90?hl=en)
  - Popular press piece: "I stopped using CAD software and let Claude design my 3D parts." — [MakeUseOf](https://www.makeuseof.com/stopped-using-cad-claude-design-3d-parts/)

### Inferences
- An agent around a frontier model is the best near-term bet for a solo builder. Its differentiators are a structured intermediate spec (dimensions, constraints, feature order), CADTests-style requirement checks, and robust tool APIs that avoid API hallucination (MCP over Onshape FeatureScript, Fusion, or CadQuery). Fine-tuning or RL of an open model is a later cost and latency optimization once a gym and verifier exist.

### Gaps
- I found no 2026 sources measuring these problems quantitatively:
  - robustness to downstream parameter edits
  - topological naming failures
  - GD&T and tolerance generation
  - manufacturability (DFM) awareness
  - long feature histories (more than about 30 features)
  - licensing constraints on training data, such as ABC/Onshape public-document terms
- These remain open but are not evidenced here.

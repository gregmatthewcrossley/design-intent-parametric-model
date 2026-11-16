# FDM dimensional capability (consumer printers, 0.4 mm nozzle, 0.2 mm layers)

Scope: data to replace the placeholders in the PLA/FDM process rule pack (position ±0.1 mm, dimension ±0.15 mm, extrusion width 1.125 × nozzle, overhang 45°, horizontal holes up to Ø10 mm without support), plus hole undersize and elephant's foot for as-made prediction. Researched 2026-11-16. Two primary metrology papers on a current consumer printer (Bambu Lab X1-Carbon, 2026) carry most of the numbers below. Sources marked **(secondhand)** are search-engine summaries or vendor/hobby guides I could not verify against a primary text.

## 1. Typical dimensional and positional accuracy; dependence on size and axis

### Takeaway
An untuned modern consumer printer (Bambu X1C, PLA, 0.4 mm nozzle) prints XY outer dimensions about **0.1 to 0.13 mm undersize**, with small scatter (σ ≈ 0.03 to 0.04 mm). The error is a roughly **constant absolute offset**, not a percentage, so small features suffer most in relative terms. Z runs slightly long (about +0.05 mm) and is the noisier, position-dependent axis. In ISO 286-1 terms this is **IT9 to IT14** depending on size and axis, and ±0.1 to ±0.3 mm is the commonly quoted desktop band.

### Cited Findings
- Byczuk, Rucki et al., euspen ICE 2026 (Bambu Lab X1 Carbon, PLA Basic, 0.4 mm nozzle, 0.2 mm layer, enclosed): rings with 0.8 mm walls, nominal sizes 5/10/15/20/25 mm, 100 parts per size, caliper plus CMM. "Without compensation, all XY dimensions were systematically undersized by approximately −0.12 mm across the nominal size range. The variability was relatively small (std ca. 0.03–0.04 mm)." — [Byczuk et al., euspen 2026, ICE26126](https://www.euspen.eu/knowledge-base/ICE26126.pdf)
- Same study: "Z-height overshoot (ca. +0.05 mm) was observed." — [Byczuk et al. 2026](https://www.euspen.eu/knowledge-base/ICE26126.pdf)
- Same study: "Thin wall thickness was undersized (0.75–0.78 mm)" for a nominal 0.8 mm wall, i.e. −0.02 to −0.05 mm. — [Byczuk et al. 2026](https://www.euspen.eu/knowledge-base/ICE26126.pdf)
- Same study, introduction (citing its ref. [1]): "Typical baseline dimensional accuracy for desktop FDM objects lies in the range of ±0.1–±0.3 mm, corresponding roughly to coarse tolerance classes IT11–IT14." IT7 is "generally considered beyond the native FDM capabilities." — [Byczuk et al. 2026](https://www.euspen.eu/knowledge-base/ICE26126.pdf)
- Same study, compensation: a uniform horizontal expansion of +0.064 mm per side centred the distributions, but small features then overshot by +0.016 to +0.025 mm. The final hybrid correction was +0.05 mm per side, an XY scale of about +0.09%, Z about −1%, and +2 to 3% extrusion for thin walls. After it, all CMM-measured samples were within IT7. Tight tolerances are reachable by per-printer calibration, not natively. — [Byczuk et al. 2026](https://www.euspen.eu/knowledge-base/ICE26126.pdf)
- Gebre, Cristofolini, Zago, Gallo, *Material Design & Processing Communications* 2026, DOI 10.1155/mdp2/7177386 (Bambu Lab X1-Carbon, 0.4 mm nozzle, PLA, 0.16 mm layer, manufacturer-recommended unoptimized settings, CMM plus caliper). "Achievable ISO 286-1 International Tolerance grades ranged from IT9 to IT14 … Absolute dimensional deviations remained approximately constant across nominal sizes, whereas percentage errors increased for smaller features due to scale effects." — [Gebre et al. 2026 (open access PDF)](https://iris.unitn.it/retrieve/aaecc8a0-0420-472b-9a40-4d43d7df5e0b/Material%20Design%20%20%20Processing%20Communications%20-%202026%20-%20Gebre%20-%20Influence%20of%20Geometry%20and%20Size%20on%20Precision%20and%20Accuracy%20in.pdf)
- Gebre et al.: XY deviations showed no significant dependence on plate position (p = 0.98 and 0.13), but Z did (p < 0.001), with "higher negative deviations on the fan-side". The authors attribute this to localized cooling. Larger parts showed this less. — [Gebre et al. 2026](https://iris.unitn.it/retrieve/aaecc8a0-0420-472b-9a40-4d43d7df5e0b/Material%20Design%20%20%20Processing%20Communications%20-%202026%20-%20Gebre%20-%20Influence%20of%20Geometry%20and%20Size%20on%20Precision%20and%20Accuracy%20in.pdf)
- Gebre et al.: curved external surfaces averaged −0.11 ± 0.10 and −0.10 ± 0.10 mm, with extremes from −0.28 to +0.15 mm. Internal corners and top surfaces were within about 0.15 mm of nominal. — [Gebre et al. 2026](https://iris.unitn.it/retrieve/aaecc8a0-0420-472b-9a40-4d43d7df5e0b/Material%20Design%20%20%20Processing%20Communications%20-%202026%20-%20Gebre%20-%20Influence%20of%20Geometry%20and%20Size%20on%20Precision%20and%20Accuracy%20in.pdf)
- Gebre et al., Table 4 comparison: CNC turning and milling reach IT7 to IT10, injection moulding IT8 to IT12, and the tested FDM machine IT9 to IT14. — [Gebre et al. 2026](https://iris.unitn.it/retrieve/aaecc8a0-0420-472b-9a40-4d43d7df5e0b/Material%20Design%20%20%20Processing%20Communications%20-%202026%20-%20Gebre%20-%20Influence%20of%20Geometry%20and%20Size%20on%20Precision%20and%20Accuracy%20in.pdf)
- Older benchmarking: Minetola, Iuliano and Marchiandi (CIRP CMS 2015) expressed FDM accuracy as IT grades using CMM. The industrial Dimension Elite beat the desktop machines in most ISO size ranges, "especially for smaller sizes". These are 2015-era printers, outside the 5-year window. — [Minetola et al. 2015 (Polito repository)](https://iris.polito.it/retrieve/handle/11583/2633926/92483/CMS%202015%20-%20Benchmarking%20of%20FDM%20machines.pdf) **(secondhand: read via search summary)**
- Decker and Yee (Int. J. Rapid Manufacturing, 2015) propose a simplified FDM benchmark artifact. I could not access its numeric results. — [Inderscience](https://www.inderscience.com/filter.php?aid=73573) **(secondhand)**
- ISO 2768 is a machining standard. A euspen 2021 paper notes that AM lacks an equivalent general-tolerance standard and proposes a benchmark artifact. — [Duco et al., euspen SIG 2021](https://orbi.umons.ac.be/bitstream/20.500.12907/2684/1/Duco2021VI_euspenSpit.pdf) **(secondhand)**
- Positional (centre-to-centre) data: a hole-plate study (25 holes, Ø5.5 mm, 20 mm pitch, CMM) reported centre-coordinate repeatability of about 6 to 7 µm (1σ) and derived X/Y scale corrections of about 1.0015 and 1.0009. I could not open the paper (HTTP 403), and the excerpt did not name the printer. — [core.ac.uk 43254592](https://core.ac.uk/download/43254592.pdf) **(secondhand, unverified)**

### Inferences
- **Dimension tolerance (wall/thickness, XY):** the error is mostly bias, not scatter. For a feature bounded by two printed perimeters, untuned output is about −0.1 to −0.13 mm on outer dimensions (and +0.1 to +0.15 mm too small on holes; see §2), with ±3σ ≈ ±0.1 mm around that bias. A symmetric ±0.15 mm band around nominal does not contain the uncompensated bias plus scatter (the bias alone uses up most of it). Recommended for the pack:
  - **Model it as bias plus band:** bias −0.10 mm (outer features), ±0.10 mm spread. Equivalently, an asymmetric tolerance of +0.05 / −0.25 mm uncompensated.
  - **If a single symmetric value is needed:** nominal **±0.2 mm**, low ±0.1 mm (calibrated printer with XY compensation, per Byczuk), high ±0.3 mm (uncalibrated or older bed-slinger; the top of the ±0.1 to ±0.3 band).
  - The current ±0.15 mm is optimistic for an uncalibrated printer but fine for a tuned Bambu or Prusa.
- **Z (height):** about +0.05 mm bias (Byczuk). Z is also quantized to the layer height, so any Z dimension not a multiple of 0.2 mm is rounded. That rounding is a geometric fact of slicing, not from the sources. Suggested Z band: ±0.1 mm nominal plus the quantization of up to half a layer (0.1 mm). High value about ±0.2 mm.
- **Position tolerance (relative position of two printed features):** the contour-shrink offset largely cancels in centre-to-centre distances, since both features shift symmetrically. Residual error is then axis scale (about 0.1 to 0.15%: Byczuk's +0.09% correction; the secondhand hole-plate figures of 0.09 to 0.15%) plus local scatter. Recommended: **±0.1 mm + 0.15% of the distance**. Low ±0.05 mm for short distances on a calibrated printer; high ±0.2 mm + 0.3% for an uncalibrated printer or features across the plate. For features ≤ 50 mm apart the current ±0.1 mm placeholder is reasonable.
- Absolute error is roughly size-independent for 3 to 36 mm features (Gebre; Byczuk 5 to 25 mm), so tolerances should be absolute mm plus a small scale term, not percentages.

### Gaps
- No peer-reviewed study found that measures **centre-to-centre hole positional error** on a current consumer printer (Prusa MK4, Bambu, Creality K1) with a CMM. The positional recommendation is inferred.
- No ISO/ASTM 52902 or NIST artifact dataset for current consumer printers (2021 to 2026) was located within the search budget.
- Only Bambu X1C has modern metrology data. Prusa MK3/MK4 appears only in hole data (§2). I found nothing on Creality or Ultimaker specifically from the last 5 years.
- I could not read the numeric per-size IT table (Gebre Table 3) from the text extraction. Only the IT9 to IT14 range is confirmed.

## 2. Hole undersize (vertical and horizontal), polygon effects, compensation

### Takeaway
Vertical holes Ø6 to 10 mm printed at 0.2 mm layers come out about **0.12 to 0.24 mm undersize on diameter**, roughly constant in mm rather than proportional. Horizontal and near-horizontal holes are similar on average but less round, and small ones are worse: a Ø2.3 mm inclined hole printed to Ø2.05 mm. Standard practice is a slicer XY hole compensation of about +0.05 to +0.1 mm per side, or drilling/reaming when the fit matters.

### Cited Findings
- Popescu et al., *Applied Sciences* 2023, 13, 41, DOI 10.3390/app13010041. Vertical through-holes Ø6/8/10 mm on a Prusa Replica with PrusaSlicer, PLA, measured with pin gauges and caliper. At **0.2 mm layer**, mean diameters were:
  - Ø10: 9.866 to 9.800 mm (−0.13 to −0.20)
  - Ø8: 7.873 to 7.778 mm (−0.13 to −0.22)
  - Ø6: 5.876 to 5.762 mm (−0.12 to −0.24)
  - At 0.32 mm layers: Ø10 down to 9.708 mm (−0.29) and Ø8 down to 7.667 mm (−0.33).
  Layer thickness was the most influential factor, followed by shell count. — [Popescu et al. 2023 (MDPI PDF)](https://mdpi-res.com/d_attachment/applsci/applsci-13-00041/article_deploy/applsci-13-00041.pdf)
- Popescu et al.: across five sites (Prusa Replica, Original Prusa i3 MK3S+ with PrusaSlicer, Creality CR10 with Cura, Ender 3 with Simplify3D, Mojo with ABS), there was "no statistically significant difference between the diameters of the holes." — [Popescu et al. 2023](https://mdpi-res.com/d_attachment/applsci/applsci-13-00041/article_deploy/applsci-13-00041.pdf)
- Popescu et al., near-horizontal holes (axes 5 to 15° from horizontal), Ø2.3 mm nominal: measured about 2.05 mm by pin gauge. A 1.883 mm pin passed through all three holes in one specimen. "The inclined holes are built undersized and enlarging them by drilling allows obtaining accurate diameters." — [Popescu et al. 2023](https://mdpi-res.com/d_attachment/applsci/applsci-13-00041/article_deploy/applsci-13-00041.pdf)
- Gebre et al. 2026 (Bambu X1C, CMM): the GBTA cylinder groups (the extraction calls them "cylinders", so they may be external bosses rather than holes) all showed negative diameter deviation. Means were **−0.134 ± 0.015 mm vertical** and **−0.108 ± 0.029 mm horizontal**, with cylindricity of −0.075 and −0.052 mm. The deviation was "approximately constant in magnitude across nominal sizes." Horizontal cylinders had a wider range because of the staircase effect. — [Gebre et al. 2026](https://iris.unitn.it/retrieve/aaecc8a0-0420-472b-9a40-4d43d7df5e0b/Material%20Design%20%20%20Processing%20Communications%20-%202026%20-%20Gebre%20-%20Influence%20of%20Geometry%20and%20Size%20on%20Precision%20and%20Accuracy%20in.pdf)
- Knoop and Schoeppner, SFF 2017, on an *industrial* Stratasys machine (0.1778 mm layers, T12 nozzle), CMM-scanned Ø3 to 80 mm: internal diameters up to 18 mm were undersized for all specimens. The undersize was directional, larger in the filament-deposition direction. Shrink factors improved larger diameters. Industrial printer, so indicative only. — [Knoop & Schoeppner 2017](https://utw10945.utweb.utexas.edu/sites/default/files/2017/Manuscripts/GeometricalAccuracyofHolesandCylindersManufa.pdf)
- Hernandez et al. (cited by Popescu): the smaller the hole, the larger the mean dimensional deviation. — [Popescu et al. 2023, lit. review](https://mdpi-res.com/d_attachment/applsci/applsci-13-00041/article_deploy/applsci-13-00041.pdf)
- A PLA study on Ø6.35 mm FFF holes reports undersizing of more than 1 mm. This is far outside the other data and may reflect poor settings. — [scientific.net SSP 391](https://www.scientific.net/SSP.391.29.pdf) **(secondhand: search snippet only)**
- Hubs design guide: vertical holes print undersized. Print them undersized and drill to final size when accuracy is critical. No numeric offset is given. — [Hubs FDM design guide](https://www.hubs.com/knowledge-base/how-design-parts-fdm-3d-printing/)
- OrcaSlicer offers "X-Y hole compensation" (positive values enlarge holes) and "X-Y contour compensation", tuned via its tolerance calibration. — [OrcaSlicer wiki: precision](https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_precision)
- OrcaSlicer "Convert holes to polyholes" makes holes polygons with fewer sides so each segment "prints more reliably". The edge count is about 2 × diameter (mm) for a 0.4 mm nozzle, with a minimum of 3 and a default cap of 50, and an optional per-layer twist. Only convex holes with more than 8 points are converted. — [OrcaSlicer wiki: precision](https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_precision)

### Inferences
- **As-made vertical hole model:** Ø_printed = Ø_nominal − 0.15 mm (nominal). Low (best case or calibrated) −0.05 mm; high −0.30 mm (0.3 mm layers, older printers). Apply as an absolute offset, not a percentage: over Ø6 to 10 mm the undersize is flat. In % terms that is about 1.5% at Ø10 and 2.5% at Ø6, rising steeply for Ø < 3 mm.
- **As-made horizontal hole model:** similar mean (−0.1 to −0.25 mm) but with roundness error from the staircase effect and sag at the crown. For Ø < 3 mm, expect −0.25 mm or worse (Popescu's Ø2.3 → 2.05). The top of a horizontal hole is the drooping region, so the vertical diameter tends to be smaller than the horizontal one. That direction is inferred from mechanism; I found no paper that separates it numerically.
- **Polygon/tessellation effect (geometry, not from sources):** if a hole is exported as an inscribed n-gon, the effective diameter for a pin is the inscribed-circle diameter D·cos(π/n). A 32-gon loses 0.48% (0.05 mm on Ø10). The tool should export holes with fine tessellation, or model the polygon explicitly (polyholes) so the loss is accounted for.
- **Compensation practice:** apply about +0.05 to +0.1 mm per side of hole XY compensation in the slicer, or design holes +0.15 to +0.2 mm oversize on diameter. Drill or ream for fits tighter than about ±0.1 mm. Byczuk's +0.05 to +0.064 mm per side for outer contours is consistent with this.

### Gaps
- No modern-consumer-printer dataset separates horizontal-hole vertical vs. horizontal diameters (sag at the crown).
- Gebre's "cylinders" may be bosses; their sign suggests contour shrink, but I could not confirm whether holes were measured separately.
- No source quantified the polyhole improvement numerically.

## 3. Elephant's foot magnitude and slicer compensation defaults

### Takeaway
Slicers treat elephant's foot as about **0.1 to 0.2 mm per side** of first-layer flare at 0.4 mm nozzle. PrusaSlicer's official profiles enable compensation, and Prusa recommends about 0.2 mm. I found no peer-reviewed measurement of the flare magnitude.

### Cited Findings
- Prusa: "Values around 0.2 mm usually work well for the default 0.4 mm nozzle." "Official Prusa profiles have this setting turned on by default." It shrinks the first layer, and since PrusaSlicer 2.2 it avoids over-shrinking thin lines. — [Prusa Knowledge Base: Elephant foot compensation](https://help.prusa3d.com/article/elephant-foot-compensation_114487)
- A Prusa KB reader comment (not the article): with a 0.4 mm nozzle you shouldn't need more than about half the first-layer extrusion width. Lowering the nozzle temperature 5 to 10 °C can help more. — [Prusa KB comments](https://help.prusa3d.com/article/elephant-foot-compensation_114487) **(user comment)**
- OrcaSlicer applies the compensation at full strength on the first layer and tapers it linearly over a set number of layers. It is skipped with a raft. Causes listed are the weight of material above, thermal expansion, high bed temperature, and bed-levelling error. The wiki page does not state the default value. — [OrcaSlicer wiki: precision](https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_precision)
- Cura's equivalent is "Initial Layer Horizontal Expansion", entered as a negative value (e.g. −0.1 mm). — [3dnatives](https://www.3dnatives.com/en/how-to-avoid-the-elephant-foot-effect-in-fdm-3d-printing-2607234/amp/) **(secondhand)**
- Hubs: put a 45° chamfer or radius on edges touching the build plate to hide elephant's foot. No magnitude is given. — [Hubs FDM design guide](https://www.hubs.com/knowledge-base/how-design-parts-fdm-3d-printing/)
- Gebre et al. saw localized positive deviations at lower measurement heights, "suggesting localized expansion associated with build plate adhesion effects." — [Gebre et al. 2026](https://iris.unitn.it/retrieve/aaecc8a0-0420-472b-9a40-4d43d7df5e0b/Material%20Design%20%20%20Processing%20Communications%20-%202026%20-%20Gebre%20-%20Influence%20of%20Geometry%20and%20Size%20on%20Precision%20and%20Accuracy%20in.pdf)

### Inferences
- **As-made model:** first-layer outward flare of **+0.15 mm per side nominal** (range +0.05 to +0.3), decaying over the first 1 to 3 layers (0.2 to 0.6 mm of height). With slicer compensation enabled (Prusa default), predict about 0 ± 0.1 mm. Holes touching the bed shrink correspondingly at the bottom.
- A rule-pack check: chamfer bed-contact edges by ≥ 0.3 to 0.5 mm, or flag mating faces on the first layer.

### Gaps
- No peer-reviewed measurement of elephant's foot magnitude on consumer printers was found.
- The default values in OrcaSlicer/Bambu Studio and Cura (Cura's default is believed to be 0) were not confirmed from primary profiles.

## 4. Extrusion width conventions

### Takeaway
PrusaSlicer's auto width is **1.125 × nozzle** (0.45 mm at 0.4 mm). Bambu and Orca use about **0.42 mm (105%)** as the global default, and Orca recommends 105 to 120% for outer walls. Cura's line width defaults to the nozzle size (0.4 mm), though I did not verify that against a primary source. Wider-than-nozzle lines are squished beyond the orifice to improve bonding and strength. Bridges are the exception, at about 100%.

### Cited Findings
- PrusaSlicer: entering 0 for extrusion width derives it from the nozzle diameter as 1.125 × nozzle. Prusa's general guidance is about 110% of nozzle, and forum guidance puts the upper limit around 120%. — [Prusa KB: Creating profiles for different nozzles](https://help.prusa3d.com/article/creating-profiles-for-different-nozzles_127540) **(confirmed via search summary; direct fetch of the Prusa extrusion-width article 404'd)**
- OrcaSlicer wiki: start at 100% of nozzle. Outer wall 105 to 120%, inner wall typically ≥ 120%, top surface 100 to 105%, sparse infill about 115%, internal solid about 110%, bridges about 100%. Wider lines improve "layer bonding and print strength". Above 150% risks over-extrusion. With Arachne the widths are references, not fixed values. — [OrcaSlicer wiki: line width](https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_line_width.html)
- Bambu Lab's global default line width is 0.42 mm for a 0.4 mm nozzle. Sources conflict on the outer wall (0.42 vs 0.40 mm). — [Bambu forum: Default line width of 0.42](https://forum.bambulab.com/t/default-line-width-of-0-42/20400) **(secondhand/forum)**
- The same Bambu forum thread notes Cura uses 0.4 mm (= nozzle). — [Bambu forum](https://forum.bambulab.com/t/default-line-width-of-0-42/20400) **(secondhand)**

### Inferences
- Pack entry: extrusion width **nominal 1.125 × nozzle** (0.45 mm), keyed to the slicer. Low 1.0 × (Cura, 0.40 mm); high 1.2 × (0.48 mm). Bambu/Orca is 1.05 × (0.42 mm). The rule pack should take width from the slicer profile, because minimum-wall and thin-wall rules depend on it (2 perimeters = 0.84 to 0.90 mm).
- Byczuk's 0.8 mm walls came out 0.75 to 0.78 mm on Bambu. A wall designed as an exact multiple of the nominal width still prints about 0.03 mm thin.

### Gaps
- Cura's default (line width = machine nozzle size) was not confirmed from Ultimaker's documentation (support page did not render).
- Prusa's rationale for the exact 1.125 factor was not found in a primary source.

## 5. Unsupported overhang limit and bridging

### Takeaway
45° from vertical is the universal design-guide default. Peer-reviewed work (Jiang et al. 2018) shows the printable threshold moves substantially with fan speed, print speed and temperature. With good part cooling, consumer printers commonly print 50 to 60° acceptably, but I found no modern numeric study. For bridges, Hubs says some sag is always present beyond about 5 mm. Hobby guides cite about 20 mm as clean on a tuned printer. I found no peer-reviewed PLA bridge-length limit.

### Cited Findings
- Hubs: "an overhang can usually be printed up to 45° without compromising quality". At 45° each layer is 50% supported by the layer below. Test images go to 70° in 5° steps. — [Hubs FDM design guide](https://www.hubs.com/knowledge-base/how-design-parts-fdm-3d-printing/)
- Hubs: bridge sag and support marks are "to some extent always present unless the bridge is less than 5mm." — [Hubs FDM design guide](https://www.hubs.com/knowledge-base/how-design-parts-fdm-3d-printing/)
- Jiang, Stringer, Xu, Zhong, "Investigation of printable threshold overhang angle in extrusion-based additive manufacturing for reducing support waste", *Int. J. Computer Integrated Manufacturing* 31(10):961–969, 2018, DOI 10.1080/0951192X.2018.1466398. They tested 20/30/40/50° overhangs and found "the printable threshold overhang angle varies substantially" with fan speed, print speed and print temperature. A follow-up (Jiang, Xu, Stringer) varied extrusion temperature from 175 to 220 °C. — [Auckland ResearchSpace](https://researchspace.auckland.ac.nz/handle/2292/44788) **(abstract only; numeric thresholds not accessed)**
- Pricci, *Polymers* 2025, 17(21):2858, DOI 10.3390/polym17212858. This used a pellet extruder with a 1.2 mm nozzle (not representative of 0.4 mm filament). A fixed 20 mm bridge sagged 1.93 to 5.69 mm depending on temperature, speed and fan, and the fan reduced sag. No maximum span is stated. — [PMC12608786](https://pmc.ncbi.nlm.nih.gov/articles/PMC12608786)
- Vendor guide: a well-tuned printer gives about 20 mm with no visible sag, 20 to 50 mm with slight sag, 50 to 80 mm with visible sag, and >80 mm is unreliable. — [QIDI bridging guide](https://qidi3d.com/blogs/news/3d-printing-bridging-techniques-guide) **(secondhand, unvalidated vendor blog)**
- A 2026 *Additive Manufacturing Letters* paper reports wave-inspired toolpaths printing support-free horizontal (90°) overhangs in PLA on an open-frame printer. Manufacturability there is governed by toolpath, not the angle threshold. — [3Dnatives coverage](https://www.3dnatives.com/en/support-free-3d-printing-research-15062026/) **(press coverage)**

### Inferences
- **Overhang limit:** nominal **45°** (keep). Low 40° for conservative or cosmetic surfaces and poorly cooled printers. High 60° for modern high-cooling printers (Bambu, MK4) on non-cosmetic faces. The high value is inferred from Hubs' test range and Jiang's settings dependence, not measured.
- **Horizontal holes without support:** the region of a horizontal hole steeper than 45° from vertical is the top cap. Its chord is about 0.71 × D, so a Ø10 hole bridges about 7 mm, between Hubs' 5 mm "no sag" and the ~20 mm "clean" figure (geometric inference). Recommended: **Ø10 nominal** for acceptable function with some crown sag (about 0.1 to 0.3 mm, consistent with horizontal-hole undersize). Low Ø6 mm (about 4 mm bridge, within Hubs' 5 mm) for cosmetic or precise holes. High about Ø20 mm (about 14 mm bridge) on well-cooled printers. Above that, use a teardrop or diamond profile, or support. Teardrop practice comes from common practice; I did not cite a source for it.
- **Maximum bridge length:** nominal 10 mm, low 5 mm (Hubs), high 20 to 30 mm (secondhand vendor guidance).

### Gaps
- I found no peer-reviewed measurement of maximum PLA bridge length or sag vs. span with a 0.4 mm filament printer. The "2026 PLA beam study" (spans 60 to 140 mm) was seen only via secondary summary.
- The numeric thresholds in Jiang et al. 2018 were not accessible.
- VDI 3405-3 and ISO/ASTM 52910 were not consulted (paywalled), so I have no standards-body value for overhang or bridging.

## 6. Recommended nominal + low/high per pack entry

### Takeaway
Summary table synthesized from §§1–5. "Low" is the tighter or better-case value and "high" the looser or worse-case value.

| Pack entry | Current | Nominal | Low (tuned) | High (untuned/worse) | Main basis |
|---|---|---|---|---|---|
| Position tolerance (centre-to-centre) | ±0.1 mm | ±0.1 mm + 0.15% of distance | ±0.05 mm | ±0.2 mm + 0.3% | Byczuk scale corr. +0.09%; secondhand 0.09 to 0.15%; inference |
| Dimension tolerance (XY wall/size) | ±0.15 mm | bias −0.10, ±0.10 (or symmetric ±0.2) | ±0.1 (compensated) | ±0.3 | Byczuk −0.12 ± 0.035; Gebre IT9 to 14; ±0.1 to 0.3 band |
| Z dimension | — | +0.05 bias, ±0.1 + layer quantization | ±0.05 | ±0.2 | Byczuk +0.05; Gebre Z worst axis |
| Extrusion width | 1.125 × nozzle | 1.125 × (PrusaSlicer) | 1.0 × (Cura) | 1.2 × | Prusa KB; Orca wiki; Bambu 1.05 × |
| Overhang limit | 45° | 45° | 40° | 60° | Hubs; Jiang 2018 (settings-dependent) |
| Horizontal hole, no support | Ø10 | Ø10 | Ø6 | Ø20 | Hubs 5 mm bridge; chord geometry; vendor 20 mm |
| Vertical hole undersize (on Ø) | — | −0.15 mm | −0.05 mm | −0.30 mm | Popescu (Prusa, 0.2 mm), Gebre −0.13 |
| Horizontal hole undersize (on Ø) | — | −0.15 mm (Ø ≥ 5) / −0.25 (Ø < 3) | −0.1 | −0.4 | Gebre −0.11; Popescu Ø2.3 → 2.05 (pin 1.88) |
| Elephant's foot (per side, layer 1) | — | +0.15 mm uncompensated; 0 with comp. | +0.05 | +0.3 | Prusa KB 0.2 mm comp. default |
| Thin wall (2 perimeters) | — | −0.03 mm vs. design | −0.02 | −0.05 | Byczuk 0.8 → 0.75 to 0.78 |

### Inferences
- All values assume PLA, 0.4 mm nozzle, 0.2 mm layers, and a recent printer at default profile settings. They are "assumed, unreviewed" defaults in the sense of the project's assumption mechanism, and per-printer calibration (Byczuk) can cut XY error by an order of magnitude.

### Gaps
- Material other than PLA (PETG, ABS) shrinks more. I did not cover it.
- No cross-printer modern study (Prusa MK4 vs. Bambu vs. Creality K1) with common metrology was found.

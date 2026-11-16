# Mechanical strength of FDM-printed PLA, PETG and ABS (for a printed shelf-bracket load check)

Scope: printed (not moulded) strength values with scatter and test conditions; the across-layer ratio; flexural vs. tensile for a bending check; creep / sustained-load derating. Current pack placeholders: in-layer tensile PLA 50 (40–60), PETG 45 (38–52), ABS 35 (30–40) MPa; across/in ratio 0.5 (0.4–0.6); bending check with safety factor 2.

Research date 2026-11-16. Some planned primary sources (Chacón 2017, Rodríguez-Panes 2018 full tables, Kiendl & Gao 2020 numbers, Popescu 2018, PETG papers by Hsueh / Szykiedans, Ultimaker / BASF Forward AM / eSun sheets) could not be read in full: MDPI returned 403, others were paywalled or not reached. They are listed under Gaps rather than cited from memory.

## Q1. Printed tensile strength in-layer vs. across layers (peer-reviewed)

### Takeaway
Printed in-layer (flat, raster along load) tensile strength for PLA is about 50–56 MPa in recent studies. Upright (across-layer) specimens lose about a third: one controlled PLA study measured 55.5 to 35.5 MPa, a ratio of 0.64. The classic Ahn et al. (2002) ABS work shows that raster direction alone can swing printed ABS from 10% to 73% of moulded strength.

### Cited Findings
- **Eryildiz (2021), "Effect of Build Orientation on Mechanical Behaviour and Build Time of FDM 3D-Printed PLA Parts", *European Mechanical Science*, DOI 10.26701/ems.881254.** Conditions: commercial 1.75 mm PLA, 0.4 mm nozzle, 0.2 mm layers, 0.8 mm walls, **30 % infill**, 60 mm/s, ASTM D638 Type IV, 1 mm/min. Tensile strength: flat 0° = **55.49 MPa**, flat 45° = 53.47, flat 90° = 51.77, **upright = 35.52 MPa**, i.e. 36 % lower than flat. Upright specimens failed by interlayer fracture. Table 2 gives means only, no SD. — [Eryildiz PDF](https://dergipark.org.tr/en/download/article-file/1580962)
- **Ahn, Montero, Odell, Roundy & Wright (2002), "Anisotropic material properties of fused deposition modeling ABS", *Rapid Prototyping Journal* 8(4):248–257, DOI 10.1108/13552540210441166.** Stratasys FDM machine with ABS P400. Injection-moulded ABS P400 made from chopped filament failed at **26 MPa**. The FDM specimens failed at **10 % to 73 %** of that, depending on raster (axial 0°, transverse 90°, crisscross, ±45°) and air gap. With a –0.003 in (negative) air gap, the axial and crisscross cases reached **65–72 %** of moulded strength. Compressive strength was 80–90 % of moulded. The paper notes that typical bulk ABS tensile strength is 32–45 MPa (citing ASM 1988), so ABS P400 was a weak grade. It also gives design rules, for example "build so that tensile loads are carried axially along the fibres" and "consider the effect of build orientation". — [Ahn et al. PDF (Univ. of Utah mirror)](https://iss.mech.utah.edu/wp-content/uploads/sites/103/2012/10/Ahn-Anisotropic_material-2002.pdf); [DOI](https://www.doi.org/10.1108/13552540210441166)
- **Rodríguez-Panes, Claver & Camacho (2018), *Materials* 11(8):1333, DOI 10.3390/ma11081333.** Compares PLA and ABS over layer height, infill density and layer orientation (yield stress, tensile strength, strain at break, modulus). Qualitative conclusions: PLA is stiffer and stronger than ABS; ABS results show less variability; infill % is the most influential parameter, more so in PLA; the bond between layers in PLA "turns out to be extremely strong". Numeric tables were not retrieved (403). — [PMC6119930](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6119930/)
- **Chacón et al. (2017), "Additive manufacturing of PLA structures using fused deposition modelling", *Materials & Design* 124:143–157 (DOI 10.1016/j.matdes.2017.03.065).** Tensile and 3-point bending tests over build orientation, layer thickness and feed rate. **For upright specimens, strength rose with thicker layers and fell with higher feed rate.** For flat and on-edge specimens these effects were small, except at very low layer thickness. On-edge gave the best mechanical performance. Numeric values were not retrieved; the findings come from secondary summaries. — [summary via SciELO/typeset listings](https://typeset.io/papers/additive-manufacturing-of-pla-structures-using-fused-2di2prhe0s)
- **Kiendl & Gao (2020), *Composites Part B* 180.** Standard layups alternating at 90° give **nearly isotropic in-plane stiffness and strength** but strongly anisotropic toughness, switching between brittle and ductile behaviour with load direction. Numbers were not retrieved. — [NTNU Open record](https://ntnuopen.ntnu.no/ntnu-xmlui/handle/11250/2628204)
- A review notes that Z-direction strength can be "sometimes an order of magnitude" lower than along-thread strength. It also argues that bending tests suit interlayer strength better than tensile tests. — [PMC6414919](https://pmc.ncbi.nlm.nih.gov/articles/PMC6414919)
- **PETG.** Studies in *Polymers* 15:3029 (2023) compare flat vs. on-edge PETG over several specimen geometries. ASTM D3039 bars gave 18–21 % higher tensile strength than ISO 527 dog-bones, so specimen geometry alone shifts the result. PETG studies disagree on which in-plane raster angle is strongest. — [PMC10385694](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10385694/)

### Inferences
- In-layer printed PLA of about 50–56 MPa is consistent across studies, even at 30 % infill when the walls carry the gauge section. Upright PLA is about 35 MPa.
- Ahn's ABS P400 numbers (~17–19 MPa in-layer) come from a 2002 industrial machine and a low-strength grade. They should not set the absolute ABS value, but they are the best evidence that raster direction matters as much as build direction.

### Gaps
- No study read in full reported SDs for upright PLA, PETG or ABS under hobby-printer conditions. Chacón 2017 and Rodríguez-Panes 2018 tables, Popescu et al. 2018 (review), Hsueh et al. and Szykiedans et al. (PETG) were not reached.

## Q2. Datasheet values (orientation, standard, conditions)

### Takeaway
Manufacturer sheets give printed PLA at about 50–52 MPa, PETG at 47–51 MPa and ABS at about 33 MPa in-layer (ISO 527). Their "vertical" columns are inconsistent: Prusa's "vertical xz" is an on-edge print, not an across-layer one.

### Cited Findings
- **Prusament PLA TDS v1.1 (27-07-2022).**
  - Test conditions: Original Prusa i3 MK3; PrusaSlicer 1.40 "0.20 mm FAST" (0.20 mm layers); 2 perimeters; 0 top/bottom solid layers; 100 % rectilinear infill; 200 mm/s; 215 °C nozzle; 60 °C bed.
  - Tensile yield strength (ISO 527-1): **horizontal 51 ± 3 MPa**, **vertical xz 59 ± 2 MPa**.
  - Flexural strength (ISO 178): **horizontal 83 ± 6 MPa**, vertical xz 99 ± 1 MPa. Modulus 2.3 / 2.4 GPa.
  - Filament tensile yield 57 ± 1 MPa (ISO 527).
  - **"Interlayer adhesion" 17 ± 3 MPa** (in-house Prusa Polymers method).
  - HDT 55 °C (both 0.45 and 1.80 MPa).
  - The sheet warns that values are "significantly dependent on print settings".
  - The older v1.0 sheet (2018) also had a "Vertical Z-axis" column, but its text layer is font-encoded and could not be decoded reliably.
  - Sources: [Prusament PLA TDS v1.1 (MatterHackers mirror)](https://www.matterhackers.com/r/xFvGl8); [v1.0, Prusa CDN](https://cdn.shopify.com/s/files/1/1745/6181/files/PRUSA_PLA_TechSheet_ENG.pdf)
- **Prusament PETG TDS v1.1 (16-02-2022).**
  - Test conditions: same printer and profile as the PLA sheet; 250 °C nozzle, 80 °C bed, 100 % infill, 2 perimeters.
  - Tensile yield strength (ISO 527-1): **horizontal 47 ± 2 MPa**, vertical xz 50 ± 1 MPa.
  - Flexural strength (ISO 178): **horizontal 66 ± 2 MPa**, vertical xz 70 ± 1 MPa.
  - Filament yield 46 ± 1 MPa.
  - **Interlayer adhesion 18 ± 4 MPa** (in-house).
  - HDT 68 °C.
  - Source: [Prusament PETG TDS v1.1 (mirror)](https://www.3dprintergear.com.au/assets/files/technical-data-sheet%20(1).pdf)
- **Polymaker PolyLite PLA TDS V5.3/V5.4.** Tensile (ISO 527 / GB/T 1040): **X-Y 52.3 ± 0.3 MPa, Z 40.5 ± 0.5 MPa**, giving Z/XY = 0.77. These values come from search snippets and the Polymaker wiki; the PDF download was blocked. — [Polymaker wiki PolyLite PLA](https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/pla/polylite-tm-pla); [TDS V5.3](https://polymaker.com/wp-content/uploads/lana-downloads/PolyLite_PLA_TDS_V5.3.pdf)
- **Polymaker PolyLite PETG TDS V5.4.** Tensile **X-Y about 50.8 MPa, Z about 42.8 MPa** (Z/XY ≈ 0.84). Bending strength X-Y 69.6 ± 0.8 MPa (ISO 178). Elongation at break X-Y 8.4 % vs. Z 3.3 %. **Conflict:** the older V5.2 sheet lists X-Y 31.9 ± 1.1 MPa and Z 13.4 ± 2.0 MPa (Z/XY ≈ 0.42), with bending 53.7 MPa. The cause (formulation change or test method change) is not explained. Values are from search snippets. — [TDS V5.4](https://polymaker.com/wp-content/uploads/lana-downloads/PolyLite_PETG_TDS_EN_V5.4.pdf); [TDS V5.2](https://cdn.shopify.com/s/files/1/0789/2979/files/PolyLite_PETG_TDS_V5.2.pdf); [wiki](https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/petg-pet/polylite-tm-petg)
- **Polymaker PolyLite ABS TDS V5.6 (2025-12-30), read directly.**
  - Tensile strength (ISO 527): **X-Y 33.4 MPa** (the ± value is garbled in the PDF text) and **Z 29.7 ± 0.3 MPa**, so Z/XY ≈ 0.89.
  - Bending strength X-Y **56.2 ± 0.3 MPa**; no Z value.
  - Specimen conditions: 260 °C nozzle, 90 °C bed, 100 % infill, 2 shells, 3 top/bottom layers, **cooling fan OFF**.
  - Older V5.1 sheet: bending strength 72.8 MPa (conflicting).
  - Sources: [Polymaker PolyLite ABS TDS V5.6](https://polymaker.com/wp-content/uploads/lana-downloads/TDS_Polymaker_PolyLite-ABS_V5.6_2025-12-30_EN.pdf); [V5.5](https://polymaker.com/wp-content/uploads/lana-downloads/PolyLite-ABS_TDS_EN_V5.5.pdf)
- **Polymaker PolyLite PLA Pro V5.6 (2026-01-05).** Snippet shows about X-Y 49.8 ± 0.4 and Z 36.5 ± 0.6 MPa (Z/XY ≈ 0.73), but the label alignment in the text extract is uncertain. — [TDS PLA Pro V5.6](https://polymaker.com/wp-content/uploads/TDS_Polymaker_PolyLite-PLA-Pro_V5.6_2026-01-05_EN.pdf)

### Inferences
- **Do not read Prusa's "vertical xz" as across-layer.** It is the on-edge orientation, and it is stronger than flat. Prusa's across-layer figure is the separate "interlayer adhesion" row: PLA 17/51 ≈ **0.33** and PETG 18/47 ≈ **0.38**. That method is in-house and its specimen geometry is not stated.
- Polymaker's Z values (ratio 0.73–0.89) are far more optimistic than Prusa's interlayer adhesion (0.33–0.38) or Eryildiz (0.64). The difference probably comes from specimen design and from settings such as fan off and 100 % infill (an inference; Polymaker does not describe its Z specimens).
- Datasheet scatter (± 0.3 to ± 3 MPa) reflects one lab and one printer. Between-printer and between-settings scatter is much larger: compare the PETG V5.2 and V5.4 sheets.

### Gaps
- Ultimaker, BASF Forward AM and eSun sheets were not retrieved. The Prusa PLA/PETG v1.0 Z-axis column could not be decoded. The Polymaker PLA and PETG PDFs returned 146-byte stubs (blocked), so those values rest on snippets and wiki copies.

## Q3. Across-layer / in-layer ratio: range and drivers

### Takeaway
Reported ratios span about **0.3 to 0.9**: Prusa interlayer adhesion about 0.33–0.38, Eryildiz PLA 0.64, Polymaker 0.73–0.89, and Polymaker PETG V5.2 0.42. The main drivers are interface temperature history (nozzle temperature, part-cooling fan, layer time) and layer height. A single 0.5 (0.4–0.6) band is too narrow.

### Cited Findings
- Eryildiz PLA: upright/flat-0° = 35.52/55.49 = **0.64** (0.2 mm layers, 30 % infill). — [Eryildiz](https://dergipark.org.tr/en/download/article-file/1580962)
- Prusament interlayer adhesion: PLA 17 ± 3 vs. horizontal 51 ± 3 MPa, and PETG 18 ± 4 vs. 47 ± 2 MPa. — [PLA TDS](https://www.matterhackers.com/r/xFvGl8); [PETG TDS](https://www.3dprintergear.com.au/assets/files/technical-data-sheet%20(1).pdf)
- Polymaker Z/XY ratios: PLA 40.5/52.3, PETG 42.8/50.8 (V5.4) or 13.4/31.9 (V5.2), ABS 29.7/33.4 (fan off). — sources as in Q2.
- **Drivers.** Several studies agree:
  - Nozzle temperature is the most influential factor for interlayer bond strength. — [Thermal-history prediction of interlayer bond strength](https://www.researchgate.net/publication/366868722_Thermal_history_based_prediction_of_interlayer_bond_strength_in_parts_manufactured_by_material_extrusion_additive_manufacturing)
  - Layer height is also key: larger layers reduce bonding area and transverse strength. — [NSF PAR](https://par.nsf.gov/servlets/purl/10181525); [Hardware factors study](https://www.researchgate.net/publication/333034313_Hardware_Factors_Influencing_Interlayer_Bonding_Strength_of_Parts_Obtained_by_Fused_Filament_Fabrication)
  - Part cooling lowers bond strength. — [same Hardware factors study](https://www.researchgate.net/publication/333034313_Hardware_Factors_Influencing_Interlayer_Bonding_Strength_of_Parts_Obtained_by_Fused_Filament_Fabrication); [Nonisothermal welding in FFF](https://www.sciencedirect.com/science/article/abs/pii/S2214860419316550)
- Chacón 2017 (PLA): the properties of upright specimens rose with thicker layers and fell with higher feed rate. This partly contradicts the "thinner is better" result above, so the layer-height effect is not monotonic across studies. — [summary](https://typeset.io/papers/additive-manufacturing-of-pla-structures-using-fused-2di2prhe0s)
- Interlayer adhesion depends mainly on layer thickness in the build direction, while intralayer properties depend on transverse dimensions and thermal gradients. — [Springer 2025, s00170-025-15502-1](https://link.springer.com/article/10.1007/s00170-025-15502-1)

### Inferences
- Suggested pack entry: **across/in ratio nominal 0.5, range 0.3–0.8.** For a no-false-PASS check, use the low end (0.3) whenever the bending tension face lies across layers. PLA printed with a full part-cooling fan (the default) sits toward the low end; ABS with the fan off and an enclosure sits toward the high end.
- Better still, orient the bracket arm so its bending stress runs along layers (print the bracket lying on its side), so the across-layer ratio does not govern. That is a rule-pack orientation recommendation, not a material value.

### Gaps
- No paired dataset found that sweeps fan % and nozzle temperature for PLA/PETG/ABS on the same printer and reports the Z/XY ratio with SD.

## Q4. Flexural vs. tensile strength for a bending check

### Takeaway
Printed flexural strength is about 1.4–1.7× printed tensile strength (Prusa PLA 83 vs. 51; PETG 66 vs. 47; Polymaker ABS 56 vs. 33 MPa). For a first-order check with σ = M·c/I, the tensile value is the conservative choice, especially when the tension face is across layers.

### Cited Findings
- Prusament PLA: flexural (ISO 178) horizontal 83 ± 6 MPa vs. tensile 51 ± 3 MPa, a ratio of **1.63**. — [PLA TDS](https://www.matterhackers.com/r/xFvGl8)
- Prusament PETG: flexural 66 ± 2 vs. tensile 47 ± 2 MPa, a ratio of **1.40**. — [PETG TDS](https://www.3dprintergear.com.au/assets/files/technical-data-sheet%20(1).pdf)
- Polymaker ABS: bending 56.2 ± 0.3 vs. tensile 33.4 MPa, a ratio of **1.68**. — [ABS TDS V5.6](https://polymaker.com/wp-content/uploads/lana-downloads/TDS_Polymaker_PolyLite-ABS_V5.6_2025-12-30_EN.pdf)
- Tensile test results on printed specimens do not translate well to flexural properties, and printed tensile properties were 30–53 % below bulk in cited work. — [search summary of PMC6414919 / related review](https://pmc.ncbi.nlm.nih.gov/articles/PMC6414919)
- Bending (3-point) is argued to be the more appropriate test for interlayer strength, because the layer interface limits strength. — [PMC6414919](https://pmc.ncbi.nlm.nih.gov/articles/PMC6414919)

### Inferences
- Flexural strength is higher than tensile strength partly because of the non-linear stress distribution beyond yield and because dense perimeters sit at the outer fibres. ISO 178 also reports the stress at maximum load using the elastic formula. These effects depend on the geometry of the test specimen and may not carry over to a bracket arm with sparse infill. Recommendation: **check bending stress against the tensile (in-layer or across-layer) strength.** Record the flexural value in the pack as an upper reference (a "headroom" note), not as the allowable.
- Sparse infill: Rodríguez-Panes found infill % to be the dominant parameter. If the arm is printed below 100 % infill, σ should be computed on the solid perimeter shell section, or the strength should be reduced. This needs a separate rule.

### Gaps
- No printed flexural data across layers (upright 3-point bending) with numbers for PLA/PETG/ABS was retrieved. Polymaker lists bending Z as "N/A".

## Q5. Creep and sustained-load derating

### Takeaway
No multi-year creep-rupture data for printed PLA or PETG was found. The published FDM creep tests run for hours. General thermoplastic design guidance puts long-term working stress at **20–40 % of short-term strength**, falling to 3–5 % near the heat-deflection temperature. PLA's HDT is only about 55 °C, so a sustained-load derating of about 0.3 (0.2–0.4) is a defensible, clearly provisional pack value for PLA, and about 0.4 for PETG/ABS.

### Cited Findings
- Protolabs (injection-moulding material guide): long-term working stress "will typically be between 20–40 % of the short-term strength". When the service temperature "approaches the DTUL values it is possible for the sustainable working stress to be only 3–5 %". This is vendor guidance for moulded thermoplastics, not printed parts. — [Protolabs guide](https://www.protolabs.com/resources/guides-and-trend-reports/thermoplastic-material-selection-for-injection-molding/)
- Waseem et al. (2020), *Polymers* 12:2962. Tensile creep of FDM PLA per ASTM D2990, response-surface model. **Rupture times were only about 2.1–2.2 h** at the (high) test stress. Infill pattern was significant for rupture time, and the optimum was 0.1 mm layers, 100 % infill, hexagonal pattern. — [PMC7764475](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7764475/)
- Dogan (2022), *Strojniški vestnik*: printed PLA and other polymers tested at 25/40/60 °C and 10/20 MPa. Material, temperature and stress level all significantly affect creep. Tests were short-duration. — [SV-JME](https://ojs30.sv-jme.eu/index.php/sv-jme/article/view/191)
- PLA FDM creep varies with building direction and raster orientation, and creep publications on FDM PLA are "very limited". — [J. Mech. Behav. Biomed. Mater. 2023 (S1751616123003788)](https://www.sciencedirect.com/science/article/abs/pii/S1751616123003788)
- Flexural creep of printed thermoplastics is affected by physical aging. — [arXiv 2302.11240](https://arxiv.org/pdf/2302.11240)
- An accelerated-ageing study found tensile strength fell 36 % for PETG but only 5.3 % for PLA after UV-B exposure. This matters only if the bracket gets sunlight. — [PMC8659210](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8659210/)
- Prusament HDT: PLA 55 °C, PETG 68 °C. Polymaker ABS HDT is 98 °C at 1.8 MPa. — Prusa and Polymaker TDS as above.

### Inferences
- PLA at 25–30 °C runs at roughly 25–30 °C below its HDT. That is closer to the "near DTUL" regime than PETG (about 40 °C margin) or ABS (about 70 °C margin). Suggested derating factors: **PLA 0.3 (0.2–0.4); PETG 0.4 (0.3–0.5); ABS 0.4 (0.3–0.5)**. A warm wall or sunlit window should push PLA to the low end or below. Keep these marked *provisional / unreviewed* until printed creep-rupture data exists.
- How derating interacts with SF 2: in this framing, derating × strength gives the long-term strength and SF 2 then covers load and geometry uncertainty. Example for PLA across layers: 50 × 0.3 (ratio) × 0.3 (creep) / 2 ≈ 2.3 MPa allowable. That is very conservative. The pack should state clearly whether SF 2 already includes creep, so the designer is not double-penalised or under-protected.
- Creep deflection (sag) may govern before rupture does for a shelf. A stiffness/creep-strain check (e.g. ≤ 1 % long-term strain at a creep modulus) is worth a later rule.

### Gaps
- No creep-rupture curve (stress fraction vs. time to 1–10 years) for printed PLA, PETG or ABS was found. No Plastics Design Library or Campus creep data for PLA/PETG was retrieved. No printed-part derating factor from a standard or handbook was found; 20–40 % is a vendor rule of thumb for moulded parts.

## Summary of recommended pack entries (inference, built on the findings above)

| Entry | Current | Recommended nominal (low–high) | Basis |
|---|---|---|---|
| PLA in-layer tensile | 50 (40–60) | **50 (40–58)** | Prusa 51 ± 3; Polymaker 52.3; Eryildiz 55.5 (30 % infill); PLA Pro ~49.8 |
| PETG in-layer tensile | 45 (38–52) | **45 (32–52)** | Prusa 47 ± 2; Polymaker V5.4 50.8 vs. V5.2 31.9 |
| ABS in-layer tensile | 35 (30–40) | **33 (25–40)** | Polymaker 33.4; bulk ABS 32–45; Ahn P400 FDM ~17–19 (old grade, sets the floor) |
| Across/in-layer ratio | 0.5 (0.4–0.6) | **0.5 (0.3–0.8)** | Prusa interlayer 0.33–0.38; Eryildiz 0.64; Polymaker 0.73–0.89 |
| Flexural/tensile (reference only) | — | 1.4–1.7 | Prusa PLA/PETG, Polymaker ABS; use tensile for the check |
| Sustained-load derating | — | **PLA 0.3 (0.2–0.4); PETG/ABS 0.4 (0.3–0.5)** | 20–40 % rule (Protolabs); PLA HDT 55 °C; no printed creep-rupture data |

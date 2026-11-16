# Rule pack engineering data: hand anthropometrics and safety factors

Researched 2026-11-16. Units are mm unless stated. "Computed" means I calculated it this session from the public ANSUR II CSVs (unweighted sample statistics, linear-interpolated percentiles). The official ANSUR II report (NATICK/TR-15/007) publishes *weighted* statistics, so its values may differ by about 1 mm. I could not open the report PDF to cross-check.

## (A1) ANSUR II hand length, hand breadth, and finger measurements

### Takeaway
ANSUR II has hand length, hand breadth, hand circumference and palm length. It has **no index-finger or fingertip measurements**: no finger length, no finger breadth, no distal phalanx breadth. The current hand placeholders (190 × 85) are very close to the pooled ANSUR II medians (190 × 86).

### Cited Findings
- The public ANSUR II files are `ANSUR_II_MALE_Public.csv` (n = 4,082) and `ANSUR_II_FEMALE_Public.csv` (n = 1,986). They are linked from the Penn State OpenLab page, which also links the TR-15/007 methods/summary report PDF — [OpenLab ANSUR II](https://www.openlab.psu.edu/ansur2/); direct files at [male CSV](https://tools.openlab.psu.edu/publicData/ANSUR_II_MALE_Public.csv), [female CSV](https://tools.openlab.psu.edu/publicData/ANSUR_II_FEMALE_Public.csv), [TR-15/007 PDF](https://tools.openlab.psu.edu/publicData/ANSURII-TR15-007.pdf)
- Units are mm, except mass, which is in hectograms. Male and female data should be analysed separately, because a combined sample doesn't represent any real population (secondhand, search summary) — [OpenLab ANSUR](https://www.openlab.psu.edu/ansur/); [calmcode ergonomics dataset](https://calmcode.io/datasets/ergonomics)
- The raw data were released publicly in 2017 by NSRDEC — [army.mil](https://www.army.mil/article/188601/for_good_measure_natick_releases_raw_data_from_army_wide_anthropometric_survey)
- The hand-related columns in the CSV header are `handlength`, `handbreadth`, `handcircumference`, `palmlength`, `forearmhandlength`, `thumbtipreach`, `wristcircumference` and `overheadfingertipreachsitting`. There is no finger-length, finger-breadth or fingertip column (verified by reading the CSV header) — [male CSV](https://tools.openlab.psu.edu/publicData/ANSUR_II_MALE_Public.csv)
- **Computed from the public CSVs** — [male CSV](https://tools.openlab.psu.edu/publicData/ANSUR_II_MALE_Public.csv), [female CSV](https://tools.openlab.psu.edu/publicData/ANSUR_II_FEMALE_Public.csv):

| Variable | Sample | n | Mean | SD | P5 | P50 | P95 |
|---|---|---|---|---|---|---|---|
| `handlength` | Male | 4082 | 193.3 | 9.9 | 177 | 193 | 210 |
| `handlength` | Female | 1986 | 181.1 | 10.1 | 165 | 180 | 199 |
| `handlength` | Pooled M+F | 6068 | 189.3 | 11.5 | 171 | 190 | 208 |
| `handbreadth` | Male | 4082 | 88.3 | 4.4 | 81 | 88 | 96 |
| `handbreadth` | Female | 1986 | 78.2 | 3.8 | 72 | 78 | 85 |
| `handbreadth` | Pooled M+F | 6068 | 85.0 | 6.3 | 74 | 86 | 94 |
| `handcircumference` | Male | 4082 | 212.3 | 10.2 | 195 | 212 | 230 |
| `handcircumference` | Female | 1986 | 186.6 | 8.8 | 173 | 187 | 202 |
| `palmlength` | Male | 4082 | 116.5 | 6.2 | 107 | 116 | 127 |
| `palmlength` | Female | 1986 | 108.7 | 5.9 | 100 | 108 | 119 |

- The midpoint of the male and female means, weighting each sex equally (not by sample size), is 187.2 for hand length, 83.2 for hand breadth and 112.6 for palm length (computed, same sources).
- ANSUR II `handbreadth` is breadth across the metacarpal-phalangeal joints. That is the definition the FAA appendix uses for its own ANSUR-style "Hand Breadth" item. I did not open the ANSUR II measurer's handbook to confirm it — [FAA HFDS App. B](https://hf.tc.faa.gov/hfds/download-hfds/hfds_pdfs/App_B_Tech_Ops_Anthropometrics.pdf)

### Inferences
- The pooled sample is about two-thirds male, so pooled means sit closer to male values than an equal-sex population would.
- The Army population is younger and fitter than the general population, so these values only roughly represent consumers. For drawing scale references, a difference of a few mm doesn't matter.

### Gaps
- I did not cross-check against the weighted values in the official TR-15/007 tables (Gordon et al. 2014), because the PDF was not opened this session.

## (A2) Index finger and fingertip dimensions (not in ANSUR II)

### Takeaway
The best primary source I could open is the FAA Technical Operations anthropometric survey (Bradtmiller et al. 2008, n = 1,244, civilian workforce). It gives index finger length and index finger breadth **at the proximal interphalangeal (PIP) joint**. The breadth at the fingertip (distal) is a few mm smaller. Greiner 1991 (NATICK/TR-92/011) measures digit 2 distal interphalangeal (DIP) joint breadth, but DTIC returned 403, so I have no numbers from it. The widely quoted "16–20 mm fingertip width" figure is secondhand and its attribution is disputed.

### Cited Findings
- FAA HFDS Appendix B (Bradtmiller, Hodge, Kristensen & Mucher 2008, 1,244 FAA Tech Ops personnel, 25 sites) — [FAA HFDS App. B](https://hf.tc.faa.gov/hfds/download-hfds/hfds_pdfs/App_B_Tech_Ops_Anthropometrics.pdf):
  - **Index finger length** (fingertip to the crease at the base of the index finger), percentiles 1/5/50/95/99: men 64/67/74/82/86 mm; women 59/62/69/76/81 mm.
  - **Index finger breadth at the PIP joint**: men 18/19/21/23/24 mm; women 15/16/18/21/22 mm.
  - Hand breadth (at the metacarpal-phalangeal joints): men 78/80/88/96/99 mm; women 68/71/77/84/86 mm. These agree with the ANSUR II values computed above to within 1 mm, which is a useful consistency check.
- Greiner, *Hand Anthropometry of U.S. Army Personnel*, NATICK/TR-92/011 (Dec 1991; sometimes cited as 1992). Its measurement list includes digit 2 DIP joint breadth (item 15), and its summary statistics and percentiles start on p. 41. I could not retrieve the values (DTIC returned 403; the uvic.ca mirror served HTML) — [DTIC ADA244533](https://apps.dtic.mil/sti/pdfs/ADA244533.pdf); [mirror](https://www.ece.uvic.ca/~bctill/papers/mocap/Greiner_1992.pdf)
- Secondhand: "an MIT Touch Lab study … found that the average width of the index finger is 1.6 to 2 cm (16–20 mm) for most adults" (usually traced to Dandekar, Raju & Srinivasan 2003). A commenter on the article questions whether the MIT paper states an average width at all — [Smashing Magazine](https://www.smashingmagazine.com/2012/02/finger-friendly-design-ideal-mobile-touchscreen-target-sizes/); same figure in [NN/g](https://www.nngroup.com/articles/touch-target-size/)
- Secondhand: NN/g cites Parhi, Karlson & Bederson for a minimum touch target of 10 × 10 mm (this is a target size, not a finger size) — [NN/g](https://www.nngroup.com/articles/touch-target-size/)
- Boike et al. 2025 (n = 162 adults, Minnesota) report index finger length of 95 ± 5 mm in men and 87 ± 5 mm in women. They measure with rulers to a different landmark than the FAA "crease" definition, so the numbers are not comparable. They report no breadth values — [J Hand Surg Glob Online 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC12309929/)

### Inferences
- **Recommended reference fingertip:** breadth **18 mm**, length of the visible pad / distal segment **about 25 mm**.
  - 18 mm sits between the FAA PIP-joint medians (21 men / 18 women; the distal end of the finger is narrower than the PIP joint) and the middle of the secondhand 16–20 mm range.
  - The current placeholder of 16 mm is at the low end of the range: plausible for a female or small fingertip, small for a "typical adult".
  - The 25 mm length placeholder is a distal-phalanx length. I found no primary source for it this session, so leave it marked unverified.
- **Recommended reference hand (one representative value): length 190 mm, breadth 85 mm.** These equal the pooled ANSUR II medians (190 / 86) to within 1 mm. Change the source note from "to be sized from ANSUR II" to "ANSUR II pooled P50, `handlength` / `handbreadth`, computed from public CSV". For an equal-sex weighting, use 187 × 83.
- If the pack ever sizes hand *clearance* rather than drawing a reference, use the male P95 (210 × 96) instead of medians.

### Gaps
- I have no primary-source numbers for distal (fingertip/DIP) index finger breadth. Greiner 1991 (DTIC ADA244533, item 15) is the source to fetch manually. Pheasant & Haslegrave's *Bodyspace* also tabulates finger breadths, but I did not access it.
- I did not verify ISO 9241-410 or ISO 9241-9 finger-size figures.
- I did not access the Dandekar et al. 2003 primary paper.

## (B1) Standards: test loads and safety factors for wall-mounted shelving

### Takeaway
None of the standards I found give a single "design SF" for consumer wall shelves. The figures below are the multipliers implied by test loads and anchor tables:
- UL 2442 (TV/display mounts) tests at 4× rated load (≤ 100 lb displays).
- Drywall anchor makers convert ultimate to allowable at 4:1.
- EN 16122 tests shelves and supports with distributed loads in kg/dm², not with a multiplier.

### Cited Findings
- UL 2442 (wall/ceiling mounts for displays): the mount must be tested to at least **4× its weight rating** for displays of ≤ 100 lb, or **2× rating + 200 lb** for heavier displays (UL Standards & Engagement summary; I did not see the standard text) — [ULSE](https://ulse.org/insight/ul-standards-engagement-standards-matter-how-standards-wall-and-ceiling-mounts-help-prevent-serious/). A retailer states "×2 plus 100 lb", which conflicts with ULSE; prefer ULSE — [screenmounts.com.au](https://www.screenmounts.com.au/blogs/news/tv-wall-mount-weight-limit)
- EN 16122 (domestic and non-domestic storage furniture, strength/durability test methods), as applied in accredited lab test reports:
  - shelf-support test (cl. 6.1.5): 0.65 kg/dm² for 10 cycles;
  - overload test (cl. 10.1.3): 2.5 kg/dm² in one report;
  - shelf-deflection test: 1.5 kg/dm² in another report.

  These figures are as applied in specific product reports. The standard sets the requirement levels (in EN 16121 for domestic use) — [BCI/Teknologisk test report, steel shelving EN 16121/16122/14073](https://bci.dk/media/27195/829645-1-60_30-classic-steel-shelving-en-16121_16122_14073-uk.pdf); [String shelves EN 16121 report](https://media.stringfurniture.com/media/norce/f2a5dd1a-5d3f-427c-b7b2-c9f4d2a9fc04?format=pdf); [CATAS comparison table of furniture tests](https://catas.com/uploads/media/catas-tabellanormemobilieng.pdf?v3.1=)
- Anchor manufacturers:
  - Wall Twister: published drywall values are ultimate and should be reduced by a minimum SF of 4.0 to get allowable working load. It notes that failure is by pull-out from the drywall and that capacity depends on the drywall, not the screw — [Wall Twister data sheet](https://cdn.adiglobaldistribution.us/pim/Original/10284/4731-Wall-Twister-Product-Data-Sheet.pdf)
  - Sure Wall (SC Fastening): the table already gives allowable loads "based on a safety factor of 4.0", so don't divide again — [Sure Wall](https://catalog.scfastening.com/Asset/Sure%20Wall.pdf)
  - L.H. Dottie toggle bolts: allowable loads calculated with SF 4.0; "consistency of drywall varies greatly", so use as guidelines only — [LH Dottie brochure](https://cdn.adiglobaldistribution.us/pim/Original/10059/LH-TBC82_Manufacturer_Brochure.pdf)
  - Confast: values are average ultimate; "a safety factor of 4:1 or 25% is generally accepted as a safe working load" — [Confast Wall Driller](https://www.confast.com/wall-driller-technical-information)

### Inferences
- ASTM F2057 covers clothing storage unit tip-over, and UL 1678 / UL 2442-type standards cover carts and mounts for AV equipment. Neither is a shelf-bracket strength standard. This is from my background knowledge; I did not verify scope text this session. For a consumer wall shelf, EN 16121/16122 is the closest furniture standard, and UL 2442's 4× is the closest analogue for a wall-mounted product's static proof test.
- A 20 kg rated shelf checked UL-2442-style would be proof-tested at 80 kg without cracking, bending or falling. That is consistent with an SF of 4, not 2.

### Gaps
- I did not see the full EN 16121/16122 text or its load-level tables, the full UL 2442 text, or ANSI/BIFMA (BIFMA X5.9 for storage, which includes wall-hung units). I found no BIFMA multiplier this session.

## (B2) Safety factors for static loads on unreinforced thermoplastics, and which quantity to apply them to

### Takeaway
Plastics design literature converges on roughly **2 for short-term static load** and roughly **4 for long-term (sustained, creep-governed) static load**, preferably applied to creep-rupture or creep-modulus data rather than short-term tensile strength. A loaded shelf bracket carries a sustained load, so SF 2 on short-term strength is unconservative, particularly for PLA printed by FDM.

### Cited Findings
- Recommended factors of about 2.0 for short-term static and 4.0 for long-term static loading. The paper also cites 1.5–2 for static load and 2–2.85 in a pallet application (Horvath). The extracted table was garbled, so treat this as approximate — [ResearchGate: Design criteria and safety factors for plastic components design](https://www.researchgate.net/publication/240421046_Design_criteria_and_safety_factors_for_plastic_components_design)
- Worked example with a design SF of 2 on polycarbonate: once long-term effects are included, the allowable operating stress came out at only about 1/12 of short-term tensile strength. Use creep modulus in FEA, and get creep-rupture data under worst-case conditions — [PlasticsToday](https://www.plasticstoday.com/materials/long-term-testing-critical-for-material-selection)
- Mitsubishi Chemical's design guide recommends using creep data together with a safety factor when setting load — [MCAM design guide](https://www.professionalplastics.com/professionalplastics/content/MGC-Design-Guide.pdf)
- Smithers Rapra lists "reduced design safety factors" among the classic causes of plastic product failure — [Smithers Rapra](https://www.sintef.no/globalassets/project/ffs/dokumenter/seminar-juni2010/rapra-ffs-2010.pdf)

### Inferences
Recommendation for the hand-calc check (my synthesis, not a quoted standard):
1. **Anchors and fixings:** compare the design load with the manufacturer's *allowable* load. If only ultimate is given, divide it by 4. Don't add a second factor if the table already says "allowable (SF 4)".
2. **Printed bracket body:** Allowable stress = σ_ref / SF, using the strength in the weakest print direction (across layers, Z-direction) as σ_ref:
   - SF ≥ 2 for short-term or transient load;
   - SF ≈ 4 for sustained load such as a loaded shelf. Alternatively, use SF 2 applied to a creep-rupture strength at the design life.

   For PLA specifically, also flag heat (PLA softens around 55–60 °C) as an assumption. That figure is background knowledge, not verified this session.
3. **Proof-load framing (optional):** assert that the structure survives 4 × rated load (UL 2442 analogue), i.e. 80 kg for a 20 kg rating.
4. **Load definition:** state the rated load as a design input (20 kg). Optionally cross-check it as a distributed load using EN 16122's 1.5–2.5 kg/dm² on the shelf area.
- Net effect for the current pack: raising SF from 2 to 4 for the sustained-load case doubles the required section modulus for the bracket.

### Gaps
- I did not access the BASF, Covestro or DuPont design guides directly. The 2/4 split comes from one secondary paper (garbled table) plus consistent practitioner sources.
- I found no authoritative SF for FDM-printed parts; the knockdown for layer anisotropy needs its own source.

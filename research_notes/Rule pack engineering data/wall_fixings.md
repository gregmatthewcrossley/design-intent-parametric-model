# Wall fixings for a small shelf bracket: axial pull-out (tension) and shear capacity

Scope: 1/2" (12.5 mm) gypsum board anchors and #8/#10 wood screws into softwood studs. The values replace the rule-pack placeholders "drywall with anchors" (200 N, 150–250) and "wood stud" (800 N, 600–1000) per fixing. Research date: 2026-11-16.

Unit conversions used throughout: 1 lbf = 4.448 N, 1 kgf = 9.807 N, and 1 lb/in = 0.1751 N/mm.

Source-quality legend:
- **[P]** primary: the manufacturer's own sheet or a code/handbook text that I read directly.
- **[S]** secondhand: a retailer listing, forum post or search snippet.
- **[C]** computed by me from a cited equation.
- **[M]** from my background knowledge with no source retrieved this session; verify before relying on it.

---

## Q1. Drywall anchors in 1/2" (12.5 mm) gypsum board: ultimate vs. rated tension and shear, by anchor type

### Takeaway
In 1/2" board, ultimate tension spans roughly 10× across anchor types:
- Plastic expansion plugs and self-drilling anchors: about 130–450 N (30–100 lbf).
- Plastic toggles: about 640 N (143 lbf).
- Metal strap toggles: about 600–1060 N (134–238 lbf).
- 5/8" board adds roughly 20–50%.

Manufacturers publish either *ultimate* (average lab failure) values or *safe working* values. Toggler recommends 1/4 of ultimate. Cobra publishes "safe working loads" at 2:1. ITW E-Z Ancor publishes averages and says to apply "appropriate safety factors". A single "drywall with anchors" class at 200 N is a reasonable *ultimate tension* value for a plastic or self-drilling anchor. It is too high to use as an allowable value, and far too low for a toggle.

### Cited findings

**TOGGLER SNAPTOGGLE (metal channel strap toggle, metric BM series; UNC 3/16-24 and 1/4-20 equivalents) [P]**
- Ultimate tensile, 12.5 mm drywall:
  - BM5: 108 kg = 1,059 N (238 lbf). BM6: 120 kg = 1,177 N (265 lbf). BM8: 122 kg. BM10: 124 kg.
- Ultimate tensile, 15 mm drywall:
  - BM5: 161 kg = 1,579 N (355 lbf). BM6: 161 kg. BM8: 217 kg. BM10: 261 kg.
- Ultimate shear, 12.5 mm drywall: BM5 112 kg = 1,098 N (247 lbf). BM6 109 kg = 1,069 N (240 lbf).
- Ultimate shear, 15 mm drywall: BM5 135 kg = 1,324 N (298 lbf). BM6 146 kg = 1,432 N (322 lbf).
- Over a 25 ga steel stud, 12.5 mm: BM5 186 kg, BM6 192 kg.
- Test basis and safety factor:
  - The sheet says "All tests carried out indicate the ultimate working load (UWL) using equivalent UNC thread anchors & bolts… Industry safety standards recommend ¼ of UWL".
  - Pull-out values are "based on independent laboratory tests done according to U.S. Government standards… guides only and cannot be guaranteed".
  - Tension failure in drywall is defined as "onset of gouging of drywall material".
  - Anchors meet Type V of Federal Spec FF-B-588-D (superseded).
- Source: [Toggler Technical Bulletin, SNAPTOGGLE metric](https://toggler.co.uk/wp-content/uploads/2021/09/Metric-Technical_SNAPTOGGLE.pdf)
- The imperial 3/16-24 SnapToggle is quoted at 238 lb ultimate pull-out in 1/2" drywall and 356 lb in 5/8" [S]. This agrees with the metric BM5 sheet. Source: [Hardware Hut listing](https://hardwarehut.com/products/307675/toggler-anchor-system-snaptoggle-3-1624-toggle-bolt-2-per-bag-with-bolts)
- McMaster-Carr lists the 1/4"-20 SnapToggle in 1/2" drywall at 260 lbf pull-out and 240 lbf shear [S, basis not stated]. Source: [McMaster-Carr snap toggles](https://www.mcmaster.com/snap-toggles)
- **Compatibility note:** SnapToggle and FlipToggle take *machine bolts* (3/16-24, 1/4-20, M5, M6), not #8/#10 wood screws. Source: [Toggler SNAPTOGGLE bulletin](https://toggler.co.uk/wp-content/uploads/2021/09/Metric-Technical_SNAPTOGGLE.pdf)

**TOGGLER plastic hollow-wall anchor TB (folding plastic toggle, 8 mm hole, 3.5–6 mm screws, so #8/#10 fit) [P]**
- Ultimate tensile pull-out: 12.5 mm drywall 65 kg = 637 N (143 lbf). 9.5 mm drywall 44 kg.
- Ultimate shear: 12.5 mm drywall 76 kg = 745 N (168 lbf). 9.5 mm drywall 57 kg.
- Grip range is 9.5–13 mm, so 15/16 mm board needs the TC size. TC in 15 mm board: tension 72 kg = 706 N, shear 107 kg = 1,049 N.
- The tests used a 4.0 mm screw.
- The sheet says "Industry standards recommend ¼ of ultimate test load."
- Source: [Toggler Technical Bulletin, TOGGLER hollow-wall anchors (HWA)](https://toggler.co.uk/wp-content/uploads/2021/09/Metric-Technical_HWA.pdf)

**Cobra FlipToggle (single-strap metal toggle, bolts 10-24 / 1/4-20) [P]**
- Safe working loads at 2:1 in 1/2" drywall:
  - 10-24 bolt: 67 lb tension / 106 lb shear.
  - 1/4-20 bolt: 74 lb tension / 137 lb shear.
- Safe working loads at 2:1 in 5/8" drywall:
  - 10-24 bolt: 107 lb / 188 lb.
  - 1/4-20 bolt: 120 lb / 209 lb.
- Implied ultimates (×2) in 1/2":
  - 10-24: 134 lbf (596 N) tension and 212 lbf (943 N) shear.
  - 1/4-20: 148 lbf (658 N) tension and 274 lbf (1,219 N) shear.
- The sheet states "Safe working loads represent a safety factor of 2:1 from ultimate test loads". It also requires ≥ 1.5" (38 mm) between anchors.
- Source: [Cobra FlipToggle technical sheet](https://cdn.rona.ca/documents/FLIPTOGGLE-COBRA-Technicalsheet.pdf)

**Cobra TripleGrip (plastic expansion and winged plug) [P]**
- Safe working loads at 2:1 in 1/2" drywall:
  - #8 grey: 21 lb tension / 35 lb shear.
  - #10 blue: 29 lb / 46 lb.
  - #6: 18 / 29.
  - #12: 37 / 61.
- Safe working loads at 2:1 in 5/8" drywall: #8 32 / 51 lb; #10 44 / 77 lb.
- Implied ultimates (×2) in 1/2":
  - #8: 42 lbf (187 N) tension and 70 lbf (311 N) shear.
  - #10: 58 lbf (258 N) tension and 92 lbf (409 N) shear.
- The sheet notes "Loads may vary according to the quality of the drywall".
- Source: [Cobra TripleGrip technical sheet](https://cdn.rona.ca/documents/TRIPLEGRIP-COBRA%20-TechnicalSheet.pdf)
- A retailer-hosted table lists #6 TripleGrip in 1/2" at 36 lb max pull / 58 lb max shear [S]. That is consistent with 2 × the safe values. Source: [Guillevin spec PDF](https://www.guillevin.com/cdn/shop/files/Technical-Specs-Detail-7f7d9a7d-a331-4ed4-94ac-715891dc5567.pdf)

**Cobra WallDriller Plus (self-drilling, nylon/acetal, expanding) [P]**
- Safe working loads at SF 2 in 1/2" drywall:
  - #8 × 1-1/2": 43 lb tension / 115 lb shear.
  - #10 × 1-3/4": 50 lb / 118 lb.
- Safe working loads at SF 2 in 5/8" drywall, #10: 60 / 175 lb.
- Implied ultimates in 1/2":
  - #8: 86 lbf (383 N) tension and 230 lbf (1,023 N) shear.
  - #10: 100 lbf (445 N) tension and 236 lbf (1,050 N) shear.
- The sheet says "Safe working loads are average tested loads for items flush to wall and will vary with items hung away from the wall." This matters for a cantilevered bracket.
- Source: [Cobra WallDriller Plus technical sheet](https://cdn.rona.ca/documents/COBRA%20-%20WallDriller%20Plus%20-%20Technical%20Sheet.pdf)
- For the plain nylon WallDriller, a retailer lists ultimate 50 lb tension and 110 lb shear at 1/2" [S]. Source: [Toolbox Supply listing](https://www.toolboxsupply.com/collections/anchors-hollow-wall-expansion/products/cobra-anchors-029s-walldriller-hollow-wall-nylon-anchors-with-screw-8-4-pack)

**Cobra WallGripper (self-drilling nylon, wings expand behind board, #8) [P]**
- Safe working loads at 2:1 in 1/2" drywall: 35 lb (16 kg) tension / 85 lb (38 kg) shear.
- Implied ultimate: 70 lbf (311 N) tension and 170 lbf (756 N) shear.
- Source: [Cobra WallGripper technical sheet (hosted by InspectApedia)](https://inspectapedia.com/structure/Cobra-WallGripper-Molly-Strength.pdf)

**ITW Buildex E-Z Ancor (self-drilling zinc and nylon) [P]**
- "Ultimate holding weight" in 1/2" drywall:
  - Light Duty Plastic (E-Z Lite): 30 lbs.
  - Light Duty Zinc: 40 lbs.
  - Medium Duty (E-Z Zinc / E-Z Plastic Plus, #6–#8): 50 lbs.
  - Twist-N-Lock (#8): 75 lbs.
  - Heavy Duty E-Z Toggle (#8 screw supplied): 85 lbs.
- In 5/8" drywall: 40 / 50 / 75 / 80 / 150 lbs respectively.
- In 1/2": medium duty is 50 lbf = 222 N; E-Z Toggle is 85 lbf = 378 N.
- The sheet does **not** say whether these are tension or shear. It says: "These performance values are averages obtained under laboratory conditions… will change depending on age, moisture content and surface treatment… Appropriate safety factors should be applied." It also says "Do Not Use For Mounting Televisions".
- Source: [ITW Buildex E-Z Ancor product data (BuildSite)](https://www.buildsite.com/pdf/itwbuildex/E-Z-ANCOR-Self-Drilling-Drywall-Anchors-Product-Data-2964390.pdf)
- Other quotes for the zinc E-Z Ancor in 1/2" give 150 lb shear / 50 lb pullout, as ultimate averages [S]. Sources: [Lawson Products](https://www.lawsonproducts.com/products/self-drilling-wall-anchor-1-5-8-95096); [ITW 6400 data sheet via Orgill](https://images.orgill.com/weblarge/10003/ITW_6400_Data_Sheet.pdf)
- Zoro retailer listings [S] are not consistent with the ITW sheet:
  - Nylon 1-5/8": 50 lb tension, 75 lb "max ultimate tension", 141 lb shear.
  - Zinc 1-5/8": 117 lb max ultimate tension, 193 lb shear.
  - Sources: [Zoro nylon](https://www.zoro.com/itw-buildex-wall-anchor-1-58-in-l-nylon-50-lb-tension-strength-100-pk-5035902/i/G012483423/); [Zoro zinc](https://www.zoro.com/itw-buildex-wall-anchor-1-58-in-l-zinc-alloy-61-lb-tension-strength-25-pk-ez25/i/G412483443/)

**fischer DuoPower (nylon universal plug), 12.5 mm plasterboard [S, search snippet only; I did not read the datasheet text]**
- Current datasheet: "recommended loads" of 0.12–0.15 kN (27–34 lbf) across sizes.
- Older datasheet: 0.09–0.15 kN, with a footnote that recommended loads "include a safety factor of 7".
- If SF 7 applies, the implied mean ultimate is about 0.6–1.0 kN. That looks high next to the US plug data above, so treat it as unverified.
- Source: [fischer DuoPower VKU datasheet](https://electrical4less.co.uk/wp-content/uploads/2024/07/VKU_DUOPOWER_EN-1.pdf); [fischer UK DuoPower product page](https://www.fischer.co.uk/en-gb/products/standard-fixings/plastic-fixings/duopower)

**Safety factors as manufacturers state them**
- Toggler: 4:1 ("industry standards recommend ¼ of ultimate test load") — [Toggler HWA bulletin](https://toggler.co.uk/wp-content/uploads/2021/09/Metric-Technical_HWA.pdf)
- Cobra: 2:1 for drywall and 4:1 for concrete, on the same TripleGrip sheet — [Cobra TripleGrip](https://cdn.rona.ca/documents/TRIPLEGRIP-COBRA%20-TechnicalSheet.pdf)
- ITW: unspecified ("appropriate safety factors") — [ITW E-Z Ancor](https://www.buildsite.com/pdf/itwbuildex/E-Z-ANCOR-Self-Drilling-Drywall-Anchors-Product-Data-2964390.pdf)
- fischer: 7 on plasterboard recommended loads [S] — [fischer DuoPower VKU](https://electrical4less.co.uk/wp-content/uploads/2024/07/VKU_DUOPOWER_EN-1.pdf)
- A generic toggle-bolt table notes "the suggested safe working load is 1/4 the loads listed" [S]. Source: [Anchor toggle bolt table (cdn.shopify)](https://cdn.shopify.com/s/files/1/0056/7856/3437/files/Anchorstogbolt.pdf)

### Inferences
- **Summary table, 1/2" (12.5 mm) board, per fixing, ultimate (mean lab failure):**

| Category (fits #8/#10?) | Ultimate tension N (lbf) | Ultimate shear N (lbf) | Basis |
|---|---|---|---|
| Plastic expansion plug (yes) | 190–260 (42–58) | 310–410 (70–92) | Cobra TripleGrip ×2 |
| Self-drilling, light/medium (yes, ≤ #8 typically) | 130–220 (30–50) | ~670 (150) [S] | ITW E-Z Ancor |
| Self-drilling, expanding or winged (yes) | 310–445 (70–100) | 760–1,050 (170–236) | Cobra WallGripper, WallDriller Plus ×2; ITW Twist-N-Lock 75 lb, E-Z Toggle 85 lb |
| Plastic folding toggle (yes) | ~640 (143) | ~745 (168) | Toggler TB |
| Metal strap toggle (no, machine bolt) | 600–1,180 (134–265) | 940–1,100 (212–247) | Cobra FlipToggle ×2; Toggler SnapToggle |
| Spring/wing toggle, molly | not found | not found | see Gaps |

- For 5/8" (15–16 mm) board, scale tension up by about 1.2–1.5×. Examples:
  - TripleGrip #8: 21 → 32 lb safe.
  - SnapToggle BM5: 108 → 161 kg.
  - E-Z medium: 50 → 75 lb.
- Toggles are an exception: 12.5 mm board is at the top of the TB plastic toggle's grip range.
- In a cantilever-shelf geometry, tension governs because tension capacity is roughly 1/2–1/3 of shear capacity for every expanding or self-drilling anchor above. Cobra also warns that values are "for items flush to wall".
- Using the existing 200 N value:
  - As an *ultimate tension* for a generic plastic or self-drilling anchor, it sits mid-range.
  - As an *allowable*, it overstates capacity by about 2–4×.
- Recommendation for the rule pack:
  - Split the category so that it records both ultimate and allowable:
    - plug/self-drilling: ultimate tension nominal 250 N, range 130–450.
    - plastic toggle: 640 N, range 450–700.
    - strap toggle: 1,000 N, range 600–1,200.
  - Have the design check divide by its own safety factor of 4.

### Gaps
- Spring (wing) toggles and molly (hollow-wall sleeve) anchors: I retrieved no primary data. The Hillman, Simpson, Hilti and Rawlplug sheets were not reached in this session's budget. Simpson's FlipToggle catalog snippet showed no gypsum table.
- The ITW E-Z Ancor "ultimate holding weight" does not state its load direction.
- I did not read the Toggler imperial (UNC) bulletin directly. The 238 lb figure is retailer-quoted, but it matches the metric sheet.
- I found no ICC-ES evaluation report for gypsum-board anchors. These products appear to be rated only by manufacturer tests under the superseded FF-B-588 / ASTM E488-style pull tests.
- No coefficient of variation is published, so the low end of each range should be treated as the minimum of the published means, not a 5th percentile.

---

## Q2. Wood screws (#8, #10) into a softwood stud: NDS withdrawal, adjustment factors, ultimate ratio, Eurocode 5

### Takeaway
- NDS reference withdrawal design value for a #8/#10 wood screw in SPF or Douglas fir is about 14–24 N per mm of thread penetration (82–135 lb/in).
- That gives about 360–950 N (81–213 lbf) per screw for 25–40 mm penetration.
- The Wood Handbook ultimate (mean) is about 5.5× higher: about 2.0–5.2 kN (450–1,170 lbf) per screw.
- The current placeholder "800 N (600–1000)" matches an NDS *allowable* value for a #10 in denser stud lumber with about 35–40 mm penetration. It is about 1/3–1/4 of the ultimate.

### Cited findings
- **NDS equation:** The NDS wood-screw reference withdrawal design value is W = 2850 G² D (lb per inch of thread penetration), with D the screw diameter and G the specific gravity (NDS 12.2.2 / Table 12.2B) [S, transcribed by third parties]. A worked example gives 95.5 lb/in for D = 0.19 in, G = 0.42, which matches my computation. Sources: [Applied Engineering ER-0262 citing NDS 12.2.2](https://forms.iapmo.org/ues_reports/reports/ER_0262.pdf); [Scribd NDS worksheet](https://www.scribd.com/document/467022983/VALUE)
- I could not read the AWC primary text: the [AWC NDS 2018 with Commentary, Ch. 12](https://awc.org/wp-content/uploads/2021/10/AWC_NDS2018-withCommentary_20210928_AWCWebsite_Chapter12.pdf) link now redirects to an AWC landing page.
- **Wood Handbook ultimate equation:**
  - The text: "Ultimate test values for withdrawal loads of wood screws inserted into the side grain of seasoned wood may be expressed as" p = K G² D L (Eq. 8-10). Here p is the maximum withdrawal load, G the specific gravity (oven-dry weight and volume at 12% MC), D the shank diameter and L the threaded penetration.
  - "These values are based on reaching ultimate load in 5- to 10-min."
  - Validity: lead holes of about 70% of root diameter in softwoods; gauges per Table 8-8 (25.4 mm length: gauges 3–12; 38.1 mm: 5–14).
  - "The withdrawal loads of screws inserted in the end grain… should average 75% of the load sustained by screws inserted in the side grain."
  - Table 8-9 shank diameters: #8 = 4.17 mm (0.164 in); #10 = 4.83 mm (0.190 in).
  - Source: [Wood Handbook FPL-GTR-190 (2010) Ch. 8, reproduced in CED Engineering course S03-019 [S, verbatim copy]](https://www.cedengineering.com/userfiles/S03-019%20-%20Wood%20as%20An%20Engineering%20Material%20-%20Fastenings%20-%20US.pdf). The 2021 edition is [FPL-GTR-282 Ch. 8](https://www.fpl.fs.usda.gov/documnts/fplgtr/fplgtr282/chapter_08_fpl_gtr282.pdf); the server returned 502 when I tried it.
- **The coefficient:** The equation images did not extract. Engineers Edge gives the inch-pound form as p = 15,700 G² D L (lb, in) [S]. Converting units gives a metric coefficient of 108.2 (N, mm) [C]. Source: [Engineers Edge wood screw withdrawal calculator](https://engineersedge.com/calculators/wood_screw_pullout_withdraw_resistance_15385.htm)
- **Ratio of design value to ultimate:**
  - 15,700 / 2,850 = 5.5 [C].
  - An Eng-Tips commentator reads the 2850 term as including "a 1/5 reduction (safety factor) from the ultimate" [S]. The exact basis (1/5 of mean, after rounding) is in NDS Commentary C12.2.2, which I did not retrieve. Source: [Eng-Tips thread](https://www.eng-tips.com/threads/failure-load-for-nds-dowel-type-fasteners.434954)
- **Adjustment factors (NDS Table 11.3.1, 2018) [M]:**
  - Withdrawal W' = W × p × C_D × C_M × C_t × C_eg.
  - C_D: 0.9 permanent, 1.0 ten-year "normal" occupancy, 1.15 two-month snow.
  - C_M: 0.7 if wet in service.
  - C_t: 1.0 below 100 °F.
  - C_eg: withdrawal from end grain is not permitted for wood screws.
  - The NDS also requires the wood screw to be loaded in withdrawal from side grain, with thread penetration ≥ about 1" for lateral design.
  - Treat these as background knowledge only; no source was retrieved this session.
- **Product evaluation reports:** ICC-ES reports for proprietary screws tabulate withdrawal "per inch of thread penetration" to be multiplied by NDS adjustment factors, and derive design values with FOS = 3 on average test results (AC233 §3.2.1). Sources: [ICC-ES ESR-3933](https://icc-es.org/wp-content/uploads/report-directory/ESR-3933.pdf); [IAPMO ER-0262](https://forms.iapmo.org/ues_reports/reports/ER_0262.pdf)

**Computed values [C]** (G = 0.42 for SPF/hem-fir-ish; G = 0.50 for Douglas fir-larch; reference W with C_D = 1.0; ultimate from 15,700 G² D L)

| Screw, G | NDS ref. per mm | Ultimate per mm | NDS ref. @25 mm | NDS ref. @40 mm | Ultimate @25 mm | Ultimate @40 mm |
|---|---|---|---|---|---|---|
| #8 (4.17 mm), 0.42 | 14.4 N/mm (82 lb/in) | 79.5 N/mm (454 lb/in) | 360 N (81 lbf) | 577 N (130 lbf) | 1,990 N (447 lbf) | 3,180 N (715 lbf) |
| #10 (4.83 mm), 0.42 | 16.7 N/mm (95.5 lb/in) | 92.2 N/mm (526 lb/in) | 418 N (94 lbf) | 669 N (150 lbf) | 2,300 N (518 lbf) | 3,690 N (829 lbf) |
| #8, 0.50 | 20.5 N/mm (117 lb/in) | 113 N/mm (644 lb/in) | 512 N (115 lbf) | 819 N (184 lbf) | 2,820 N (634 lbf) | 4,510 N (1,014 lbf) |
| #10, 0.50 | 23.7 N/mm (135 lb/in) | 131 N/mm (746 lb/in) | 593 N (133 lbf) | 949 N (213 lbf) | 3,260 N (734 lbf) | 5,220 N (1,174 lbf) |

Penetration arithmetic:
- Drywall plus bracket is 12.5 + 5 = 17.5 mm.
- A 50 mm (2") screw leaves about 32 mm in the stud; a 1-1/2" screw leaves about 20 mm; a 2-1/2" screw leaves about 46 mm.
- Count only the *threaded* length in the stud. Partially threaded wood screws have a smooth shank of about 1/3 of their length, and the tapered tip contributes little.

**Eurocode 5 (EN 1995-1-1:2004+A1:2008 §8.7.2) [M for exact form; partial confirmation from secondary sources]**
- Equation 8.40a (as I recall it): F_ax,α,Rk = n_ef · f_ax,k · d · l_ef · k_d / (1.2 cos²α + sin²α).
  - f_ax,k = 0.52 d^-0.5 l_ef^-0.1 ρ_k^0.8 (N/mm²).
  - k_d = min(d/8; 1).
  - Valid for 6 mm ≤ d ≤ 12 mm and 0.6 ≤ d₁/d ≤ 0.75.
  - For other screws, including #8/#10 at about 4–5 mm, the characteristic withdrawal parameter comes from EN 14592 testing as declared in the product's DoP/ETA.
- An LNEC poster cites the "0.52 ρ^0.8 … d … l_ef" form [S]. Source: [LNEC poster, Cruz et al.](https://repositorio.lnec.pt/bitstream/123456789/1006078/1/3_27_p224_poster_cruzetal.pdf)
- A structuralbasics tutorial combines the characteristic capacity with k_mod = 0.9 (short-term, SC2) and γ_M = 1.3 for connections, F_ax,Rd = k_mod F_ax,Rk / γ_M. It also checks head pull-through as a separate mode. Source: [StructuralBasics, tensile capacity of screws](https://www.structuralbasics.com/tensile-capacity-of-screws-eurocode-tutorial/)
- Illustrative calculation [C, extrapolated outside the d ≥ 6 mm validity]:
  - Inputs: d = 4.5 mm, l_ef = 30 mm, ρ_k = 350 kg/m³ (C16 softwood).
  - f_ax,k ≈ 18.9 N/mm², k_d = 0.56.
  - F_ax,Rk ≈ 1.44 kN (324 lbf, characteristic, about the 5th percentile).
  - Design value F_ax,Rd ≈ 0.66 kN (permanent load, k_mod = 0.6) or 0.88 kN (medium-term, k_mod = 0.8).
  - These sit close to the NDS reference values (0.42–0.95 kN), which is a reasonable cross-check.

### Inferences
- Read as a per-fixing *allowable / reference design* value, the "wood stud 800 N (600–1000)" placeholder is plausible only for a #10 with about 35–40 mm thread in G ≈ 0.5 lumber. For SPF and a #8 with about 25–30 mm thread, the NDS allowable is about 360–500 N.
- Read as *ultimate*, 800 N is about 3× too conservative. Mean ultimate is about 2–5 kN.
- Recommendation:
  - Nominal reference/allowable (C_D = 1.0): 500 N (112 lbf), range 350–950 N.
  - Nominal ultimate: 2,500 N (560 lbf), range 1,800–5,200 N.
  - Use C_D = 0.9 for the permanent self-weight portion.
- At the top of the ultimate range, other modes may govern before wood withdrawal:
  - Steel tensile failure of a #8 screw. Root diameter is about 3 mm, so about 7 mm² × 500–800 MPa ≈ 3.5–5.6 kN; this figure is mine [M].
  - Head pull-through of a thin 3D-printed bracket, which is very likely the real limit for a 5 mm PLA bracket.
  - The bracket rule pack should check head pull-through separately (EC5 treats it as a separate mode; see StructuralBasics above).
- The Wood Handbook ultimate assumes pilot holes of about 70% of root diameter. Self-drilling or undersized pilots in SPF may differ, by an unknown amount.

### Gaps
- I could not open the NDS 2018/2024 primary text (Table 12.2B, C12.2.2 commentary, Table 11.3.1). The 2850 constant and the 1/5 basis are secondhand-confirmed only.
- I could not open the FPL-GTR-282 (2021) Ch. 8 PDF (HTTP 502). The 15,700 coefficient comes from Engineers Edge, because the equation images in the 2010 text did not extract.
- I did not retrieve the EN 1995-1-1 §8.7.2 text. The exponents and validity limits are from memory, partly corroborated. The EN 1995-1-1 revision (second-generation Eurocode 5, prEN 1995-1-1:2025) may change this clause, and I did not check it.
- I found no data on drywall-gap effects. Drywall between bracket and stud reduces lateral capacity (NDS gap provisions) but not withdrawal.

---

## Q3. Combined tension and shear interaction

### Takeaway
- **NDS (wood screws/lag screws):** Hankinson-type interaction between withdrawal and lateral design values, with α the angle between the wood surface and the load direction.
- **Drywall anchors:** none of the manufacturer sheets I retrieved (Toggler, Cobra, ITW) publishes an interaction equation. They give separate tension and shear values only.

### Cited findings
- **Combined lateral and withdrawal, sheathing fasteners:** A Missouri S&T NDS course page gives Z'α = Z'W' / (Z' sin α + W' cos α) for sheathing fasteners under combined uplift and lateral load. Here W' is the adjusted withdrawal (× thread penetration) and Z' the adjusted lateral value. Source: [Missouri S&T, Combined lateral and withdrawal loads](https://web.mst.edu/jthomas/classes/5260/concept/12/13/index.html)
- **NDS 12.4.1:** ICC-ES and IAPMO reports for screws state that combined lateral and withdrawal loads must be designed per NDS §12.4.1 (§11.4.1 in the 2012 edition). Sources: [ICC-ES ESR-3933](https://icc-es.org/wp-content/uploads/report-directory/ESR-3933.pdf); [IAPMO ER-0262](https://forms.iapmo.org/ues_reports/reports/ER_0262.pdf)
- **Form of NDS 12.4.1 [M, not verified]:** For lag screws and wood screws it is Z'α = (W'p) Z' / [(W'p) cos²α + Z' sin²α]. The linear sin/cos form above is §12.4.2 for nails and spikes.
- **Drywall anchors:** The Toggler, Cobra and ITW sheets list only separate tension and shear values. Toggler notes holding strength varies "inversely with … the distance of the load from the wall". Sources: [Toggler HWA](https://toggler.co.uk/wp-content/uploads/2021/09/Metric-Technical_HWA.pdf); [Cobra WallDriller Plus](https://cdn.rona.ca/documents/COBRA%20-%20WallDriller%20Plus%20-%20Technical%20Sheet.pdf)

### Inferences
- **Drywall anchors:** Use the conventional concrete-anchor interaction (N/N_allow)^(5/3) + (V/V_allow)^(5/3) ≤ 1.0, or the more conservative linear N/N_allow + V/V_allow ≤ 1.0 [M]. This convention comes from ACI 318 Ch. 17 and manufacturer concrete-anchor practice; I found no drywall-specific source.
- **Wood screws, for this bracket:** α ≈ 90° for the upper screw (mostly withdrawal) gives Z'α → W'p. The lower screw sits near the pivot and is mostly in shear plus bearing. So a per-fixing check of the upper screw in tension with a shear term is adequate.
- **Upper-fixing tension from the shelf moment:** T ≈ M / s, where s is the lever arm from the upper fixing to the pivot. The pivot is the bracket's bottom edge bearing on the wall (or the lower fixing).
  - This prying amplifies the load. Example: a 300 mm deep shelf with load at mid-depth (150 mm) and fixings 100 mm apart gives T ≈ 1.5 × the vertical load, or more if the pivot is the lower screw.
  - This is my own mechanics, not sourced.

### Gaps
- I could not retrieve the NDS 12.4.1 primary text, so the squared form for wood screws is from memory.
- I found no published interaction data for any gypsum-board anchor, and no independent (non-manufacturer) test series for anchors under combined tension, shear and moment.

---

## Q4. Recommended nominal values and ranges; which basis a design check should use

### Takeaway
Store **ultimate (mean failure)** capacity in the rule pack, and let dipm's design check apply its own safety factor. Recommended factors:
- Drywall anchors: 4, following Toggler and "industry standards".
- Wood screws: 5, matching the NDS 1/5 basis, or ≥ 3 when the input is already a characteristic or 5th-percentile value.

Mixing in manufacturers' "safe" values would double-count factors, because Cobra uses 2:1, Toggler 4:1, fischer 7 and NDS about 5.

### Cited findings
- Basis by source:
  - Cobra publishes safe loads at 2:1 — [Cobra FlipToggle](https://cdn.rona.ca/documents/FLIPTOGGLE-COBRA-Technicalsheet.pdf)
  - Toggler publishes ultimates and recommends 1/4 — [Toggler SNAPTOGGLE](https://toggler.co.uk/wp-content/uploads/2021/09/Metric-Technical_SNAPTOGGLE.pdf)
  - ITW publishes average lab values without a factor — [ITW E-Z Ancor](https://www.buildsite.com/pdf/itwbuildex/E-Z-ANCOR-Self-Drilling-Drywall-Anchors-Product-Data-2964390.pdf)
  - fischer publishes recommended loads that include SF 7 [S] — [fischer DuoPower VKU](https://electrical4less.co.uk/wp-content/uploads/2024/07/VKU_DUOPOWER_EN-1.pdf)
  - The NDS reference value is about 1/5.5 of the Wood Handbook ultimate [C from cited equations] — [Engineers Edge](https://engineersedge.com/calculators/wood_screw_pullout_withdraw_resistance_15385.htm); [IAPMO ER-0262](https://forms.iapmo.org/ues_reports/reports/ER_0262.pdf)

### Inferences
**Proposed rule-pack values (per fixing, 1/2" board or 2× softwood stud, #8/#10 screw)**

| Category | Ultimate tension nominal (low–high) | Allowable tension (÷4 for anchors, NDS ref for wood) | Ultimate shear nominal (low–high) |
|---|---|---|---|
| Drywall, plastic plug / self-drilling | 250 N / 56 lbf (130–450 N; 30–100 lbf) | 60 N / 14 lbf (35–110 N) | 600 N / 135 lbf (310–1,050 N) |
| Drywall, plastic folding toggle (TOGGLER TB-type) | 640 N / 143 lbf (450–700 N) | 160 N / 36 lbf | 745 N / 168 lbf (600–800 N) |
| Drywall, metal strap toggle (machine bolt) | 1,000 N / 225 lbf (600–1,180 N) | 250 N / 56 lbf | 1,000 N / 225 lbf (940–1,100 N) |
| Wood stud, #8/#10 wood screw, 25–40 mm thread | 2,500 N / 560 lbf (1,800–5,200 N) | 500 N / 112 lbf (350–950 N; NDS W'p, C_D = 1.0) | lateral not researched here (NDS yield-limit Z) |

- The existing "drywall with anchors 200 N (150–250)" is roughly right as the *ultimate tension* of a plug or self-drilling anchor. Widen its range to 130–450 N and label it ultimate.
- If the pack keeps a single "drywall" class, it should default to the plug/self-drilling class, because #8/#10 wood screws imply that class (toggles of the SnapToggle type need machine bolts). The plastic folding toggle (TOGGLER TB) also takes #8/#10 screws, so it could be offered as a stronger reading.
- The existing "wood stud 800 N (600–1000)" sits in the *allowable* band, at the high end. Relabel it as allowable with a nominal of about 500 N and range 350–950 N. Alternatively, switch to ultimate 2,500 N (1,800–5,200) with SF 5.
- **Combined-load default:** linear N/N_u + V/V_u ≤ 1/SF for anchors, and NDS 12.4.1 for wood screws. The upper fixing's tension should include the prying amplification M/s.
- **Missing fixing class:** A 5 mm 3D-printed bracket probably fails by screw-head pull-through or bracket cracking before a stud screw withdraws. The rule pack should carry a separate head pull-through or bearing check.

### Gaps
- None of these values is a characteristic (5th-percentile) value. The drywall data are manufacturer means with unknown scatter.
- Board quality, age and moisture (ITW's caveat) and installation quality are not quantified anywhere I found.
- I found no independent third-party test series (e.g. from a consumer-testing lab) comparing anchor types side by side. This session found none.

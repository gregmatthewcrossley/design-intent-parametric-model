# Tolerance, Uncertainty and Scale

*Status: steps 1, 2 and 4 of §5 built in GUI iteration 3 (2026-11-16): margins with worst-case ranges, heatmap and guess styling, all four scale cues; as-made prediction (3) and sampling (5) remain. Pack numbers are placeholders (NOTES #58).*

*Discussed and decided 2026-11-16, in response to review items MATH-07, MATH-09, PAIN-05 and PAIN-12 (see [`review-response.md`](review-response.md) C1, C2). The author asked for tolerance and uncertainty to be first-class concerns.*

## 1. Four concepts, kept apart

| Concept | What it is | Example | Audience |
|---|---|---|---|
| **Tolerance** (variation) | The as-made part differs from the model, within limits | FDM hole prints 0.2 mm undersize ± 0.1 | Designer, always |
| **Uncertainty** (unknowns) | Inputs we're unsure of: loads, material strength, use | "20 kg" might be 0–30 kg; PETG strength scatter | Designer, always |
| **Guesses** | Decisions the *model* made that the designer hasn't confirmed | A.3 placement = exposed-plate midpoint | Designer, always, visibly distinct |
| **Numerical robustness** | Kernel epsilons and coincidence tolerances | 1e-7 mm | Engine only: one documented tolerance policy plus a near-coincidence linter |

## 2. Engine model

- **Quantities carry ranges**, e.g. `t = 5 mm ± 0.15 (fdm_printing.wall)` or `load = 20 kg, assumed 0–30 (R.a1)`. Sources:
  - rule packs: process capability, shrink and offset compensation;
  - component packages: datasheet tolerances for off-the-shelf parts (central to integration-heavy design);
  - assumptions: the range is part of the assumption record.
- **Propagation. Decided: worst-case by default, sampling opt-in.**
  - **Worst-case intervals** for fits and tolerance stack-ups: simple, conservative, explainable.
  - **Monte Carlo sampling**, opt-in per check (typically strength/load), where worst-case is unrealistically pessimistic. Sampling uses a fixed seed, so results are repeatable.
- **Checks report margins. Decided: this comes first.** Every check reports a nominal value, a worst-case value, the limit, and the margin, e.g. "clearance 0.6 mm nominal, 0.1 mm worst case (limit 0)". Sampled checks report the failure fraction. A thin margin is a distinct state from an ample one. This also implements B1: no bare PASS.
- **As-designed vs. as-made** (next after margins). Process rule packs predict as-made geometry: FDM hole shrinkage, first-layer elephant's foot, molding shrink. Checks run on both. Folklore like "+0.3 mm on every printed hole" becomes explicit, cited, and checkable.
- **Sensitivity is graded geometrically:** how far features move and how much margins change, not by volume % (B4). The walkthrough's prototype plan targets the thinnest margins under the most uncertainty.

## 3. Seeing uncertainty

One visual channel per meaning, used consistently, with **one uncertainty mode on at a time** to avoid overload (PAIN-06):

| Meaning | Channel |
|---|---|
| Margin | Face color, like an FEA plot: green ample → amber thin → red negative |
| Variation | Soft edges or a translucent min/max material envelope ("ghost") |
| Variation (alternative) | **Animated samples** of as-made variants: hypothetical outcome plots (Hullman, Resnick & Adar 2015); off under `prefers-reduced-motion` |
| Guess vs. confirmed (PAIN-12) | Hatched/dashed = model guess, solid = designer-confirmed, in the tree, viewport, and inspector alike |
| A check's value distribution | Small interval bar or histogram with the limit line, in the inspector |

## 4. Seeing scale (all four cues chosen for prototyping)

1. **Depth of field by magnification.** A simulated physical camera whose depth of field narrows as magnification rises, so small features read as small, the way a macro photograph does. Basis: blur patterns change perceived size and distance (Held, Cooper, O'Brien & Banks 2010, *ACM Transactions on Graphics*); tilt-shift "miniature" photography is the same effect. Focus follows the hovered or selected point.
2. **1:1 real-size mode, calibrated automatically.** Browsers don't expose physical screen size: CSS `mm` is a fixed 96 px/in convention, withheld partly to prevent fingerprinting. **The local engine asks the OS instead:**
   - macOS: CoreGraphics `CGDisplayScreenSize`. Verified on the author's MacBook: 301.8 × 196.0 mm, 1800 × 1169 points.
   - Windows and Linux: EDID-backed equivalents.

   The browser reports which screen it's on (CSS-px size, `devicePixelRatio`, and on Chromium the Window Management API's screen details). The engine matches the display and computes **CSS px per mm = screen width in CSS px ÷ physical width in mm**, which holds under macOS scaled resolutions. It recomputes on screen change and on browser zoom. If the OS reports a missing or implausible size (some TVs and cheap panels), it falls back to one-time credit-card calibration, with an optional "check with a coin" confirmation.
3. **Process texture at magnification.** FDM layer lines at their real pitch (e.g. 0.2 mm) and extrusion width (e.g. 0.4 mm) fade in when zoomed close, plus a rule-pack check for features thinner than the nozzle. For molding: surface finish and minimum wall.
4. **Reference objects.** A fingertip (sized from ANSUR II anthropometric data), an M3 screw or a coin appears beside relevant features, such as buttons, holes, and small details. Shown only when relevant, and toggleable.

Also planned: an adaptive scale bar (like a map's) and size-on-hover callouts.

### 4.1 Interaction decisions (2026-11-16, second pass)

| Question | Decision |
|---|---|
| Blur vs. precise inspection | **Two viewport modes.** *Work view* is crisp, with subtle scale cues (scale bar, process texture, size callouts). *Photo view* has physically based depth of field, soft lighting, and a reference object. Toggle between them quickly |
| What drives focus in photo view | **The cursor:** focus follows the point under the pointer |
| 1:1 real-size mode and the camera | **Snaps the camera to the nearest standard view** (orthographic, head-on), where true size is meaningful |
| Scale cues vs. uncertainty modes | Scale cues are a **separate, always-available layer**. Process texture is **shading only, never color**, so it never competes with the margin heatmap |
| Reference objects | **Chosen automatically by context** (fingertip near buttons, screw near holes, hand for the whole part), **ghosted and placed beside the part**, and toggleable |
| Where the controls live | A **View menu in the header strip** |
| Touch and pen devices | Out of scope for now: design for cursor devices |

### 4.2 Assume material and fabrication early

When the designer hasn't specified them, dipm **makes material and fabrication-method assumptions early**, so the render can show the right textures and details, and so checks have something concrete to work from. The default is **PLA on a standard FDM printer** (0.4 mm nozzle, 0.2 mm layers).

- **It's an ordinary assumption** (architecture §4.8): `made_by: model`, unreviewed, and **visibly distinct** from designer-confirmed context (PAIN-12). It is shown in the header strip, e.g. "Assumed: PLA · FDM 0.2 mm · change", one click from changing it.
- **The process pack is the single source** for both checks (rule pack) *and* appearance. The pack that knows "layers are 0.2 mm" also renders 0.2 mm layer lines, so the render can't disagree with the checks.
- **What each process contributes** (shading and normal detail, not color):

| Process | Visual details |
|---|---|
| FDM (default) | Layer lines at real pitch; top-surface extrusion lines (perimeters, infill direction); Z-seam; slight first-layer "elephant's foot"; faint overhang droop and support-contact roughness where the walkthrough's fabricate stage predicts supports |
| SLA / resin | Very fine layers, support nubs on the supported side |
| Injection molding | Parting line; gate vestige; ejector-pin witness marks; draft-aware gloss; subtle sink over thick sections |
| CNC milling | Tool-path marks and scallops on 3D surfaces; inside-corner radii from tool diameter |
| Sheet metal | Bend radii; grain direction; burr side |

- **It also feeds as-made prediction** (§2): the same assumption that draws layer lines also predicts undersized holes and elephant's foot for checks.
- **Material** sets surface appearance (PLA matte; PETG slightly glossy; ABS; aluminum; steel) and, through rule packs, strength and tolerance data. A **material change is high-sensitivity** when strength checks depend on it, so it's surfaced early in review.

## 5. Order of work

1. **Margins on checks** (engine): ranges on quantities, worst-case propagation, and margin reporting, together with B1 (no bare PASS) and B2 (real load and tool-access checks for the bracket).
2. **GUI:** the margin heatmap and guess-vs-confirmed styling (PAIN-12 / B5).
3. **As-made prediction** for FDM.
4. **Scale cues:** 1:1 auto-calibration first (smallest and most concrete), then process texture, reference objects, and depth of field.
5. **Opt-in sampling** for load checks; animated outcome plots.

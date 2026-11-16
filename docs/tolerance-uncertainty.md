# Tolerance, Uncertainty and Scale

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

## 5. Order of work

1. **Margins on checks** (engine): ranges on quantities, worst-case propagation, and margin reporting, together with B1 (no bare PASS) and B2 (real load and tool-access checks for the bracket).
2. **GUI:** the margin heatmap and guess-vs-confirmed styling (PAIN-12 / B5).
3. **As-made prediction** for FDM.
4. **Scale cues:** 1:1 auto-calibration first (smallest and most concrete), then process texture, reference objects, and depth of field.
5. **Opt-in sampling** for load checks; animated outcome plots.

// Iteration 3 pure logic (docs/gui.md §8.4 criterion 10): margins and the heatmap, the scale bar,
// 1:1 math (against the author's MacBook: 301.8 × 196.0 mm at 1800 × 1169 points), the blur cap,
// texture fade thresholds and the reference-object choice.
import { describe, expect, it } from "vitest";
import { checkMargin, faceMargins, heatColor, marginBar, worse } from "../src/margins";
import { calibrate, cssPxPerMm, formatMm, nearestStdView, orthoHeightMm, perspectivePxPerMm, plausiblePxPerMm,
         scaleBarStep, type DisplayJ } from "../src/scale";
import { BLUR_CAP_PX, cappedBlur, cocMm, cocPx, easeFocus, focalLength, magnification } from "../src/photo";
import { FADE_FULL_PX, FADE_START_PX, pitchPx, textureFade, visibleFrom } from "../src/texture";
import { chooseReference, besidePart, CARD_MAX_PART_MM } from "../src/reference";
import { bracket as bracketBuild } from "./fixture";
import type { IntentCheckJ } from "../src/types";

const MACBOOK: DisplayJ = { id: 1, name: "Built-in Retina Display", builtin: true, mm: [301.8, 196.0], px: [1800, 1169],
                            scale: 2, plausible: true };

function check(id: string, state: IntentCheckJ["state"], rel: number | null, faces: number[]): IntentCheckJ {
  return { id, node: "R", statement: "", plain: "", kind: "rule", rung: 1, state, reason: "", governing: "t", terms: [],
           headline: rel === null ? null : { name: "t", plain: "", unit: "mm", sense: ">=", nominal: 1, worst: 1, limit: 1,
                                             limit_worst: 1, margin: rel, margin_worst: rel, margin_rel: rel,
                                             state: state === "not run" ? "ample" : state, inputs: [], method: "", formula: "" },
           assumptions: [], method_assumptions: [], features: [], faces, priority: "must", source: "", reviewed: true };
}

describe("margins and the heatmap", () => {
  it("takes the smallest margin per face; grey where no check applies", () => {
    const b = bracketBuild();
    b.intent_checks = [check("R.c1", "failing", -5.1, [1, 2]), check("R.c2", "ample", 1, [2, 3]),
                       check("R.c4", "thin", 0.05, [3]), check("R.c3", "not run", null, [0, 1, 2, 3])];
    const fm = faceMargins(b);
    expect(fm.map((m) => m.state)).toEqual(["none", "failing", "failing", "thin"]);
    expect(fm[2].checks).toEqual(["R.c1", "R.c2"]);
    expect(fm[3].by).toBe("R.c4");
    expect(fm.map((m) => heatColor(m).token)).toEqual(["none", "fail", "fail", "warn"]);
  });

  it("orders states first, then relative margin; ample shades by size", () => {
    const a = checkMargin(check("a", "ample", 0.8, [])), t = checkMargin(check("t", "thin", 0.05, []));
    expect(worse(a, t).by).toBe("t");
    const a2 = checkMargin(check("a2", "ample", 0.3, []));
    expect(worse(a, a2).by).toBe("a2");
    expect(heatColor(a2).strength).toBeLessThan(heatColor(a).strength);
  });

  it("places margin bar marks around zero and flags negative / off-scale", () => {
    const m = marginBar(-5.08, -11.2);
    expect(m.negative).toBe(true);
    expect(m.offLeft).toBe(true);
    expect(m.worst).toBe(0);
    const p = marginBar(0.5, 0.25);
    expect(p.negative).toBe(false);
    expect(p.nominal).toBeCloseTo(0.75);
    expect(p.worst).toBeCloseTo(0.625);
  });
});

describe("scale bar", () => {
  it("chooses 1 / 2 / 5 × 10ⁿ mm steps no longer than the target", () => {
    expect(scaleBarStep(3, 120)).toMatchObject({ mm: 20, label: "2 cm" });
    expect(scaleBarStep(5.964, 120).mm).toBe(20);
    expect(scaleBarStep(10, 120).mm).toBe(10);
    expect(scaleBarStep(0.5, 120).mm).toBe(200);
    expect(scaleBarStep(150, 120).mm).toBe(0.5);
    for (const ppm of [0.07, 0.3, 1, 2.7, 9, 33, 480]) {
      const s = scaleBarStep(ppm, 120);
      expect(s.px).toBeLessThanOrEqual(120 + 1e-9);
      expect(s.px).toBeGreaterThanOrEqual(120 / 2.5 - 1e-9);
      expect([1, 2, 5]).toContain(Math.round(s.mm / Math.pow(10, Math.floor(Math.log10(s.mm)))));
    }
    expect(scaleBarStep(0, 120).mm).toBe(0);
    expect(formatMm(0.5)).toBe("500 µm");
    expect(formatMm(2000)).toBe("2 m");
  });
});

describe("1:1 real size", () => {
  it("matches the author's MacBook: 1800 pt / 301.8 mm, the 30 mm leg within ±0.5 mm", () => {
    const ppm = cssPxPerMm(MACBOOK, 1800, 2);
    expect(ppm).toBeCloseTo(1800 / 301.8, 6);
    const legPx = 30 * ppm;                       // what the ortho camera draws
    expect(Math.abs(legPx / (1800 / 301.8) - 30)).toBeLessThan(0.5);
    expect(orthoHeightMm(900, ppm)).toBeCloseTo(900 / ppm);
  });

  it("follows browser zoom whether or not screen.width reflects it", () => {
    // Chrome-style: screen width in CSS px shrinks with zoom (125 %: 1440 CSS px)
    expect(cssPxPerMm(MACBOOK, 1440, 2.5)).toBeCloseTo(1440 / 301.8, 6);
    // screen width unchanged, zoom recovered from devicePixelRatio / backing scale
    expect(cssPxPerMm(MACBOOK, 1800, 2.5)).toBeCloseTo(1800 / 301.8 / 1.25, 6);
    expect(cssPxPerMm({ ...MACBOOK, scale: null }, 1800, 2.5)).toBeCloseTo(1800 / 301.8, 6);
  });

  it("rejects implausible sizes and calibrates with an ID-1 card", () => {
    expect(plausiblePxPerMm(5.96)).toBe(true);
    expect(plausiblePxPerMm(0.2)).toBe(false);
    expect(plausiblePxPerMm(Infinity)).toBe(false);
    expect(calibrate(85.6 * 5.964)).toBeCloseTo(5.964, 9);
  });

  it("snaps to the nearest standard view", () => {
    expect(nearestStdView([1.25, 1, 0.85])).toBe("right");
    expect(nearestStdView([0.2, 0.9, 0.3])).toBe("front");
    expect(nearestStdView([0, -0.1, -1])).toBe("bottom");
    expect(nearestStdView([0.1, 0.2, 0.99])).toBe("top");
  });

  it("perspective px/mm at the orbit target", () => {
    expect(perspectivePxPerMm(900, 30, 500)).toBeCloseTo(900 / (2 * 500 * Math.tan(Math.PI / 12)));
  });
});

describe("photo view optics", () => {
  const f = focalLength(30);
  it("derives the focal length from the field of view", () => {
    expect(f).toBeCloseTo(12 / Math.tan(Math.PI / 12), 6);  // ≈ 44.8 mm on a 24 mm-high sensor
  });

  it("thin lens: no blur in focus, more blur with magnification", () => {
    expect(cocMm(f, 4, 500, 500)).toBe(0);
    const far = cocPx(f, 4, 1000, 1200, 900), near = cocPx(f, 4, 500, 600, 900);
    expect(near).toBeGreaterThan(far);              // same relative depth, closer focus: narrower DOF
    expect(magnification(f, 500)).toBeGreaterThan(magnification(f, 1000));
  });

  it("caps the blur", () => {
    const raw = cocPx(f, 4, 150, 2000, 900);
    expect(raw).toBeGreaterThan(BLUR_CAP_PX);
    expect(cappedBlur(raw)).toBe(BLUR_CAP_PX);
    expect(cappedBlur(3.2)).toBe(3.2);
    expect(cappedBlur(-1)).toBe(0);
  });

  it("eases focus towards the target, instantly without motion", () => {
    const x = easeFocus(500, 600, 16);
    expect(x).toBeGreaterThan(500);
    expect(x).toBeLessThan(600);
    expect(easeFocus(500, 600, 16, 0)).toBe(600);
  });
});

describe("process texture", () => {
  it("fades in from about 2 px to 4 px and is gone before aliasing", () => {
    expect(textureFade(1)).toBe(0);
    expect(textureFade(FADE_START_PX)).toBe(0);
    expect(textureFade(3)).toBeGreaterThan(0);
    expect(textureFade(3)).toBeLessThan(1);
    expect(textureFade(FADE_FULL_PX)).toBe(1);
    expect(textureFade(40)).toBe(1);
  });

  it("0.2 mm layers: invisible at fit (≈3 px/mm), visible zoomed close", () => {
    expect(textureFade(pitchPx(0.2, 3, 2))).toBe(0);      // 1.2 device px
    expect(textureFade(pitchPx(0.2, 12, 2))).toBe(1);     // 4.8 device px
    const v = visibleFrom(0.2, 2);
    expect(v.start).toBeCloseTo(5);
    expect(v.full).toBeCloseTo(10);
  });
});

describe("reference objects", () => {
  it("a screw for a screw hole, else the part as a whole", () => {
    const b = bracketBuild();
    b.references = { screws: { "#8": { major: 4.166, head: 8.6, clearance: 4.5, length: 25 } },
                     card: { width: 85.6, height: 53.98, corner_radius: 3.18, thickness: 0.76 },
                     fingertip: { breadth: 16, length: 25, placeholder: true }, hand: { length: 190, breadth: 85, placeholder: true } };
    b.features.find((x) => x.id === "A.P.holes")!.detail = { screw: "#8", centres: [[0, 5, 9], [0, 5, 50]], normal: [0, 1, 0], diameter: 4.5 };
    const big = { min: [-15, 0, 0], max: [15, 160, 150] };
    const r = chooseReference(b, 2, big);
    expect(r).toMatchObject({ kind: "screw", screw: "#8", centre: [0, 5, 50], axis: [0, 1, 0] });
    expect(chooseReference(b, 0, big).kind).toBe("hand");
    expect(chooseReference(b, null, { min: [0, 0, 0], max: [CARD_MAX_PART_MM, 10, 10] }).kind).toBe("card");
    const at = besidePart(big, [0, 5, 50], [1, 0, 0], 4.3);
    expect(at).toEqual([15 + 12 + 4.3, 5, 50]);                 // beside the part, at the hole's depth and height
    const d = besidePart(big, [0, 80, 75], [1, -1, 0], 10);     // a diagonal screen-right clears every corner
    const s2 = Math.SQRT1_2;
    const corners = [[-15, 0], [15, 0], [-15, 160], [15, 160]].map(([x, y]) => (x - 0) * s2 - (y - 80) * s2);
    expect((d[0] - 0) * s2 - (d[1] - 80) * s2).toBeCloseTo(Math.max(...corners) + 12 + 10, 6);
  });
});

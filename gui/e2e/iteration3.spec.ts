// Iteration 3 acceptance (docs/gui.md §8.4): honest status and real scale, through a real browser
// against `dipm serve` on temp copies of the bracket.  /api/display is stubbed through
// DIPM_DISPLAY_STUB (the author's MacBook: 301.8 × 196.0 mm at 1800 × 1169 points).
// DIPM_SHOTS=1 also saves the iter3-*.png screenshots, light and dark (npm run screenshots).
import { expect, test, type Page } from "@playwright/test";
import { existsSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { copyDesign, startServer, type Server } from "./server";

const SHOTS = !!process.env.DIPM_SHOTS;
const OUT = join(process.cwd(), "screenshots");
const MACBOOK = { id: 1, name: "Built-in Retina Display", builtin: true, main: true, mm: [301.8, 196.0], px: [1800, 1169],
                  origin: [0, 0], scale: 2 };
const EXTERNAL = { id: 2, name: "Studio Display", builtin: false, main: false, mm: [596.7, 335.6], px: [2560, 1440],
                   origin: [1800, 0], scale: 2 };
const STUB = { DIPM_DISPLAY_STUB: JSON.stringify([MACBOOK, EXTERNAL]) };

async function ready(page: Page) {
  await page.waitForSelector("[data-testid=build-status]");
  await page.waitForFunction(() => ((window as any).__dipm?.viewer.states().length ?? 0) > 0);
}
const buildOf = (page: Page) => page.evaluate(() => (window as any).__dipm.build.value);
const faceOf = (page: Page, tag: string) => page.evaluate((t) =>
  (window as any).__dipm.build.value.faces.find((f: any) => f.entries[0]?.tag === t)?.id as number, tag);
const visible = (page: Page, face: number) => page.evaluate((f) => (window as any).__dipm.viewer.visiblePoint(f), face);
async function menu(page: Page, testid: string, on = true) {
  await page.getByTestId("view-menu").click();
  const el = page.getByTestId(testid);
  if (on) await el.check(); else await el.uncheck();
  await page.getByTestId("view-menu").click();
}
async function shot(page: Page, name: string) {
  if (!SHOTS) return;
  await page.waitForTimeout(450);
  await page.screenshot({ path: join(OUT, name) });
}
async function theme(page: Page, scheme: "light" | "dark") {
  await page.emulateMedia({ colorScheme: scheme });
  if ((await page.evaluate(() => document.documentElement.dataset.theme)) !== scheme) {
    await page.locator(".theme-toggle").click();           // the app's own toggle: panels and viewport together
  }
  await page.waitForFunction((s) => document.documentElement.dataset.theme === s, scheme);
}
async function both(page: Page, name: string, setup: () => Promise<void>) {
  if (!SHOTS) return;
  for (const scheme of ["light", "dark"] as const) {
    await theme(page, scheme);
    await setup();
    await shot(page, `${name}-${scheme}.png`);
  }
  await theme(page, "light");
}

test.describe("iteration 3: the bracket", () => {
  let srv: Server;
  test.beforeEach(async () => { srv = await startServer(copyDesign("examples/shelf_bracket.py"), STUB); });
  test.afterEach(() => srv.stop());

  test("§8.4-1: no bare PASS; R.c1 failing with a negative margin bar and plain language", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    const st = page.getByTestId("build-status");
    await expect(st).not.toContainText("PASS");
    await expect(page.getByTestId("tier-kernel")).toHaveText("Kernel ✓");
    await expect(st).toContainText("Intent checks 3 of 11 run");
    // honest result: R.c1 fails (architecture §8.4a) and so does R.c4 at worst case (the access
    // cylinder touches the gusset by construction)
    await expect(page.getByTestId("tier-failing")).toHaveText("2 failing");
    const rc1 = page.getByTestId("check-R.c1");
    await expect(rc1.getByTestId("check-state")).toHaveText("failing");
    await expect(rc1).toContainText("Holds 20 kg at the arm tip with a safety factor of 2");
    await expect(rc1.getByTestId("margin-bar").first()).toHaveAttribute("data-sign", "negative");
    await expect(rc1).toContainText("margin -1,016 N");
    // engine terms behind Details
    await expect(page.locator(".checks-table")).toHaveCount(0);
    await page.getByTestId("details-toggle").check();
    await expect(rc1.getByTestId("check-details")).toContainText("arm bending stress × SF");
    await expect(page.locator(".checks-table")).toBeVisible();
    await page.getByTestId("details-toggle").uncheck();
    // clicking the failing tier opens the checks panel at the row
    await page.getByTestId("tier-failing").click();
    await expect(rc1).toBeVisible();
    await both(page, "iter3-status", async () => { await page.getByTestId("tier-failing").click(); });
  });

  test("§8.4-2: model-made items are hatched; reviewing one makes it solid everywhere at once", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    const slot = page.locator('[data-slot="A.3.cable/centered_on.point"] [data-testid=slot-guess]');
    await expect(slot).toHaveAttribute("data-guess", "1");
    await expect(page.locator('[data-node="A.3"][data-testid=node-guesses]')).toHaveText("2?");
    await expect(page.getByTestId("context-chip")).toHaveAttribute("data-guess", "1");   // layer height, nozzle assumed
    // R.a1 appears in the checks panel ("relies on R.a1") hatched
    const ra1 = page.locator('[data-testid="check-R.c1"] [data-pkey="assumption:R.a1"]');
    await expect(ra1).toHaveAttribute("data-guess", "1");
    // accept the A.3 reading: solid in the interpretations panel and in the tree count, at once
    await slot.getByTestId("accept-slot:A.3.cable/centered_on.point").click();
    await expect(slot).toHaveAttribute("data-guess", "0");
    await expect(page.locator('[data-node="A.3"][data-testid=node-guesses]')).toHaveText("1?");
    // accept R.a1 (into the intent file): solid in the checks panel too
    await ra1.getByTestId("accept-assumption:R.a1").click();
    await expect(ra1).toHaveAttribute("data-guess", "0");
    expect(readFileSync(srv.design.replace(/\.py$/, ".intent.yaml"), "utf8"))
      .toMatch(/id: R\.a1,[^\n]*status: accepted/);
  });

  test("§8.4-4: margin heatmap: R.c1 faces red, faces in no check grey, legend shown", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await menu(page, "uncertainty-heatmap");
    await expect(page.getByTestId("heat-legend")).toBeVisible();
    const b = await buildOf(page);
    const rc1 = b.intent_checks.find((c: any) => c.id === "R.c1");
    const involved = new Set<number>(b.intent_checks.filter((c: any) => c.state !== "not run").flatMap((c: any) => c.faces));
    const states: string[] = await page.evaluate(() => (window as any).__dipm.viewer.states());
    for (const f of rc1.faces) expect(states[f]).toBe("heatFail");
    const none = states.map((s, i) => [s, i] as const).filter(([, i]) => !involved.has(i));
    expect(none.length).toBeGreaterThan(0);
    for (const [s] of none) expect(s).toBe("heatNone");
    await both(page, "iter3-heatmap", async () => { await page.mouse.move(700, 860); });
  });

  test("§8.4-5 and -7: photo view focuses under the cursor, blur grows with magnification; a #8 screw ghost", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await menu(page, "view-photo");
    await page.getByRole("button", { name: "front", exact: true }).click();
    await page.getByRole("button", { name: "iso", exact: true }).click();
    const hole = await faceOf(page, "A.P.holes.countersink(0)");   // the lower screw hole (its countersink faces the camera)
    const b = await buildOf(page);
    const lower = b.features.find((f: any) => f.id === "A.P.holes").detail.centres[0];
    const armEnd = [0, 160, 147.5];                              // the arm tip, far from the lower screw
    const hover = async () => {
      const pt = await visible(page, hole);
      expect(pt, "lower screw hole visible").not.toBeNull();
      await page.mouse.move(pt!.x, pt!.y);
      await expect.poll(async () => {
        const s = await page.evaluate(() => (window as any).__dipm.viewer.photoState());
        return Math.abs(s.focus - s.target) / s.target;
      }).toBeLessThan(0.01);
      return page.evaluate((pts) => (window as any).__dipm.viewer.photoState(pts), [lower, armEnd]);
    };
    const far = await hover();
    expect(far.blur[0].raw).toBeLessThan(1.0);                 // the screw hole is sharp
    expect(far.blur[1].raw).toBeGreaterThan(far.blur[0].raw + 1);   // the arm end is blurred
    // a #8 screw, generated from the hole's spec, ghosted beside the part
    await expect.poll(() => page.evaluate(() => (window as any).__dipm.viewer.referenceState()?.kind)).toBe("screw");
    const ref = await page.evaluate(() => (window as any).__dipm.viewer.referenceState());
    expect(ref.label).toBe("#8 screw");
    const part = await page.evaluate(() => (window as any).__dipm.viewer.partBounds());
    const overlaps = [0, 1, 2].every((i) => ref.box[i] < part.max[i] && ref.box[i + 3] > part.min[i]);
    expect(overlaps).toBe(false);                                // beside, never overlapping
    await both(page, "iter3-photo-dof", async () => {
      const pt = await visible(page, hole);
      await page.mouse.move(pt!.x, pt!.y);
      await page.waitForTimeout(500);
    });
    if (SHOTS) {
      await page.evaluate(() => (window as any).__dipm.viewer.dolly(0.6));
      await both(page, "iter3-reference", async () => {
        const pt = await visible(page, hole);
        await page.mouse.move(pt!.x, pt!.y);
        await page.waitForTimeout(500);
      });
      await page.evaluate(() => (window as any).__dipm.viewer.dolly(1 / 0.6));
    }
    // magnification up: the same depth difference blurs more
    await page.evaluate(() => (window as any).__dipm.viewer.dolly(0.5));
    const near = await hover();
    expect(near.magnification).toBeGreaterThan(far.magnification);
    expect(near.blur[1].raw).toBeGreaterThan(far.blur[1].raw);
    expect(near.blur[1].capped).toBeLessThanOrEqual(near.cap);   // blur is capped
  });

  test("§8.4-6: 1:1 on the MacBook: the 30 mm leg measures 30 mm ±0.5; screen change recomputes", async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, screen: { width: 1800, height: 1169 },
                                           deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    await page.goto(srv.url);
    await ready(page);
    await page.getByRole("button", { name: "front", exact: true }).click();
    await menu(page, "toggle-1to1");
    await expect(page.getByTestId("one-to-one")).toHaveText("1:1 on Built-in Retina Display");
    await expect.poll(() => page.evaluate(() => (window as any).__dipm.viewer.oneToOneState().pxPerMm))
      .toBeCloseTo(1800 / 301.8, 6);
    expect((await page.evaluate(() => (window as any).__dipm.viewer.oneToOneState())).view).toBe("front");
    // the bracket leg is 30 mm wide (X from -15 to 15): measured on the glass in mm
    const px = await page.evaluate(() => (window as any).__dipm.viewer.measureCssPx([-15, 0, 75], [15, 0, 75]));
    const mm = px / (1800 / 301.8);
    expect(Math.abs(mm - 30)).toBeLessThan(0.5);
    await both(page, "iter3-1to1", async () => { await page.mouse.move(700, 860); });
    // moving the window to the external display (simulated screen change) recomputes
    await page.evaluate(() => (window as any).__dipm.measure({ width: 2560, height: 1440, left: 1800, top: 0 }));
    await expect(page.getByTestId("one-to-one")).toHaveText("1:1 on Studio Display");
    await expect.poll(() => page.evaluate(() => (window as any).__dipm.viewer.oneToOneState().pxPerMm))
      .toBeCloseTo(2560 / 596.7, 6);
    const mm2 = (await page.evaluate(() => (window as any).__dipm.viewer.measureCssPx([-15, 0, 75], [15, 0, 75]))) / (2560 / 596.7);
    expect(Math.abs(mm2 - 30)).toBeLessThan(0.5);
    await ctx.close();
  });

  test("§8.4-9a: the inferred orientation is recorded, hatched, drives the layer lines, and accepting writes it", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    const rec = JSON.parse(readFileSync(srv.design.replace(/\.py$/, ".resolution.json"), "utf8"));
    expect(rec.orientation.label).toBe("Print with the shelf face down");
    expect(rec.orientation.runner_up.down_face).toBe("wall face");
    expect(rec.orientation.rationale).toMatch(/0 mm² overhang/);
    const b = await buildOf(page);
    expect(b.appearance.build_direction).toEqual(b.orientation.up);
    await page.getByTestId("context-chip").click();
    const o = page.getByTestId("orientation");
    await expect(o).toHaveClass(/guess/);
    await expect(o).toContainText("runner-up wall face down");
    const intentBefore = readFileSync(srv.design.replace(/\.py$/, ".intent.yaml"), "utf8");
    expect(intentBefore).not.toContain("print_orientation");    // nothing wrote the intent file
    await page.getByTestId("context-picker").getByTestId("accept-orientation").click();
    await expect(o).toHaveClass(/confirmed/);
    const intentAfter = readFileSync(srv.design.replace(/\.py$/, ".intent.yaml"), "utf8");
    expect(intentAfter).toMatch(/about: print_orientation, value: ['"]?0,0,-1['"]?/);
    expect(intentAfter).toMatch(/made_by: model[^\n]*status: accepted/);
    // later inference never replaces an accepted orientation
    const r = await page.evaluate(() => fetch("/api/orientation", { method: "POST", headers: { "content-type": "application/json" },
                                                                    body: JSON.stringify({ action: "infer" }) }).then((x) => x.json()));
    expect(r.note).toMatch(/never replaces/);
    expect((await buildOf(page)).orientation.reviewed).toBe(true);
  });

  test("§8.4-8: a failing proposal offers Accept anyway…, needs a reason, then shows reviewed with failing checks", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    // a proposal addressing R (whose R.c1 and R.c4 fail): a harmless DSL comment change
    const py = readFileSync(srv.design, "utf8");
    const res = await page.evaluate(async ({ py }) => {
      const src = await fetch("/api/intent").then((r) => r.json());
      const enc = new TextEncoder().encode(py);
      const h = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", enc))).map((x) => x.toString(16).padStart(2, "0")).join("");
      const r = await fetch("/api/proposals", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ summary: "R: document the load case", rationale: "comment only",
                               files: { "shelf_bracket.py": py.replace("# --- R parameters", "# --- R parameters (20 kg at the tip)") },
                               base_hashes: { "shelf_bracket.py": h, "shelf_bracket.intent.yaml": src.hash },
                               addresses_nodes: ["R"] }) });
      return r.json();
    }, { py });
    expect(res.id).toBe("p1");
    const item = page.locator('[data-proposal="p1"]');
    await expect(item.getByTestId("proposal-status")).toHaveText("ready for review", { timeout: 30_000 });
    await item.click();
    await expect(page.getByTestId("proposal-failing")).toContainText("R.c1");
    await expect(page.getByTestId("accept-proposal")).toHaveCount(0);
    await page.getByTestId("accept-anyway").click();
    await expect(page.getByTestId("confirm-accept-anyway")).toBeDisabled();
    await page.getByTestId("override-reason").fill("Prototype print to test the anchors; redesign follows.");
    await page.getByTestId("confirm-accept-anyway").click();
    await expect(item.getByTestId("proposal-status")).toHaveText("accepted");
    const review = JSON.parse(readFileSync(srv.design.replace(/\.py$/, ".review.json"), "utf8"));
    expect(review.overrides.R.reason).toMatch(/Prototype/);
    expect(review.overrides.R.failing).toContain("R.c1");
    await page.locator('[data-row="node:R"] .row-id').click();
    await expect(page.getByTestId("reviewed-failing")).toHaveText("reviewed with failing checks");
  });

  test("#53/#55/#57: Queue for Claude shows requests waiting with a copyable prompt", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await page.evaluate(() => fetch("/api/requests", { method: "POST", headers: { "content-type": "application/json" },
                                                       body: JSON.stringify({ node: "A.3", note: "move it" }) }));
    await page.reload();
    await ready(page);
    await expect(page.getByTestId("requests-waiting")).toHaveText("1 request waiting");
    await page.getByTestId("requests-waiting").click();
    await expect(page.getByTestId("claude-prompt")).toHaveValue(/get_requests[\s\S]*propose_patch/);
  });
});

test("§8.4-3: no stated context: 'Assumed: PLA · FDM 0.2 mm', hatched; 0.2 mm layer lines only when zoomed close", async ({ page }) => {
  const design = copyDesign("examples/shelf_bracket.py");
  const ip = design.replace(/\.py$/, ".intent.yaml");
  writeFileSync(ip, readFileSync(ip, "utf8").replace(/^context: .*\n/m, ""));
  const srv = await startServer(design, STUB);
  try {
    await page.goto(srv.url);
    await ready(page);
    const chip = page.getByTestId("context-chip");
    await expect(chip).toContainText("Assumed: PLA · FDM 0.2 mm");
    await expect(chip).toHaveAttribute("data-guess", "1");
    const tex = () => page.evaluate(() => (window as any).__dipm.viewer.textureState());
    await expect.poll(async () => (await tex()).on).toBe(true);
    let t = await tex();
    expect(t.pitch).toBeCloseTo(0.2, 6);
    expect(t.fade).toBe(0);                                  // zoomed out: no lines
    // close up on the mount face, between the screw holes (vertical in print: layer lines across it)
    await page.evaluate(() => (window as any).__dipm.viewer.lookAt([8, 5, 22], 55));
    t = await tex();
    expect(t.pitchPx).toBeGreaterThan(4);
    expect(t.fade).toBe(1);                                  // close: 0.2 mm lines drawn
    await both(page, "iter3-texture", async () => { await page.mouse.move(700, 860); });
    await page.getByRole("button", { name: "fit", exact: true }).click();
    expect((await tex()).fade, JSON.stringify(await tex())).toBe(0);
    // confirming the context writes it into the intent file; the chip turns solid
    await chip.click();
    await page.getByTestId("context-confirm").click();
    await expect(chip).toHaveAttribute("data-guess", "1");   // still hatched: the orientation is a guess
    await expect(chip).not.toContainText("Assumed:");
    expect(readFileSync(ip, "utf8")).toMatch(/context: \{process: fdm_printing, material: PLA, layer_height: 0\.2 mm, nozzle: 0\.4 mm\}/);
  } finally {
    srv.stop();
  }
});

test("§8.4-6 fallback: a reported size of 0 shows the card calibration", async ({ page }) => {
  const srv = await startServer(copyDesign("examples/shelf_bracket.py"),
                                { DIPM_DISPLAY_STUB: JSON.stringify([{ ...MACBOOK, mm: [0, 0] }]) });
  try {
    await page.goto(srv.url);
    await ready(page);
    await menu(page, "toggle-1to1");
    await expect(page.getByTestId("calibration")).toBeVisible();
    await expect(page.getByTestId("one-to-one")).toHaveCount(0);
    const card = page.getByTestId("cal-card");
    const w = await card.evaluate((e) => e.getBoundingClientRect().width);
    await page.getByTestId("cal-save").click();
    await expect(page.getByTestId("one-to-one")).toContainText("(calibrated)");
    await expect.poll(() => page.evaluate(() => (window as any).__dipm.viewer.oneToOneState().pxPerMm))
      .toBeCloseTo(w / 85.6, 3);
  } finally {
    srv.stop();
  }
});

test("§8.4-9: a design with no review record opens with the first-open prompt", async ({ page }) => {
  const design = copyDesign("examples/shelf_bracket.py");
  const rv = design.replace(/\.py$/, ".review.json");
  unlinkSync(rv);
  const srv = await startServer(design, STUB);
  try {
    await page.goto(srv.url);
    await ready(page);
    await expect(page.getByTestId("first-open")).toBeVisible();
    expect(existsSync(rv)).toBe(false);                       // nothing was baselined automatically
    await page.getByTestId("review-one-by-one").click();
    await expect(page.getByTestId("first-open")).toHaveCount(0);
    expect(JSON.parse(readFileSync(rv, "utf8")).reviewed).toEqual({});
    await page.reload();
    await ready(page);
    await expect(page.getByTestId("first-open")).toHaveCount(0);
  } finally {
    srv.stop();
  }
});

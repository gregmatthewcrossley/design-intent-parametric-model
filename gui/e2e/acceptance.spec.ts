// Acceptance criteria of docs/gui.md §6, driven through a real browser against `dipm serve`.
import { expect, test, type Page } from "@playwright/test";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { copyDesign, startServer, type Server } from "./server";

type Dipm = {
  viewer: {
    visiblePoint(f: number): { x: number; y: number } | null;
    states(): string[];
    hasGhost(): boolean;
    cameraState(): number[];
  };
  build: { value: any };
};

async function ready(page: Page) {
  await page.waitForSelector("[data-testid=build-status]");
  await page.waitForFunction(() => {
    const d = (window as any).__dipm as Dipm | undefined;
    return !!d && d.viewer.states().length > 0;
  });
}

const buildOf = (page: Page) => page.evaluate(() => ((window as any).__dipm as Dipm).build.value);

async function clickFace(page: Page, tag: string) {
  const pt = await page.evaluate((t) => {
    const d = (window as any).__dipm as Dipm;
    const f = d.build.value.faces.find((x: any) => x.entries[0]?.tag === t);
    return f ? d.viewer.visiblePoint(f.id) : null;
  }, tag);
  expect(pt, `face ${tag} visible`).not.toBeNull();
  await page.mouse.click(pt!.x, pt!.y);
}

test.describe("shelf bracket", () => {
  let srv: Server;
  // a copy: since iteration 2 the GUI can write the intent file, and these tests must never touch examples/
  test.beforeAll(async () => { srv = await startServer(copyDesign("examples/shelf_bracket.py")); });
  test.afterAll(() => srv.stop());

  test("1: the tree shows R, A, A.P, A.P.1, A.P.2, A.3, B, B.1, C with green dots", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    const ids = await page.locator(".row-node .row-id").allInnerTexts();
    expect(ids.map((s) => s.trim())).toEqual(["R", "A", "A.P", "A.P.1", "A.P.2", "A.3", "B", "B.1", "C"]);
    expect(await page.locator(".row-node .row-id .dot-ok").count()).toBe(9);
    await expect(page.getByTestId("build-status")).toHaveText("PASS");
  });

  test("2: shelf_depth 200 -> 300 rebuilds; holes re-spread; cable stays mid-plate", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    const before = await buildOf(page);
    const field = page.getByLabel("shelf_depth value");
    await field.fill("300");
    await field.press("Enter");
    await page.waitForFunction((id) => ((window as any).__dipm as Dipm).build.value.mesh_id !== id, before.mesh_id);
    const after = await buildOf(page);
    const det = (b: any, id: string) => b.features.find((f: any) => f.id === id).detail;
    expect(after.params.shelf_depth).toBe(300);
    expect(det(after, "A.P.holes").centres).not.toEqual(det(before, "A.P.holes").centres);
    expect(det(after, "A.3.cable").centres[0][2]).toBeCloseTo((0.75 * 300 - 5 - 0.4 * 300) / 2, 4);
    await field.fill("200");
    await field.press("Enter");
    await page.waitForFunction(() => ((window as any).__dipm as Dipm).build.value.params.shelf_depth === 200);
  });

  test("3: clicking a countersink face shows its genealogy and highlights A.P.2", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await clickFace(page, "A.P.holes.countersink(1)");
    await expect(page.getByTestId("why-summary").first())
      .toHaveText("A.P.holes.countersink(1) · hole@A.P.2 · pattern@A.P (wall screw pattern)");
    await expect(page.locator('[data-row="node:A.P.2"]')).toHaveClass(/primary/);
  });

  test("4: clicking A.P lights both screw holes' faces and nothing else", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await page.locator('[data-row="node:A.P"]').click();
    await page.mouse.move(5, 5); // leave the panel: only the pinned selection remains
    const r = await page.evaluate(() => {
      const d = (window as any).__dipm as Dipm;
      const st = d.viewer.states();
      return d.build.value.faces.filter((_: any, i: number) => st[i] === "lit").map((f: any) => f.entries[0].tag).sort();
    });
    expect(r).toEqual(["A.P.holes.countersink(0)", "A.P.holes.countersink(1)", "A.P.holes.wall(0)", "A.P.holes.wall(1)"]);
  });

  test("5: four slots, zero questions, zero notices (DECISIONS #32)", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await expect(page.locator(".slot")).toHaveCount(4);
    await expect(page.getByTestId("question")).toHaveCount(0);
    await expect(page.getByTestId("notice")).toHaveCount(0);
  });

  test("9: connections view: intents, uses, parameters; shelf_depth lights every feature it drives", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await page.getByTestId("expand").click();
    await expect(page.getByTestId("connections")).toBeVisible();
    await expect(page.locator("[data-c-feat]")).toHaveCount(6);
    const b = await buildOf(page);
    for (const f of b.features) expect(f.serves.length).toBeGreaterThan(0);
    const uses = (id: string) => b.features.find((f: any) => f.id === id).uses;
    expect(uses("A.P.holes")).toContain("C.gusset");
    expect(uses("A.3.cable")).toContain("C.gusset");
    const p = (id: string) => b.features.find((f: any) => f.id === id).params;
    expect(p("A.P.holes")).toContain("screw");
    expect(p("B.1.screw")).toContain("screw");
    await page.locator('[data-c-param="shelf_depth"]').click();
    await page.mouse.move(5, 890);
    const lit = await page.locator("[data-c-feat].lit, [data-c-feat].indirect").count();
    expect(lit).toBe(6);
    await expect(page.locator('[data-c-feat="R.body"]')).toHaveClass(/lit/);
    await expect(page.locator('[data-c-feat="A.3.cable"]')).toHaveClass(/indirect/);
  });

  test("WHY ⇄ HOW: build order, animated transition, instant under reduced motion", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await page.getByTestId("view-how").click();
    const anims = await page.evaluate(() => document.querySelectorAll(".rows [data-flip]")[0]
      ? Array.from(document.querySelectorAll(".rows [data-flip]")).filter((e) => e.getAnimations().length > 0).length : -1);
    expect(anims).toBeGreaterThan(0);
    const ids = await page.locator(".row-feature .row-id").allInnerTexts();
    expect(ids.map((s) => s.trim())).toEqual(["R.body", "C.gusset", "A.P.holes", "A.3.cable", "B.1.screw", "R.fillet"]);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.getByTestId("view-why").click();
    const n = await page.evaluate(() => Array.from(document.querySelectorAll(".rows [data-flip]"))
      .filter((e) => e.getAnimations().length > 0).length);
    expect(n).toBe(0);
  });

  test("below 1024 px the panels become tabs", async ({ page }) => {
    await page.setViewportSize({ width: 900, height: 800 });
    await page.goto(srv.url);
    await ready(page);
    await expect(page.locator(".tabs")).toBeVisible();
    await page.getByRole("tab", { name: "Checks" }).click();
    await expect(page.locator(".checks-table")).toBeVisible();
  });
});

test("6: a question gets answer buttons; answering records the preference and rebuilds", async ({ page }) => {
  const design = copyDesign("tests/fixtures/question_channel.py");
  const srv = await startServer(design);
  try {
    await page.goto(srv.url);
    await ready(page);
    await expect(page.getByTestId("question")).toHaveCount(1);
    const before = (await buildOf(page)).mesh_id;
    await page.locator('[data-testid=question] button[data-reading="through_all"]').click();
    await expect(page.getByTestId("question")).toHaveCount(0);
    const after = await buildOf(page);
    expect(after.mesh_id).not.toBe(before);
    expect(after.signature.VEFRSH[5]).toBe(2);
    const prefs = design.replace(/\.py$/, ".prefs.json");
    expect(existsSync(prefs)).toBe(true);
    expect(JSON.parse(readFileSync(prefs, "utf8")).answers).toEqual({
      "hole.extent@channel_question:D": { reading: "through_all" } });
  } finally {
    srv.stop();
  }
});

test("7: a failing parameter shows in checks, tree and tinted faces; the last good model stays", async ({ page }) => {
  const srv = await startServer(join(process.cwd(), "../tests/fixtures/invariant_fail.py"));
  try {
    await page.goto(srv.url);
    await ready(page);
    const field = page.getByLabel("hole_u value");
    await field.fill("0.75");
    await field.press("Enter");
    await expect(page.getByTestId("build-status")).toHaveText("FAIL · 1");
    await expect(page.locator('[data-check-row="H.hole"] td.fail')).toHaveCount(1);
    await expect(page.getByTestId("check-error")).toContainText("delta_H");
    await expect(page.locator('[data-row="node:H"] .row-id .dot-fail')).toHaveCount(1);
    await page.waitForFunction(() => ((window as any).__dipm as Dipm).viewer.states().includes("fail"));
    await page.waitForFunction(() => ((window as any).__dipm as Dipm).viewer.hasGhost());
    await expect(page.getByTestId("fail-banner")).toBeVisible();
  } finally {
    srv.stop();
  }
});

test("8: saving the design file rebuilds within ~1 s, keeping camera and selection", async ({ page }) => {
  const design = copyDesign("tests/fixtures/invariant_fail.py");
  const srv = await startServer(design);
  try {
    await page.goto(srv.url);
    await ready(page);
    await page.locator("button", { hasText: "top" }).click();
    await page.locator('[data-row="node:S"]').click();
    const cam = await page.evaluate(() => ((window as any).__dipm as Dipm).viewer.cameraState());
    const gen0 = (await buildOf(page)).generation;
    const t0 = Date.now();
    writeFileSync(design, readFileSync(design, "utf8").replace('"stiffening rib under the plate"', '"rib under the plate"'));
    await page.waitForFunction((g) => ((window as any).__dipm as Dipm).build.value.generation > g, gen0, { timeout: 5000 });
    const dt = Date.now() - t0;
    expect(dt).toBeLessThan(1500);
    await expect(page.locator('[data-row="node:S"] .row-sub')).toHaveText("rib under the plate");
    await expect(page.locator('[data-row="node:S"]')).toHaveClass(/selected/);
    const cam2 = await page.evaluate(() => ((window as any).__dipm as Dipm).viewer.cameraState());
    expect(cam2).toEqual(cam);
    console.log(`file save -> rebuilt in browser: ${dt} ms`);
  } finally {
    srv.stop();
  }
});

test("9b: an untagged feature is flagged 'no intent'", async ({ page }) => {
  const srv = await startServer(join(process.cwd(), "../tests/fixtures/diagnostics.py"));
  try {
    await page.goto(srv.url);
    await ready(page);
    await expect(page.getByTestId("diagnostics")).toContainText("X.untagged no intent");
    await page.getByTestId("expand").click();
    await expect(page.locator('[data-c-feat="X.untagged"] .flag-text')).toHaveText("no intent");
    await expect(page.locator('[data-c-node="B"] .flag-text')).toHaveText("no feature");
  } finally {
    srv.stop();
  }
});

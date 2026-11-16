// Saves review screenshots to gui/screenshots/ (light and dark).  `npm run screenshots`.
import { test, type Page } from "@playwright/test";
import { join } from "node:path";
import { startServer, type Server } from "./server";

const OUT = join(process.cwd(), "screenshots");

async function ready(page: Page) {
  await page.waitForSelector("[data-testid=build-status]");
  await page.waitForFunction(() => ((window as any).__dipm?.viewer.states().length ?? 0) > 0);
  await page.waitForTimeout(500);
}

async function clickFace(page: Page, tag: string) {
  const pt = await page.evaluate((t) => {
    const d = (window as any).__dipm;
    const f = d.build.value.faces.find((x: any) => x.entries[0]?.tag === t);
    return d.viewer.visiblePoint(f.id);
  }, tag);
  await page.mouse.click(pt.x, pt.y);
  await page.mouse.move(1000, 760); // empty background: the pinned selection, not a hover, is shown
}

test.describe("screenshots", () => {
  let srv: Server;
  test.beforeAll(async () => { srv = await startServer(join(process.cwd(), "../examples/shelf_bracket.py")); });
  test.afterAll(() => srv.stop());

  test("bracket, WHY, countersink pinned (light)", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto(srv.url);
    await ready(page);
    await clickFace(page, "A.P.holes.countersink(1)");
    await page.waitForTimeout(300);
    await page.screenshot({ path: join(OUT, "bracket-why-light.png") });
  });

  test("bracket, HOW, screw parameter selected (dark)", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto(srv.url);
    await ready(page);
    await page.getByTestId("view-how").click();
    await page.locator('[data-param="screw"] .param-name').click();
    await page.mouse.move(700, 700);
    await page.waitForTimeout(500);
    await page.screenshot({ path: join(OUT, "bracket-how-dark.png") });
  });

  test("bracket, connections view, shelf_depth selected (light)", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto(srv.url);
    await ready(page);
    await page.getByTestId("expand").click();
    await page.locator('[data-c-param="shelf_depth"]').click();
    await page.mouse.move(700, 700);
    await page.waitForTimeout(300);
    await page.screenshot({ path: join(OUT, "bracket-connections-light.png") });
  });
});

test("failing build with the last good model (dark)", async ({ page }) => {
  const srv = await startServer(join(process.cwd(), "../tests/fixtures/invariant_fail.py"));
  try {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto(srv.url);
    await ready(page);
    const field = page.getByLabel("hole_u value");
    await field.fill("0.75");
    await field.press("Enter");
    await page.waitForFunction(() => (window as any).__dipm.viewer.hasGhost());
    await page.waitForTimeout(400);
    await page.screenshot({ path: join(OUT, "failure-dark.png") });
  } finally {
    srv.stop();
  }
});

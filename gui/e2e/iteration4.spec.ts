// Iteration 4 (docs/purpose-loop.md §4 GUI): the impact view, a purpose proposal reviewed as a
// tree diff, the alternatives compare view and component ghosts, against `dipm serve` on temp
// copies of the rod holder's seed (tests/fixtures/rod_holder/, frozen
// when the author accepted p5 into examples/rod_holder.*).  The model is simulated by e2e/simulate_loop.py (fixed texts
// from tests/fixtures/rod_loop.py).  DIPM_SHOTS=1 also saves iter4-*.png, light and dark.
import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { join } from "node:path";
import { copyDesign, PY, ROOT, startServer, type Server } from "./server";

const SHOTS = !!process.env.DIPM_SHOTS;
const OUT = join(process.cwd(), "screenshots");
const SIM = join(ROOT, "gui/e2e/simulate_loop.py");

function simulateLoop(design: string, n = 3): { purpose: string; group: string; alternatives: { id: string; label: string }[] } {
  const out = execFileSync(PY, [SIM, design, String(n)], { cwd: ROOT, encoding: "utf8", timeout: 180_000,
                                                           env: { ...process.env, PYTHONWARNINGS: "ignore" } });
  return JSON.parse(out.trim().split("\n").pop()!);
}

async function ready(page: Page) {
  await page.waitForSelector("[data-testid=build-status]");
  await page.waitForFunction(() => ((window as any).__dipm?.viewer.states().length ?? 0) > 0);
}
async function theme(page: Page, scheme: "light" | "dark") {
  await page.emulateMedia({ colorScheme: scheme });
  if ((await page.evaluate(() => document.documentElement.dataset.theme)) !== scheme) await page.locator(".theme-toggle").click();
}
async function shot(page: Page, name: string) {
  if (!SHOTS) return;
  await page.waitForTimeout(500);
  await page.screenshot({ path: join(OUT, name) });
}
async function openProposal(page: Page, id: string) {
  const item = page.locator(`[data-proposal="${id}"]`).first();
  await item.scrollIntoViewIfNeeded();
  await item.click();
  await expect(page.getByTestId("proposal-detail")).toBeVisible();
}

test.describe("iteration 4: purpose -> geometry loop", () => {
  let srv: Server;
  let sim: ReturnType<typeof simulateLoop>;
  test.beforeAll(async () => {
    test.setTimeout(240_000);
    const design = copyDesign("tests/fixtures/rod_holder/rod_holder.py");
    sim = simulateLoop(design);
    srv = await startServer(design);
  });
  test.afterAll(() => srv?.stop());

  for (const scheme of ["light", "dark"] as const) {
    test(`impact view marks invalidated nodes (${scheme})`, async ({ page }) => {
      await page.goto(srv.url);
      await theme(page, scheme);
      await ready(page);
      await expect(page.getByTestId("impact-chip")).toContainText("invalidated");
      await page.getByTestId("impact-chip").click();
      const panel = page.getByTestId("impact-panel");
      await expect(panel).toBeVisible();
      await expect(page.getByTestId("impact-terms")).toContainText("shelf");
      // criterion 1: B, B.1 and R.a1 invalidated; A and R.c2 survive
      for (const id of ["B", "B.1", "R.a1"]) {
        await expect(panel.locator(`[data-impact="${id}"]`)).toHaveAttribute("data-impact-class", "invalidated");
      }
      await expect(panel.locator('[data-impact="R"]')).toHaveAttribute("data-impact-class", "changed");
      await expect(panel.locator('[data-impact="A"]')).toHaveCount(0);
      await expect(panel.locator('[data-impact="R.c2"]')).toHaveCount(0);
      // marks in the WHY tree
      await page.getByTestId("view-why").click();
      await expect(page.locator('[data-row="node:B"] [data-testid=impact-mark]')).toHaveAttribute("data-impact-class", "invalidated");
      await expect(page.locator('[data-row="node:R"] [data-testid=impact-mark]')).toHaveAttribute("data-impact-class", "changed");
      await expect(page.locator('[data-row="node:A"] [data-testid=impact-mark]')).toHaveCount(0);
      await shot(page, `iter4-impact-${scheme}.png`);
    });

    test(`purpose proposal as a tree diff (${scheme})`, async ({ page }) => {
      await page.goto(srv.url);
      await theme(page, scheme);
      await ready(page);
      await openProposal(page, sim.purpose);
      const diff = page.getByTestId("purpose-diff");
      await expect(diff).toBeVisible();
      await expect(diff.locator('[data-pd="R"]')).toHaveAttribute("data-pd-status", "changed");
      await expect(diff.locator('[data-pd="B"]')).toHaveAttribute("data-pd-status", "changed");
      await expect(diff.locator('[data-pd="B.1"]')).toHaveAttribute("data-pd-status", "removed");
      // bindings read in plain language, hatched (model-made, unreviewed)
      const holds = diff.locator('[data-pd-check="B.c1"]');
      await expect(holds).toHaveAttribute("data-form", "holds_cylinder");
      await expect(holds.locator(".pd-binding")).toContainText("Holds rod");
      await expect(holds.locator(".pd-binding")).toHaveAttribute("data-guess", "1");
      // criterion 2: the unbindable check shows as descriptive, not run
      await expect(diff.locator('[data-pd-check="B.c3"] [data-testid=pd-check-state]')).toHaveText("descriptive, not run");
      await expect(page.getByTestId("purpose-components")).toContainText("rod");
      await expect(page.getByTestId("accept-purpose")).toBeVisible();
      await expect(page.getByTestId("try-purpose")).toBeVisible();
      await diff.locator('[data-pd="B"]').scrollIntoViewIfNeeded();
      await shot(page, `iter4-purpose-diff-${scheme}.png`);
    });

    test(`alternatives compare view (${scheme})`, async ({ page }) => {
      await page.goto(srv.url);
      await theme(page, scheme);
      await ready(page);
      await openProposal(page, sim.alternatives[0].id);
      await page.getByTestId("open-alternatives").click();
      const view = page.getByTestId("alternatives");
      await expect(view).toBeVisible();
      await expect(view.locator(".alt-col")).toHaveCount(3);
      await expect(view.locator("img[data-loaded]")).toHaveCount(3, { timeout: 20_000 });
      // honest status per alternative: C fails retention, not-run checks stay not run
      const C = view.locator('[data-alt="C"]');
      await expect(C.locator('[data-alt-check="B.c2"]')).toHaveAttribute("data-state", "failing");
      await expect(C.locator('[data-alt-check="B.c3"]')).toHaveAttribute("data-state", "not run");
      await expect(view.locator('[data-alt="B"] [data-alt-check="B.c4"]')).toHaveAttribute("data-state", /ample|thin/);
      await expect(C.getByTestId("accept-anyway")).toBeVisible();
      await expect(view.locator('[data-alt="A"] [data-testid=alt-attempts] summary')).toContainText("2 build(s) of 6");
      await expect(view.locator('[data-alt="A"] [data-testid=margin-bar]').first()).toBeVisible();
      await shot(page, `iter4-alternatives-${scheme}.png`);
    });

    test(`component envelopes ghosted in the viewport (${scheme})`, async ({ page }) => {
      await page.goto(srv.url);
      await theme(page, scheme);
      await ready(page);
      await openProposal(page, sim.alternatives[1].id);
      await page.getByTestId("open-alternatives").click();
      await page.locator('[data-alt="B"] [data-testid=alt-thumb]').click();     // shows B in the viewport
      await expect(page.getByTestId("compare-banner")).toBeVisible();
      await page.waitForFunction(() => (window as any).__dipm.viewer.componentState().length === 2);
      const st = await page.evaluate(() => (window as any).__dipm.viewer.componentState());
      expect(st.map((g: any) => [g.component, g.shape, g.dashed]).sort()).toEqual([["reel", "box", true], ["rod", "cylinder", true]]);
      const rod = st.find((g: any) => g.component === "rod");
      expect(rod.box[4] - rod.box[1]).toBeGreaterThan(9.9);      // Ø10 nominal rod across Y
      await expect(page.getByTestId("ghost-legend")).toContainText("rod");
      await page.evaluate(() => (window as any).__dipm.viewer.setView("iso"));
      await shot(page, `iter4-ghosts-${scheme}.png`);
      // the View menu toggle hides them
      await page.getByTestId("view-menu").click();
      await page.getByTestId("toggle-ghosts").uncheck();
      await page.getByTestId("view-menu").click();
      await page.waitForFunction(() => (window as any).__dipm.viewer.componentState().length === 0);
      await page.getByTestId("view-menu").click();
      await page.getByTestId("toggle-ghosts").check();
    });
  }

  test("accept to try keeps the intent file unwritten", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    const before = await (await fetch(srv.url + "api/intent")).json();
    await openProposal(page, sim.purpose);
    await page.getByTestId("try-purpose").click();
    await expect(page.locator(`[data-proposal="${sim.purpose}"] [data-testid=proposal-status]`)).toHaveText("accepted to try");
    const after = await (await fetch(srv.url + "api/intent")).json();
    expect(after.hash).toBe(before.hash);
  });
});

test("accepting an alternative applies its purposes and closes its siblings", async ({ page }) => {
  test.setTimeout(240_000);
  const design = copyDesign("tests/fixtures/rod_holder/rod_holder.py");
  const sim = simulateLoop(design, 2);
  const srv = await startServer(design);
  try {
    await page.goto(srv.url);
    await ready(page);
    await openProposal(page, sim.alternatives[1].id);       // B: no failing checks
    await page.getByTestId("open-alternatives").click();
    await page.locator('[data-alt="B"] [data-testid=accept-alternative]').click();
    await expect(page.getByTestId("alternatives")).toHaveCount(0);
    const r = await (await fetch(srv.url + "api/proposals")).json();
    const st = Object.fromEntries(r.proposals.map((p: any) => [p.id, p.status]));
    expect(st[sim.alternatives[1].id]).toBe("accepted");
    expect(st[sim.alternatives[0].id]).toBe("rejected");
    expect(st[sim.purpose]).toBe("accepted");
    // the new purposes are in the file and the live build ghosts the components
    await page.waitForFunction(() => (window as any).__dipm.viewer.componentState().length === 2, null, { timeout: 30_000 });
  } finally {
    srv.stop();
  }
});

test("a designer edit of a purpose proposal becomes a revised, designer-made proposal", async ({ page }) => {
  test.setTimeout(240_000);
  const design = copyDesign("tests/fixtures/rod_holder/rod_holder.py");
  const sim = simulateLoop(design, 2);
  const srv = await startServer(design);
  try {
    await page.goto(srv.url);
    await ready(page);
    await openProposal(page, sim.purpose);
    await page.locator('[data-pd="B"] [data-testid=pd-edit]').click();
    await page.getByTestId("pd-edit-input").fill("Cradle: holds the rod blank gently");
    await page.getByTestId("pd-edit-save").click();
    await expect(page.locator(`[data-proposal="${sim.purpose}"] [data-testid=proposal-status]`)).toHaveText("rejected");
    const r = await (await fetch(srv.url + "api/proposals")).json();
    const q = r.proposals.find((p: any) => p.revises === sim.purpose);
    expect(q.source).toBe("designer");
    expect(q.kind).toBe("purpose");
  } finally {
    srv.stop();
  }
});

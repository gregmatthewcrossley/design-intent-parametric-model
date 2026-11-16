// Iteration 2 acceptance (docs/gui.md §7.2 criteria 1–6 and §7.3), through a real browser
// against `dipm serve`, with Claude simulated over MCP stdio (e2e/simulate_claude.py).
// Every test works on a temp copy of the bracket's design set.  DIPM_SHOTS=1 also saves the
// review screenshots (npm run screenshots).
import { expect, test, type Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { copyDesign, PY, ROOT, startServer, type Server } from "./server";

const SHOTS = !!process.env.DIPM_SHOTS;
const OUT = join(process.cwd(), "screenshots");
const SIM = join(ROOT, "gui/e2e/simulate_claude.py");
const NEW_A3 = "Cable pass-through, offset 10 mm above the lower screw";

async function ready(page: Page) {
  await page.waitForSelector("[data-testid=build-status]");
  await page.waitForFunction(() => ((window as any).__dipm?.viewer.states().length ?? 0) > 0);
}

const buildOf = (page: Page) => page.evaluate(() => (window as any).__dipm.build.value);
const intentFile = (srv: Server) => srv.design.replace(/\.py$/, ".intent.yaml");
const row = (page: Page, id: string) => page.locator(`[data-row="node:${id}"]`);
const rowId = (page: Page, id: string) => row(page, id).locator(".row-id");   // click the label, not the action buttons

/** Pin a tree node (clicking a pinned node unpins it, so only click when needed). */
async function selectNode(page: Page, id: string) {
  if (!/\bselected\b/.test((await row(page, id).getAttribute("class")) ?? "")) await rowId(page, id).click();
  await expect(row(page, id)).toHaveClass(/\bselected\b/);
}

async function shot(page: Page, name: string) {
  if (!SHOTS) return;
  await page.mouse.move(1000, 820);
  await page.waitForTimeout(350);
  await page.screenshot({ path: join(OUT, name) });
}

async function editStatement(page: Page, id: string, text: string) {
  await selectNode(page, id);
  await row(page, id).press("F2");
  const input = page.getByTestId("statement-input");
  await expect(input).toBeVisible();
  await input.fill(text);
  await input.press("Enter");
}

function simulateClaude(design: string, ...args: string[]): any {
  const out = execFileSync(PY, [SIM, design, ...args], { cwd: ROOT, encoding: "utf8", timeout: 120_000 });
  return JSON.parse(out);
}

test.describe("iteration 2a: intent file and GUI editing", () => {
  let srv: Server;
  test.beforeEach(async () => { srv = await startServer(copyDesign("examples/shelf_bracket.py")); });
  test.afterEach(() => srv.stop());

  test("2a-1: the tree loads from shelf_bracket.intent.yaml and looks like iteration 1", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    const ids = await page.locator(".row-node .row-id").allInnerTexts();
    expect(ids.map((s) => s.trim())).toEqual(["R", "A", "A.P", "A.P.1", "A.P.2", "A.3", "B", "B.1", "C"]);
    expect(await page.locator(".row-node .row-id .dot-ok").count()).toBe(9);
    await expect(page.locator(".stale-tag")).toHaveCount(0);
    const b = await buildOf(page);
    expect(b.tree.from_file).toBe(true);
    await expect(row(page, "R").locator(".row-sub")).toHaveText("Support a shelf on a wall");
    await expect(page.getByTestId("diagnostics")).not.toContainText("missing from the intent file");
  });

  test("2a-2: editing A.3 writes the file minimally; A.3 and A.3.cable go stale; mark reviewed clears it", async ({ page }) => {
    if (SHOTS) await page.emulateMedia({ colorScheme: "dark" });
    await page.goto(srv.url);
    await ready(page);
    const before = readFileSync(intentFile(srv), "utf8");
    await editStatement(page, "A.3", NEW_A3);
    await expect(page.getByTestId("stale-A.3")).toBeVisible();
    const after = readFileSync(intentFile(srv), "utf8");
    const a = before.split("\n"), c = after.split("\n");
    expect(c.length).toBe(a.length);
    const changed = a.map((l, i) => [l, c[i]]).filter(([x, y]) => x !== y);
    expect(changed).toEqual([["            statement: Cable pass-through, centered on the plate",
                              `            statement: ${NEW_A3}`]]);
    expect(c[0]).toBe(a[0]); // the header comment survives
    // the features that realize A.3: WHY chip, HOW row, connections view
    await expect(row(page, "A.3").locator('[data-chip="feat:A.3.cable"]')).toHaveClass(/chip-stale/);
    await shot(page, "iter2-stale-dark.png");
    await page.getByTestId("view-how").click();
    await expect(page.getByTestId("stale-feat-A.3.cable")).toBeVisible();
    await expect(page.locator(".rows .stale-tag")).toHaveCount(1);   // HOW: the one feature
    await page.getByTestId("expand").click();
    await expect(page.getByTestId("stale-c-A.3")).toBeVisible();
    await expect(page.getByTestId("stale-c-feat-A.3.cable")).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByTestId("view-why").click();
    // mark reviewed in the inspector
    await selectNode(page, "A.3");
    await expect(page.getByTestId("stale-box")).toContainText("was “Cable pass-through, centered on the plate”");
    await page.getByTestId("mark-reviewed").click();
    await expect(page.locator(".stale-tag")).toHaveCount(0);
    const review = JSON.parse(readFileSync(srv.design.replace(/\.py$/, ".review.json"), "utf8"));
    expect(review.reviewed["A.3"].content.statement).toBe(NEW_A3);
  });

  test("2a-3: adding a child under B creates B.2, flagged 'no feature'", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await selectNode(page, "B");
    await page.getByTestId("add-B").click();
    await expect(row(page, "B.2")).toBeVisible();
    const input = page.getByTestId("statement-input");
    await input.fill("Second screw up into the shelf");
    await input.press("Enter");
    await expect(row(page, "B.2").locator(".row-sub")).toHaveText("Second screw up into the shelf");
    await expect(page.getByTestId("diagnostics")).toContainText("B.2 intent with no feature");
    const txt = readFileSync(intentFile(srv), "utf8");
    expect(txt).toContain("          - id: B.2\n            statement: Second screw up into the shelf\n");
  });

  test("2a-4: deleting C asks in-page; afterwards C.gusset shows 'no intent'", async ({ page }) => {
    let dialogs = 0;
    page.on("dialog", (d) => { dialogs++; void d.dismiss(); });
    await page.goto(srv.url);
    await ready(page);
    await selectNode(page, "C");
    await page.getByTestId("delete-C").click();
    const confirm = page.getByTestId("confirm-delete");
    await expect(confirm).toContainText("Delete C?");
    await expect(confirm).toContainText("C.gusset will show “no intent”");
    await expect(row(page, "C")).toBeVisible(); // nothing happened yet
    await page.keyboard.press("Escape");        // cancel works
    await expect(confirm).toHaveCount(0);
    await row(page, "C").focus();
    await page.keyboard.press("Delete");        // keyboard path to the same confirmation
    await page.getByTestId("confirm-delete-yes").click();
    await expect(row(page, "C")).toHaveCount(0);
    await expect(page.getByTestId("diagnostics")).toContainText("C.gusset no intent");
    await expect(page.getByTestId("diagnostics")).toContainText("C used in the DSL but missing from the intent file");
    await expect(page.locator('[data-row="group:no-intent"] [data-chip="feat:C.gusset"]')).toBeVisible();
    expect(readFileSync(intentFile(srv), "utf8")).not.toContain("id: C\n");
    expect(dialogs).toBe(0); // never window.confirm()
  });

  test("2a-5: saving the file in an editor during a GUI edit is a conflict, not an overwrite", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await selectNode(page, "A.3");
    await row(page, "A.3").press("F2");
    const input = page.getByTestId("statement-input");
    await input.fill(NEW_A3);
    // meanwhile, an editor saves the intent file
    const f = intentFile(srv);
    writeFileSync(f, readFileSync(f, "utf8").replace("statement: Shelf support", "statement: Shelf support (editor)"));
    await expect(row(page, "B").locator(".row-sub")).toHaveText("Shelf support (editor)");
    await input.press("Enter");
    const banner = page.getByTestId("conflict-banner");
    await expect(banner).toBeVisible();
    await expect(banner).toContainText(NEW_A3);
    let txt = readFileSync(f, "utf8");
    expect(txt).toContain("Shelf support (editor)");
    expect(txt).not.toContain(NEW_A3); // no silent overwrite
    await shot(page, "iter2-conflict-light.png");
    await page.getByTestId("conflict-reapply").click();
    await expect(banner).toHaveCount(0);
    txt = readFileSync(f, "utf8");
    expect(txt).toContain("Shelf support (editor)");
    expect(txt).toContain(NEW_A3); // both edits, nothing lost
  });

  test("2a-6: an invalid intent file shows readable errors and keeps the last good tree", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    const f = intentFile(srv);
    writeFileSync(f, readFileSync(f, "utf8").replace("kind: analysis", "kind: analyis"));
    const banner = page.getByTestId("intent-error-banner");
    await expect(banner).toContainText("got 'analyis' (did you mean 'analysis'?)");
    await expect(row(page, "R")).toBeVisible();
  });

  test("drag to reparent keeps ids; checks and assumptions editors write the file", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await row(page, "A.3").dragTo(row(page, "B"), { sourcePosition: { x: 40, y: 8 }, targetPosition: { x: 40, y: 8 } });
    await expect.poll(async () => (await buildOf(page)).tree.nodes["A.3"].parent).toBe("B");
    const order = await page.locator(".row-node .row-id").allInnerTexts();
    expect(order.map((s) => s.trim())).toEqual(["R", "A", "A.P", "A.P.1", "A.P.2", "B", "B.1", "A.3", "C"]);
    // checks: add one to A.3 from the inspector
    await selectNode(page, "A.3");
    await page.getByTestId("add-check").click();
    await page.getByTestId("check-statement").fill("Clear of the lower countersink by ≥ 1 mm");
    await shot(page, "iter2-intent-editing-light.png");
    await page.getByTestId("save-check").click();
    await expect(page.locator('[data-check="A.3.c4"]')).toContainText("Clear of the lower countersink");
    // assumptions: challenge R.a1
    await selectNode(page, "R");
    await page.getByTestId("status-R.a1").selectOption("challenged");
    await expect.poll(() => readFileSync(intentFile(srv), "utf8")).toContain("status: challenged");
    const txt = readFileSync(intentFile(srv), "utf8");
    expect(txt).toContain("{id: A.3.c4, kind: relation, priority: should, statement: Clear of the lower countersink by ≥ 1 mm}");
    expect(txt.indexOf("id: A.3\n")).toBeGreaterThan(txt.indexOf("id: B.1\n")); // nested under B now
  });
});

test("rename id: the intent file and the DSL's intent literals change together", async ({ page }) => {
  const srv = await startServer(copyDesign("examples/shelf_bracket.py"));
  try {
    await page.goto(srv.url);
    await ready(page);
    await selectNode(page, "A.3");
    await page.getByTestId("rename-id").click();
    await page.getByTestId("rename-input").fill("A.C");
    await expect(page.getByTestId("rename-features")).not.toBeChecked();   // NOTES #49 change: opt-in, off by default
    await page.getByTestId("rename-go").click();
    await expect(row(page, "A.C")).toBeVisible();
    await expect(row(page, "A.3")).toHaveCount(0);
    expect(readFileSync(srv.design, "utf8")).toContain('intent("A.C", "hole"');
    expect(readFileSync(srv.design, "utf8")).toContain('"A.3.cable"');           // feature ids untouched by default
    expect(readFileSync(intentFile(srv), "utf8")).toContain("id: A.C\n");
    await expect(page.locator(".stale-tag")).toHaveCount(0);   // a rename is not an intent change
    await expect(page.getByTestId("diagnostics")).not.toContainText("missing from the intent file");
  } finally {
    srv.stop();
  }
});

test.describe("iteration 2b: the model in the loop", () => {
  test.setTimeout(180_000);
  let srv: Server;
  test.beforeEach(async () => { srv = await startServer(copyDesign("examples/shelf_bracket.py")); });
  test.afterEach(() => srv.stop());

  test("A.3 → offset 10 mm above the lower screw: ask, propose, reject with comment, revise, compare, accept", async ({ page }) => {
    await page.goto(srv.url);
    await ready(page);
    await editStatement(page, "A.3", NEW_A3);
    await expect(page.getByTestId("stale-A.3")).toBeVisible();
    // Ask Claude from the stale node
    await selectNode(page, "A.3");
    await page.getByTestId("ask-note").fill("Keep it clear of the countersink.");
    await page.getByTestId("ask-claude").click();
    await expect(page.getByTestId("request-pending")).toBeVisible();

    // "Claude" answers through MCP: a first, wrong proposal (12 mm)
    const p1 = simulateClaude(srv.design, "propose", "12");
    expect(p1.status).toBe("ready");
    const item1 = page.locator('[data-proposal="p1"]');
    await expect(item1).toContainText("ready for review");
    await item1.click();
    await page.getByTestId("reject-comment").fill("The intent says 10 mm, not 12.");
    await page.getByTestId("reject-proposal").click();
    await expect(item1.getByTestId("proposal-status")).toHaveText("rejected");
    const fb = simulateClaude(srv.design, "feedback", "p1");
    expect(fb.feedback[0].feedback.at(-1)).toMatchObject({ kind: "reject", comment: "The intent says 10 mm, not 12." });

    // the revised proposal
    const p2 = simulateClaude(srv.design, "propose", "10", "p1");
    expect(p2.revises).toBe("p1");
    const item2 = page.locator('[data-proposal="p2"]');
    await expect(item2).toContainText("no failing checks here");     // R.c1 fails at R, not at the addressed A.3
    await item2.click();
    const detail = page.getByTestId("proposal-detail");
    await expect(detail).toContainText("revises p1");
    await expect(page.getByTestId("proposal-check-status")).toContainText("Kernel ✓");
    await expect(detail).toContainText("9/9 parameter sample points pass");
    await expect(page.getByTestId("text-diff")).toContainText("+    d.hole(\"A.3.cable\", on=mount_face, at=offset(wall_pts[0], Z, 10.0)");
    await expect(page.getByTestId("semantic-diff")).toContainText("interpretation − A.3.cable/centered_on.point");
    await expect(page.getByTestId("centre-move")).toHaveText("A.3.cable: (0, 5, 32.5) → (0, 5, 19)");

    // geometry before / after: the changed face is the cable hole, and it moved down 13.5 mm
    const ev = (await page.evaluate(() => (window as any).__dipm.proposals.value.find((p: any) => p.id === "p2").evaluation));
    const zOf = async (face: number) => page.evaluate((f) => (window as any).__dipm.viewer.faceCentroid(f)[2], face);
    const nSelected = () => page.evaluate(() => (window as any).__dipm.viewer.states().filter((s: string) => s === "selected").length);
    await page.getByTestId("compare-before").click();
    await expect(page.getByTestId("compare-banner")).toContainText("before");
    await expect(page.getByTestId("compare-banner")).toContainText("COMPARING PROPOSAL p2 · inspection paused");   // #57
    await expect.poll(nSelected).toBe(1);                     // the proposal mesh is loaded and painted
    expect(await zOf(ev.changed_faces.before[0])).toBeCloseTo(32.5, 0);
    await page.getByTestId("compare-after").click();
    await expect(page.getByTestId("compare-banner")).toContainText("after");
    await expect.poll(() => zOf(ev.changed_faces.after[0])).toBeLessThan(20);
    expect(await zOf(ev.changed_faces.after[0])).toBeCloseTo(19, 0);
    expect(await nSelected()).toBe(1);
    expect(ev.face_tags.after[ev.changed_faces.after[0]]).toBe("A.3.cable.wall(0)");
    await page.getByTestId("compare-overlay").click();
    await expect.poll(() => page.evaluate(() => (window as any).__dipm.viewer.hasGhost())).toBe(true);
    if (SHOTS) {   // make room for the proposals panel in the right column
      for (const sec of ["inspector", "checks", "interpretations"]) await page.locator(`[data-section="${sec}"] .section-head`).click();
      await page.locator('[data-section="proposals"]').scrollIntoViewIfNeeded();
    }
    await shot(page, "iter2-proposals-overlay-light.png");

    // accept: the patch is applied, review recorded, staleness cleared
    await page.getByTestId("accept-proposal").click();
    await expect(item2.getByTestId("proposal-status")).toHaveText("accepted");
    await expect(page.locator(".stale-tag")).toHaveCount(0);
    await expect(page.getByTestId("compare-banner")).toHaveCount(0);
    expect(readFileSync(srv.design, "utf8")).toContain("at=offset(wall_pts[0], Z, 10.0)");
    const b = await buildOf(page);
    expect(b.status.kernel.state).toBe("pass");
    expect(b.features.find((f: any) => f.id === "A.3.cable").detail.centres[0][2]).toBeCloseTo(19, 4);
    expect(b.interpretations.slots.length).toBe(3);
    const fb2 = simulateClaude(srv.design, "feedback");
    expect(fb2.feedback.map((x: any) => [x.id, x.status])).toEqual([["p1", "rejected"], ["p2", "accepted"]]);
  });
});

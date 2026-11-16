// Iteration 4b (docs/purpose-loop.md §7): the GUI starts headless Claude Code for a queued
// request.  Never the real `claude`: the server runs the stub tests/fixtures/fake_claude
// (DIPM_CLAUDE_BIN), which checks the restricted flags, starts `dipm mcp` from the generated
// config and plays the rod holder's loop over MCP.  DIPM_SHOTS=1 saves iter4b-*.png.
import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";
import { copyDesign, FAKE_CLAUDE, startServer, type Server } from "./server";

const SHOTS = !!process.env.DIPM_SHOTS;
const OUT = join(process.cwd(), "screenshots");
const SEED = "tests/fixtures/rod_holder/rod_holder.py";

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
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, name) });
}
async function selectNode(page: Page, id: string) {
  const row = page.locator(`[data-row="node:${id}"]`);
  if (!/\bselected\b/.test((await row.getAttribute("class")) ?? "")) await row.locator(".row-id").click();
  await expect(row).toHaveClass(/\bselected\b/);
}
const stub = (mode: string, extra: Record<string, string> = {}) =>
  ({ DIPM_CLAUDE_BIN: FAKE_CLAUDE, DIPM_CLAUDE_AUTORUN: "1", DIPM_STUB_MODE: mode, ...extra });

for (const scheme of ["light", "dark"] as const) {
  test(`queuing a request starts Claude, streams its steps and links its proposals (${scheme})`, async ({ page }) => {
    test.setTimeout(180_000);
    const srv = await startServer(copyDesign(SEED), stub("loop", { DIPM_STUB_DELAY: "0.5" }));
    try {
      await page.goto(srv.url);
      await theme(page, scheme);
      await ready(page);
      await selectNode(page, "R");
      await page.getByTestId("ask-note").fill("It should hold a fishing rod now.");
      await page.getByTestId("ask-claude").click();
      // criterion 1: the run starts by itself and its steps stream into the header
      const badge = page.getByTestId("claude-status");
      await expect(badge).toHaveAttribute("data-state", "running");
      await expect(badge).toContainText("Claude is working on r1…");
      await expect(page.getByTestId("request-pending")).toHaveAttribute("data-status", "running");
      await expect(page.getByTestId("claude-step")).toContainText("evaluating attempt", { timeout: 60_000 });
      await badge.click();
      const steps = page.getByTestId("claude-steps");
      await expect(steps).toContainText("reading the impact report");
      await expect(steps).toContainText("submitted purpose proposal p1");
      await expect(page.getByTestId("claude-cancel")).toBeVisible();
      await shot(page, `iter4b-running-${scheme}.png`);
      // finished: proposals linked to the request at submission
      await expect(page.getByTestId("claude-run")).toHaveAttribute("data-status", "done", { timeout: 90_000 });
      await expect(steps).toContainText("submitted 2 alternatives (p2, p3)");
      await expect(page.getByTestId("claude-usage")).toContainText("$0.04");
      await expect(page.getByTestId("claude-status")).toContainText("Claude finished r1 · proposed p1, p2, p3");
      await expect(page.getByTestId("request-pending")).toHaveAttribute("data-status", "proposed");
      await expect(page.getByTestId("request-pending")).toContainText("request r1: proposed: p1, p2, p3");
      const reqs = await (await fetch(srv.url + "api/requests")).json();
      expect(reqs.requests[0]).toMatchObject({ id: "r1", status: "proposed", proposals: ["p1", "p2", "p3"] });
      const ps = await (await fetch(srv.url + "api/proposals")).json();
      expect(ps.proposals.map((p: any) => [p.id, p.requests, p.run])).toEqual(
        [["p1", ["r1"], "run1"], ["p2", ["r1"], "run1"], ["p3", ["r1"], "run1"]]);
      // the transcript is the stream-json, verbatim
      const href = await page.getByTestId("claude-transcript").getAttribute("href");
      const tx = (await (await fetch(new URL(href!, srv.url))).text()).trim().split("\n");
      expect(JSON.parse(tx[0]).subtype).toBe("init");
      expect(JSON.parse(tx[tx.length - 1]).type).toBe("result");
      // criterion 4: answered by pending proposals, so nothing to run again
      await expect(page.getByTestId("claude-run-now")).toBeDisabled();
      const again = await fetch(srv.url + "api/claude/run", { method: "POST", body: "{}" });
      expect(again.status).toBe(409);
      expect((await again.json()).code).toBe("nothing");
      await shot(page, `iter4b-finished-${scheme}.png`);
    } finally {
      srv.stop();
    }
  });
}

test("cancel stops the run; the request fails with the reason and can be run again", async ({ page }) => {
  test.setTimeout(120_000);
  const srv: Server = await startServer(copyDesign(SEED), stub("hang"));
  try {
    await page.goto(srv.url);
    await ready(page);
    const r = await page.evaluate(() => fetch("/api/requests", { method: "POST", headers: { "content-type": "application/json" },
                                                                 body: JSON.stringify({ node: "R", note: "" }) }).then((x) => x.json()));
    expect(r.run.status).toBe("running");
    const badge = page.getByTestId("claude-status");
    await expect(page.getByTestId("claude-step")).toContainText("reading the requests", { timeout: 60_000 });
    await badge.click();
    await page.getByTestId("claude-cancel").click();
    await expect(page.getByTestId("claude-run")).toHaveAttribute("data-status", "cancelled", { timeout: 20_000 });
    await expect(page.getByTestId("claude-reason")).toHaveText("cancelled by the designer");
    await expect(badge).toContainText("Claude stopped on r1: cancelled");
    const row = page.locator('[data-testid=request-row][data-request="r1"]');
    await expect(row).toHaveAttribute("data-status", "failed");
    await expect(row).toContainText("failed: cancelled by the designer");
    await expect(page.getByTestId("claude-run-now")).toBeEnabled();      // a failed request may be retried
  } finally {
    srv.stop();
  }
});

test("without a claude binary, queuing falls back to the copyable prompt", async ({ page }) => {
  const srv = await startServer(copyDesign(SEED), { DIPM_CLAUDE_AUTORUN: "1" });   // DIPM_CLAUDE_BIN points nowhere
  try {
    await page.goto(srv.url);
    await ready(page);
    await selectNode(page, "R");
    await page.getByTestId("ask-claude").click();
    await expect(page.getByTestId("request-pending")).toContainText("copy the prompt");
    await expect(page.getByTestId("requests-waiting")).toHaveText("1 request waiting");
    await page.getByTestId("requests-waiting").click();
    await expect(page.getByTestId("claude-unavailable")).toContainText("is not an executable file");
    await expect(page.getByTestId("claude-prompt")).toHaveValue(/get_requests[\s\S]*propose_alternatives/);
    await expect(page.getByTestId("claude-run-now")).toHaveCount(0);
    const s = await (await fetch(srv.url + "api/claude")).json();
    expect(s.available.ok).toBe(false);
    expect(s.run).toBeNull();
  } finally {
    srv.stop();
  }
});

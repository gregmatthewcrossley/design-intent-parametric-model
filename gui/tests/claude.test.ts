// Iteration 4b (docs/purpose-loop.md §7): what the header and the proposals panel say about a
// headless Claude run and the requests it works on.
import { describe, expect, it } from "vitest";
import { canRunNow, currentStep, headerState, idList, requestText, runHeadline } from "../src/claude";
import type { ClaudeStatusJ, RequestJ, RunJ } from "../src/types";

const req = (id: string, status: string, extra: Partial<RequestJ> = {}): RequestJ =>
  ({ id, created: "", node: "R", note: "", change: null, status, proposals: [], ...extra });

const run = (extra: Partial<RunJ> = {}): RunJ => ({
  id: "run1", design: "rod_holder", requests: ["r3"], status: "running", started: "", ended: null, reason: "",
  proposals: [], steps: [], ...extra,
});

const status = (extra: Partial<ClaudeStatusJ> = {}): ClaudeStatusJ => ({
  available: { ok: true, bin: "/x/claude", source: "PATH", reason: "" },
  settings: { auto_run: true, model: null, timeout_s: 1200 }, running: false, run: null, runs: [], waiting: 0,
  runnable: [], prompt: "p", ...extra,
});

describe("headless Claude runs: texts", () => {
  it("names the run's requests and its proposals", () => {
    expect(idList(["r1"])).toBe("r1");
    expect(idList(["p1", "p2", "p3", "p4"])).toBe("p1, p2 and 2 more");
    expect(runHeadline(run())).toBe("Claude is working on r3…");
    expect(runHeadline(run({ status: "done", proposals: ["p6", "p7", "p8"] }))).toBe("Claude finished r3 · proposed p6, p7, p8");
    expect(runHeadline(run({ status: "done" }))).toBe("Claude finished r3: nothing proposed");
    expect(runHeadline(run({ status: "cancelled" }))).toBe("Claude stopped on r3: cancelled");
    expect(runHeadline(run({ status: "timeout", proposals: ["p6"] }))).toBe("Claude stopped on r3: timed out · proposed p6");
    expect(runHeadline(run({ status: "failed" }))).toBe("Claude could not finish r3");
  });

  it("shows the latest step that is not Claude talking", () => {
    expect(currentStep(run())).toBe("starting…");
    expect(currentStep(run({ steps: [
      { at: "", kind: "tool", text: "evaluating attempt 2 of 'V-saddle'" },
      { at: "", kind: "say", text: "Claude: trying a deeper V" }] }))).toBe("evaluating attempt 2 of 'V-saddle'");
    expect(currentStep(run({ status: "done", steps: [] }))).toBe("");
  });

  it("header: a run in progress wins, then requests waiting, then the last run until dismissed", () => {
    const steps = [{ at: "", kind: "tool", text: "reading the impact report" }];
    expect(headerState(status({ running: true, run: run({ steps }) }), [req("r4", "open")], null))
      .toEqual({ kind: "running", text: "Claude is working on r3…", step: "reading the impact report" });
    expect(headerState(status(), [req("r4", "open"), req("r5", "open")], null)).toEqual({ kind: "waiting", text: "2 requests waiting" });
    const done = run({ status: "done", proposals: ["p6"] });
    expect(headerState(status({ run: done }), [req("r3", "proposed")], null))
      .toEqual({ kind: "last", text: "Claude finished r3 · proposed p6", tone: "ok" });
    expect(headerState(status({ run: done }), [], "run1")).toEqual({ kind: "none" });
    expect(headerState(status({ run: run({ status: "failed" }) }), [], null)).toMatchObject({ kind: "last", tone: "warn" });
    expect(headerState(null, [req("r1", "open")], null)).toEqual({ kind: "waiting", text: "1 request waiting" });
  });

  it("request states in words", () => {
    expect(requestText(req("r1", "open"))).toBe("waiting for Claude");
    expect(requestText(req("r1", "running"))).toBe("Claude is working on it");
    expect(requestText(req("r1", "proposed", { proposals: ["p5"] }))).toBe("proposed: p5");
    expect(requestText(req("r1", "failed", { status_detail: "run2: cancelled by the designer" }))).toBe("failed: cancelled by the designer");
    expect(requestText(req("r1", "answered"))).toBe("answered");
  });

  it("Run Claude now: only with a usable claude, no run going, and an open or failed request", () => {
    expect(canRunNow(status(), [req("r1", "open")])).toBe(true);
    expect(canRunNow(status(), [req("r1", "failed")])).toBe(true);
    expect(canRunNow(status(), [req("r1", "proposed")])).toBe(false);     // answered by a pending proposal
    expect(canRunNow(status({ running: true }), [req("r1", "open")])).toBe(false);
    expect(canRunNow(status({ available: { ok: false, bin: "claude", source: "PATH", reason: "no" } }), [req("r1", "open")])).toBe(false);
    expect(canRunNow(null, [req("r1", "open")])).toBe(false);
  });
});

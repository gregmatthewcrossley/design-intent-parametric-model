# Purpose → Geometry Loop

*Status: spec agreed 2026-11-16 (scope and driver chosen by the author); **built 2026-11-16** (iteration 4). Decisions: `src/dipm/NOTES.md` DECISIONS #73–89 (all [REVIEW]), TODOs 19–25. Tests: pytest 231, vitest 51, Playwright 47. Criteria 1–4, 6, 7 pass; criterion 5's live run produced purpose proposal p1 and alternatives p2–p4 for `rod_holder`, pending the author's review. Deviations: (a) the impact report keeps A.3 (cable pass-through) as *survives* because matching is by words, but the live purpose proposal removes it on design judgment; (b) accepting a purpose proposal does not mark the geometry reviewed. Code: `impact.py`, `vocabulary.py` (17 forms + descriptive), `components.py` (starter envelopes are placeholders).*

*Iteration 4. Test case: the author's edit of the bracket's root purpose from "Support a shelf on a wall" to "Support a fishing rod on a wall".*

## 1. Goal

When a designer changes a purpose, dipm and a language model produce **new, verified geometry**, offered as proposals the designer chooses between. Until now, nothing turned a changed purpose into new geometry: the purpose went stale and the geometry stayed as it was.

**The condition that governs everything else:** new geometry is only as trustworthy as the checks that ran on it. A purpose whose checks can't be computed shows as *not run*, never as passing (B1, "no false PASS").

## 2. Decisions (author, 2026-11-16)

| Question | Decision |
|---|---|
| Who drives the loop | **Claude Code via the dipm MCP server.** The designer registers the server (`claude mcp add …`, never run automatically). A Claude Code session drives the loop with dipm's tools. dipm holds the loop's logic and state, so a built-in agent could drive it later without redesign |
| Pack data | Apply the recommendations of [`reports/Rule pack engineering data.md`](../reports/Rule%20pack%20engineering%20data.md): store failure loads with their basis; checks apply SF 4 on anchors, about 5 on wood screws, 4 on printed plastic under sustained load (creep is not double-counted); undersize offset plus scatter for print tolerance; plastic plug as the default drywall anchor. Drop `placeholder` only where the report justifies it |

## 3. The loop

Each stage leaves a record in the proposal, so the designer can see how the model got there.

1. **Impact.** dipm diffs the old and new purpose trees, using the review baseline, and classifies every node and check as *changed*, *invalidated* or *survives*. Invalidated means it depends on what changed, through `supports`, `source`, nesting or features that serve it. The model gets this as a structured impact report, and the GUI shows it.
2. **Re-plan purposes first.** The model proposes a revised purpose subtree: new or changed child purposes, assumptions with ranges, components, and checks. This is a **purpose proposal**: it changes only the intent file, and the designer reviews it before any geometry exists. Wrong decompositions are cheap to fix as text. Designer edits made during this review count as designer-made.
3. **Computable checks** (NOTES TODO 4). Every check in a purpose proposal is either bound to a computable form from a small, fixed **check vocabulary** or explicitly marked descriptive, and so *not run*. The model writes the binding; dipm evaluates it. The vocabulary, first cut:
   - **Relations:** coincident, centered on, symmetric about, parallel, distance between, inside face.
   - **Rules from packs:** minimum wall, overhang, hole/edge distance, bridging.
   - **Fit and clearance against a component envelope:** "holds a Ø6–14 mm cylinder", "clears a 70 × 60 × 40 mm box at this pose", "the rod cannot leave the cradle without lifting at least *h*" (a retention check).
   - **Hand calculations from packs:** load, bending, anchor pull-out, as in R.c1, generalized.
   - **Tool access,** as in R.c4.

   Each binding evaluates to nominal, worst case, limit and margin, the same as iteration 3. A binding can be wrong, so it shows the model-made styling until the designer accepts it.
4. **Components.** Off-the-shelf things the design must fit, such as a fishing rod or a reel, become **component envelopes**: simple parametric solids with ranges (a cylinder Ø6–14 mm; a reel box). Each comes from a component pack where one exists, otherwise from a model-made, unreviewed assumption with its source stated. They render ghosted, like reference objects, and checks bind to them.
5. **Solutions.** Once the designer accepts the purpose proposal (or "accept to try"), the model writes or edits the design program. dipm builds it and runs the kernel invariants, interpretations and every bound check. The model iterates on failures within a **budget** (default 6 build attempts per alternative), then submits **2 or 3 alternatives** as geometry proposals. Each one carries:
   - its margins;
   - which checks ran, did not run, or failed;
   - what it assumed;
   - the attempt log.

   A proposal that still fails is submitted honestly as failing, with its best attempt.
6. **Choice.** The designer compares alternatives in the GUI, side by side with their margins, and accepts one. "Accept anyway…" for failing proposals keeps its recorded override (#54). Accepted items become designer-confirmed; everything else stays hatched.

## 4. Supporting changes

- **MCP tools:**
  - `get_impact`: the stage-1 report.
  - `get_check_vocabulary`: forms, parameters and examples.
  - `propose_purposes`: an intent-file-only proposal with check bindings validated on submit.
  - `evaluate`: build a candidate design text without proposing it, returning the full tiered report. This is the model's inner loop.
  - `get_components`.
- **Change notification:** a purpose edit in the GUI creates an open request, as "Queue for Claude" does. A driving session picks open requests up through `get_requests`, and the GUI shows "N requests waiting". Automatic pickup: §7.
- **GUI:**
  - an impact view, with invalidated nodes marked in the tree;
  - purpose proposals reviewed as a tree diff, with each binding readable in plain language;
  - an alternatives compare view of 2 or 3 proposals showing their margins and thumbnails;
  - component envelopes ghosted in the viewport.
- **The example:** the shelf bracket stays the regression fixture with its committed purposes. The author's fishing-rod edit moves into a new design, `examples/rod_holder.*`, seeded from the bracket, and the loop runs on that.

## 5. Acceptance criteria

1. Editing a root purpose produces an impact report that marks the right nodes invalidated. For shelf → fishing rod: B, B.1 and R.a1 are invalidated; A and R.c2 survive.
2. A purpose proposal with an unbindable check is accepted only with that check shown as *descriptive, not run*.
3. Every check vocabulary form has unit tests with a passing and a failing case, and reports margins.
4. On `rod_holder`, an end-to-end run driven through the MCP tools (scripted in tests with a stub "model" that submits fixed texts) produces a purpose proposal, then at least 2 geometry alternatives, each with bound checks run and honest status.
5. A live run by Claude on `rod_holder` produces real alternatives that the author can review in the GUI. Nothing is accepted on the author's behalf.
6. Nothing writes the intent file or the design program except an accepted proposal or the designer.
7. The pack data matches the report, with `placeholder` flags per the report's table.

## 6. Out of scope

Direct sketch and feature authoring in the GUI (needs the sketch solver); a built-in agent; learned checks (rung 3); assemblies. Component packs beyond a hand-written starter set.

## 7. Automatic pickup: the GUI starts Claude (iteration 4b, spec agreed 2026-11-16; **built 2026-11-16**)

*Built: `src/dipm/claude_runner.py`, `gui/src/claude.ts`; decisions NOTES #90–101 ([REVIEW]), TODOs 26–31. Tests: pytest 250, vitest 56, Playwright 47+4 (a stub `claude` via `DIPM_CLAUDE_BIN`; tests never start the real binary). Criteria 1–4 pass; 5 (live run) is the author's. As built: a purpose edit also auto-runs (#93); requests go open → running → proposed → answered on acceptance, and reopen if every linked proposal is rejected or only a purpose proposal was accepted; proposals link to requests by node at submission (#92). Command: `claude -p <prompt> --output-format stream-json --verbose --mcp-config .dipm/runs/run<n>.mcp.json --strict-mcp-config --tools "" --allowedTools <the 16 dipm tools> --disallowedTools Bash,Edit,Write,Read,… --permission-mode dontAsk [--model …]`. Env: `DIPM_CLAUDE_BIN`, `DIPM_CLAUDE_AUTORUN`, `DIPM_CLAUDE_TIMEOUT`. Unconfirmed until a live run: the stream-json event shapes and the not-logged-in wording (#94, TODO 26).*

**Problem.** MCP is pull-based: Claude Code calls dipm, but dipm can't wake Claude. Until now, "Queue for Claude" only wrote a request into `.dipm/`, and the designer had to paste a prompt into a Claude Code session.

**Decision (author, 2026-11-16).** dipm launches **Claude Code itself, headless** (`claude -p`), so the driver stays Claude Code on the designer's own plan, with no API key (§2). A built-in Agent SDK driver stays out of scope.

- **Trigger.** Queuing a request starts a run automatically. A **"Run Claude now"** button covers requests left open. An **auto-run** toggle, on by default and remembered per design, turns automatic starting off.
- **Launch.** `claude -p <prompt> --mcp-config <generated config: the dipm MCP server for this design> --strict-mcp-config`, run from the repo root.
  - The prompt is built from the request: its node, note and change, plus the loop instructions.
  - Only dipm's MCP tools are available (`--tools` / `--allowedTools`), with no shell and no file-editing tools. Anything else is denied, never prompted. Even so, Claude can only *propose*: it never writes files.
  - Output uses `--output-format stream-json`. The binary is found on `PATH`, overridable with `DIPM_CLAUDE_BIN`.
  - The model is the designer's Claude Code default, optionally overridden in settings.
- **Runs.**
  - One run at a time per design; further requests queue behind it.
  - The designer can cancel a run, and a timeout (default 20 min) stops it.
  - Each run's transcript is saved in `.dipm/runs/<run id>.jsonl`.
  - A request moves open → running → proposed (with links to its proposals) or failed (with the reason).
  - Proposals made by a run are linked to the request when submitted, not only when accepted, so a request already answered by a pending proposal isn't handled twice.
- **GUI.**
  - The status shows "Claude is working on r3…" with live, plain-language steps taken from the stream ("reading the impact report", "evaluating attempt 2 of 'V-saddle'", "submitted 3 alternatives").
  - It offers cancel, "open transcript", and the usage/cost line when the stream reports one.
- **Fallback.** If `claude` isn't installed or isn't logged in, the GUI says so and shows the copyable prompt, as before.
- **Safety.** dipm only ever starts `claude` for a request the designer queued (or with auto-run on). Each run is bounded by the request, the timeout and the restricted tool list. Nothing is committed.
- **Acceptance.**
  1. With a stub `claude` (via `DIPM_CLAUDE_BIN`), queuing a request starts a run with the restricted flags, streams its steps to the GUI, and links the proposals it submits.
  2. Cancel and timeout work.
  3. A missing binary falls back to copy-paste.
  4. A request already answered by a pending proposal isn't re-run.
  5. A live run on `rod_holder` is triggered by the author from the GUI.

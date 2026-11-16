# Response to the fresh-eyes review

*From the project author, 2026-11-16, on `reports/Fresh eyes review.md` (commit e84902b). Recorded verbatim from the review page. Actions are tracked in [`docs/review-response.md`](../docs/review-response.md).*

- **Agreed:** all items except those below, including every high-severity issue (ISS-01..10).
- **Strong agreement, with notes:**
  - **MATH-07** (no tolerance/robustness model)
  - **MATH-09** (uncertainty labelled, not modelled). *"I want to make sure uncertainty and tolerance are handled as first-class concerns. I also want to talk about how to visualize uncertainty, and also how to help visualize the scale of things using photographic visual clues (ie when zoomed in very close, the focal point becomes very narrow, like in real life. I have a tendency to lose track of just how small a feature will be when I'm staring at the clean edges and faces of geometry rendered on a screen)."*
  - **PAIN-01** (designers often don't know their intent yet)
  - **PAIN-06** (explanation overload and engine jargon)
  - **PAIN-07** (intent-tree cognitive load at scale)
  - **PAIN-12** (system guesses harden into intent). *"Model-made/unreviewed items should be recorded and shown as distinct from designer-made/designer-reviewed."*
  - **ISS-08** (assumes known, stateable intent). *"Early stage industrial design means a lot of experimentation and negotiation between competing constraints."*
- **Later to-do:** **PAIN-08** (handoff to engineering and manufacturing).
- **To discuss:**
  - **PAIN-04** (design-rationale tools died of maintenance cost): *"I'm not sure I understand this one."*
  - **PAIN-09** (round-trip editing): *"Let's take a moment to compare this project with the OnShape API, and make sure that at the very least, parametric design trees made by this project can be cleanly re-created with native OnShape API calls."*
- **Disagreed:** **HN-06** (industrial designer: "automates the last 20%… makes me write a requirements doc for the fun part"). *"Perhaps this is specific to my own ID work, but when I am designing a product that connects many complex off-the-shelf components, each with electrical, mechanical, thermal and human-interface constraints, I find myself spending hours drawing sketches and defining features and editing the feature tree, work that feels analogous to typing out computer code without autocomplete or LLM help."*

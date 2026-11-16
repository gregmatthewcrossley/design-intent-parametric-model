"""A scripted stand-in for the model driving the purpose -> geometry loop (iteration 4).

Drives `dipm.proposals.ProposalStore` on a temp copy of examples/rod_holder.* with the fixed
texts of tests/fixtures/rod_loop.py: a purpose proposal, a few `evaluate` attempts per
alternative label (so each has an attempt log), then 2 or 3 alternatives built against the
purpose proposal.  Nothing is accepted.

    python simulate_loop.py <design.py> [n_alternatives]   -> prints {purpose, group, alternatives}
"""
import json
import os
import sys
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tests", "fixtures"))

import rod_loop  # noqa: E402

from dipm.fileio import file_sha256  # noqa: E402
from dipm.proposals import ProposalStore  # noqa: E402

# label -> (attempts as (lip, standoff, summary), rationale): the last attempt is submitted
ALTS = {
    "A": ([(4.0, 45.0, "first cradle, 4 mm lip"), (12.0, 45.0, "lip raised to 12 mm")],
          "Compact: the rod sits 45 mm from the wall behind a 12 mm lip."),
    "B": ([(12.0, 65.0, "rod 65 mm out so the reel clears the wall")],
          "Stand-off: 65 mm from the wall so a 60–90 mm wide reel clears it."),
    "C": ([(3.0, 65.0, "minimal lip: 3 mm")],
          "Minimal lip, easy to lift the rod out (fails the 5 mm retention honestly)."),
}


def main(design: str, n: int) -> None:
    warnings.simplefilter("ignore")
    st = ProposalStore(design)
    intent = st.files.intent
    p = st.create_purpose("Rod holder purposes: cradle, retention, reel clearance",
                          "The root purpose changed from a shelf to a fishing rod: the shelf support (B, B.1) and the "
                          "shelf load (R.c1, R.a1) are invalidated; wall mounting survives.",
                          rod_loop.PURPOSE_TEXT, file_sha256(intent), ["R", "B"])
    p = st.evaluate(p["id"])
    name = os.path.basename(design)
    labels = list(ALTS)[:n]
    alts = []
    for lab in labels:
        attempts, why = ALTS[lab]
        for lip, so, summary in attempts:
            st.evaluate_candidate({name: rod_loop.design_text(lip, so, label=lab)}, lab, p["id"], summary)
        lip, so, summary = attempts[-1]
        alts.append({"label": lab, "summary": f"{lab}: {summary}", "rationale": why,
                     "files": {name: rod_loop.design_text(lip, so, label=lab)}})
    ps = st.create_alternatives("Rod holder alternatives", "three takes on the cradle", alts,
                                {name: file_sha256(design)}, ["R", "B"], purpose=p["id"])
    out = [st.evaluate(q["id"]) for q in ps]
    print(json.dumps({"purpose": p["id"], "group": ps[0]["group"],
                      "alternatives": [{"id": q["id"], "label": q.get("alternative"), "status": q["status"]} for q in out]}))


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 3)

"""Stub "model" texts for the purpose -> geometry loop on examples/rod_holder (criterion 4).

`PURPOSE_TEXT` is a revised rod_holder.intent.yaml (a purpose proposal); `design_text(...)`
is a rod-holder design program the stub submits as geometry alternatives.  Fixed texts, so the
end-to-end test (tests/test_purpose_loop.py) and the GUI e2e (gui/e2e/simulate_loop.py) are
deterministic.
"""

PURPOSE_TEXT = """\
# Rod holder: the intent tree (stub purpose proposal for tests).
design: rod_holder
context: {process: fdm_printing, material: PETG, install: drywall with anchors, style: minimal_industrial}
components:
  - {id: rod, statement: Rod blank where the holder grips it, shape: cylinder, pack: fishing_rod_blank, source: packs.COMPONENTS.fishing_rod_blank (placeholder), made_by: model, status: proposed}
  - {id: reel, statement: Spinning reel hanging under the rod, shape: box, size: "90..140 x 60..90 x 90..130 mm", source: "estimate, no cited source", made_by: model, status: proposed}
intents:
  - id: R
    statement: Support a fishing rod on a wall
    checks:
      - {id: R.c1, kind: analysis, source: world, priority: must, statement: "Carries the rod and reel (0.2–1 kg) on two wall screws", binding: {form: anchor_pullout, anchors: A.P.holes, load: "component:rod", at: "component:rod", seat: cradle_seat, made_by: model, status: proposed}}
      - {id: R.c2, kind: rule, source: "world:fdm_printing.overhang", priority: must, statement: "Printable without supports (overhang ≤ 45°)"}
      - {id: R.c3, kind: learned score, source: "human:minimal_industrial", priority: nice to have, statement: Proportions look balanced}
      - {id: R.c4, kind: rule, source: "human:care.tool_access", priority: must, statement: Every wall screw can be driven by a standard screwdriver, binding: {form: tool_access, holes: A.P.holes, diameter: "30", length: "150", made_by: model, status: proposed}}
    assumptions:
      - {id: R.a1, statement: "Rod and reel weigh 0.2–1 kg, resting in the cradle (static)", made_by: model, supports: [R.c1], sensitivity: medium, status: proposed}
      - {id: R.a3, statement: "Installer uses a standard screwdriver or drill, no right-angle adapter", made_by: model, supports: [R.c4], sensitivity: medium, status: proposed}
    children:
      - id: A
        statement: Wall mounting
        children:
          - id: A.P
            statement: Wall screw pattern
            children:
              - id: A.P.1
                statement: Lower wall screw hole
              - id: A.P.2
                statement: Upper wall screw hole
      - id: B
        statement: "Cradle: holds the rod blank"
        checks:
          - {id: B.c1, kind: relation, priority: must, statement: "Holds a Ø6–14 mm blank", binding: {form: holds_cylinder, component: rod, seat: cradle_seat, axis: X, made_by: model, status: proposed}}
          - {id: B.c2, kind: relation, priority: must, statement: "The rod cannot roll out without lifting at least 5 mm", binding: {form: retention, component: rod, seat: cradle_seat, min_lift: "5", made_by: model, status: proposed}}
          - {id: B.c3, kind: rule, priority: should, statement: "No sharp edge touches the blank finish", binding: {form: descriptive, reason: "edge sharpness is not in the vocabulary yet", made_by: model, status: proposed}}
          - {id: B.c4, kind: relation, priority: must, statement: "The reel hangs clear of the holder and the wall", binding: {form: clears_box, component: reel, hangs_from: rod, seat: cradle_seat, along: "90..200", made_by: model, status: proposed}}
"""


def design_text(lip: float = 12.0, standoff: float = 45.0, gap: float = 20.0, label: str = "A") -> str:
    """A U-cradle rod holder: wall plate with two countersunk screws below the cradle, an arm out to
    `standoff` from the wall, a lip `lip` above the cradle floor."""
    return f'''"""Rod holder, stub alternative {label} (tests/fixtures/rod_loop.py)."""
from dipm import Design, X, Z, countersink, face_point, intent
from dipm.checks import overhang
from dipm.sketch import YZ, Profile


def make_design():
    d = Design("rod_holder", doc="stub alternative {label}")
    d.use_intent(__file__)
    t = d.param("t", 5.0, range=(4.0, 6.0), doc="plate thickness")
    lip = d.param("lip", {lip!r}, range=({lip - 1!r}, {lip + 1!r}), doc="lip height above the cradle floor")
    width = 20.0
    floor, a, tl, gap, top = 70.0, 6.0, 5.0, {gap!r}, 95.0
    y2 = {standoff!r} + gap / 2 + tl
    P = Profile(YZ, points={{"o": (0.0, 0.0), "b": (t, 0.0), "arm_lo": (t, floor - a), "tip_lo": (y2, floor - a),
                            "tip_hi": (y2, floor + lip), "lip_in_hi": (y2 - tl, floor + lip),
                            "lip_in_lo": (y2 - tl, floor), "floor_in": ({standoff!r} - gap / 2, floor),
                            "back_lo": ({standoff!r} - gap / 2, top - 10.0), "back_top": (t, top), "wall_top": (0.0, top)}},
                edge_names={{"o-b": "bottom", "b-arm_lo": "front_low", "arm_lo-tip_lo": "arm_under",
                            "tip_lo-tip_hi": "lip_out", "tip_hi-lip_in_hi": "lip_top", "lip_in_hi-lip_in_lo": "lip_in",
                            "lip_in_lo-floor_in": "floor", "floor_in-back_lo": "back", "back_lo-back_top": "hood",
                            "back_top-wall_top": "top", "wall_top-o": "wall"}},
                winding="ccw", name="cradle")
    body = d.extrude("R.body", P, distance=width, symmetric=True, tags=intent("R", "skeleton"))
    front = body.side("front_low")
    pts = [face_point(front, along=(Z, u), across=(X, 0.5)) for u in (0.2, 0.7)]
    d.hole("A.P.holes", on=front, at=pts, spec=countersink("#8"),
           tags=(intent("A.P", "pattern"), intent("A", "wall_mount")), instance_tags=["A.P.1", "A.P.2"])
    d.export("wall_face", body.side("wall"))
    d.export("cradle_seat", body.side("floor"))
    d.export("lip", body.side("lip_top"))
    d.check("R.c2", overhang())
    d.use_lock(__file__)
    return d


design = make_design()
'''

"""dipm: v0 DSL core for design-intent -> parametric CAD (placeholder package name).

Start with NOTES.md next to this file.  Section references are to docs/dsl.md and
docs/architecture.md.

Public API (embedded Python; see examples/shelf_bracket.py):

    from dipm import Design, intent, sketch
    d = Design("bracket")
    t = d.param("t", 5.0, range=(4, 8))
    body = d.extrude("E", profile, distance=6 * t, symmetric=True, tags=intent("R", "skeleton"))
    b = d.build(t=6)              # pure: parameters -> Build
    b.why(face)                   # "why is this here?"

Ambiguous intent words (hole extent, centered_on) are resolved by `interpret.resolve`
(architecture §10 item 2) and recorded in a lock file; see NOTES.md §6.
"""
from . import intent_layer  # noqa: F401
from . import interpret  # noqa: F401
from . import sketch  # noqa: F401
from .errors import (CardinalityError, DipmError, InteractionError, InvariantError, KernelError,  # noqa: F401
                     ParameterError, PolicyError, SketchError)
from .expr import Param, emax, emin, ev  # noqa: F401
from .intent_layer import (THROUGH_ALL, at, blind, centered_on, centerline, circular_pattern, clearance,  # noqa: F401
                     clearance_diameter, countersink, distribute, edge_distance, face_point, head_diameter,
                     linear_pattern, midpoint, offset, plain, through, tool_access_radius)
from .interpret import Interpretation, Preferences, resolve  # noqa: F401
from .kernel import ORIGIN, X, Y, Z, Vec3  # noqa: F401
from .ops import Expect  # noqa: F401
from .program import Build, Design, IntentTag, intent  # noqa: F401
from .refs import (ERROR_ON_MERGE, ERROR_ON_SPLIT, PROPAGATE_ALL, Ref, Tag, at_least, edges_between,  # noqa: F401
                   exactly, one)
from .sketch import XY, XZ, YZ, Plane, Profile  # noqa: F401

__version__ = "0.0.1"

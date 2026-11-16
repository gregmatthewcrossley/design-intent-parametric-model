"""Shared fixtures.  The bracket example is loaded from examples/ by path (it is not a package)."""
from __future__ import annotations

import importlib.util
import os
import pathlib

# Iteration 4b: nothing in the test suite may start the real `claude`.  Auto-run defaults to off
# and the binary points nowhere; the runner tests opt in with the stub (tests/fixtures/fake_claude).
os.environ["DIPM_CLAUDE_BIN"] = "/nonexistent/claude-is-disabled-in-tests"
os.environ["DIPM_CLAUDE_AUTORUN"] = "0"

import pytest

from dipm import XY, Design, Profile, intent
from dipm.sketch import rect_points

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "shelf_bracket.py"


def load_example():
    spec = importlib.util.spec_from_file_location("shelf_bracket_example", EXAMPLE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def bracket_mod():
    return load_example()


@pytest.fixture(scope="session")
def bracket(bracket_mod):
    return bracket_mod.design


@pytest.fixture(scope="session")
def bracket_build(bracket):
    return bracket.build()


def block(name="block", Lx=40.0, Wy=30.0, Hz=20.0):
    """40 x 30 x 20 block 'E' from rectangle a(0,0) b(Lx,0) c(Lx,Wy) d(0,Wy), extruded +Z (spike 02 base body).
    E.side(a-b) is -Y, (b-c) +X, (c-d) +Y, (d-a) -X; E.cap(START) z=0, E.cap(END) z=Hz."""
    d = Design(name)
    E = d.extrude("E", Profile(XY, rect_points(0.0, 0.0, Lx, Wy)), Hz, tags=intent("R", "skeleton"))
    return d, E


BRACKET_SET = ("shelf_bracket.py", "shelf_bracket.intent.yaml", "shelf_bracket.interpretations.json",
               "shelf_bracket.review.json", "shelf_bracket.resolution.json")


def copy_bracket(dst: pathlib.Path) -> pathlib.Path:
    """Copy the bracket's design set (DSL, intent file, lock) to `dst`; tests that write files use this."""
    import shutil
    for f in BRACKET_SET:
        shutil.copy(EXAMPLE.parent / f, dst / f)
    return dst / "shelf_bracket.py"


A3_OLD = "at=centered_on(mount_face)"
A3_NEW = "at=offset(wall_pts[0], Z, 10.0)"


def a3_offset_patch(py_text: str, mm: float = 10.0) -> str:
    """The scripted 'Claude' change of gui.md §7.3: A.3 from 'centered on the plate' to
    'offset <mm> mm above the lower screw'."""
    out = py_text.replace(A3_OLD, f"at=offset(wall_pts[0], Z, {mm})")
    out = out.replace("centered_on, centerline,", "centered_on, centerline, offset,")
    out = out.replace('"cable pass-through, centred on the plate"', f'"cable pass-through, {mm:g} mm above the lower screw"')
    assert out != py_text
    return out


ROD_SET = ("rod_holder.py", "rod_holder.intent.yaml", "rod_holder.interpretations.json", "rod_holder.review.json",
           "rod_holder.resolution.json")


#: The rod holder as seeded in iteration 4 (fishing-rod root, the rest still the bracket's, the
#: shelf review record).  Frozen here because examples/rod_holder.* is the author's live design:
#: accepting a proposal there (p5, 2026-11-16) must not change what the tests start from.
ROD_SEED = ROOT / "tests" / "fixtures" / "rod_holder"


def copy_rod_holder(dst: pathlib.Path) -> pathlib.Path:
    """Copy the rod holder's seed design set (iteration 4) to `dst`."""
    import shutil
    for f in ROD_SET:
        shutil.copy(ROD_SEED / f, dst / f)
    return dst / "rod_holder.py"

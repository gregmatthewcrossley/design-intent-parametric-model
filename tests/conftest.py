"""Shared fixtures.  The bracket example is loaded from examples/ by path (it is not a package)."""
from __future__ import annotations

import importlib.util
import pathlib

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
               "shelf_bracket.review.json")


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

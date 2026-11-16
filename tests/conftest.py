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

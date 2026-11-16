"""CLI smoke tests: python -m dipm build/stability."""
from dipm.cli import main

from conftest import EXAMPLE


def test_cli_build_report_and_outputs(tmp_path, capsys):
    rc = main(["build", str(EXAMPLE), "--param", "shelf_depth=250", "-p", "screw=#10", "--out", str(tmp_path), "--step"])
    out = capsys.readouterr().out
    assert rc == 0
    for s in ("shelf_depth = 250.0", "A.P.holes", "pattern@A.P", "k=1: hole@A.P.2", "delta_H=2", "Signature:",
              "adjacency hash (topology)", "canonical (brep)", "mount_face", "Result: PASS"):
        assert s in out, s
    files = sorted(p.suffix for p in tmp_path.iterdir())
    assert files == [".brep", ".step"]


def test_cli_bad_param(capsys):
    assert main(["build", str(EXAMPLE), "-p", "t=99"]) == 2
    assert "outside declared range" in capsys.readouterr().err


def test_cli_faces_and_stability(capsys):
    assert main(["build", str(EXAMPLE), "--faces"]) == 0
    assert "created as A.3.cable.wall(0)" in capsys.readouterr().out
    assert main(["stability", str(EXAMPLE)]) == 0
    assert "points stable" in capsys.readouterr().out

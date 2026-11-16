"""CLI smoke tests: python -m dipm build/stability."""
from dipm.cli import main

from conftest import EXAMPLE


def test_cli_build_report_and_outputs(tmp_path, capsys):
    rc = main(["build", str(EXAMPLE), "--param", "shelf_depth=250", "-p", "screw=#10", "--out", str(tmp_path), "--step"])
    out = capsys.readouterr().out
    assert rc == 3          # iteration 3: kernel passes, R.c1 (and R.c4) fail -> exit 3, no bare PASS (B1)
    for s in ("shelf_depth = 250.0", "A.P.holes", "pattern@A.P", "k=1: hole@A.P.2", "delta_H=2", "Signature:",
              "adjacency hash (topology)", "canonical (brep)", "mount_face", "Result: kernel invariants pass",
              "[FAILING] R.c1", "[not run] R.c3"):
        assert s in out, s
    files = sorted(p.suffix for p in tmp_path.iterdir())
    assert files == [".brep", ".step"]


def test_cli_bad_param(capsys):
    assert main(["build", str(EXAMPLE), "-p", "t=99"]) == 2
    assert "outside declared range" in capsys.readouterr().err


def test_cli_faces_and_stability(capsys):
    assert main(["build", str(EXAMPLE), "--faces"]) == 3
    assert "created as A.3.cable.wall(0)" in capsys.readouterr().out
    assert main(["stability", str(EXAMPLE)]) == 0
    assert "points stable" in capsys.readouterr().out

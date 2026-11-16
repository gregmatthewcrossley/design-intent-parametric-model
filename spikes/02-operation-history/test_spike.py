"""Regression tests pinning spike 02's findings.  Run: ../../.venv/bin/python -m pytest -q"""
import pytest

import ops   # puts spike 01 on sys.path via common
import q4_clean
from common import audit_history, checks, topo
from refs import CardinalityError


# ---------------------------------------------------------------- invariants on every default model

@pytest.mark.parametrize("name", list(ops.DEFAULTS))
def test_euler_and_validity_hold_on_defaults(name):
    r = ops.DEFAULTS[name]()
    c = checks(r.shape)
    assert c["euler_ok"] and c["valid"], c


@pytest.mark.parametrize("name", [n for n in ops.DEFAULTS if n != "pattern.overlap_tool_list"
                                  and n != "pattern.overlap_compound(neg)"])
def test_defaults_match_declared_roles_and_deltas(name):
    import q1_roles
    a = q1_roles.analyse(name, ops.DEFAULTS[name]())
    assert a["roles_ok"] and a["dH_ok"] and a["dS_ok"], a
    assert a["coverage"]["unnamed"] == []          # every result face is reachable from a role/reference
    if name not in ("draft.4sides", "shell.no_openings"):
        assert a["base_ok"], a["base_refs"]


# ---------------------------------------------------------------- revolve

def test_full_revolve_drops_generated_for_axis_normal_edges():
    r = ops.revolve(360)
    assert r.notes and "bottom" in r.notes[0] and "top" in r.notes[0]       # workaround was needed
    assert len(r.roles["side(bottom)"]) == 1 and len(r.roles["side(top)"]) == 1   # ...and works
    assert "cap(START)" not in r.roles
    assert checks(r.shape)["VEFRSH"][5] == 1                                   # annulus revolve: genus 1


def test_partial_revolve_needs_no_workaround_and_on_axis_full_revolve_is_genus_0():
    assert ops.revolve(359.9).notes == []
    r = ops.revolve(360, r_in=0.0)
    assert checks(r.shape)["VEFRSH"][5] == 0 and r.roles["side(inner)"] == []


# ---------------------------------------------------------------- chamfer

def test_chamfer_isdeleted_false_positives_like_fillet():
    r = ops.chamfer(3.0)
    assert audit_history(r.algo, r.audit_inputs, r.shape)["false_deleted"] > 0


def test_chamfer_corner_patches_come_from_generated_vertex():
    r = ops.chamfer(2.0, "all12")
    corners = [k for k in r.roles if k.startswith("corner")]
    assert len(corners) == 8 and all(len(r.roles[k]) == 1 for k in corners)


def test_chamfer_that_would_consume_a_face_fails_loudly():
    with pytest.raises(RuntimeError):
        ops.chamfer(15.0, "ridge")
    ops.chamfer(14.99, "ridge")   # just below: fine, END cap still exactly one face


# ---------------------------------------------------------------- shell

def test_shell_inner_is_generated_rim_is_modified_opening():
    r = ops.shell(-2.0)
    assert all(len(v) == 1 for v in r.roles.values())
    assert r.ledger.genealogy("E", "cap", "END") == [(("SH", "modified"),)]   # opening ref lands on the rim


def test_thicksolid_without_openings_is_an_offset_not_a_hollow():
    r = ops.shell(-2.0, ())
    c = checks(r.shape)
    assert c["VEFRSH"][4] == 1 and abs(c["volume"] - 36 * 26 * 16) < 1e-6
    v = ops.shell_void(2.0)
    assert checks(v.shape)["VEFRSH"][4] == 2       # the real hollow: offset + cut, dS = +1


def test_collapsing_shell_returns_invalid_shape_without_raising():
    r = ops.shell(-15.0)
    assert not topo.is_valid(r.shape)


# ---------------------------------------------------------------- loft / sweep

def test_loft_incompatible_sections_split_side_faces():
    r = ops.loft(third="circle")
    assert len(r.roles["side(from=s0.b-c)"]) == 2 and len(r.roles["side(from=s0.a-b)"]) == 1
    assert r.algo.GeneratedFace(_loft_edge(r, "s0", "b-c")).IsNull()      # single-face API gives up on splits
    assert not r.algo.GeneratedFace(_loft_edge(r, "s0", "a-b")).IsNull()


def _loft_edge(r, sec, name):
    """Input edge `name` of loft section `sec`, taken from the section wire in wire order."""
    from OCP.BRepTools import BRepTools_WireExplorer
    wx, i, order = BRepTools_WireExplorer(r.audit_inputs[sec]), 0, ["a-b", "b-c", "c-d", "d-a"]
    while wx.More():
        if order[i] == name:
            return wx.Current()
        i += 1
        wx.Next()
    raise KeyError(name)


def test_ruled_loft_gives_one_face_per_span():
    r = ops.loft(ruled=True, third="square")
    assert all(len(v) == 2 for k, v in r.roles.items() if k.startswith("side"))


def test_sweep_segment_roles_and_closed_spine():
    r = ops.sweep()
    assert all(len(r.roles[f"side(from={e}, along=spine{i})"]) == 1 for e in ("a-b", "b-c") for i in (0, 1))
    c = ops.sweep("closed")
    assert "cap(START)" not in c.roles and checks(c.shape)["VEFRSH"][5] == 1


def test_self_intersecting_sweep_passes_euler_but_fails_brepcheck():
    r = ops.sweep(bend_r=5, pw=12)
    c = checks(r.shape)
    assert c["euler_ok"] and not c["valid"]


# ---------------------------------------------------------------- draft

def test_draft_reports_drafted_faces_via_generated_and_no_edge_history():
    r = ops.draft(5.0)
    spike01 = r.notes[0]["spike01_ledger_counts"]
    assert spike01["E.side(a-b)"] == 0                     # spike-01 ledger (Modified only) loses them
    assert r.ledger.count("E", "side", "a-b") == 1          # Ledger2 follow_generated keeps them
    assert r.ledger.count("E", "lateral_edge", "a") == 0    # no edge history at all
    assert r.notes[1]["derived_lateral_edges"] == {"a": 1, "b": 1, "c": 1, "d": 1}


def test_draft_beyond_collapse_fails_loudly():
    with pytest.raises(RuntimeError):
        ops.draft(37.0)


# ---------------------------------------------------------------- patterns

def test_overlapping_instances_in_one_compound_tool_silently_cut_nothing():
    bad = ops.pattern_holes("linear", n=2, pitch=5, combine="compound")
    good = ops.pattern_holes("linear", n=2, pitch=5, combine="tool_list")
    cb, cg = checks(bad.shape), checks(good.shape)
    assert cb["valid"] and cb["euler_ok"]                    # passes the generic checks...
    assert abs(cb["volume"] - 24000.0) < 1e-6                # ...but nothing was removed
    assert cb["VEFRSH"][4] > 1                               # only dS (and volume) give it away
    assert cg["VEFRSH"][4] == 1 and cg["VEFRSH"][5] == 1     # tool list: one merged slot, genus 1


def test_instance_off_the_part_changes_dH_and_cardinality():
    r = ops.pattern_holes("linear", n=4, pitch=12)
    assert len(r.roles["instance(3).wall"]) == 0 and checks(r.shape)["VEFRSH"][5] == 3


def test_ring_of_overlapping_holes_splits_the_disc():
    r = ops.pattern_holes("circular", n=12)
    assert checks(r.shape)["solids"] == 2


def test_shared_tshape_instances_resolve_separately():
    r = ops.pattern_holes("linear", n=3)
    walls = [r.roles[f"instance({k}).wall"][0] for k in range(3)]
    assert not walls[0].IsSame(walls[1]) and not walls[1].IsSame(walls[2])


# ---------------------------------------------------------------- mirror + clean

def test_mirror_images_and_merge_policy():
    r = ops.mirror(0.0)
    assert r.roles["image(of=E.side(p-q))"] == []              # mirror-plane face is internal after fuse
    rc = ops.mirror(0.0, clean=True)
    with pytest.raises(CardinalityError):
        rc.ledger.resolve("E", "cap", "START", policy="error_on_merge")
    a = rc.ledger.resolve("E", "cap", "START")[0]
    b = rc.ledger.resolve("M", "cap", "START")[0]
    assert a.IsSame(b)                                          # two references now alias one face


def test_clean_history_is_complete_and_bracket_refs_survive():
    rows = {r["case"]: r for r in q4_clean.run_cases()}
    for r in rows.values():
        a = r["audit"]
        assert a["false_deleted"] == a["missed_delete"] == a["modified_not_in_result"] == 0
    br = rows["spike-01 bracket"]
    assert all(v["resolves"] is True for v in br["refs"].values())
    assert br["identity_kept"]["faces"] == "19/19"              # nothing to merge -> sub-shapes untouched
    sw = rows["sweep line+arc"]["refs"]
    assert sw["S.side(from=a-b, along=spine0)"]["last_events"] == ["merged"]
    seq = rows["overlapping holes, sequential (wall split at seam)"]
    assert seq["count_before_clean"]["P.wall(instance1)"] == 2 and seq["refs"]["P.wall(instance1)"]["n"] == 1


# ---------------------------------------------------------------- determinism

@pytest.mark.parametrize("name", ["revolve.full", "chamfer.two_edges", "shell.open_top", "loft.square_to_circle",
                                  "sweep.pipe_open", "draft.4sides", "pattern.circular_holes", "mirror.fuse_clean"])
def test_rebuild_is_byte_identical(name):
    a, b = ops.DEFAULTS[name](), ops.DEFAULTS[name]()
    assert topo.brep_bytes(a.shape) == topo.brep_bytes(b.shape)


def test_offset_join_is_not_byte_deterministic_but_role_geometry_is():
    import q3_determinism as q3
    runs = [ops.shell(-2.0, ()) for _ in range(4)]
    assert len({topo.brep_bytes(r.shape) for r in runs}) > 1
    assert len({q3.role_geom_fingerprint(r) for r in runs}) == 1
    assert len({str(topo.signature(r.shape)) for r in runs}) == 1

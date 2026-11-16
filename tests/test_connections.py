"""Intent tree, parameter dependencies and diagnostics (src/dipm/connections.py; docs/gui.md §2 items 4, 9)."""
from dipm import XY, Design, Profile, intent, plain, centered_on
from dipm.connections import (ancestors, diagnostics, feature_params, intent_tree, minimal_nodes,
                              param_dependencies, params_through_uses, parent_of)
from dipm.sketch import rect_points


def test_parent_and_ancestors():
    assert parent_of("A.P.1") == "A.P" and parent_of("A") == "R" and parent_of("R") is None
    assert ancestors("A.P.1") == ["A.P", "A", "R"]
    assert minimal_nodes(["A.P", "A"]) == ["A.P"] and minimal_nodes(["A.1", "C.1"]) == ["A.1", "C.1"]


def test_param_dependencies_walk_expressions_profiles_and_closures(bracket):
    fp = feature_params(bracket)
    assert fp == {"R.body": ["shelf_depth", "t"], "C.gusset": ["shelf_depth", "t"], "A.P.holes": ["screw"],
                  "A.3.cable": [], "B.1.screw": ["screw"], "R.fillet": ["t"]}
    assert param_dependencies((1, "x", None)) == []


def test_params_through_uses():
    direct = {"a": ["p"], "b": ["q"], "c": []}
    assert params_through_uses(direct, {"b": ["a"], "c": ["b"]}) == {"a": ["p"], "b": ["p", "q"], "c": ["p", "q"]}
    assert params_through_uses({"a": ["p"], "b": []}, {"a": ["b"], "b": ["a"]}) == {"a": ["p"], "b": ["p"]}


def test_bracket_intent_tree(bracket, bracket_build):
    from dipm import intent_store
    t = intent_tree(bracket, bracket_build)
    assert t["roots"] == ["R"] and t["order"] == ["R", "A", "A.P", "A.P.1", "A.P.2", "A.3", "B", "B.1", "C"]
    n = t["nodes"]
    assert n["R"].children == ["A", "B", "C"] and n["A"].children == ["A.P", "A.3"]
    assert n["A"].implicit is False and n["A"].features == ["A.P.holes", "A.3.cable"]
    # NOTES #45 change: the DSL's tags carry no wording when an intent file exists; without the
    # file the label falls back to the intent words, with it the statement wins
    assert n["A.3"].label == "hole"
    assert all(x.status == "ok" for x in n.values())
    plain = intent_store.load(str(bracket.intent_file)).to_plain()
    t2 = intent_tree(bracket, bracket_build, intent=plain)
    assert t2["nodes"]["A.3"].label == "Cable pass-through, centered on the plate"


def test_tree_without_a_build_and_implicit_nodes():
    d = Design("t")
    E = d.extrude("X.Y.body", Profile(XY, rect_points(0.0, 0.0, 10.0, 10.0)), 2.0, tags=intent("X.Y", "skeleton"))
    d.hole("Z.h", E.cap("END"), centered_on(E.cap("END")), plain(2.0))
    t = intent_tree(d)
    assert t["order"] == ["R", "X", "X.Y"] and t["nodes"]["X"].implicit and t["nodes"]["R"].implicit
    assert t["nodes"]["X.Y"].status == "not_built" and t["nodes"]["X.Y"].label == "skeleton"
    diag = diagnostics(d, t, {"X.Y.body": [], "Z.h": ["X.Y.body"]})
    assert diag["no_intent"] == ["Z.h"] and diag["no_feature"] == [] and diag["cross_intent"] == []

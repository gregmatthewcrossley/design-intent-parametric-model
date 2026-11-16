"""The intent file store (src/dipm/intent_store.py; docs/gui.md §7.2 criterion 6)."""
import os
import random
import threading

import pytest

from dipm import intent_store as S
from dipm.fileio import file_sha256

from conftest import EXAMPLE

INTENT = EXAMPLE.with_name("shelf_bracket.intent.yaml")


def test_bracket_file_loads_and_round_trips_byte_identical():
    text = INTENT.read_text(encoding="utf-8")
    doc = S.loads(text)
    assert doc.design == "shelf_bracket"
    assert doc.node_ids() == ["R", "A", "A.P", "A.P.1", "A.P.2", "A.3", "B", "B.1", "C"]
    assert S.dumps(doc) == text                          # canonical input -> byte-identical output
    assert doc.hash == file_sha256(str(INTENT))


def test_canonical_form_is_a_fixed_point_and_orders_keys():
    messy = """# head comment
intents:
  - children:
    - statement: child   # keep me
      id: R.1
    statement: "root"
    id: R
design: x
"""
    once = S.canonical(messy)
    assert once.splitlines()[:4] == ["# head comment", "design: x", "intents:", "  - id: R"]
    assert "# keep me" in once and 'statement: "root"' in once        # comments and quote style kept
    assert S.canonical(once) == once                                    # idempotent


@pytest.mark.parametrize("seed", range(20))
def test_round_trip_property_random_trees(seed):
    rnd = random.Random(seed)
    lines = ["# generated", "design: d", "intents:"]

    def node(nid, depth, indent):
        pad = " " * indent
        lines.append(f"{pad}- id: {nid}")
        lines.append(f"{pad}  statement: {rnd.choice(['Plain text', '\"quoted: yes\"', 'ünïcode ≥ 2×Ø'])}"
                     + (f"  # c{nid}" if rnd.random() < 0.3 else ""))
        if rnd.random() < 0.4:
            lines.append(f"{pad}  checks:")
            lines.append(f"{pad}    - {{id: {nid}.c1, kind: rule, statement: x}}")
        if depth < 3 and rnd.random() < 0.7:
            lines.append(f"{pad}  children:")
            for k in range(rnd.randint(1, 3)):
                node(f"{nid}.{k + 1}", depth + 1, indent + 4)

    node("R", 0, 2)
    text = "\n".join(lines) + "\n"
    canon = S.canonical(text)
    assert S.canonical(canon) == canon
    assert S.loads(canon).node_ids() == S.loads(text).node_ids()


@pytest.mark.parametrize("text, needle", [
    ("design: x\nintents: []\n", "at least one intent"),
    ("design: x\nintents:\n  - id: R\n", "missing required key 'statement'"),
    ("design: x\nintents:\n  - id: R\n    statement: s\n    chekcs: []\n", "unknown key 'chekcs' (did you mean 'checks'?)"),
    ("design: x\nintents:\n  - id: R\n    statement: s\n    checks:\n      - {id: R.c1, kind: analyis, statement: s}\n",
     "file.intents[0] (R).checks[0] (R.c1).kind: must be one of relation, rule, analysis, learned score, live judgment; got 'analyis' (did you mean 'analysis'?)"),
    ("design: x\nintents:\n  - id: R\n    statement: 12\n", "must be text; got a number (quote it to keep it text)"),
    ("design: x\nintents:\n  - id: R\n    statement: s\n    children:\n      - {id: R, statement: t}\n", "id 'R' is used twice"),
    ("design: x\nintents:\n  - id: R x\n    statement: s\n", "is not a valid id"),
    ("design: x\nintents:\n  - id: R\n    statement: [unclosed\n", "line "),
    ("design: x\ndesign: y\nintents:\n  - {id: R, statement: s}\n", "line "),
])
def test_schema_errors_are_readable(text, needle):
    with pytest.raises(S.IntentSchemaError) as e:
        S.loads(text)
    assert any(needle in m for m in e.value.errors), e.value.errors


def test_edit_keeps_comments_order_and_gives_a_minimal_diff(tmp_path):
    p = tmp_path / "x.intent.yaml"
    p.write_text(INTENT.read_text(encoding="utf-8"), encoding="utf-8")
    doc = S.load(str(p))
    S.apply_ops(doc, [{"op": "edit_statement", "id": "A.3", "statement": "Cable pass-through, offset 10 mm above the lower screw"}])
    S.save(doc, base_hash=file_sha256(str(p)))
    before = INTENT.read_text(encoding="utf-8").splitlines()
    after = p.read_text(encoding="utf-8").splitlines()
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert len(before) == len(after) and len(changed) == 1
    assert changed[0][1].strip() == "statement: Cable pass-through, offset 10 mm above the lower screw"
    assert after[0].startswith("# Shelf bracket")


def test_ops_add_delete_move_checks_assumptions():
    doc = S.loads(INTENT.read_text(encoding="utf-8"))
    r = S.apply_ops(doc, [{"op": "add_child", "parent": "B"}])
    assert r == [{"id": "B.2"}]
    assert S.apply_ops(doc, [{"op": "add_child", "parent": "R", "statement": "Mounting hardware"}]) == [{"id": "D"}]
    # dotted ids used only in the DSL are never captured by a new node
    assert S.next_child_id(doc, "B", taken={"B.7"}) == "B.8"
    S.apply_ops(doc, [{"op": "move", "id": "A.3", "parent": "B"}])
    assert dict((i, p) for i, p, _ in doc.nodes())["A.3"] == "B"        # id stable, parent changed
    with pytest.raises(S.IntentOpError, match="subtree"):
        S.apply_op(doc, {"op": "move", "id": "A", "parent": "A.P.1"})
    removed = S.apply_ops(doc, [{"op": "delete", "id": "A"}])[0]["removed"]
    assert removed == ["A", "A.P", "A.P.1", "A.P.2"]
    with pytest.raises(S.IntentOpError, match="root"):
        S.apply_op(doc, {"op": "delete", "id": "R"})
    c = S.apply_ops(doc, [{"op": "add_check", "id": "C", "check": {"kind": "rule", "statement": "t ≥ 3 mm"}}])[0]
    assert c["check_id"] == "C.c1"
    S.apply_ops(doc, [{"op": "edit_check", "id": "C", "check_id": "C.c1", "fields": {"priority": "must"}}])
    assert doc.node_plain("C")["checks"] == [{"id": "C.c1", "kind": "rule", "priority": "must", "statement": "t ≥ 3 mm"}]
    S.apply_ops(doc, [{"op": "remove_check", "id": "C", "check_id": "C.c1"}])
    assert "checks" not in doc.node_plain("C")
    S.apply_ops(doc, [{"op": "edit_assumption", "id": "R", "assumption_id": "R.a1",
                       "fields": {"status": "challenged", "rationale": "shelves get leaned on"}}])
    a1 = doc.node_plain("R")["assumptions"][0]
    assert a1["status"] == "challenged" and a1["rationale"] == "shelves get leaned on"
    text = S.dumps(doc)
    assert S.canonical(text) == text
    with pytest.raises(S.IntentSchemaError, match="did you mean 'challenged'"):   # validated after the ops
        S.apply_ops(S.loads(text), [{"op": "edit_assumption", "id": "R", "assumption_id": "R.a1",
                                     "fields": {"status": "challenge"}}])


def test_atomic_write_and_conflict(tmp_path):
    p = tmp_path / "x.intent.yaml"
    p.write_text(INTENT.read_text(encoding="utf-8"), encoding="utf-8")
    doc = S.load(str(p))
    h0 = doc.hash
    p.write_text(p.read_text(encoding="utf-8").replace("Shelf support", "Shelf support (edited elsewhere)"), encoding="utf-8")
    S.apply_ops(doc, [{"op": "edit_statement", "id": "C", "statement": "Gusset"}])
    with pytest.raises(S.IntentConflict) as e:
        S.save(doc, base_hash=h0)
    assert e.value.current_hash == file_sha256(str(p)) != h0
    assert "edited elsewhere" in p.read_text(encoding="utf-8")            # nothing overwritten
    # concurrent readers never see a partial file: every read parses
    text_a, text_b = S.dumps(S.load(str(p))), S.dumps(doc)
    stop, bad = threading.Event(), []

    def reader():
        while not stop.is_set():
            try:
                S.loads(p.read_text(encoding="utf-8"))
            except Exception as ex:   # noqa: BLE001
                bad.append(ex)

    t = threading.Thread(target=reader)
    t.start()
    for i in range(60):
        S.save(S.loads(text_a if i % 2 else text_b), str(p))
    stop.set()
    t.join()
    assert bad == []
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]


def test_rename_id_in_doc():
    doc = S.loads(INTENT.read_text(encoding="utf-8"))
    S.rename_id_in_doc(doc, "A.P", "A.W")
    ids = doc.ids()
    assert {"A.W", "A.W.1", "A.W.2", "A.W.c1"} <= ids and not any(i.startswith("A.P") for i in ids)

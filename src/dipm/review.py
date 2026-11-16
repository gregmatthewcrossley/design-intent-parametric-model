"""Stale-solution status (docs/gui.md §7.2).

Moving from intent to solution is the learned step, so editing an intent node does not
change geometry: it marks the node's solution **stale** until the designer (or an accepted
proposal) confirms the solution still fits.

* `node_hash(node)`: a hash of a node's own content (statement, checks, assumptions; not its
  children, not its position), over plain data, so it does not depend on the file format.
* `<design>.review.json` records, per node, the hash the designer accepted plus a snapshot of
  that content (so the GUI and Claude can show *what* changed).  Machine-written JSON, stable
  key order, no timestamps; commit it next to the design like the interpretations lock.
* A node is stale if its current hash differs from the recorded one, or it has no record.
* **No review file yet** (NOTES #48 change, iteration 3): nothing is reviewed and nothing is
  written automatically.  The GUI asks once: *mark all reviewed* (writes every node) or
  *review one by one* (writes an empty record, so the prompt does not come back).
* **Accepted items** (`accepted`): model-made items the designer reviewed that do not live in
  the intent file, e.g. an interpretation reading (`slot:<id>` -> the reading accepted).  It
  stays reviewed only while the same reading is chosen.
* **Overrides** (`overrides`, #54): nodes accepted with failing checks ("Accept anyway…"),
  with the failing checks, the reason and the time.  Such a node shows as *reviewed with
  failing checks* until its checks pass.
"""
from __future__ import annotations

import hashlib
import json
import os

from .fileio import atomic_write

SUFFIX = ".review.json"
CONTENT_KEYS = ("statement", "checks", "assumptions")


def path_for(design_file: str) -> str:
    return os.path.splitext(os.path.abspath(design_file))[0] + SUFFIX


def node_content(node: dict) -> dict:
    """The part of a (plain) node that its solution answers to."""
    return {k: node.get(k) or ([] if k != "statement" else "") for k in CONTENT_KEYS}


def node_hash(node: dict) -> str:
    blob = json.dumps(node_content(node), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def plain_nodes(intent_plain: dict) -> dict:
    """id -> plain node (without children) for every node of a plain intent document."""
    out: dict = {}

    def walk(lst):
        for n in lst or []:
            out[n["id"]] = {k: v for k, v in n.items() if k != "children"}
            walk(n.get("children"))

    walk(intent_plain.get("intents"))
    return out


def current_hashes(intent_plain: dict) -> dict:
    return {nid: node_hash(n) for nid, n in plain_nodes(intent_plain).items()}


class ReviewRecord:
    """`<design>.review.json`: {"version": 1, "reviewed": {node id: {"hash", "content"}}}."""

    def __init__(self, path: str, reviewed: dict | None = None, exists: bool = False,
                 accepted: dict | None = None, overrides: dict | None = None):
        self.path = path
        self.reviewed: dict = reviewed or {}
        self.exists = exists
        self.accepted: dict = accepted or {}
        self.overrides: dict = overrides or {}

    @classmethod
    def load(cls, path: str) -> "ReviewRecord":
        if not os.path.exists(path):
            return cls(path, {}, False)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls(path, dict(data.get("reviewed") or {}), True, dict(data.get("accepted") or {}),
                   dict(data.get("overrides") or {}))

    def accept_item(self, key: str, value) -> None:
        self.accepted[key] = value

    def item_reviewed(self, key: str, value) -> bool:
        return key in self.accepted and self.accepted[key] == value

    def override(self, nodes, failing: list, reason: str, at: str, proposal: str = "") -> None:
        for n in nodes:
            self.overrides[n] = {"failing": list(failing), "reason": reason, "at": at,
                                 **({"proposal": proposal} if proposal else {})}

    def baseline(self, intent_plain: dict) -> None:
        """Accept the current content of every node as reviewed (in memory).  Used only for the
        designer's explicit "mark all reviewed" (never automatically since iteration 3)."""
        if self.exists or self.reviewed:
            return
        for nid, n in plain_nodes(intent_plain).items():
            self.reviewed[nid] = {"hash": node_hash(n), "content": node_content(n)}

    def mark(self, intent_plain: dict, ids) -> list:
        """Record the current content of `ids` as reviewed.  Returns the ids recorded."""
        nodes = plain_nodes(intent_plain)
        done = []
        for nid in ids:
            if nid in nodes:
                self.reviewed[nid] = {"hash": node_hash(nodes[nid]), "content": node_content(nodes[nid])}
                done.append(nid)
        return done

    def forget_missing(self, intent_plain: dict) -> None:
        nodes = plain_nodes(intent_plain)
        for nid in [k for k in self.reviewed if k not in nodes]:
            del self.reviewed[nid]

    def text(self) -> str:
        data = {"version": 1, "reviewed": {k: self.reviewed[k] for k in sorted(self.reviewed)}}
        if self.accepted:
            data["accepted"] = {k: self.accepted[k] for k in sorted(self.accepted)}
        if self.overrides:
            data["overrides"] = {k: self.overrides[k] for k in sorted(self.overrides)}
        return json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + "\n"

    def save(self) -> None:
        atomic_write(self.path, self.text())
        self.exists = True

    def stale(self, intent_plain: dict) -> dict:
        """node id -> {hash, reviewed_hash, reviewed (content snapshot or None), changed (fields)}
        for every stale node."""
        out = {}
        for nid, n in plain_nodes(intent_plain).items():
            h = node_hash(n)
            rec = self.reviewed.get(nid)
            if rec is not None and rec.get("hash") == h:
                continue
            before = (rec or {}).get("content")
            cur = node_content(n)
            changed = [k for k in CONTENT_KEYS if before is None or before.get(k) != cur.get(k)]
            out[nid] = {"hash": h, "reviewed_hash": (rec or {}).get("hash"), "reviewed": before,
                        "current": cur, "changed": changed, "new": rec is None}
        return out

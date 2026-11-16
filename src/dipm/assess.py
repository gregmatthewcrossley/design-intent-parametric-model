"""One honest assessment of a build: context, print orientation, intent checks with margins,
tiered status and provenance (docs/gui.md §8.2 3E.1–3E.6, 3E.10).

`assess()` is what the CLI report, `dipm serve`, proposal evaluations and `dipm mcp` all call
after `Design.build`, so they cannot disagree.  It never writes a file; callers that may
(the server, `dipm interpret`) pass a `ResolutionRecord` and save it when `record_changed`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import packs
from .checks import evaluate_checks, tiered_status
from .resolution import (ResolutionRecord, context_items, context_summary, context_values, orientation_for,
                         path_for as record_path_for, record_context)


@dataclass
class Assessment:
    context: dict                  # key -> {value, made_by, status, reviewed, source}
    context_summary: str
    orientation: dict | None
    appearance: dict | None
    checks: list                   # checks.CheckResult
    status: dict                   # checks.tiered_status
    record_changed: bool = False
    notes: list = field(default_factory=list)


def intent_for(design, design_path: str | None = None) -> dict | None:
    from . import intent_store
    path = design.intent_file or (intent_store.path_for(design_path) if design_path else None)
    if not path or not os.path.exists(path):
        return None
    try:
        return intent_store.load(path).to_plain()
    except intent_store.IntentSchemaError:
        return None


def defaults_build(design, build):
    """The build at the design's defaults (the orientation key and inference use it)."""
    if build is not None and build.params == design.resolve_params({}):
        return build
    try:
        return design.build(on_fail="record")
    except Exception:   # noqa: BLE001
        return None


def assess(design, build, intent_plain: dict | None = None, record: ResolutionRecord | None = None,
           reviewed_nodes: set | None = None, key_build=None, force_orientation: bool = False) -> Assessment:
    items = context_items((intent_plain or {}).get("context"))
    values = context_values(items)
    changed = False
    if record is not None:
        changed |= record_context(record, items)
        record.data["design"] = design.name
    kb = key_build if key_build is not None else defaults_build(design, build)
    orient, ch = orientation_for(build, intent_plain, record, values, key_build=kb, force=force_orientation)
    changed |= ch
    checks = evaluate_checks(design, build, intent_plain, values, orient, reviewed_nodes)
    status = tiered_status(build, checks)
    app = packs.appearance(values)
    if app is not None and orient is not None:
        app["build_direction"] = orient["up"]
        app["orientation_reviewed"] = bool(orient.get("reviewed"))
    return Assessment(items, context_summary(items), orient, app, checks, status, changed)


def assess_file(design, build, design_path: str, write_record: bool = False, force_orientation: bool = False):
    """CLI / MCP convenience: read the intent file and the resolution record next to the design."""
    from .review import ReviewRecord, path_for as review_path
    intent = intent_for(design, design_path)
    rec = ResolutionRecord.load(record_path_for(design_path))
    review = ReviewRecord.load(review_path(design_path))
    reviewed = set(review.reviewed) - set(review.stale(intent)) if intent else set()
    a = assess(design, build, intent, rec, reviewed, force_orientation=force_orientation)
    if write_record and a.record_changed:
        rec.save()
    return a, rec

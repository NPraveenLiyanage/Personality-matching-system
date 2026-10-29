"""Rebuild a full evidence-pipeline result from the stored stage outputs of a run, with no model call.

Uses the stored extraction records and the stored raw assessor rows, applies the CURRENT verifier and ranker, and returns the
supported list, the labelled exploration list, the verification log and the final class of every area. Used by the pilot app
(instant recorded examples, and the all-area classes that annotate the baseline engines' lists) and by a consistency test.
"""
from __future__ import annotations

from dataclasses import fields

from . import rank, verify
from .schema import EvidenceRecord

_FIELDS = {f.name for f in fields(EvidenceRecord)}


def records_from_dicts(dicts: list[dict]) -> list[EvidenceRecord]:
    return [EvidenceRecord(**{k: v for k, v in d.items() if k in _FIELDS}) for d in dicts]


def rebuild(stages: dict, defs: dict, regulated: dict | None = None) -> dict:
    """stages: the `stages` dict of an engine result / a benchmark run entry (needs extraction.records and assessment.raw_rows)."""
    ex, asm = stages.get("extraction") or {}, stages.get("assessment") or {}
    records = records_from_dicts(ex.get("records") or [])
    raw = asm.get("raw_rows")
    if not records or not raw:
        return dict(supported=[], exploration=[], validation_log=[], classes={}, records=records, ok=False)
    rows = {r["area_id"]: r for r in raw}
    for r in asm.get("reask_raw_rows") or []:          # a targeted re-ask replaces the first answer for those areas
        rows[r["area_id"]] = r
    area_ids = list(defs["areas"])
    v = verify.verify(dict(assessments=[rows[a] for a in area_ids if a in rows]), records, area_ids, regulated)
    if v.errors:
        return dict(supported=[], exploration=[], validation_log=[], classes={}, records=records, ok=False, errors=v.errors)
    names = {aid: d["name"] for aid, d in defs["areas"].items()}
    out = rank.rank(v.rows, records, names)
    out.update(validation_log=[dict(area_id=a.area_id, original_class=a.original_class, final_class=a.support_class,
                                    changes=a.changes) for a in v.rows.values() if a.changes],
               classes={aid: a.support_class for aid, a in v.rows.items()}, records=records, ok=True)
    return out

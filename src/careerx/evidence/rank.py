"""Deterministic ranking and locally built explanations from validated assessment rows.

No model text is used for ordering. The supported list can be shorter than 10 (or empty); areas that are only domain exposure or a
stated interest go to a separate, labelled exploration list.
"""
from __future__ import annotations

from .schema import EvidenceRecord
from .verify import AreaAssessment

_TIER = {"direct": 0, "transferable": 1}
_RECENCY = {"recent": 0, "mid": 1, "old": 2, "unknown": 3}
EXPLORATION_LABEL = {"domain_exposure_only": "Industry exposure only: the work served this field, but the evidence does not "
                                              "show doing this occupation's work",
                     "interest_only": "Stated interest: not yet backed by experience",
                     "in_progress_study": "Study in progress: a pathway to explore, not yet established practice"}


def _best_recency(a: AreaAssessment, by_eid: dict) -> int:
    return min((_RECENCY.get(by_eid[e].dates.get("recency", "unknown"), 3) for e, _ in a.evidence), default=3)


def sort_key(a: AreaAssessment, by_eid: dict):
    return (_TIER[a.support_class], -(a.relevance or 0), _best_recency(a, by_eid), -len({e for e, _ in a.evidence}), a.area_id)


def explain(a: AreaAssessment, by_eid: dict) -> str:
    """Explanation assembled from the cited records (role, dates, quote), not from model prose."""
    parts = []
    for eid, basis in a.evidence[:3]:
        r: EvidenceRecord = by_eid[eid]
        who = r.role or (r.qualification or {}).get("subject") or r.evidence_type.replace("_", " ")
        when = " - ".join(x for x in (r.dates.get("start"), r.dates.get("end")) if x)
        parts.append(f'{who}{f" ({when})" if when else ""}: "{r.quote}"')
    lead = {"direct": "Direct evidence", "transferable": "Transferable evidence"}.get(a.support_class, "Context")
    return f"{lead} - " + " | ".join(parts) if parts else lead


def rank(rows: dict[str, AreaAssessment], records: list[EvidenceRecord], names: dict[str, str]) -> dict:
    by_eid = {r.evidence_id: r for r in records}
    sup = sorted((a for a in rows.values() if a.support_class in _TIER), key=lambda a: sort_key(a, by_eid))
    exp = sorted((a for a in rows.values() if a.support_class in EXPLORATION_LABEL),
                 key=lambda a: (a.support_class != "interest_only", a.area_id))

    def item(i: int | None, a: AreaAssessment) -> dict:
        return dict(rank=i, area_id=a.area_id, name=names.get(a.area_id, a.area_id), support_class=a.support_class,
                    relevance=a.relevance, evidence_ids=[e for e, _ in a.evidence], explanation=explain(a, by_eid),
                    qualification_gaps=a.qualification_gaps, uncertainty=a.uncertainty, status=a.status,
                    label=EXPLORATION_LABEL.get(a.support_class))
    return dict(supported=[item(i, a) for i, a in enumerate(sup, 1)], exploration=[item(None, a) for a in exp])

"""Backend validation of the assessment rows against the validated evidence records.

Enforces STRUCTURE, not semantics: ids, types, ranges, that cited records exist, that their type/contribution/negation/basis can
legitimately support the claimed class, and (for regulated occupations) that a cited record's role or qualification subject matches
a reviewed term list. Whether the evidence really supports the area in meaning is measured by the benchmark and the manual audit,
not guaranteed here. Rows are only ever downgraded, never strengthened, and every change is logged on the row.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .assess import BASES, POSITIVE, SUPPORT_CLASSES, UNCERTAINTY
from .schema import EvidenceRecord

_NO_SUPPORT_TYPES = ("listed_skill_only", "stated_interest")
_BASIS_FIELD_OK = {
    "role": lambda r: bool(r.role),
    "actions": lambda r: bool(r.candidate_actions or r.candidate_responsibilities),
    "qualification": lambda r: bool(r.qualification and (r.qualification.get("subject") or r.qualification.get("level"))),
    "tools": lambda r: bool(r.tools_methods),
}


@dataclass
class AreaAssessment:
    area_id: str
    support_class: str
    original_class: str
    relevance: int | None
    evidence: list[tuple[str, str]]          # (evidence_id, basis) kept after validation
    rationale: str | None
    qualification_gaps: list[str]
    uncertainty: str
    status: str = "accepted"                 # accepted | repaired
    changes: list[str] = field(default_factory=list)


@dataclass
class Verified:
    rows: dict[str, AreaAssessment] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)       # response-level problems (missing/duplicate ids, bad shape)
    rejected: list[dict] = field(default_factory=list)    # rows that could not be parsed at all

    @property
    def status(self) -> str:
        if self.errors:
            return "failed"
        return "repaired" if any(r.status == "repaired" for r in self.rows.values()) or self.rejected else "accepted"


def _matches(terms: list[str], text: str) -> bool:
    return any(re.search(r"\b" + re.escape(t.strip().lower()), text.lower()) for t in terms if t.strip())


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def verify(data, records: list[EvidenceRecord], area_ids: list[str], regulated: dict | None = None) -> Verified:
    out = Verified()
    if not isinstance(data, dict) or not isinstance(data.get("assessments"), list):
        out.errors.append("response is not an object with an 'assessments' list")
        return out
    regulated = regulated or {}
    by_eid = {r.evidence_id: r for r in records}
    seen: dict[str, dict] = {}
    for i, raw in enumerate(data["assessments"]):
        aid = raw.get("area_id") if isinstance(raw, dict) else None
        if not isinstance(aid, str) or aid not in area_ids:
            out.rejected.append(dict(index=i, reasons=[f"invalid area_id {aid!r}"]))
        elif aid in seen:
            out.errors.append(f"duplicate row for {aid}")
        else:
            seen[aid] = raw
    missing = [a for a in area_ids if a not in seen]
    if missing:
        out.errors.append(f"missing rows for {len(missing)} areas: {', '.join(missing[:8])}")
    if out.errors:
        return out
    for aid in area_ids:
        row, reasons = _check_row(aid, seen[aid], by_eid, regulated.get(aid))
        if row is None:
            out.errors.append(f"{aid}: {'; '.join(reasons)}")
        else:
            out.rows[aid] = row
    return out


def _check_row(aid: str, raw: dict, by_eid: dict, reg_terms: list[str] | None):
    miss = [k for k in ("support_class", "relevance", "evidence", "rationale", "qualification_gaps", "uncertainty") if k not in raw]
    if miss:
        return None, [f"missing fields {miss}"]
    cls = raw["support_class"]
    if cls not in SUPPORT_CLASSES:
        return None, [f"invalid support_class {cls!r}"]
    if raw["uncertainty"] not in UNCERTAINTY:
        return None, [f"invalid uncertainty {raw['uncertainty']!r}"]
    if not (isinstance(raw["evidence"], list) and all(isinstance(e, dict) for e in raw["evidence"])):
        return None, ["evidence must be a list of objects"]
    if not (isinstance(raw["qualification_gaps"], list) and all(isinstance(g, str) for g in raw["qualification_gaps"])):
        return None, ["qualification_gaps must be a list of strings"]
    if raw["rationale"] is not None and not isinstance(raw["rationale"], str):
        return None, ["rationale must be a string or null"]
    rel = raw["relevance"]
    if rel is not None and not (_is_int(rel) and 0 <= rel <= 4):
        return None, [f"relevance must be an integer 0-4 or null, got {rel!r}"]

    changes: list[str] = []
    ev: list[tuple[str, str]] = []
    for e in raw["evidence"]:
        eid, basis = e.get("evidence_id"), e.get("basis")
        if eid not in by_eid:
            changes.append(f"dropped unknown evidence id {eid!r}")
        elif basis not in BASES:
            changes.append(f"dropped citation {eid} with invalid basis {basis!r}")
        elif (eid, basis) not in ev:
            ev.append((eid, basis))

    final = cls
    if cls in POSITIVE:
        valid = []
        for eid, basis in ev:
            r = by_eid[eid]
            if basis in ("domain", "interest"):
                changes.append(f"citation {eid} (basis {basis}) cannot support {cls}")
            elif r.evidence_type in _NO_SUPPORT_TYPES:
                changes.append(f"citation {eid} is a {r.evidence_type} record and cannot support {cls}")
            elif r.negation:
                changes.append(f"citation {eid} is a negated statement")
            elif r.contribution not in ("own", "shared"):
                changes.append(f"citation {eid} has contribution {r.contribution!r}; own or shared needed")
            elif not _BASIS_FIELD_OK[basis](r):
                changes.append(f"citation {eid} has no {basis} content on the record")
            else:
                valid.append((eid, basis))
        if reg_terms and valid:
            ok = [(e, b) for e, b in valid if _matches(reg_terms, " ".join(filter(None, [
                by_eid[e].role, (by_eid[e].qualification or {}).get("subject")])))]
            if not ok:
                changes.append("regulated occupation: no cited role or qualification subject matches the reviewed terms")
            valid = ok
        if not valid:
            final = _downgrade(ev, by_eid)
            changes.append(f"downgraded {cls} -> {final}: no valid supporting citation left")
            if final != "domain_exposure_only":
                ev = []
        else:
            ev = valid
    elif cls == "interest_only":
        ev = [(e, b) for e, b in ev if by_eid[e].evidence_type == "stated_interest"]
        if not ev:
            final = "unsupported"
            changes.append("downgraded interest_only -> unsupported: no stated_interest record cited")
    elif cls == "domain_exposure_only":
        ev = [(e, b) for e, b in ev if by_eid[e].domain_context]
        if not ev:
            final = "unsupported"
            changes.append("downgraded domain_exposure_only -> unsupported: no cited record has a domain_context")
    else:                                      # unsupported / insufficient_info carry no evidence
        if ev:
            changes.append(f"cleared evidence on a {cls} row")
        ev = []

    if final in POSITIVE:
        if rel is None:
            rel = 1
            changes.append("relevance missing on a supported row; set to the lowest value 1")
        # a downgrade from direct to transferable is never made silently: classes only move down when no valid citation remains
    else:
        if rel is not None:
            changes.append("relevance cleared on a non-supported row")
        rel = None
    rationale = raw["rationale"] if final in POSITIVE + ("domain_exposure_only",) else None
    gaps = raw["qualification_gaps"] if final in POSITIVE else []
    return AreaAssessment(aid, final, cls, rel, ev, rationale, gaps, raw["uncertainty"],
                          status="repaired" if changes else "accepted", changes=changes), []


def _downgrade(ev: list[tuple[str, str]], by_eid: dict) -> str:
    cited = [by_eid[e] for e, _ in ev]
    if any(r.domain_context for r in cited):
        return "domain_exposure_only"
    if cited and all(r.evidence_type in _NO_SUPPORT_TYPES for r in cited):
        return "insufficient_info"
    return "unsupported"

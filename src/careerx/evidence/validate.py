"""Backend validation of the extraction response.

Each record ends up accepted, repaired (with the list of changes) or rejected (with reasons). Repairs only ever weaken a claim
(drop an unsupported date, downgrade a contribution); nothing is silently strengthened. Quote existence is checked here;
whether the evidence semantically supports a career area is a later stage (verify.py).
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field

from .schema import (CONTRIBUTIONS, EVIDENCE_TYPES, MAX_QUOTE_WORDS, MIN_QUOTE_CHARS, MIN_QUOTE_WORDS, RECENCY,
                     REFERENCE_DATE, EvidenceRecord, Passage)

_TYPOGRAPHY = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
                             "−": "-", " ": " ", "•": "-", "·": "-"})
_SECTION_TYPE = {"education": "education", "certifications": "certification"}   # section headings come from ingest, not the model
_ACTIVITY_TYPES = ("employment", "internship", "project", "volunteering", "research", "applied_skill")
_REQUIRED = ("passage_id", "quote", "evidence_type", "role", "candidate_actions", "candidate_responsibilities",
             "tools_methods", "domain_context", "qualification", "contribution", "dates", "negation", "ambiguities",
             "missing_info")


def norm(s: str) -> str:
    """Matching form for quotes: NFKC, typographic quotes/dashes/bullets folded, whitespace collapsed, case-insensitive."""
    s = unicodedata.normalize("NFKC", s).translate(_TYPOGRAPHY)
    return re.sub(r"\s+", " ", s).strip().casefold()


@dataclass
class Outcome:
    records: list[EvidenceRecord] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)      # {index, reasons, raw_quote}
    errors: list[str] = field(default_factory=list)         # response-level problems

    @property
    def status(self) -> str:
        if self.errors or (not self.records and self.rejected):
            return "rejected"
        if self.rejected or any(r.status == "repaired" for r in self.records):
            return "repaired"
        return "accepted"


def recency_from_end(end: str | None, ref=REFERENCE_DATE) -> str:
    """recent (<=5 years before the reference date or ongoing), mid (<=10), old, else unknown. Computed locally, never by the model."""
    if not end:
        return "unknown"
    if re.search(r"\b(present|current|now|ongoing|to date)\b", end, re.I):
        return "recent"
    years = re.findall(r"\b(?:19|20)\d{2}\b", end)
    if not years:
        return "unknown"
    age = ref.year - int(years[-1])
    return "recent" if age <= 5 else "mid" if age <= 10 else "old"


def _ungrounded(actions: list[str], text_n: str) -> list[str]:
    """Actions whose longer words mostly do not occur in the cited passage (possible invention)."""
    bad = []
    for a in actions:
        w = [x for x in re.findall(r"[a-z]{4,}", norm(a))]
        if w and sum(x[:5] in text_n for x in w) / len(w) < 0.5:
            bad.append(a)
    return bad


def _is_str_list(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def validate_response(data, passages: list[Passage]) -> Outcome:
    out = Outcome()
    if not isinstance(data, dict):
        out.errors.append("response is not a JSON object")
        return out
    recs = data.get("records")
    if not isinstance(recs, list):
        out.errors.append("'records' missing or not a list")
        return out
    by_id = {p.id: p for p in passages if not p.is_reference}
    refs = {p.id for p in passages if p.is_reference}
    normed = {pid: norm(p.sent_text) for pid, p in by_id.items()}
    n = 0
    for i, raw in enumerate(recs):
        rec, reasons = _check_record(raw, by_id, refs, normed)
        if rec is None:
            out.rejected.append(dict(index=i, reasons=reasons, raw_quote=str(raw.get("quote", ""))[:120] if isinstance(raw, dict) else ""))
            continue
        n += 1
        rec.evidence_id = f"E{n:03d}"
        out.records.append(rec)
    return out


def _check_record(raw, by_id: dict, refs: set, normed: dict):
    if not isinstance(raw, dict):
        return None, ["record is not an object"]
    changes: list[str] = []
    flags: list[str] = []
    missing = [k for k in _REQUIRED if k not in raw]
    if missing:
        return None, [f"missing fields: {', '.join(missing)}"]
    extra = [k for k in raw if k not in _REQUIRED]
    if extra:
        changes.append(f"dropped unknown fields: {', '.join(sorted(extra))}")

    reasons = []
    if not isinstance(raw["passage_id"], str):
        return None, ["passage_id is not a string"]
    if not isinstance(raw["quote"], str):
        return None, ["quote is not a string"]
    if raw["evidence_type"] not in EVIDENCE_TYPES:
        reasons.append(f"invalid evidence_type {raw['evidence_type']!r}")
    if raw["contribution"] not in CONTRIBUTIONS:
        reasons.append(f"invalid contribution {raw['contribution']!r}")
    for k in ("role", "domain_context"):
        if raw[k] is not None and not isinstance(raw[k], str):
            reasons.append(f"{k} must be string or null")
    for k in ("candidate_actions", "candidate_responsibilities", "tools_methods", "ambiguities", "missing_info"):
        if not _is_str_list(raw[k]):
            reasons.append(f"{k} must be a list of strings")
    if not isinstance(raw["negation"], bool):
        reasons.append("negation must be a boolean")
    q = raw["qualification"]
    if q is not None and not (isinstance(q, dict) and set(q) == {"subject", "level"}
                              and all(v is None or isinstance(v, str) for v in q.values())):
        reasons.append("qualification must be null or {subject, level} strings/null")
    d = raw["dates"]
    if not (isinstance(d, dict) and set(d) == {"start", "end", "duration_months", "recency"}):
        reasons.append("dates must have exactly start, end, duration_months, recency")
    else:
        if any(d[k] is not None and not isinstance(d[k], str) for k in ("start", "end")):
            reasons.append("dates.start/end must be string or null")
        if d["duration_months"] is not None and not (_is_num(d["duration_months"]) and 0 <= d["duration_months"] <= 1200):
            reasons.append("dates.duration_months must be a finite number 0-1200 or null")
        if d["recency"] not in RECENCY:
            reasons.append(f"invalid recency {d['recency']!r}")
    if reasons:
        return None, reasons

    pid = raw["passage_id"]
    if pid in refs:
        return None, [f"passage {pid} is a References passage; referees' details are not the participant's evidence"]
    qn = norm(raw["quote"])
    words = len(raw["quote"].split())
    if words < MIN_QUOTE_WORDS or len(qn) < MIN_QUOTE_CHARS:
        return None, [f"quote too short (<{MIN_QUOTE_WORDS} words or <{MIN_QUOTE_CHARS} chars)"]
    if words > MAX_QUOTE_WORDS:
        return None, [f"quote longer than {MAX_QUOTE_WORDS} words"]
    if pid not in by_id:
        found = [p for p, t in normed.items() if qn in t]
        if len(found) == 1:
            changes.append(f"passage_id {pid!r} unknown; quote found only in {found[0]}")
            pid = found[0]
        else:
            return None, [f"unknown passage_id {pid!r}"]
    elif qn not in normed[pid]:
        found = [p for p, t in normed.items() if qn in t]
        if len(found) == 1:
            changes.append(f"quote not in {pid}; found only in {found[0]}, passage_id corrected")
            pid = found[0]
        else:
            return None, [f"quote not found in cited passage {pid}" + (" (found in several others)" if found else "")]

    p = by_id[pid]
    text_n = norm(p.sent_text)
    dates = dict(d)
    for k in ("start", "end"):
        if dates[k]:
            years = re.findall(r"\b(?:19|20)\d{2}\b", dates[k])
            if years and any(y not in text_n for y in years):
                changes.append(f"dates.{k} {dates[k]!r} not in passage; set to null")
                dates[k] = None
    recency = recency_from_end(dates["end"])
    if recency != dates["recency"]:
        changes.append(f"recency recomputed from end date: {recency!r} (model said {dates['recency']!r})")
        dates["recency"] = recency
    contribution = raw["contribution"]
    if (contribution == "own" and raw["evidence_type"] in _ACTIVITY_TYPES
            and not raw["candidate_actions"] and not raw["candidate_responsibilities"]):
        changes.append("contribution 'own' without any listed action; downgraded to 'unknown'")
        contribution = "unknown"
    etype = raw["evidence_type"]
    if q and (q.get("subject") or q.get("level")) and etype in ("listed_skill_only", "applied_skill") and p.section in _SECTION_TYPE:
        changes.append(f"evidence_type {etype!r} -> {_SECTION_TYPE[p.section]!r}: a qualification stated in the {p.section} section")
        etype = _SECTION_TYPE[p.section]
    if etype == "listed_skill_only" and raw["candidate_actions"]:
        flags.append("listed_skill_only record lists actions; check it is not applied evidence")
    if q and etype not in ("education", "certification"):
        flags.append("qualification set on a non-education/certification record")
    if raw["negation"] and contribution == "own":
        flags.append("negated statement marked as own contribution")
    if p.section in ("summary", "header") and etype in _ACTIVITY_TYPES + ("education", "certification"):
        flags.append("from the summary section: a self-description to corroborate, not primary evidence")
    bad = _ungrounded(raw["candidate_actions"] + raw["candidate_responsibilities"], text_n)
    if bad:
        flags.append("actions not grounded in the passage: " + "; ".join(bad[:3]))
    unseen = [t for t in raw["tools_methods"] if norm(t) not in text_n]
    if unseen:
        flags.append("tools not literally in passage: " + ", ".join(unseen[:5]))

    rec = EvidenceRecord(
        evidence_id="", passage_id=pid, section=p.section, page=p.page, quote=raw["quote"].strip(),
        evidence_type=etype, role=raw["role"], candidate_actions=list(raw["candidate_actions"]),
        candidate_responsibilities=list(raw["candidate_responsibilities"]), tools_methods=list(raw["tools_methods"]),
        domain_context=raw["domain_context"], qualification=dict(q) if q else None, contribution=contribution,
        dates=dates, negation=raw["negation"], ambiguities=list(raw["ambiguities"]), missing_info=list(raw["missing_info"]),
        status="repaired" if changes else "accepted", changes=changes, flags=flags)
    return rec, []

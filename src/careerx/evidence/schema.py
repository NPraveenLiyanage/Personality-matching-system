"""Evidence record schema (evidence_v1): enums, the strict JSON Schema sent to the model, and the dataclasses."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

SCHEMA_VERSION = "evidence_v1"
REFERENCE_DATE = date(2026, 10, 15)   # mirrors careerx.pipeline.REFERENCE_DATE (a test keeps them equal); recency is computed from it, not by the model

EVIDENCE_TYPES = ("employment", "internship", "project", "education", "certification", "volunteering",
                  "research", "applied_skill", "listed_skill_only", "stated_interest")
CONTRIBUTIONS = ("own", "shared", "team_only", "unknown")
RECENCY = ("recent", "mid", "old", "unknown")

MIN_QUOTE_WORDS = 2
MIN_QUOTE_CHARS = 8
MAX_QUOTE_WORDS = 40


def _nullable(t: str) -> dict:
    return {"type": [t, "null"]}


_STRS = {"type": "array", "items": {"type": "string"}}

RECORD_SCHEMA = {
    "type": "object",
    "properties": {
        "passage_id": {"type": "string"},
        "quote": {"type": "string"},
        "evidence_type": {"type": "string", "enum": list(EVIDENCE_TYPES)},
        "role": _nullable("string"),
        "candidate_actions": _STRS,
        "candidate_responsibilities": _STRS,
        "tools_methods": _STRS,
        "domain_context": _nullable("string"),
        "qualification": {
            "type": ["object", "null"],
            "properties": {"subject": _nullable("string"), "level": _nullable("string")},
            "required": ["subject", "level"], "additionalProperties": False},
        "contribution": {"type": "string", "enum": list(CONTRIBUTIONS)},
        "dates": {
            "type": "object",
            "properties": {"start": _nullable("string"), "end": _nullable("string"),
                           "duration_months": _nullable("number"),
                           "recency": {"type": "string", "enum": list(RECENCY)}},
            "required": ["start", "end", "duration_months", "recency"], "additionalProperties": False},
        "negation": {"type": "boolean"},
        "ambiguities": _STRS,
        "missing_info": _STRS,
    },
    "required": ["passage_id", "quote", "evidence_type", "role", "candidate_actions", "candidate_responsibilities",
                 "tools_methods", "domain_context", "qualification", "contribution", "dates", "negation",
                 "ambiguities", "missing_info"],
    "additionalProperties": False,
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {"records": {"type": "array", "items": RECORD_SCHEMA}, "extraction_notes": _STRS},
    "required": ["records", "extraction_notes"],
    "additionalProperties": False,
}


@dataclass
class Passage:
    id: str
    section: str
    page: int | None
    text: str                 # original extracted text
    sent_text: str            # redacted text the model sees; quotes are validated against this
    is_reference: bool = False


@dataclass
class EvidenceRecord:
    evidence_id: str          # assigned locally (E001...), never taken from the model
    passage_id: str
    section: str
    page: int | None
    quote: str
    evidence_type: str
    role: str | None
    candidate_actions: list[str]
    candidate_responsibilities: list[str]
    tools_methods: list[str]
    domain_context: str | None
    qualification: dict | None
    contribution: str
    dates: dict
    negation: bool
    ambiguities: list[str]
    missing_info: list[str]
    status: str = "accepted"                      # accepted | repaired
    changes: list[str] = field(default_factory=list)   # what a repair altered
    flags: list[str] = field(default_factory=list)     # non-blocking review flags

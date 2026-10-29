"""Stage 2: validated evidence records + area definitions -> one assessment row per area (model call; validation is in verify.py).

The assessor sees only the validated records, the extraction warnings and the area definitions. It never sees the raw CV or any
personality data.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from .schema import EvidenceRecord

PROMPT_PATH = Path(__file__).with_name("assess_v2.md")
PROMPT_VERSION = "assess_v2"
DEFINITIONS_PATH = Path(__file__).resolve().parents[3] / "data" / "processed" / "area_definitions_v1.yaml"
REGULATED_PATH = Path(__file__).resolve().parents[3] / "data" / "processed" / "regulated_areas_v1.yaml"

SUPPORT_CLASSES = ("direct", "transferable", "domain_exposure_only", "interest_only", "in_progress_study", "unsupported",
                   "insufficient_info")
POSITIVE = ("direct", "transferable")
BASES = ("role", "actions", "qualification", "tools", "domain", "interest")
UNCERTAINTY = ("low", "medium", "high")

_STRS = {"type": "array", "items": {"type": "string"}}
ROW_SCHEMA = {
    "type": "object",
    "properties": {
        "area_id": {"type": "string"},
        "support_class": {"type": "string", "enum": list(SUPPORT_CLASSES)},
        "relevance": {"type": ["integer", "null"]},
        "evidence": {"type": "array", "items": {
            "type": "object",
            "properties": {"evidence_id": {"type": "string"}, "basis": {"type": "string", "enum": list(BASES)}},
            "required": ["evidence_id", "basis"], "additionalProperties": False}},
        "rationale": {"type": ["string", "null"]},
        "qualification_gaps": _STRS,
        "uncertainty": {"type": "string", "enum": list(UNCERTAINTY)},
    },
    "required": ["area_id", "support_class", "relevance", "evidence", "rationale", "qualification_gaps", "uncertainty"],
    "additionalProperties": False,
}
RESPONSE_SCHEMA = {"type": "object",
                   "properties": {"assessments": {"type": "array", "items": ROW_SCHEMA}, "notes": _STRS},
                   "required": ["assessments", "notes"], "additionalProperties": False}


def load_definitions(path=None) -> dict:
    return yaml.safe_load(Path(path or DEFINITIONS_PATH).read_text(encoding="utf-8"))


def load_regulated(path=None) -> dict:
    return yaml.safe_load(Path(path or REGULATED_PATH).read_text(encoding="utf-8"))["areas"]


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def record_view(r: EvidenceRecord) -> dict:
    return dict(evidence_id=r.evidence_id, evidence_type=r.evidence_type, section=r.section, role=r.role,
                actions=r.candidate_actions, responsibilities=r.candidate_responsibilities, tools=r.tools_methods,
                domain_context=r.domain_context, qualification=r.qualification, contribution=r.contribution,
                dates=r.dates, negation=r.negation, quote=r.quote)


def build_reask_user(records: list[EvidenceRecord], defs: dict, area_ids: list[str]) -> str:
    """Targeted second pass: only rows that claimed direct/transferable support without citing any evidence."""
    areas = [dict(area_id=a, name=defs["areas"][a]["name"], definition=defs["areas"][a]["definition"],
                  typical_activities=defs["areas"][a]["typical_activities"],
                  evidence_examples=defs["areas"][a]["evidence_examples"],
                  qualification_gaps=defs["areas"][a]["qualification_gaps"],
                  **({"scope_note": defs["areas"][a]["reviewer_scope_note"]} if defs["areas"][a].get("reviewer_scope_note") else {}))
             for a in area_ids]
    return json.dumps(dict(
        instruction=("In your previous answer these areas were marked direct or transferable but cited no evidence_id. A claim "
                     "without a citation is rejected. For each area below, either cite the supporting records (evidence_id with "
                     "basis) or change support_class to the class the records justify. Return one row per area listed."),
        records=[record_view(r) for r in records], warnings=[], areas=areas), ensure_ascii=False)


def build_user(records: list[EvidenceRecord], warnings: list[dict], defs: dict, use_confusions: bool = False) -> str:
    """use_confusions is off by default: the contextual-confusion lists are kept for reviewers and for a separate ablation."""
    areas = []
    for aid, d in defs["areas"].items():
        a = dict(area_id=aid, name=d["name"], definition=d["definition"], typical_activities=d["typical_activities"],
                 evidence_examples=d["evidence_examples"], qualification_gaps=d["qualification_gaps"])
        if d.get("reviewer_scope_note"):
            a["scope_note"] = d["reviewer_scope_note"]
        if use_confusions:
            a["common_contextual_confusions"] = d["common_contextual_confusions"]
        areas.append(a)
    return json.dumps(dict(records=[record_view(r) for r in records], warnings=[w["code"] for w in warnings], areas=areas),
                      ensure_ascii=False)

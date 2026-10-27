"""CV passages -> validated evidence records. The chat function is injected so tests run offline.

`chat(system, user, schema, cfg)` returns a ChatResult (or a plain string, wrapped). Nothing here raises for a bad model answer:
malformed, truncated or empty responses end as status "failed" with the reason recorded.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import client as ev_client
from .ingest import Ingest
from .schema import RESPONSE_SCHEMA, SCHEMA_VERSION, EvidenceRecord
from .validate import Outcome, validate_response

PROMPT_PATH = Path(__file__).with_name("extract_v1.md")
PROMPT_VERSION = "extract_v1"


@dataclass
class ExtractionResult:
    status: str                                   # accepted | repaired | rejected | failed
    records: list[EvidenceRecord] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)       # ingest warnings (poor extraction, instruction-like text)
    notes: list[str] = field(default_factory=list)           # the model's extraction_notes
    meta: dict = field(default_factory=dict)                 # model/provider/usage/versions


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_user(ing: Ingest) -> str:
    items = [dict(id=p.id, section=p.section, page=p.page, text=p.sent_text) for p in ing.sendable()]
    return "<<<PASSAGES\n" + json.dumps({"passages": items}, ensure_ascii=False) + "\nPASSAGES>>>"


def _parse(text: str):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    return json.loads(t)


def run_extraction(ing: Ingest, chat=None, cfg: dict | None = None) -> ExtractionResult:
    res = ExtractionResult(status="failed", warnings=list(ing.warnings),
                           meta=dict(schema_version=SCHEMA_VERSION, prompt_version=PROMPT_VERSION))
    if not ing.sendable():
        res.errors.append("no readable passages; nothing was sent. This is not evidence of absent experience")
        return res
    chat = chat or ev_client.chat
    try:
        raw = chat(system_prompt(), build_user(ing), RESPONSE_SCHEMA, cfg)
    except ev_client.EvidenceLLMError as e:
        res.errors.append(str(e))
        return res
    if isinstance(raw, str):
        raw = ev_client.ChatResult(content=raw)
    res.meta.update(model=raw.model, provider=raw.provider, request_id=raw.request_id, finish_reason=raw.finish_reason,
                    usage=raw.usage, latency_s=raw.latency_s)
    if raw.finish_reason == "length":
        res.errors.append("response truncated (finish_reason=length); not parsed")
        return res
    try:
        data = _parse(raw.content)
    except ValueError:
        res.errors.append("response is not valid JSON")
        return res
    out: Outcome = validate_response(data, ing.passages)
    res.records, res.rejected, res.errors = out.records, out.rejected, out.errors
    res.status = "failed" if out.errors else out.status
    if isinstance(data, dict) and isinstance(data.get("extraction_notes"), list):
        res.notes = [n for n in data["extraction_notes"] if isinstance(n, str)]
    return res

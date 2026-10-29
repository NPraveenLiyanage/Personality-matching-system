"""Evidence-first engine: CV text -> passages -> validated evidence -> area assessment -> verification -> deterministic ranking.

`chat(system, user, schema, cfg)` is injected (same signature as `evidence.client.chat`) so everything runs offline in tests.
A failure at any stage is returned as a failure with the reason. No fallback to another engine or model.
Both stages' outputs are kept in result["stages"] so every error can be attributed to extraction or assessment.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from . import assess, client as ev_client, extract, ingest, rank, verify
from .schema import SCHEMA_VERSION

ENGINE_ID = "llm_evidence"


def _result(**kw) -> dict:
    base = dict(engine_id=ENGINE_ID, engine_version=f"{SCHEMA_VERSION}+{extract.PROMPT_VERSION}+{assess.PROMPT_VERSION}",
                status="failed", errors=[], warnings=[], supported=[], exploration=[], validation_log=[], stages={}, run_meta={})
    base.update(kw)
    return base


def run(cv_text: str, name: str, defs: dict, chat=None, cfg: dict | None = None, regulated: dict | None = None,
        use_confusions: bool = False) -> dict:
    chat = chat or ev_client.chat
    ing = ingest.ingest_text(cv_text, [name] if name else None)
    ex = extract.run_extraction(ing, chat, cfg)
    res = _result(warnings=ex.warnings)
    res["stages"]["extraction"] = dict(status=ex.status, records=[asdict(r) for r in ex.records], rejected=ex.rejected,
                                       errors=ex.errors, notes=ex.notes)
    res["run_meta"]["extraction"] = ex.meta
    if ex.status in ("failed", "rejected"):
        res["errors"] = ["extraction " + ex.status + ": " + "; ".join(ex.errors or [str(x["reasons"]) for x in ex.rejected][:3])]
        return res
    names = {aid: d["name"] for aid, d in defs["areas"].items()}
    if not ex.records:
        res["status"] = "no_evidence"
        res["errors"] = ["no usable evidence records were extracted; this is not evidence of absent experience"]
        return res

    area_ids = list(defs["areas"])
    try:
        raw = chat(assess.system_prompt(), assess.build_user(ex.records, ex.warnings, defs, use_confusions),
                   assess.RESPONSE_SCHEMA, cfg)
    except ev_client.EvidenceLLMError as e:
        res["errors"] = [f"assessment failed: {e}"]
        return res
    if isinstance(raw, str):
        raw = ev_client.ChatResult(content=raw)
    res["run_meta"]["assessment"] = dict(model=raw.model, provider=raw.provider, request_id=raw.request_id,
                                         finish_reason=raw.finish_reason, usage=raw.usage, latency_s=raw.latency_s,
                                         prompt_version=assess.PROMPT_VERSION)
    if raw.finish_reason == "length":
        res["errors"] = ["assessment truncated (finish_reason=length); not parsed"]
        return res
    try:
        data = json.loads(raw.content.strip())
    except ValueError as e:
        res["errors"] = ["assessment is not valid JSON"]
        c = raw.content or ""      # synthetic benchmark text only; kept so a parse failure can be diagnosed
        res["stages"]["assessment"] = dict(parse_error=str(e)[:200], content_chars=len(c), head=c[:200], tail=c[-200:])
        return res
    v = verify.verify(data, ex.records, area_ids, regulated)
    res["stages"]["assessment"] = dict(raw_rows=data.get("assessments") if isinstance(data, dict) else None,
                                       errors=v.errors, rejected=v.rejected)
    if v.errors:
        res["errors"] = ["assessment " + "; ".join(v.errors[:3])]
        return res
    uncited = [r["area_id"] for r in data["assessments"] if r.get("support_class") in assess.POSITIVE and not r.get("evidence")]
    if uncited:                                  # one bounded targeted re-ask; the answer goes through the same verification
        res["stages"]["assessment"]["reask_areas"] = uncited
        try:
            raw2 = chat(assess.system_prompt(), assess.build_reask_user(ex.records, defs, uncited), assess.RESPONSE_SCHEMA, cfg)
            if isinstance(raw2, str):
                raw2 = ev_client.ChatResult(content=raw2)
            res["run_meta"]["reask"] = dict(model=raw2.model, finish_reason=raw2.finish_reason, usage=raw2.usage,
                                            latency_s=raw2.latency_s, request_id=raw2.request_id)
            data2 = json.loads(raw2.content.strip()) if raw2.finish_reason != "length" else None
            v2 = verify.verify(data2, ex.records, uncited, regulated) if data2 is not None else None
            if v2 is not None and not v2.errors:
                for aid, row2 in v2.rows.items():
                    row2.changes.insert(0, "re-asked: first answer cited no evidence")
                    row2.status = "repaired"
                    v.rows[aid] = row2
                res["stages"]["assessment"]["reask_raw_rows"] = data2["assessments"]
            else:
                res["stages"]["assessment"]["reask_error"] = (v2.errors if v2 else ["truncated or unreadable re-ask"])[:3]
        except (ev_client.EvidenceLLMError, ValueError) as e:
            res["stages"]["assessment"]["reask_error"] = [str(e)[:160]]
    res["validation_log"] = [dict(area_id=a.area_id, original_class=a.original_class, final_class=a.support_class,
                                  changes=a.changes) for a in v.rows.values() if a.changes]
    res.update(rank.rank(v.rows, ex.records, names))
    res["status"] = "accepted" if ex.status == "accepted" and v.status == "accepted" else "repaired"
    return res

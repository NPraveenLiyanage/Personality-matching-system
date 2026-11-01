"""Step 2: PersonaMap work-style fit for the areas Step 1 supports (model call, then code-side verification).

The model sees only the minimal report text (`PersonaMap.report_text()`), the structured preference bands and the areas' own
descriptions. It never sees the CV, the evidence records or the support classes, so the personality judgement stays independent of
the evidence, and no single call carries both documents. It cannot add areas or change a support class.

Verification mirrors `verify.py`: downgrade-only, every change logged. A reason or watch-out survives only if its quote is found
verbatim in the report text that was sent and its wording makes no ability claim. A strong or stretch band with no surviving reason
becomes `insufficient_info`. The deterministic baseline (`workstyle.baseline_fit`) is attached to every row and a two-level
disagreement is flagged low confidence. `chat(system, user, schema, cfg)` is injected, as in the other stages.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import workstyle
from ..personamap import PersonaMap
from . import client as ev_client
from .validate import norm

PROMPT_PATH = Path(__file__).with_name("fit_v1.md")
PROMPT_VERSION = "fit_v1"
BANDS = ("strong", "mixed", "stretch", "insufficient_info")
MAX_QUOTE_WORDS = 40
# Claims about ability, qualification or outcomes are outside what a preference report can say. A point containing one is dropped.
_ABILITY = re.compile(r"\b(will succeed|guarantee[sd]?|is qualified|are qualified|talent(?:ed)?|gifted|incompeten\w+|cannot|"
                      r"unable to|will be hired|best suited|perfect (?:fit|match)|destined)\b", re.I)

_REASON = {"type": "object", "additionalProperties": False, "required": ["point", "quote"],
           "properties": {"point": {"type": "string"}, "quote": {"type": "string"}}}
RESPONSE_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["fits"],
    "properties": {"fits": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["area_id", "reasoning", "fit_band", "reasons", "watch_outs"],
        "properties": {"area_id": {"type": "string"}, "reasoning": {"type": "string"},      # reasoning before the verdict
                       "fit_band": {"type": "string", "enum": list(BANDS)},
                       "reasons": {"type": "array", "items": _REASON}, "watch_outs": {"type": "array", "items": _REASON}}}}}}


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def build_user(pm: PersonaMap, candidates: list[dict], defs: dict) -> str:
    """candidates: Step 1 items (area_id, name, ...). Only each area's own description is sent, nothing from the CV."""
    areas = []
    for c in candidates:
        d = defs["areas"][c["area_id"]]
        areas.append(dict(area_id=c["area_id"], name=d["name"], definition=d["definition"],
                          typical_activities=d["typical_activities"]))
    pl = pm.payload()
    body = dict(report=pl["report_text"], preferences=pl["preferences"], balanced_scales=pl["balanced"],
                readings=pl["readings"], problem_solving_steps=pl["problem_solving_steps"], areas=areas)
    return "<<<REPORT_AND_AREAS\n" + json.dumps(body, ensure_ascii=False) + "\nREPORT_AND_AREAS>>>"


def _parse(text: str):
    return json.loads(re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip()))


def _clean(items, hay: str, log: list[str], what: str) -> list[dict]:
    out = []
    for it in items if isinstance(items, list) else []:
        point, quote = (it.get("point") or "").strip(), (it.get("quote") or "").strip()
        nq = norm(quote)
        if not point or not nq:
            log.append(f"{what} dropped: empty point or quote")
        elif len(nq.split()) > MAX_QUOTE_WORDS:
            log.append(f"{what} dropped: quote longer than {MAX_QUOTE_WORDS} words")
        elif nq not in hay:
            log.append(f"{what} dropped: quote not found in the report text")
        elif _ABILITY.search(point):
            log.append(f"{what} dropped: wording claims ability or an outcome")
        else:
            out.append(dict(point=point, quote=quote))
    return out


def verify(data, pm: PersonaMap, candidate_ids: list[str]) -> tuple[dict, list[str], list[dict]]:
    """-> (rows by area_id, response-level errors, rejected rows). Downgrade-only."""
    if not isinstance(data, dict) or not isinstance(data.get("fits"), list):
        return {}, ["response has no 'fits' list"], []
    hay = norm(pm.report_text())
    rows: dict[str, dict] = {}
    rejected: list[dict] = []
    for raw in data["fits"]:
        aid = raw.get("area_id") if isinstance(raw, dict) else None
        if aid not in candidate_ids:
            rejected.append(dict(area_id=aid, reason="not one of the areas asked about"))
            continue
        if aid in rows:
            rejected.append(dict(area_id=aid, reason="duplicate row"))
            continue
        log: list[str] = []
        band = raw.get("fit_band")
        if band not in BANDS:
            log.append(f"invalid band {band!r}")
            band = "insufficient_info"
        reasons = _clean(raw.get("reasons"), hay, log, "reason")
        watch = _clean(raw.get("watch_outs"), hay, log, "watch-out")
        if band in ("strong", "stretch") and not reasons:
            log.append(f"{band} had no surviving quoted reason; set to insufficient_info")
            band = "insufficient_info"
        rows[aid] = dict(area_id=aid, fit_band=band, original_band=raw.get("fit_band"), reasons=reasons, watch_outs=watch,
                         reasoning=(raw.get("reasoning") or "")[:800], changes=log, status="repaired" if log else "accepted")
    for aid in candidate_ids:
        if aid not in rows:
            rows[aid] = dict(area_id=aid, fit_band="insufficient_info", original_band=None, reasons=[], watch_outs=[],
                             reasoning="", changes=["the model returned no row for this area"], status="repaired")
    return rows, [], rejected


def run_fit(pm: PersonaMap, candidates: list[dict], defs: dict, chat=None, cfg: dict | None = None) -> dict:
    """-> dict(status, fits {area_id: row}, errors, warnings, run_meta, stage). Never falls back to another model; if the call
    fails, the local baseline is still returned per area under `baseline_only`, clearly separate from a model-based fit."""
    ids = [c["area_id"] for c in candidates]
    res = dict(status="failed", fits={}, errors=[], warnings=list(pm.warnings), run_meta=dict(prompt_version=PROMPT_VERSION), stage={})
    if not ids:
        res["status"] = "no_areas"
        return res
    profiles = workstyle.load_profiles()
    base = {a: workstyle.baseline_fit(pm, profiles[a]["demands"]) for a in ids}
    if not pm.report_text().strip():
        res["errors"] = ["no usable report text; the fit step was not run"]
        res["baseline_only"] = base
        return res
    chat = chat or ev_client.chat
    user = build_user(pm, candidates, defs)

    def call():
        raw = chat(system_prompt(), user, RESPONSE_SCHEMA, cfg)
        return ev_client.ChatResult(content=raw) if isinstance(raw, str) else raw

    try:
        raw = call()
    except ev_client.EvidenceLLMError as e:
        res["errors"] = [f"fit call failed: {e}"]
        res["baseline_only"] = base
        return res
    res["run_meta"].update(model=raw.model, provider=raw.provider, request_id=raw.request_id, finish_reason=raw.finish_reason,
                           usage=raw.usage, latency_s=raw.latency_s)
    data = None
    if raw.finish_reason == "length":
        res["errors"] = ["fit response truncated (finish_reason=length); not parsed"]
    else:
        try:
            data = _parse(raw.content)
        except ValueError:                       # one bounded retry of the identical request, recorded
            res["run_meta"]["json_retries"] = 1
            try:
                raw = call()
                data = None if raw.finish_reason == "length" else _parse(raw.content)
            except (ev_client.EvidenceLLMError, ValueError):
                data = None
            if data is None:
                res["errors"] = ["fit response is not valid JSON (after one retry)"]
    if data is None:
        res["baseline_only"] = base
        return res
    rows, errors, rejected = verify(data, pm, ids)
    res["stage"] = dict(rejected=rejected, errors=errors)
    if errors:
        res["errors"] = errors
        res["baseline_only"] = base
        return res
    for aid, row in rows.items():
        row["baseline"] = base[aid]
        row.update(workstyle.compare(row["fit_band"], base[aid]["band"]))
    res["fits"] = rows
    res["status"] = "accepted" if all(r["status"] == "accepted" for r in rows.values()) and not rejected else "repaired"
    return res

"""Run the prompt several times, validate, take medians and combine into the final Top 10 (backend steps 1-5)."""
from __future__ import annotations

import json
import statistics
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from . import areas, client, validate

PROMPT_PATH = Path(__file__).with_name("prompt_v1.md")
STYLE_MULT = {"fits": 1.00, "neutral": 0.95, "stretch": 0.85}
LEVEL_MULT = {"ok": 1.00, "needs_track_record": 0.45, "below_level": 0.30}
LOW_CONFIDENCE_SPREAD = 20


def system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").replace("{{AREA_LIST}}", areas.area_list_text())


def one_run(payload: dict, chat=client.chat, cfg: dict | None = None) -> dict:
    """One validated answer. Retries once; a second answer with only quote problems is repaired (and flagged)."""
    sys_p, user = system_prompt(), json.dumps(payload, ensure_ascii=False)
    problems: list[str] = []
    for attempt in (1, 2):
        try:
            data = validate.extract_json(chat(sys_p, user, cfg) if cfg else chat(sys_p, user))
        except ValueError as e:
            problems = [f"unreadable JSON: {e}"]
            continue
        fatal, quotes = validate.validate(data, payload["cv_text"])
        if fatal:
            problems = fatal
            continue
        if quotes and attempt == 1:
            problems = quotes
            continue
        data["_repaired"] = bool(quotes)
        return validate.repair_quotes(data, payload["cv_text"]) if quotes else data
    raise client.LLMError("Answer failed validation twice: " + "; ".join(problems[:5]))


def aggregate(runs: list[dict], catalogue: pd.DataFrame) -> dict:
    """Median cv per area across runs, flags by majority, final = cv x style x level."""
    cat_ids = areas.to_catalogue_ids(catalogue)
    rows = []
    for i in range(1, 95):
        rs = [next(s for s in r["scores"] if int(s["id"]) == i) for r in runs]
        cvs = [float(s["cv"]) for s in rs]
        style = Counter(s["style"] for s in rs).most_common()
        level = Counter(s["level"] for s in rs).most_common()
        ints = [s["interest"] for s in rs if s.get("interest") is not None]
        rows.append(dict(
            id=i, area_id=cat_ids[i], name=areas.NAMES[i], field=areas.FIELD_OF[i], cv=statistics.median(cvs),
            spread=max(cvs) - min(cvs),
            style=style[0][0] if len(style) == 1 or style[0][1] > style[1][1] else "neutral",
            style_reason=next((s.get("style_reason", "") for s in rs if s["style"] == style[0][0]), ""),
            level=level[0][0] if len(level) == 1 or level[0][1] > level[1][1] else "ok",
            interest=statistics.median(ints) if ints else None))
    df = pd.DataFrame(rows)
    df["final"] = (df.cv * df["style"].map(STYLE_MULT) * df["level"].map(LEVEL_MULT)).round(1)
    df["_sort"] = df.final + pd.to_numeric(df.interest).fillna(0) / 1000         # interests only break ties
    df = df.sort_values("_sort", ascending=False).drop(columns="_sort").reset_index(drop=True)
    df["rank"] = df.index + 1
    df["low_confidence"] = (df.spread > LOW_CONFIDENCE_SPREAD) & (df["rank"] <= 10)

    detail: dict[int, dict] = {}
    for r in runs:
        for d in r.get("top10_detail", []):
            i = int(d["id"])
            cur = detail.setdefault(i, dict(evidence=[], missing=[], overlaps_with=[], style_note="", level_note=""))
            seen = {e["quote"] for e in cur["evidence"]}
            cur["evidence"] += [e for e in d.get("evidence") or [] if e.get("quote") not in seen][:3 - len(cur["evidence"])]
            for k in ("missing", "overlaps_with"):
                cur[k] = list(dict.fromkeys(cur[k] + list(d.get(k) or [])))[:3 if k == "missing" else 6]
            cur["style_note"] = cur["style_note"] or d.get("style_note", "")
            cur["level_note"] = cur["level_note"] or d.get("level_note", "")
    return dict(scores=df, top10=df.head(10), detail=detail, summary=runs[0].get("participant_summary", {}),
                n_runs=len(runs), repaired=any(r.get("_repaired") for r in runs))


def run_match(payload: dict, catalogue: pd.DataFrame, chat=client.chat, runs: int | None = None,
              cfg: dict | None = None, parallel: bool = False) -> dict:
    """Full pipeline. Free models are rate limited, so runs are sequential by default."""
    n = runs or (cfg or client.settings())["runs"]
    cfg = cfg or None
    if parallel:
        with ThreadPoolExecutor(max_workers=n) as ex:
            results = list(ex.map(lambda _: _try(payload, chat, cfg), range(n)))
    else:
        results = [_try(payload, chat, cfg) for _ in range(n)]
    ok = [r for r in results if isinstance(r, dict)]
    if not ok:
        raise client.LLMError(str(results[0]))
    out = aggregate(ok, catalogue)
    out["failed_runs"] = n - len(ok)
    return out


def _try(payload, chat, cfg):
    try:
        return one_run(payload, chat, cfg)
    except client.LLMError as e:
        return e

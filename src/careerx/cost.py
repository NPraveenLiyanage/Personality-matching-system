"""Token totals and an estimated cost for a pipeline run. Prices come from bench/prices.yaml (list prices, US$ per million tokens,
fetched 2026-10-31, not re-verified). A model with no price entry has an unknown cost (None), never zero, except free-tier models
(id ending ':free'), which cost nothing. This reports an estimate only: no spend is made or implied."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

PRICES = Path(__file__).resolve().parents[2] / "bench" / "prices.yaml"


@lru_cache(maxsize=1)
def _prices() -> dict:
    return yaml.safe_load(PRICES.read_text(encoding="utf-8")).get("models", {}) if PRICES.exists() else {}


def price_for(model: str | None) -> dict | None:
    if not model:
        return None
    if model.endswith(":free"):
        return dict(input=0.0, output=0.0)
    key = model.split("/")[-1].replace(".", "-")
    return _prices().get(key)


def _calls(meta: dict) -> list[dict]:
    """The model calls recorded in run_meta (extraction, assessment, re-ask, fit), each with usage/model/latency when present."""
    out = []
    for k in ("extraction", "assessment", "reask", "fit"):
        m = meta.get(k)
        if isinstance(m, dict) and (m.get("usage") is not None or m.get("model")):
            out.append(m)
    return out


def totals(meta: dict) -> dict:
    calls = _calls(meta)
    tin = sum((c.get("usage") or {}).get("prompt_tokens", 0) for c in calls)
    tout = sum((c.get("usage") or {}).get("completion_tokens", 0) for c in calls)
    cost, unknown = 0.0, False
    for c in calls:
        u, p = c.get("usage") or {}, price_for(c.get("model"))
        if p is None:
            unknown = unknown or bool(u)
        else:
            cost += (u.get("prompt_tokens", 0) * p["input"] + u.get("completion_tokens", 0) * p["output"]) / 1e6
    return dict(calls=len(calls), prompt_tokens=tin, completion_tokens=tout,
                latency_s=round(sum(c.get("latency_s") or 0 for c in calls), 1),
                estimated_cost_usd=None if unknown else round(cost, 5),
                note="estimate at list price; None = a model without a price entry")

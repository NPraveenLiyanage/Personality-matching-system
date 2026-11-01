"""Deterministic work-style fit: what the PersonaMap says about how a person likes to work, against what an area's work demands.

Local and free; it runs on every request. It is the stable reference for the model-based fit (a large disagreement flags a result
as low confidence) and the fallback *display* when the model call fails. It never changes which areas are supported, and it says
nothing about ability or qualification.

Per dimension: preference p (the report's % for the first pole, 0-1) against the area's demand d (0-4 -> 0-1). Fit = 1 - |p - d|.
A scale within 5 points of even carries no weight (same threshold as `llm.payload.strength_word`); otherwise weight = distance
from even. The report's rating of the "Commit and execute" step stands in for the preference for fast closing (`pace`).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from .personamap import PersonaMap

PATH = Path(__file__).resolve().parents[2] / "data" / "processed" / "area_workstyle_v1.yaml"
DIM_OF = {"E": "people", "N": "abstract", "F": "values", "J": "structure"}
POLE = {"E": ("Extroverted", "Introverted"), "N": ("Intuition", "Sensing"), "F": ("Feeling", "Thinking"),
        "J": ("Judging", "Perceiving")}
DEMAND_WORDS = {"people": ("involves mostly working alone or with equipment", "involves constant contact with people"),
                "abstract": ("is concrete and hands-on", "centres on abstract ideas and patterns"),
                "values": ("rests on objective, technical judgement", "rests on care and values-based judgement"),
                "structure": ("is flexible and improvised", "is planned, scheduled and procedural"),
                "pace": ("allows slow, deliberate decisions", "demands quick decisions and firm deadlines")}
# rating of the "Commit and execute" step -> (preference for fast closing 0-1, weight)
COMMIT = {"fastest step": (1.0, 0.5), "strong": (0.8, 0.4), "steady": (0.7, 0.3), "moderate": (0.5, 0.2),
          "developing": (0.3, 0.3), "slower step": (0.2, 0.4), "slowest step": (0.0, 0.5), "weakest step": (0.0, 0.5),
          "most-skipped step": (0.0, 0.5), "least natural step": (0.0, 0.5)}
BALANCED_BELOW = 5            # points from even
HARD_GAP = 0.5                # |p - d| above this with weight >= HARD_WEIGHT is a hard mismatch
HARD_WEIGHT = 0.3
STRONG_AT, STRETCH_BELOW, MIN_WEIGHT = 0.70, 0.50, 0.25
RANK = {"stretch": 0, "mixed": 1, "strong": 2}


@lru_cache(maxsize=1)
def load_profiles(path: str | None = None) -> dict:
    return yaml.safe_load(Path(path or PATH).read_text(encoding="utf-8"))["areas"]


def _commit_pref(pm: PersonaMap) -> tuple[float, float] | None:
    for s in pm.steps or []:
        if s["step"].strip().lower().startswith("commit"):
            return COMMIT.get(s["rating"].strip().lower())
    return None


def baseline_fit(pm: PersonaMap, demands: dict) -> dict:
    """Band is strong | mixed | stretch | neutral (too little preference signal). `dims` lists what drove it."""
    dims, num, den, hard = [], 0.0, 0.0, 0
    prefs = pm.preferences or {}
    rows = []
    for k, dim in DIM_OF.items():
        if k in prefs:
            rows.append((dim, prefs[k] / 100.0, abs(prefs[k] - 50), k))
    pace = _commit_pref(pm)
    if pace:
        rows.append(("pace", pace[0], None, "commit"))
    for dim, p, dist, k in rows:
        d = demands[dim] / 4.0
        w = pace[1] if k == "commit" else (0.0 if dist < BALANCED_BELOW else dist / 50.0)
        fit = 1 - abs(p - d)
        mismatch = w >= HARD_WEIGHT and abs(p - d) > HARD_GAP
        hard += mismatch
        num, den = num + w * fit, den + w
        dims.append(dict(dim=dim, weight=round(w, 2), fit=round(fit, 2), mismatch=mismatch, note=_note(dim, k, prefs, p, d, w, fit)))
    if den < MIN_WEIGHT:
        return dict(band="neutral", score=None, dims=dims, hard_mismatches=0,
                    reasons=["Your preference results are too close to even to say anything about fit."])
    score = num / den
    band = "stretch" if (score < STRETCH_BELOW or hard >= 2) else "strong" if (score >= STRONG_AT and hard == 0) else "mixed"
    reasons = [x["note"] for x in sorted(dims, key=lambda x: -x["weight"]) if x["note"]]
    return dict(band=band, score=round(score, 2), dims=dims, hard_mismatches=hard, reasons=reasons)


def _note(dim: str, k: str, prefs: dict, p: float, d: float, w: float, fit: float) -> str:
    if w == 0:
        return ""
    low, high = DEMAND_WORDS[dim]
    demand = high if d >= 0.5 else low
    if k == "commit":
        mine = "closing decisions quickly is a strength" if p >= 0.7 else "closing decisions is where you are slowest" if p <= 0.3 \
            else "closing decisions is middling for you"
        return f"The work {demand}; in your report, {mine}."
    pole = POLE[k][0 if prefs[k] > 50 else 1]
    pct = prefs[k] if prefs[k] > 50 else 100 - prefs[k]
    if w < 0.2:
        return f"{pole} {int(round(pct))}% is close to even, so it says little about work that {demand}."
    verdict = "fits" if fit >= 0.72 else "pulls against" if fit < 0.5 else "is a partial match for"
    return f"{pole} {int(round(pct))}% {verdict} work that {demand}."


def compare(llm_band: str, base_band: str) -> dict:
    """Two levels apart (strong vs stretch) is low confidence. Neutral or insufficient information never flags."""
    if llm_band in RANK and base_band in RANK and abs(RANK[llm_band] - RANK[base_band]) >= 2:
        return dict(agree=False, low_confidence=True)
    return dict(agree=llm_band == base_band, low_confidence=False)

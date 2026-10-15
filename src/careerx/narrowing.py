"""Narrowing: from a full scored map to a Top 10 without asking anyone to rate ~100 areas.

Round 0  shortlist     top 20 by score  (10 "highly suitable" + 10 "moderately suitable") + interest wildcards
Round 1  clusters      user keeps the fields that draw them
Round 2  like/maybe/no one tap per remaining area, plus a one-line reason (the "why / why not")
Round 3  forced choice a few "pick one of three" duels around the cut-off to settle ties
Final    top 10        blended score, diversity-aware so five near-identical areas do not crowd out the rest
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

PREF_VALUE = {"like": 100.0, "maybe": 50.0, "no": 0.0}
PREF_WEIGHT = 0.40         # share of the final score that comes from the user's own reactions
DUEL_BONUS = 8.0


def shortlist(scores: pd.DataFrame, n_high: int = 10, n_moderate: int = 10, n_wild: int = 3,
              wild_min_interest: float = 0.5) -> pd.DataFrame:
    s = scores.sort_values("score", ascending=False).reset_index(drop=True)
    s["list"] = ""
    s.loc[: n_high - 1, "list"] = "Highly suitable"
    s.loc[n_high: n_high + n_moderate - 1, "list"] = "Moderately suitable"
    base = s[s.list != ""].copy()
    rest = s[s.list == ""]
    wild = rest[rest.interests >= wild_min_interest].sort_values("interests", ascending=False).head(n_wild).copy()
    wild["list"] = "You told us you are interested in this"
    out = pd.concat([base, wild], ignore_index=True)
    out["is_wildcard"] = out.list.str.startswith("You told")
    return out


def cluster_counts(sl: pd.DataFrame) -> pd.DataFrame:
    return (sl.groupby("cluster").agg(areas=("name", "count"), best=("score", "max"))
              .sort_values("best", ascending=False).reset_index())


def apply_clusters(sl: pd.DataFrame, keep: list[str] | None) -> pd.DataFrame:
    if not keep:
        return sl.copy()
    return sl[sl.cluster.isin(keep) | sl.is_wildcard].reset_index(drop=True)


def apply_ratings(sl: pd.DataFrame, ratings: dict[str, dict]) -> pd.DataFrame:
    """ratings: area_id -> {"pref": like|maybe|no, "reason": str}. Unrated counts as 'maybe'."""
    d = sl.copy()
    d["pref"] = d.area_id.map(lambda a: ratings.get(a, {}).get("pref", "maybe"))
    d["reason"] = d.area_id.map(lambda a: ratings.get(a, {}).get("reason", ""))
    d["pref_value"] = d.pref.map(PREF_VALUE)
    d["blended"] = (1 - PREF_WEIGHT) * d.score + PREF_WEIGHT * d.pref_value
    return d.sort_values("blended", ascending=False).reset_index(drop=True)


def duel_groups(d: pd.DataFrame, k: int = 10, size: int = 3, n_groups: int = 3) -> list[list[str]]:
    """Consecutive triples straddling the cut-off, e.g. ranks 6-14 for k=10."""
    start = max(0, k - 1 - (size * n_groups) // 2)
    groups = []
    ids = [a for a, p in zip(d.area_id, d.pref) if p != "no"]
    for g in range(n_groups):
        chunk = ids[start + g * size: start + (g + 1) * size]
        if len(chunk) >= 2:
            groups.append(chunk)
    return groups


def area_similarity(X, area_ids: list[str], catalogue_ids: list[str]) -> pd.DataFrame:
    """Cosine similarity between areas (from the Scorer's TF-IDF matrix)."""
    sim = cosine_similarity(X)
    return pd.DataFrame(sim, index=catalogue_ids, columns=catalogue_ids).loc[area_ids, area_ids]


def final_top(d: pd.DataFrame, duel_picks: list[str] | None = None, k: int = 10,
              sim: pd.DataFrame | None = None, diversity: float = 0.25) -> pd.DataFrame:
    """Blend, apply duel bonuses, drop 'no', then pick k with maximal-marginal-relevance diversity.

    diversity = 0 -> pure score order. diversity = 0.25 means a candidate is penalised by up to 25% of its
    score for being near-identical to something already chosen.
    """
    d = d.copy()
    d["final"] = d["blended"] if "blended" in d else d["score"]
    if duel_picks:
        d.loc[d.area_id.isin(duel_picks), "final"] += DUEL_BONUS
    pool = d[d.get("pref", "maybe") != "no"] if "pref" in d else d
    pool = pool.sort_values("final", ascending=False)
    chosen: list[str] = []
    remaining = list(pool.area_id)
    final = pool.set_index("area_id").final
    while remaining and len(chosen) < k:
        best, best_val = None, -1e9
        for a in remaining:
            pen = 0.0
            if sim is not None and chosen and diversity > 0:
                pen = float(sim.loc[a, chosen].max()) * diversity * final[a]
            val = final[a] - pen
            if val > best_val:
                best, best_val = a, val
        chosen.append(best)
        remaining.remove(best)
    # diversity decides WHICH ten; presentation order is then plain score order
    out = pool.set_index("area_id").loc[chosen].reset_index().sort_values("final", ascending=False)
    out = out.reset_index(drop=True)
    out.insert(0, "final_rank", range(1, len(out) + 1))
    return out


def reason_text(r: pd.Series) -> str:
    bits = []
    if r.get("why_cv"):
        bits.append("CV: " + r["why_cv"])
    if r.get("why_personality"):
        bits.append("Work-style: " + r["why_personality"])
    if r.get("reason"):
        bits.append("You said: " + r["reason"])
    return " | ".join(bits)

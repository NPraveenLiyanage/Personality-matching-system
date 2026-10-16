"""Diagnostics behind the 'what broke and what it taught' section and the compare view.

Every function here reproduces one real finding from the project so the report can show it live on whatever
profile is loaded, instead of describing it.
"""
from __future__ import annotations

import dataclasses
import re
from collections import Counter, defaultdict
from datetime import date

import numpy as np
import pandas as pd

from . import narrowing, scoring
from .lexicon import DEFAULT_LEXICON, get_concepts
from .profile import Profile, month_ranges


# ------------------------------------------------------------------ 1. experience: naive sum vs merged
def naive_vs_merged_years(text: str, today: date | None = None) -> dict:
    """'63 years of experience' bug: adding up overlapping roles instead of merging them."""
    rngs = month_ranges(text, today)
    covered: set[int] = set()
    for s, e in rngs:
        covered.update(range(s, e + 1))
    return dict(n_roles=len(rngs), naive_years=round(sum(e - s + 1 for s, e in rngs) / 12, 1),
                merged_years=round(len(covered) / 12, 1))


# ------------------------------------------------------------------ 2. keyword coverage
_NOISE = {
    "present", "current", "email", "phone", "address", "limited", "private", "company", "colombo", "kandy",
    "galle", "lanka", "years", "year", "month", "months", "january", "february", "march", "april", "june", "july",
    "august", "september", "october", "november", "december", "available", "request", "references", "reference",
    "across", "including", "based", "level", "within", "which", "their", "ltd", "pvt",
}


def lexicon_coverage(text: str, scorer: scoring.Scorer, lexicon: str = DEFAULT_LEXICON, top_n: int = 12) -> dict:
    """Which career-related words in the CV does the engine actually recognise?

    'Career-related' = words that are distinctive in ISCO's occupation text (appear in at most a quarter of the
    areas). A word is 'recognised' if it sits inside a phrase the keyword list looks for. Blind spots are the
    frequent career words that no phrase covers: this is the check that would have caught the keyword gap
    automatically.
    """
    concepts = get_concepts(lexicon)
    spans = [(m.start(), m.end()) for c in concepts for pat in c.triggers for m in re.finditer(pat, text, re.I)]
    idf = dict(zip(scorer.vec.get_feature_names_out(), scorer.vec.idf_))
    n = len(scorer.cat)
    idf_min = np.log((1 + n) / (1 + 0.25 * n)) + 1            # distinctive = in at most a quarter of the areas...
    idf_max = np.log((1 + n) / 2.5) + 1                       # ...but used by at least two (not a one-off like 'sandblasting')
    seen, missed = Counter(), Counter()
    surface: dict[str, Counter] = defaultdict(Counter)
    for m in re.finditer(r"[A-Za-z]{4,}", text):
        w = m.group(0).lower()
        stem = w[:5]
        if w in scoring.STOP or w in _NOISE or not (idf_min <= idf.get(stem, 0) <= idf_max):
            continue
        seen[stem] += 1
        surface[stem][w] += 1
        if not any(a < m.end() and m.start() < b for a, b in spans):     # a keyword match overlaps this word
            missed[stem] += 1
    total, miss = sum(seen.values()), sum(missed.values())
    return dict(
        recognised_pct=round(100 * (1 - miss / total), 1) if total else 100.0,
        n_terms=total,
        blind_spots=[(surface[s].most_common(1)[0][0], c) for s, c in missed.most_common(top_n)],
    )


# ------------------------------------------------------------------ 3. rank changes
def rank_movers(before: pd.DataFrame, after: pd.DataFrame, top: int = 12) -> pd.DataFrame:
    """Areas in the top `top` of either ranking, with rank before/after (move > 0 = moved up)."""
    b, a = before.set_index("name")["rank"], after.set_index("name")["rank"]
    d = pd.DataFrame({"before": b, "after": a})
    d["move"] = d.before - d.after
    d = d[(d.before <= top) | (d.after <= top)]
    return d.sort_values("after").reset_index().rename(columns={"name": "area"})


# ------------------------------------------------------------------ 4. formula versions
FORMULA_LABELS = {
    "additive": "First attempt: add the parts together",
    "average": "Second attempt: average evidence and interests",
    "final": "Final: evidence x working style x level fit",
}


def formula_comparison(profile: Profile, scorer: scoring.Scorer, weights: dict | None = None) -> dict:
    out = {}
    for f in ("additive", "average", "final"):
        s = scorer.score(profile, weights=weights, formula=f)
        out[f] = dict(scores=s, gate=scoring.sanity_gate(s))
    return out


# ------------------------------------------------------------------ 5. what-ifs
def with_interests(profile: Profile, interest_ids: list[str]) -> Profile:
    return dataclasses.replace(profile, interests={i: 1.0 for i in interest_ids}, interests_known=bool(interest_ids))


def passion_effect(profile: Profile, scorer: scoring.Scorer, interest_ids: list[str],
                   weights: dict | None = None) -> dict:
    base = scorer.score(profile, weights=weights)
    new = scorer.score(with_interests(profile, interest_ids), weights=weights)
    mv = rank_movers(base, new, top=25)
    best = mv.sort_values("move", ascending=False).head(3)
    return dict(base=base, new=new, movers=mv, best=best)


def personality_effect(profile: Profile, scorer: scoring.Scorer, weights: dict | None = None) -> dict:
    """Does work style change WHO is in the top 10, or only the order?"""
    off = scorer.score(profile, weights={**(weights or {}), "personality_influence": 0.0})
    on = scorer.score(profile, weights=weights)
    a, b = list(off.head(10).name), list(on.head(10).name)
    return dict(same_members=set(a) == set(b), entering=sorted(set(b) - set(a)), leaving=sorted(set(a) - set(b)),
                n_reordered=sum(1 for n_ in set(a) & set(b) if a.index(n_) != b.index(n_)), off=off, on=on)


def diversity_table(scores: pd.DataFrame, scorer: scoring.Scorer, levels=(0.0, 0.25, 0.5, 0.75)) -> pd.DataFrame:
    sl = narrowing.shortlist(scores)
    d0 = narrowing.apply_ratings(sl, {})
    sim = narrowing.area_similarity(scorer.X, list(d0.area_id), list(scorer.cat.area_id))
    rows, base = [], None
    for dv in levels:
        t = narrowing.final_top(d0, sim=sim, diversity=dv)
        names = set(t.name)
        base = base if base is not None else names
        rows.append(dict(diversity=dv, fields=t.cluster.nunique(), enters=sorted(names - base),
                         leaves=sorted(base - names)))
    return pd.DataFrame(rows)


def near_duplicates(scores: pd.DataFrame, scorer: scoring.Scorer, top: int = 10, n_pairs: int = 4) -> pd.DataFrame:
    ids = list(scores.head(top).area_id)
    sim = narrowing.area_similarity(scorer.X, ids, list(scorer.cat.area_id))
    nm = dict(zip(scores.area_id, scores.name))
    pairs = [(nm[a], nm[b], round(float(sim.loc[a, b]), 2)) for i, a in enumerate(ids) for b in ids[i + 1:]]
    return pd.DataFrame(pairs, columns=["area_a", "area_b", "similarity"]).sort_values(
        "similarity", ascending=False).head(n_pairs).reset_index(drop=True)


# ------------------------------------------------------------------ 6. comparing participants
def compare_profiles(results: dict[str, dict], clusters: list[str], k: int = 10) -> dict:
    """results: name -> pipeline.run output. Returns the field heat grid and the Top-10 overlap matrix."""
    names = list(results)
    heat = pd.DataFrame({n: results[n]["scores"].groupby("cluster").score.max().reindex(clusters).fillna(0)
                         for n in names}).T
    tops = {n: set(results[n]["scores"].head(k).name) for n in names}
    overlap = pd.DataFrame([[len(tops[a] & tops[b]) for b in names] for a in names], index=names, columns=names)
    shared_all = sorted(set.intersection(*tops.values())) if names else []
    return dict(heat=heat, overlap=overlap, shared_all=shared_all, tops=tops)

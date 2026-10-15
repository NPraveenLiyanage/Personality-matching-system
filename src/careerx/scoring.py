"""Transparent scoring of every career area against one profile.

score = 100 * relevance x work_style_modifier x readiness

    relevance   1 - (1 - cv) * (1 - interest_strength * interests)      (probabilistic OR)
                  cv         evidence on the CV (concept strengths x area affinity from ISCO text)
                  interests  stated passions (same concept machinery); unknown -> 0, nothing is guessed.
                A passion can lift an area the CV never mentions, but it can never lower a CV-evidenced one.
    work_style  (1 - influence) + influence * personality_fit   (PersonaMap; dimensions the report calls
                balanced get zero weight). Personality says HOW you like to work, not WHICH field, so it can
                re-order relevant areas but cannot lift an irrelevant one.
    readiness   multiplier from the education band / experience vs the area's ISCO skill band

History: (1) the first version added the four components: dry run 1 failed the sanity gate (50% of areas
'suitable') because near-constant personality/readiness terms gave every area a ~45 point floor.
(2) relevance was then a weighted mean of CV and interests, so adding one hobby capped every CV-based area at
~58; replaced by the OR above.

Everything is deterministic and every number can be traced back to a phrase in the CV, a percentage in
the PersonaMap report, or a line of ISCO text.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .lexicon import CONCEPTS, TRAIT_CUES
from .profile import DIM_NAMES, Profile

DEFAULT_WEIGHTS = dict(interest_strength=0.60, personality_influence=0.35)
HIGH, MODERATE = 70.0, 50.0

_ISCO_STOP = {
    "tasks", "task", "include", "includes", "including", "usually", "performed", "occupations", "occupation",
    "classified", "examples", "group", "groups", "workers", "worker", "related", "other", "general", "used",
    "using", "work", "works", "working", "various", "specific", "different", "within", "also", "etc",
    "elsewhere", "not", "nec", "following", "unit", "minor", "sub", "major", "type", "types", "such",
    "required", "requirements_", "persons", "person", "people_", "ensure", "ensuring", "providing", "provide",
}
STOP = set(ENGLISH_STOP_WORDS) | _ISCO_STOP


def tokenize(text: str) -> list[str]:
    """Lower-case, drop stop words, prefix-stem to 5 letters (analyse/analysis/analyst -> 'analy')."""
    return [t[:5] for t in re.findall(r"[a-z]{3,}", text.lower()) if t not in STOP]


def _rank01(x: np.ndarray) -> np.ndarray:
    order = x.argsort().argsort().astype(float)
    return order / max(len(x) - 1, 1)


class Scorer:
    def __init__(self, catalogue: pd.DataFrame, weights: dict | None = None, gamma: float = 1.5):
        self.cat = catalogue.reset_index(drop=True)
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self.gamma = gamma

        self.vec = TfidfVectorizer(tokenizer=tokenize, lowercase=False, token_pattern=None, sublinear_tf=True)
        self.X = self.vec.fit_transform(self.cat["text"])
        C = self.vec.transform([c.vocab for c in CONCEPTS])
        aff = cosine_similarity(self.X, C)                       # areas x concepts
        colmax = aff.max(axis=0, keepdims=True)
        colmax[colmax == 0] = 1
        self.aff = (aff / colmax) ** gamma                       # 0..1, best area per concept = 1
        self.concept_ids = [c.id for c in CONCEPTS]
        self.concept_labels = {c.id: c.label for c in CONCEPTS}

        # work-style axes from the ISCO text itself (rank-normalised so they are comparable)
        stems = {k: {t[:5] for t in re.findall(r"[a-z]{3,}", v.lower())} for k, v in TRAIT_CUES.items()}
        toks = [tokenize(t) for t in self.cat["text"]]
        dens = {k: np.array([sum(tt in s for tt in tk) / max(len(tk), 1) for tk in toks]) for k, s in stems.items()}
        self.axes = pd.DataFrame({k: _rank01(v) for k, v in dens.items()})
        self.axes["n_axis"] = (self.axes["ideas"] - self.axes["practical"] + 1) / 2
        self.axes["f_axis"] = (self.axes["values"] - self.axes["analytic"] + 1) / 2

        minors = self.cat["isco_minor"].str.split(",")
        self.managerial = np.array([all(m.startswith("1") for m in ms) for ms in minors])

    # ---------------------------------------------------------------- components
    def _concept_component(self, strengths: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
        s = np.array([strengths.get(cid, 0.0) for cid in self.concept_ids])
        if s.sum() == 0:
            return np.zeros(len(self.cat)), s
        raw = self.aff @ s
        return raw / raw.max(), s

    def _personality_component(self, pers: dict | None):
        n = len(self.cat)
        if not pers:
            return np.full(n, 0.5), 0.0, []
        spec = [("E", self.axes["people"].values), ("N", self.axes["n_axis"].values),
                ("F", self.axes["f_axis"].values), ("J", self.axes["structure"].values)]
        num, den, per_dim = np.zeros(n), 0.0, []
        for dim, axis in spec:
            pref = pers[dim] / 100.0
            w = abs(pref - 0.5) * 2
            fit = 1 - np.abs(pref - axis)
            num += w * fit
            den += w
            per_dim.append((dim, pref, w, fit))
        if den < 0.05:
            return np.full(n, 0.5), 0.0, per_dim
        return num / den, den, per_dim

    def _readiness_component(self, p: Profile) -> np.ndarray:
        pb = p.education_band
        out = np.empty(len(self.cat))
        for i, r in self.cat.iterrows():
            if r.band_min <= pb <= r.band_max:
                v = 1.0
            elif pb > r.band_max:                                # over-qualified for the entry route
                v = {1: 0.55}.get(pb - r.band_max, 0.30)
            else:                                                # needs more study first
                v = {1: 0.55}.get(r.band_min - pb, 0.25)
            if self.managerial[i]:                               # management needs track record
                v *= float(np.clip(0.35 + 0.08 * p.years_experience, 0.35, 1.0))
            out[i] = v
        return out

    # ---------------------------------------------------------------- scoring
    def score(self, p: Profile) -> pd.DataFrame:
        cv, s_cv = self._concept_component({k: v["strength"] for k, v in p.cv_concepts.items()})
        it, s_it = self._concept_component(p.interests)
        pe_raw, pe_w, per_dim = self._personality_component(p.personality)
        rd = self._readiness_component(p)

        # relevance: CV evidence OR stated interest (interests are 0 when unknown, never guessed)
        k = self.weights["interest_strength"] if p.interests_known else 0.0
        relevance = 1 - (1 - cv) * (1 - k * it)
        w = {"interest_strength": round(k, 2)}

        # work-style: min-max stretched across the catalogue so it re-orders instead of shifting everything
        if pe_w > 0:
            pe = (pe_raw - pe_raw.min()) / max(pe_raw.max() - pe_raw.min(), 1e-9)
        else:
            pe = np.full(len(self.cat), 0.5)
        infl = self.weights["personality_influence"] if pe_w > 0 else 0.0
        modifier = (1 - infl) + infl * pe

        total = 100 * relevance * modifier * rd

        df = self.cat[["area_id", "name", "cluster", "kind", "band_min", "band_max", "isco_minor",
                       "isco_units", "n_isco_units"]].copy()
        df["cv"], df["interests"], df["relevance"] = cv, it, relevance
        df["personality"], df["modifier"], df["readiness"] = pe, modifier, rd
        df["score"] = total.round(1)
        df["level"] = np.where(df.score >= HIGH, "High", np.where(df.score >= MODERATE, "Moderate", "Lower"))
        df["rank"] = df.score.rank(ascending=False, method="first").astype(int)

        names = self.concept_labels
        why, miss, pwhy, rwhy = [], [], [], []
        for i in range(len(df)):
            contrib = self.aff[i] * s_cv
            top = np.argsort(-contrib)[:3]
            bits = []
            for j in top:
                if contrib[j] <= 0.02:
                    continue
                cid = self.concept_ids[j]
                hits = ", ".join(p.cv_concepts[cid]["hits"][:3]) if cid in p.cv_concepts else ""
                bits.append(f"{names[cid]} ({hits})")
            why.append("; ".join(bits) if bits else "no direct CV evidence")
            absent = [(self.aff[i, j], self.concept_ids[j]) for j in range(len(self.concept_ids))
                      if s_cv[j] == 0 and s_it[j] == 0 and self.aff[i, j] >= 0.55]
            absent.sort(reverse=True)
            miss.append(", ".join(names[c] for _, c in absent[:3]))
            pwhy.append(self._personality_text(i, per_dim, p))
            rwhy.append(self._readiness_text(i, p))
        df["why_cv"], df["missing"], df["why_personality"], df["why_readiness"] = why, miss, pwhy, rwhy

        ex = self.cat["examples"].apply(lambda e: list(dict.fromkeys(e))[:6])
        df["examples"] = ex
        df.attrs["weights_used"] = {**w, "personality_influence": round(float(infl), 2)}
        df.attrs["personality_weight"] = round(float(pe_w), 2)
        return df.sort_values("score", ascending=False).reset_index(drop=True)

    # ---------------------------------------------------------------- explanations
    def _personality_text(self, i: int, per_dim, p: Profile) -> str:
        if not per_dim:
            return "no personality data"
        notes = []
        phr = {"E": ("people-facing", "independent / reflective"), "N": ("ideas and patterns", "hands-on, concrete"),
               "F": ("people and values", "objective analysis"), "J": ("planned and structured", "flexible, improvised")}
        for dim, pref, w, fit in per_dim:
            if w < 0.25:               # near-even preferences (about 38-62%) are not described as a "fit"
                continue
            if fit[i] >= 0.72:
                side = phr[dim][0] if pref > 0.5 else phr[dim][1]
                notes.append(f"{side} work fits ({DIM_NAMES[dim]} {int(p.personality[dim])}%)")
            elif fit[i] <= 0.4:
                side = phr[dim][1] if pref > 0.5 else phr[dim][0]
                notes.append(f"{side} work is a stretch ({DIM_NAMES[dim]} {int(p.personality[dim])}%)")
        return "; ".join(notes) if notes else "neutral on work-style"

    def _readiness_text(self, i: int, p: Profile) -> str:
        r = self.cat.iloc[i]
        lvl = {1: "skill level 1 (elementary)", 2: "skill level 2 (clerical/service/trades/operators)",
               3: "skill levels 3-4 (degree-level)"}
        band = lvl[r.band_min] if r.band_min == r.band_max else f"{lvl[r.band_min]} to {lvl[r.band_max]}"
        if r.band_min <= p.education_band <= r.band_max:
            t = f"your education fits: {band}"
        elif p.education_band > r.band_max:
            t = f"typically below your qualification level: {band}"
        else:
            t = f"typically needs further study: {band}"
        if self.managerial[i]:
            t += f"; management also needs track record (you: {p.years_experience:g} yrs)"
        return t


# ---------------------------------------------------------------------- sanity gate
def sanity_gate(scores: pd.DataFrame, max_share: float = 0.25, threshold: float = MODERATE) -> dict:
    """The consultant's 'matched 120 of 150 means the system is broken' check, made explicit."""
    n = len(scores)
    n_hi = int((scores.score >= HIGH).sum())
    n_mod = int(((scores.score >= MODERATE) & (scores.score < HIGH)).sum())
    share = (n_hi + n_mod) / n
    top10 = scores.head(10)
    cluster_mix = top10["cluster"].value_counts().to_dict()
    passed = share <= max_share
    return dict(
        n_areas=n, n_high=n_hi, n_moderate=n_mod, n_lower=n - n_hi - n_mod,
        share_suitable=round(share, 3), max_share=max_share, passed=passed,
        spread=dict(min=float(scores.score.min()), median=float(scores.score.median()),
                    p90=float(scores.score.quantile(0.9)), max=float(scores.score.max())),
        top10_clusters=cluster_mix,
        message=("Within tolerance: the map is selective." if passed else
                 f"Too loose: {share:.0%} of areas are 'suitable' (limit {max_share:.0%}). "
                 "Do not show this map; tighten the rubric first."),
    )

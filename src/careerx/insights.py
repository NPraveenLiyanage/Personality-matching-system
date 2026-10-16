"""Plain-English sentences generated from the numbers, so every chart opens with an answer.

Nothing here uses jargon on purpose: these strings go straight onto the page for a non-technical reader.
"""
from __future__ import annotations

import pandas as pd

from .profile import DIM_NAMES

# What each personality dimension means in everyday words: (left pole, right pole). Value = % toward the FIRST name.
SPECTRUMS = {
    "E": ("Energised by people", "Energised by quiet time"),
    "N": ("Ideas and patterns", "Facts and detail"),
    "F": ("Guided by people and values", "Guided by logic and evidence"),
    "J": ("Plans ahead", "Keeps options open"),
}


def evidence_label(v: float) -> str:
    return "strong" if v >= 0.6 else "some" if v >= 0.3 else "little"


def fit_label(modifier: float) -> str:
    return "a good fit" if modifier >= 0.93 else "an acceptable fit" if modifier >= 0.8 else "a stretch"


def level_label(readiness: float) -> str:
    return "matches your level" if readiness >= 0.95 else "may need more study or experience" if readiness >= 0.5 \
        else "is usually a different level"


def top_field(scores: pd.DataFrame, k: int = 10) -> tuple[str, int]:
    mix = scores.head(k).cluster.value_counts()
    return mix.index[0], int(mix.iloc[0])


def cluster_mix(scores: pd.DataFrame, k: int = 10, max_slices: int = 4) -> pd.DataFrame:
    """Top-k areas by field, folded to at most `max_slices` slices (a donut stays readable)."""
    mix = scores.head(k).cluster.value_counts()
    keep = mix.head(max_slices - 1) if len(mix) > max_slices else mix
    rows = [(c, int(n)) for c, n in keep.items()]
    rest = int(mix.sum() - keep.sum())
    if rest:
        rows.append(("Other fields", rest))
    return pd.DataFrame(rows, columns=["field", "areas"])


def generosity_sentence(gate: dict) -> str:
    pct = round(100 * gate["share_suitable"])
    if gate["passed"]:
        return (f"Only {pct}% of the {gate['n_areas']} areas look suitable (our limit is "
                f"{round(100 * gate['max_share'])}%), so the map is selective.")
    return (f"{pct}% of the {gate['n_areas']} areas look suitable, above our {round(100 * gate['max_share'])}% "
            "limit. A map this generous is not useful, so it should not be shown to anyone.")


def headline(scores: pd.DataFrame, gate: dict, personality_effect: dict | None = None) -> dict:
    field, n = top_field(scores)
    first = scores.iloc[0]
    cards = [
        dict(title="Strongest direction", value=field,
             text=f"{n} of the top 10 areas are in this field. The best single match is {first['name']} "
                  f"({first.score:.0f}%)."),
        dict(title="Is the map too generous?", value="No" if gate["passed"] else "Yes",
             text=generosity_sentence(gate)),
    ]
    if personality_effect is not None:
        same = personality_effect["same_members"]
        cards.append(dict(
            title="Did working style matter?",
            value="Only the order" if same else "It changed the list",
            text=("Working style re-ordered some neighbours but the same ten areas stayed in the top 10."
                  if same else
                  f"Working style pulled in {', '.join(personality_effect['entering']) or 'nothing'} and pushed out "
                  f"{', '.join(personality_effect['leaving']) or 'nothing'}.")))
    return dict(field=field, n_in_field=n, top_area=first["name"], top_score=float(first.score), cards=cards)


def why_sentences(row: pd.Series) -> list[tuple[str, str, str]]:
    """Three (label, level word, plain sentence) triples for the 'why this score' meters."""
    return [
        ("Evidence in the CV", evidence_label(row.cv), f"{row.why_cv}" if row.why_cv else "Nothing direct in the CV."),
        ("Fits how they like to work", fit_label(row.modifier), row.why_personality or "No personality data."),
        ("Level fit", level_label(row.readiness), row.why_readiness),
    ]


def passion_sentence(best: pd.DataFrame) -> str:
    if best.empty or best.iloc[0].move <= 0:
        return "That passion did not move any area much."
    r = best.iloc[0]
    return f"{r.area} moves from #{int(r.before)} to #{int(r.after)}."


def compare_sentence(cmp: dict, names: list[str]) -> str:
    if len(names) < 2:
        return "Add a second participant to compare."
    ov = cmp["overlap"]
    pairs = [(a, b, int(ov.loc[a, b])) for i, a in enumerate(names) for b in names[i + 1:]]
    a, b, n = max(pairs, key=lambda t: t[2])
    lo = min(pairs, key=lambda t: t[2])
    if len(names) == 2:
        return f"{a} and {b} share {n} of their top 10 areas."
    return (f"Most alike: {a} and {b} ({n} shared areas). Least alike: {lo[0]} and {lo[1]} "
            f"({lo[2]} shared).")


def personality_spectrum(profile) -> list[dict]:
    """Four labelled spectrum rows. pct = % toward the left label; 'balanced' = no clear preference."""
    if not profile.personality:
        return []
    rows = []
    for d in "ENFJ":
        left, right = SPECTRUMS[d]
        v = float(profile.personality[d])
        rows.append(dict(dim=d, name=DIM_NAMES[d], left=left, right=right, pct=v,
                         balanced=abs(v - 50) < 8, lean=left if v > 50 else right))
    return rows

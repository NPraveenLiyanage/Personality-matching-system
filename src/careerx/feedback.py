"""Tester feedback: the numbered list the consultant asked for, plus the validation summary.

Per area: accuracy 1-5 ("how accurate is this match for you?") and a comment that is required unless the
tester rates it highly accurate. A low score judged correct counts as accurate; a low score judged wrong
(a hidden passion, a missing CV item) is a false negative and is the most valuable row in the file.
"""
from __future__ import annotations

import pandas as pd

ACCURACY_SCALE = {
    5: "5 - Highly accurate",
    4: "4 - Accurate",
    3: "3 - Partly accurate",
    2: "2 - Inaccurate",
    1: "1 - Very inaccurate",
}
COMMENT_REQUIRED_BELOW = 5


def feedback_template(scores: pd.DataFrame) -> pd.DataFrame:
    t = scores.sort_values("score", ascending=False).reset_index(drop=True)
    out = pd.DataFrame({
        "no": range(1, len(t) + 1),
        "area_id": t.area_id,
        "career_area": t.name,
        "cluster": t.cluster,
        "match_score": t.score,
        "accuracy": pd.Series([pd.NA] * len(t), dtype="Int64"),
        "comment": "",
    })
    return out


def missing_comments(fb: pd.DataFrame) -> pd.DataFrame:
    rated = fb[fb.accuracy.notna()]
    need = rated[(rated.accuracy < COMMENT_REQUIRED_BELOW) & (rated.comment.fillna("").str.strip() == "")]
    return need


def summarise(fb: pd.DataFrame) -> dict:
    r = fb[fb.accuracy.notna()].copy()
    if r.empty:
        return dict(rated=0)
    r["accuracy"] = r.accuracy.astype(int)
    r["band"] = pd.cut(r.match_score, [-1, 30, 50, 70, 101], labels=["<30", "30-50", "50-70", "70+"])
    by_band = r.groupby("band", observed=True).accuracy.agg(["count", "mean"]).round(2)
    wrong = r[r.accuracy <= 2]
    high_wrong = wrong[wrong.match_score >= 50]      # shown as suitable, tester disagrees
    low_wrong = wrong[wrong.match_score < 50]        # shown as unsuitable, tester disagrees
    return dict(
        rated=len(r), total=len(fb),
        mean_accuracy=round(r.accuracy.mean(), 2),
        pct_accurate=round(100 * (r.accuracy >= 4).mean(), 1),
        by_band=by_band,
        false_positives=high_wrong[["career_area", "match_score", "accuracy", "comment"]],
        false_negatives=low_wrong[["career_area", "match_score", "accuracy", "comment"]],
        target_pct=90.0,
    )

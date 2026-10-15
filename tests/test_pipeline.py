"""Verification checks from the plan. Run:  python tests/test_pipeline.py   (or pytest)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from careerx import catalogue, feedback, narrowing, pipeline, scoring
from careerx.profile import build_profile, parse_personamap


def test_catalogue_covers_every_in_scope_minor_group_once():
    r = catalogue.coverage_report(pipeline.get_catalogue())
    assert r["in_scope"] == 127 and r["missing"] == [] and r["duplicates"] == [] and r["unknown"] == []
    cat = pipeline.get_catalogue()
    assert cat.text.str.split().str.len().min() > 50          # every area has real definition/task text
    assert cat.area_id.is_unique and cat.name.is_unique


def test_personamap_parse_matches_the_report():
    pm = parse_personamap(pipeline.extract_pdf_text(pipeline.SAMPLE_PM))
    assert (pm["E"], pm["N"], pm["F"], pm["J"]) == (50.0, 70.0, 55.0, 65.0)
    assert pm["balanced"] == ["E"] and pm["code"] == "XNFJ"


def test_cv_profile_sane():
    p = pipeline.sample_profile()
    assert p.education_band == 3 and 1.0 <= p.years_experience <= 1.6
    assert {"software_dev", "ml_ai", "statistics", "data_analytics"} <= set(p.cv_concepts)
    # referees' titles must not leak in
    assert "entrepreneurship" not in p.cv_concepts and "teaching" not in p.cv_concepts


def test_gate_passes_and_every_top_area_has_evidence():
    out = pipeline.run(pipeline.sample_profile())
    assert out["gate"]["passed"], out["gate"]
    top = out["scores"].head(10)
    assert (top.why_cv != "no direct CV evidence").all()
    assert (top.score > 0).all() and out["scores"].score.between(0, 100).all()


def test_interests_unknown_are_dropped_not_guessed():
    s = pipeline.run(pipeline.sample_profile())["scores"]
    assert s.attrs["weights_used"]["interest_strength"] == 0.0
    assert (s.interests == 0).all()


def test_stated_passion_creates_wildcard_without_cv_evidence():
    p = pipeline.sample_profile(interest_ids=["music_arts"])
    out = pipeline.run(p)
    sl, s = out["shortlist"], out["scores"].set_index("name")
    assert s.loc["Music performance & production", "cv"] < 0.15          # nothing on the CV
    assert "Music performance & production" in set(sl.name)               # but the passion surfaces it
    # a passion must never lower a CV-evidenced area
    base = pipeline.run(pipeline.sample_profile())["scores"].set_index("name").score
    assert (s.score >= base.reindex(s.index) - 1e-9).all()


def test_balanced_dimension_gets_zero_weight():
    sc = pipeline.get_scorer()
    p = pipeline.sample_profile()
    p.personality = {"E": 50, "N": 50, "F": 50, "J": 50}
    s = sc.score(p)
    assert s.attrs["personality_weight"] == 0 and (s.modifier == 1.0).all()


def test_readiness_penalises_management_for_early_career():
    s = pipeline.run(pipeline.sample_profile())["scores"].set_index("name")
    assert s.loc["Executive leadership & general management", "readiness"] < 0.5
    assert s.loc["Software & applications development", "readiness"] == 1.0


def test_narrowing_ends_with_exactly_ten_and_records_reasons():
    out = pipeline.run(pipeline.sample_profile())
    sl = out["shortlist"]
    ratings = {a: {"pref": "like", "reason": "interesting"} for a in sl.area_id[:5]}
    ratings.update({a: {"pref": "no", "reason": "not for me"} for a in sl.area_id[5:8]})
    d = narrowing.apply_ratings(sl, ratings)
    sc = pipeline.get_scorer()
    sim = narrowing.area_similarity(sc.X, list(d.area_id), list(pipeline.get_catalogue().area_id))
    top = narrowing.final_top(d, duel_picks=[], sim=sim)
    assert len(top) == 10 and top.area_id.is_unique
    assert not set(top.area_id) & set(sl.area_id[5:8])          # 'no' is respected
    assert (top.reason != "").sum() >= 1


def test_feedback_comment_rule_and_summary():
    s = pipeline.run(pipeline.sample_profile())["scores"]
    fb = feedback.feedback_template(s)
    fb.loc[0, "accuracy"] = 5
    fb.loc[1, "accuracy"] = 2           # no comment -> must be flagged
    fb.loc[60, "accuracy"] = 1
    fb.loc[60, "comment"] = "I love this, not in my CV"
    miss = feedback.missing_comments(fb)
    assert list(miss.no) == [2]
    summ = feedback.summarise(fb)
    assert summ["rated"] == 3 and len(summ["false_negatives"]) == 1


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:                      # noqa: BLE001
                failed += 1
                print("FAIL", name, "->", repr(e))
    sys.exit(1 if failed else 0)

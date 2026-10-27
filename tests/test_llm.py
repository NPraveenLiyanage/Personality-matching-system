"""Offline checks for the LLM matcher (fake model, no network). Run: python tests/test_llm.py  (or pytest)

A live check against OpenRouter runs only when OPENROUTER_API_KEY is set (see test_live_demo_b).
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from careerx import pipeline
from careerx.llm import areas, client, engine, payload, validate


def _answer(top: dict[int, float], quote: str, flags=None) -> dict:
    flags = flags or {}
    scores = [dict(id=i, cv=top.get(i, 5), style=flags.get(i, ("neutral", "ok"))[0], style_reason="",
                   level=flags.get(i, ("neutral", "ok"))[1], interest=None) for i in range(1, 95)]
    best = sorted(top, key=top.get, reverse=True)[:10]
    detail = [dict(id=i, evidence=[dict(quote=quote, supports="shows it")] if top[i] >= 50 else [], missing=[],
                   overlaps_with=[], style_note="", level_note="") for i in best]
    return dict(participant_summary=dict(stage="early"), scores=scores, top10_detail=detail)


CV = "Built a churn model in Python.\nLed a team of five analysts for two years."
TOP = {areas_id: 60 + k for k, areas_id in enumerate([88, 86, 84])}


def _payload():
    return dict(stage="early", education_band="degree", years_experience=1.0, stated_interests=[],
                personality={}, cv_text=CV)


def test_area_list_matches_catalogue_and_prompt_ids():
    cat = pipeline.get_catalogue()
    m = areas.to_catalogue_ids(cat)
    assert len(m) == 94 and len(set(m.values())) == 94
    assert areas.NAMES[88] == "Data science & analytics" and areas.NAMES[86] == "AI & machine learning engineering"
    assert "94. UX, product & digital design" in engine.system_prompt() and "{{" not in engine.system_prompt()


def test_redaction_and_payload_shape():
    t = payload.redact("Jane Doe jane@x.com +94 77 123 4567 https://x.io/a 2019-2021", ["Jane Doe"])
    assert "jane@x.com" not in t and "123 4567" not in t and "x.io" not in t and "Jane" not in t and "2019-2021" in t
    p = pipeline.demo_profile("demo_b")
    pl = payload.build_payload(p)
    assert set(pl) == {"stage", "education_band", "years_experience", "stated_interests", "personality", "cv_text"}
    assert pl["personality"]["energy"]["side"] in {"introverted", "balanced"}
    assert payload.personality_json({"E": 50, "N": 70, "F": 55, "J": 65})["energy"]["strength"] == "balanced"


def test_validation_catches_bad_ids_quotes_and_banned_words():
    good = _answer(TOP, "Built a churn model in Python.")
    assert validate.validate(good, CV) == ([], [])
    bad = _answer(TOP, "Invented sentence.")
    assert validate.validate(bad, CV)[1]
    broken = _answer(TOP, "x")
    broken["scores"].pop()
    assert any("missing ids" in f for f in validate.validate(broken, CV)[0])
    mb = _answer(TOP, "Built a churn model in Python.")
    mb["participant_summary"]["x"] = "an MBTI type"
    assert validate.validate(mb, CV)[0]
    fixed = validate.repair_quotes(bad, CV)
    assert max(s["cv"] for s in fixed["scores"] if s["id"] in TOP) == 49
    # line breaks in the CV do not break an otherwise exact quote
    assert validate.validate(_answer(TOP, "model in Python. Led a team of five"), CV)[1] == []


def test_aggregation_median_multipliers_and_low_confidence():
    cat = pipeline.get_catalogue()
    q = "Built a churn model in Python."
    runs = [_answer({88: 80, 86: 70, 84: 60, 6: 90}, q, {6: ("neutral", "needs_track_record")}),
            _answer({88: 82, 86: 40, 84: 62, 6: 90}, q, {6: ("neutral", "needs_track_record")}),
            _answer({88: 78, 86: 72, 84: 58, 6: 90}, q, {6: ("neutral", "needs_track_record")})]
    out = engine.aggregate(runs, cat)
    df = out["scores"].set_index("id")
    assert df.loc[88, "cv"] == 80 and df.loc[86, "cv"] == 70
    assert df.loc[88, "final"] == 76.0                       # 80 x 0.95 (neutral) x 1.0
    assert df.loc[6, "final"] == round(90 * 0.95 * 0.45, 1)   # track-record penalty drops it below the data areas
    assert out["top10"].iloc[0]["id"] == 88 and bool(df.loc[86, "low_confidence"]) is True   # runs gave 70/40/72: spread 32 > 20
    assert bool(df.loc[88, "low_confidence"]) is False
    assert out["detail"][88]["evidence"][0]["quote"] == q


def test_run_match_retries_then_succeeds_and_fails_loudly():
    cat = pipeline.get_catalogue()
    good = json.dumps(_answer(TOP, "Built a churn model in Python."))
    calls = iter(["not json", good] * 3)
    out = engine.run_match(_payload(), cat, chat=lambda s, u, c=None: next(calls), runs=3)
    assert out["failed_runs"] == 0 and len(out["top10"]) == 10
    try:
        engine.run_match(_payload(), cat, chat=lambda s, u, c=None: "nope", runs=1)
    except client.LLMError:
        pass
    else:
        raise AssertionError("expected a loud failure")


def test_live_demo_b():
    s = client.settings()
    if not s["api_key"]:
        print("SKIP live OpenRouter check (no OPENROUTER_API_KEY)")
        return
    p = pipeline.demo_profile("demo_b")
    out = engine.run_match(payload.build_payload(p), pipeline.get_catalogue(), runs=1)
    names = " | ".join(out["top10"].name.head(5))
    print("live top 5:", names)
    assert out["top10"].iloc[0].cv >= 50


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for f in fns:
        f()
        print("ok ", f.__name__)
    print(len(fns), "checks passed")

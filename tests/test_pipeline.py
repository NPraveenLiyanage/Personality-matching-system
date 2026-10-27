"""Verification checks. Run:  python tests/test_pipeline.py   (or pytest)

All default tests use the made-up demo people in data/demo, so they run on a fresh clone. One test uses real
documents from the git-ignored private_data/ folder and is skipped when it is absent.
"""
import dataclasses
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "app"))

from careerx import catalogue, diagnostics, feedback, insights, narrowing, pipeline
from careerx.profile import build_profile, estimate_years, parse_personamap

CONSULTANT_SNIPPET = ("Head of Learning & Development and Managing Director of a consulting firm. Led leadership "
                      "development programmes, instructional design and a train-the-trainer faculty. Strategic "
                      "advisor to a government ministry on policy. Produced a television series for broadcast.")


def _skip(msg):
    print("SKIP", msg)


# ------------------------------------------------------------------------------------------ data and parsing
def test_catalogue_covers_every_in_scope_minor_group_once():
    r = catalogue.coverage_report(pipeline.get_catalogue())
    assert r["in_scope"] == 127 and r["missing"] == [] and r["duplicates"] == [] and r["unknown"] == []
    cat = pipeline.get_catalogue()
    assert cat.text.str.split().str.len().min() > 50
    assert cat.area_id.is_unique and cat.name.is_unique


def test_personamap_parse_reads_percentages_and_balanced_dimension():
    text = ("Profile code\nX N F J\n50% — evenly balanced\nExtroverted\n\n\nIntroverted\n70% Intuition\nIntuition\n"
            "55% Feeling\nFeeling\n65% Judging\nJudging\n")
    pm = parse_personamap(text)
    assert (pm["E"], pm["N"], pm["F"], pm["J"]) == (50.0, 70.0, 55.0, 65.0)
    assert pm["balanced"] == ["E"] and pm["code"] == "XNFJ"
    other = parse_personamap("70% Extroverted\n50% — evenly balanced\nIntuition\n70% Thinking\n100% Judging\n")
    assert other["E"] == 70.0 and other["F"] == 30.0 and other["J"] == 100.0       # 'Thinking' = 100 - Feeling


def test_personamap_parse_handles_label_first_layout():
    """Calybrate Me layout: '■Introverted (70%) — ...' (label, then percentage in brackets)."""
    text = ("Profile code\nI S T J\n■Introverted (70%) — moderately drawn to quiet\n■Sensing (75%) — facts\n"
            "■Thinking (85%) — logic\n■Judging (90%) — structure\n")
    pm = parse_personamap(text)
    assert (pm["E"], pm["N"], pm["F"], pm["J"]) == (30.0, 25.0, 15.0, 90.0) and pm["code"] == "ISTJ"
    assert parse_personamap("Extraverted: 66%\nIntuitive: 62%\nFeeling: 58%\nPerceiving: 55%")["J"] == 45.0
    assert parse_personamap("no percentages here, profile ISTJ") is None


def test_experience_years_merge_overlapping_roles():
    """Regression: concurrent roles used to be summed (63 'years') and crashed the app's number box."""
    cv = ("PROFESSIONAL EXPERIENCE\nFounder | Jan 2010 - Dec 2012\nDirector | Jan 2011 - Dec 2013\n"
          "Advisor | Jun 2012 - Present\nEDUCATION\nBSc | 2005 - 2009\n")
    yrs = estimate_years(cv, today=date(2020, 1, 1))
    assert 10.0 <= yrs <= 10.2, yrs                                  # Jan 2010 .. Jan 2020, not 3+3+8
    assert estimate_years("EXPERIENCE\nX | Jun 2010 - 2014\nEDUCATION\n", today=date(2020, 1, 1)) == 4.6
    d = diagnostics.naive_vs_merged_years(cv, date(2020, 1, 1))
    assert d["naive_years"] > d["merged_years"] and d["n_roles"] == 3


def test_demo_profiles_are_sane():
    b = pipeline.demo_profile("demo_b")
    assert b.education_band == 3 and 8.3 <= b.years_experience <= 8.5          # Jun 2018 .. 2026-10-15
    assert {"software_dev", "databases", "data_analytics"} <= set(b.cv_concepts)
    cv = "Operations coordinator 2018 - 2022.\n\nREFERENCES\nDr A, Lecturer and Founder of an academy\n"
    refs = build_profile("x", cv)
    assert "entrepreneurship" not in refs.cv_concepts and "teaching" not in refs.cv_concepts   # referees do not leak in
    leaked = build_profile("x", cv, keep_references=True)
    assert "entrepreneurship" in leaked.cv_concepts and "teaching" in leaked.cv_concepts


# ------------------------------------------------------------------------------------------ scoring
def test_gate_passes_and_every_top_area_has_evidence_for_every_demo_person():
    for pid in pipeline.demo_ids():
        out = pipeline.run(pipeline.demo_profile(pid))
        assert out["gate"]["passed"], (pid, out["gate"])
        top = out["scores"].head(10)
        assert (top.why_cv != "no direct CV evidence").all() and out["scores"].score.between(0, 100).all()


def test_interests_unknown_are_dropped_not_guessed():
    s = pipeline.run(pipeline.demo_profile("demo_b"))["scores"]
    assert s.attrs["weights_used"]["interest_strength"] == 0.0 and (s.interests == 0).all()


def test_stated_passion_surfaces_area_without_cv_evidence_and_never_lowers_others():
    p = pipeline.demo_profile("demo_b", interest_ids=["music_arts"])
    out = pipeline.run(p)
    s = out["scores"].set_index("name")
    assert s.loc["Music performance & production", "cv"] < 0.15
    assert "Music performance & production" in set(out["shortlist"].name)
    base = pipeline.run(pipeline.demo_profile("demo_b"))["scores"].set_index("name").score
    assert (s.score >= base.reindex(s.index) - 1e-9).all()


def test_balanced_dimension_gets_zero_weight():
    p = dataclasses.replace(pipeline.demo_profile("demo_b"), personality={"E": 50, "N": 50, "F": 50, "J": 50})
    s = pipeline.get_scorer().score(p)
    assert s.attrs["personality_weight"] == 0 and (s.modifier == 1.0).all()


def test_readiness_penalises_management_for_early_career():
    p = dataclasses.replace(pipeline.demo_profile("demo_b"), years_experience=1.0)
    s = pipeline.get_scorer().score(p).set_index("name")
    assert s.loc["Executive leadership & general management", "readiness"] < 0.5
    assert s.loc["Software & applications development", "readiness"] == 1.0


def test_scorer_is_never_mutated_by_per_call_weights():
    sc = pipeline.get_scorer()
    before = dict(sc.weights)
    sc.score(pipeline.demo_profile("demo_a"), weights=dict(personality_influence=0.6, interest_strength=0.1))
    assert sc.weights == before


def test_first_formula_fails_the_generosity_gate_and_final_passes():
    fc = diagnostics.formula_comparison(pipeline.demo_profile("demo_a"), pipeline.get_scorer())
    assert not fc["additive"]["gate"]["passed"] and fc["final"]["gate"]["passed"]


# ------------------------------------------------------------------------------------------ keyword list v1 / v2
def test_lexicon_v2_sees_categories_v1_cannot():
    from careerx.lexicon import CONCEPTS_V1, CONCEPTS_V2
    v1 = build_profile("x", CONSULTANT_SNIPPET, lexicon="v1").cv_concepts
    v2 = build_profile("x", CONSULTANT_SNIPPET, lexicon="v2").cv_concepts
    new = {"learning_development", "executive_leadership", "media_production", "public_policy", "consulting_advisory"}
    assert new <= set(v2) and not (new & set(v1))
    assert {c.id for c in CONCEPTS_V1} < {c.id for c in CONCEPTS_V2}        # v2 only adds


def test_coverage_check_flags_the_blind_spots_v1_had():
    c1 = diagnostics.lexicon_coverage(CONSULTANT_SNIPPET * 3, pipeline.get_scorer("v1"), "v1")
    c2 = diagnostics.lexicon_coverage(CONSULTANT_SNIPPET * 3, pipeline.get_scorer("v2"), "v2")
    assert c2["recognised_pct"] > c1["recognised_pct"]
    assert any(w in ("learning", "television", "consulting") for w, _ in c1["blind_spots"])


# ------------------------------------------------------------------------------------------ narrowing, feedback, insights
def test_narrowing_ends_with_exactly_ten_and_records_reasons():
    out = pipeline.run(pipeline.demo_profile("demo_a"))
    sl = out["shortlist"]
    ratings = {a: {"pref": "like", "reason": "interesting"} for a in sl.area_id[:5]}
    ratings.update({a: {"pref": "no", "reason": "not for me"} for a in sl.area_id[5:8]})
    d = narrowing.apply_ratings(sl, ratings)
    sc = pipeline.get_scorer()
    sim = narrowing.area_similarity(sc.X, list(d.area_id), list(pipeline.get_catalogue().area_id))
    top = narrowing.final_top(d, duel_picks=[], sim=sim)
    assert len(top) == 10 and top.area_id.is_unique
    assert not set(top.area_id) & set(sl.area_id[5:8]) and (top.reason != "").sum() >= 1


def test_feedback_comment_rule_and_summary():
    s = pipeline.run(pipeline.demo_profile("demo_a"))["scores"]
    fb = feedback.feedback_template(s)
    fb.loc[0, "accuracy"] = 5
    fb.loc[1, "accuracy"] = 2
    fb.loc[60, "accuracy"] = 1
    fb.loc[60, "comment"] = "I love this, not in my CV"
    assert list(feedback.missing_comments(fb).no) == [2]
    summ = feedback.summarise(fb)
    assert summ["rated"] == 3 and len(summ["false_negatives"]) == 1


def test_insight_sentences_match_the_numbers():
    p = pipeline.demo_profile("demo_a")
    out = pipeline.run(p)
    s, g = out["scores"], out["gate"]
    h = insights.headline(s, g, diagnostics.personality_effect(p, pipeline.get_scorer()))
    assert h["n_in_field"] == int((s.head(10).cluster == h["field"]).sum())
    assert h["top_area"] == s.iloc[0]["name"]
    mix = insights.cluster_mix(s)
    assert mix.areas.sum() == 10 and len(mix) <= 4                        # a donut stays readable
    assert str(round(100 * g["share_suitable"])) in insights.generosity_sentence(g)


# ------------------------------------------------------------------------------------------ the apps
def test_overview_page_loads_and_survives_a_very_long_career():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app" / "pages" / "overview.py"), default_timeout=180).run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.header) >= 4
    # add a participant whose dated roles add up to far more than any widget maximum
    at.text_input[0].set_value("Long career")
    ta = [t for t in at.text_area if "paste the CV" in t.label][0]
    ta.set_value("J. Doe. BSc.\nWORK EXPERIENCE\nConsultant | Jan 1950 - Present\nEDUCATION\nBSc | 1948 - 1950\n")
    [b for b in at.button if "Add participant" in b.label][0].click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_bench_page_loads():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app" / "pages" / "bench.py"), default_timeout=180).run()
    assert not at.exception, [e.value for e in at.exception]


# ------------------------------------------------------------------------------------------ privacy
def test_no_real_participant_files_are_tracked_by_git():
    if not (ROOT / ".git").exists():
        return _skip("not a git checkout")
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    assert not [f for f in tracked if f.lower().endswith(".pdf")], "a PDF is tracked"
    assert not [f for f in tracked if f.startswith(("private_data/", "outputs/", "data/profiles/"))]
    assert not [f for f in tracked if f.endswith(".ipynb") or "__pycache__" in f]
    assert not [f for f in tracked if f.startswith("PERSONAMAP_") or f == ".env"], "participant workbook or .env is tracked"


# ------------------------------------------------------------------------------------------ optional: real data, local only
def test_real_documents_regression_if_present():
    cv, pm = pipeline.PRIVATE_DIR / "participant_a_cv.pdf", pipeline.PRIVATE_DIR / "participant_a_personamap.pdf"
    if not (cv.exists() and pm.exists()):
        return _skip("private_data not present")
    res = {}
    for lex in ("v1", "v2"):
        p = pipeline.private_profile(cv, pm, lexicon=lex, today=pipeline.REFERENCE_DATE)
        res[lex] = pipeline.run(p, lexicon=lex)
        assert res[lex]["gate"]["passed"]
    assert len(set(res["v1"]["scores"].head(10).name) & set(res["v2"]["scores"].head(10).name)) >= 8
    from careerx.profile import extract_pdf_text
    pmv = parse_personamap(extract_pdf_text(pm))
    assert pmv and set("ENFJ") <= set(pmv)


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as e:                      # noqa: BLE001
                failed += 1
                print("FAIL", name, "->", repr(e)[:400])
    sys.exit(1 if failed else 0)

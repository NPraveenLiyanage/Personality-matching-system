"""Step 2 (PersonaMap work-style fit): local baseline, model-fit verification, and the combined engine. All offline, invented data."""
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from careerx import engines, personamap as PM, workstyle as W  # noqa: E402
from careerx.evidence import client, fit  # noqa: E402
from test_personamap import report  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFS = yaml.safe_load((ROOT / "data/processed/area_definitions_v3.yaml").read_text(encoding="utf-8"))
PROFILES = W.load_profiles()
# Quotes that exist verbatim in the invented report (see test_personamap.report)
Q_PLAN = "You plan and schedule thoroughly and are slower to close the decision itself."
Q_DRAIN = "Plans that change repeatedly after they have been agreed."
Q_DECIDE = "You would bring people into decisions rather than hand them down."


def pm_from(prefs: dict, commit: str | None = None) -> PM.PersonaMap:
    steps = [dict(step="Read the situation", rating="Fastest step"), dict(step="Frame the meaning", rating="Strong"),
             dict(step="Plan the approach", rating="Strong"), dict(step="Commit and execute", rating=commit or "Moderate")]
    return PM.PersonaMap(dict(prefs, code="", balanced=[], found=sorted(prefs)), [], steps, {}, [])


def band(prefs, area, commit=None):
    return W.baseline_fit(pm_from(prefs, commit), PROFILES[area]["demands"])["band"]


# ------------------------------------------------------------------ area profiles
def test_profiles_cover_exactly_the_94_areas_with_valid_demands_and_are_marked_unreviewed():
    raw = yaml.safe_load(W.PATH.read_text(encoding="utf-8"))
    assert raw["status"] == "draft_unreviewed" and set(raw["areas"]) == set(DEFS["areas"]) and len(raw["areas"]) == 94
    for a in raw["areas"].values():
        assert set(a["demands"]) == {"people", "abstract", "values", "structure", "pace"}
        assert all(isinstance(v, int) and 0 <= v <= 4 for v in a["demands"].values())


# ------------------------------------------------------------------ deterministic baseline
def test_baseline_hand_labelled_profiles():
    structured_ideas = dict(E=40, N=85, F=30, J=85)          # planner of abstract, objective work
    warm_people = dict(E=85, N=30, F=85, J=40)               # people-centred, concrete, flexible
    assert band(structured_ideas, "A043", "Fastest step") == "strong"       # software
    assert band(structured_ideas, "A027") == "stretch"                      # personal care: people, concrete, values-led
    assert band(structured_ideas, "A055") == "mixed"                        # contact centre: strains on people/concrete, matches on structure
    assert band(warm_people, "A019", "Fastest step") == "strong"            # nursing
    assert band(warm_people, "A013") == "stretch"                           # mathematics: alone, abstract, objective
    assert band(warm_people, "A039") == "stretch"                           # data entry


def test_baseline_balanced_scales_carry_no_weight_and_all_balanced_is_neutral():
    all_even = dict(E=50, N=52, F=48, J=50)
    r = W.baseline_fit(pm_from(all_even, commit="Moderate"), PROFILES["A043"]["demands"])
    assert r["band"] == "neutral" and r["score"] is None
    dims = {d["dim"]: d for d in W.baseline_fit(pm_from(dict(E=50, N=80, F=50, J=50)), PROFILES["A043"]["demands"])["dims"]}
    assert dims["people"]["weight"] == 0 and dims["abstract"]["weight"] > 0


def test_baseline_closing_slowly_is_a_strain_only_where_the_work_demands_fast_decisions():
    p = dict(E=50, N=50, F=50, J=65)
    slow = W.baseline_fit(pm_from(p, "Most-skipped step"), PROFILES["A090"]["demands"])        # cybersecurity, pace 4
    calm = W.baseline_fit(pm_from(p, "Most-skipped step"), PROFILES["A047"]["demands"])        # libraries, pace 1
    assert slow["hard_mismatches"] == 1 and calm["hard_mismatches"] == 0 and calm["score"] > slow["score"]
    assert any("closing decisions" in x for x in slow["reasons"])


def test_baseline_reads_the_parsed_report_and_never_mentions_ability():
    pm = PM.parse_text(report())
    r = W.baseline_fit(pm, PROFILES["A043"]["demands"])
    assert r["band"] in {"strong", "mixed", "stretch"} and r["reasons"]
    assert not fit._ABILITY.search(" ".join(r["reasons"]))


def test_compare_flags_only_a_two_level_gap():
    assert W.compare("strong", "stretch")["low_confidence"] and W.compare("stretch", "strong")["low_confidence"]
    assert not W.compare("strong", "mixed")["low_confidence"]
    assert not W.compare("insufficient_info", "strong")["low_confidence"] and not W.compare("strong", "neutral")["low_confidence"]


# ------------------------------------------------------------------ model fit and its verification
CANDS = [dict(area_id="A043", name="Software"), dict(area_id="A019", name="Nursing")]


def row(aid, band_="mixed", reasons=None, watch=None):
    return dict(area_id=aid, reasoning="r", fit_band=band_, reasons=reasons if reasons is not None else
                [dict(point="The report describes careful planning.", quote=Q_PLAN)], watch_outs=watch or [])


def stub(rows, finish="stop", calls=None):
    def chat(system, user, schema, cfg=None):
        if calls is not None:
            calls.append(user)
        return client.ChatResult(content=json.dumps(dict(fits=rows)) if not isinstance(rows, str) else rows, finish_reason=finish,
                                 model="m", provider="p", usage={"completion_tokens": 10})
    return chat


def run(rows, **kw):
    return fit.run_fit(PM.parse_text(report()), CANDS, DEFS, chat=stub(rows, **kw))


def test_valid_rows_are_accepted_and_carry_the_baseline():
    r = run([row("A043", "strong"), row("A019", "mixed")])
    assert r["status"] == "accepted" and set(r["fits"]) == {"A043", "A019"}
    assert r["fits"]["A043"]["fit_band"] == "strong" and r["fits"]["A043"]["baseline"]["band"] in {"strong", "mixed", "stretch", "neutral"}
    assert r["fits"]["A043"]["reasons"][0]["quote"] == Q_PLAN


def test_fabricated_or_overlong_quotes_and_ability_wording_are_dropped_and_logged():
    bad = [dict(point="Invented.", quote="You are the most organised person alive."),
           dict(point="Fine.", quote=" ".join(["plan"] * 50)),
           dict(point="The report shows they will succeed here.", quote=Q_PLAN)]
    r = run([row("A043", "mixed", reasons=bad + [dict(point="Real.", quote=Q_DRAIN)]), row("A019", "mixed")])
    x = r["fits"]["A043"]
    assert [q["quote"] for q in x["reasons"]] == [Q_DRAIN] and len(x["changes"]) == 3 and r["status"] == "repaired"


def test_strong_or_stretch_without_a_valid_quote_becomes_insufficient_info():
    r = run([row("A043", "strong", reasons=[dict(point="x", quote="not in the report at all")]),
             row("A019", "stretch", reasons=[])])
    assert r["fits"]["A043"]["fit_band"] == "insufficient_info" and r["fits"]["A019"]["fit_band"] == "insufficient_info"
    assert r["fits"]["A043"]["original_band"] == "strong"


def test_extra_missing_and_duplicate_areas_are_handled():
    r = run([row("A043", "mixed"), row("A043", "strong"), row("A999", "strong")])
    assert r["fits"]["A043"]["fit_band"] == "mixed" and r["fits"]["A019"]["fit_band"] == "insufficient_info"
    assert "A999" not in r["fits"] and {x["reason"] for x in r["stage"]["rejected"]} == {"duplicate row", "not one of the areas asked about"}


def test_quote_matching_ignores_case_whitespace_and_line_breaks():
    q = "you plan and SCHEDULE   thoroughly and are slower to close the decision itself."
    r = run([row("A043", "strong", reasons=[dict(point="p", quote=q)]), row("A019")])
    assert r["fits"]["A043"]["fit_band"] == "strong" and r["fits"]["A043"]["changes"] == []


def test_low_confidence_when_model_and_baseline_are_two_levels_apart():
    pm = pm_from(dict(E=85, N=30, F=85, J=40), "Fastest step")
    pm.sections = {"stands_out": Q_PLAN}
    r = fit.run_fit(pm, [dict(area_id="A013", name="Maths")], DEFS, chat=stub([row("A013", "strong")]))
    assert r["fits"]["A013"]["baseline"]["band"] == "stretch" and r["fits"]["A013"]["low_confidence"] is True


def test_invalid_json_gets_one_retry_then_fails_with_baseline_only():
    calls = []
    r = fit.run_fit(PM.parse_text(report()), CANDS, DEFS, chat=stub("not json", calls=calls))
    assert len(calls) == 2 and r["status"] == "failed" and "not valid JSON" in r["errors"][0] and set(r["baseline_only"]) == {"A043", "A019"}


def test_truncation_and_provider_errors_fail_clearly_without_fallback():
    r = run([row("A043")], finish="length")
    assert r["status"] == "failed" and "truncated" in r["errors"][0] and r["fits"] == {} and "baseline_only" in r

    def boom(system, user, schema, cfg=None):
        raise client.EvidenceLLMError("HTTP 429")
    r = fit.run_fit(PM.parse_text(report()), CANDS, DEFS, chat=boom)
    assert r["status"] == "failed" and "429" in r["errors"][0] and "baseline_only" in r


def test_the_model_sees_the_report_and_area_descriptions_but_never_the_cv():
    calls = []
    run([row("A043"), row("A019")], calls=calls)
    user = calls[0]
    assert user.startswith("<<<REPORT_AND_AREAS\n") and user.endswith("\nREPORT_AND_AREAS>>>")
    body = json.loads(user[len("<<<REPORT_AND_AREAS\n"):-len("\nREPORT_AND_AREAS>>>")])
    assert set(body) == {"report", "preferences", "balanced_scales", "readings", "problem_solving_steps", "areas"}
    assert [a["area_id"] for a in body["areas"]] == ["A043", "A019"] and set(body["areas"][0]) == {
        "area_id", "name", "definition", "typical_activities"}
    assert "Kasun" not in user and "Prepared for" not in user
    assert "never" in fit.system_prompt().lower() and "untrusted" in fit.system_prompt().lower()


# ------------------------------------------------------------------ combined engine
def step1(status="accepted", sup=None, exp=None):
    return engines.EngineResult("llm_evidence", "v", status, sup if sup is not None else [dict(rank=1, area_id="A043", name="Software"),
                                dict(rank=2, area_id="A086", name="Data")], exp or [], [], [], [], {})


def test_final_engine_adds_fit_without_changing_supported_areas_or_order(monkeypatch):
    s1 = step1()
    monkeypatch.setattr(engines, "run_evidence", lambda *a, **k: s1)
    r = engines.run("final", "CV TEXT SECRET", "A", defs=DEFS, personamap_text=report(), chat=stub([row("A043", "strong"), row("A086")]))
    assert r.engine_id == "final" and [x["area_id"] for x in r.supported] == ["A043", "A086"] and r.supported[0]["rank"] == 1
    assert set(r.fit["fits"]) == {"A043", "A086"} and "fit" in r.run_meta


def test_final_engine_without_report_or_candidates_or_after_step1_failure_skips_the_fit(monkeypatch):
    s1 = step1()
    monkeypatch.setattr(engines, "run_evidence", lambda *a, **k: s1)
    r = engines.run("final", "cv", "A", defs=DEFS)
    assert r.fit == {} and any(w.startswith("no_personamap") for w in r.warnings) and len(r.supported) == 2
    monkeypatch.setattr(engines, "run_evidence", lambda *a, **k: step1(sup=[]))
    assert any(w.startswith("fit_skipped") for w in engines.run("final", "cv", "A", defs=DEFS, personamap_text=report()).warnings)
    monkeypatch.setattr(engines, "run_evidence", lambda *a, **k: step1(status="failed"))
    assert engines.run("final", "cv", "A", defs=DEFS, personamap_text=report()).fit == {}


def test_final_engine_keeps_step1_intact_when_the_fit_call_fails(monkeypatch):
    s1 = step1()
    monkeypatch.setattr(engines, "run_evidence", lambda *a, **k: s1)

    def boom(system, user, schema, cfg=None):
        raise client.EvidenceLLMError("HTTP 500")
    r = engines.run("final", "cv", "A", defs=DEFS, personamap_text=report(), chat=boom)
    assert r.status == "accepted" and len(r.supported) == 2 and r.fit["status"] == "failed" and r.fit["baseline_only"]
    assert any(w.startswith("fit_failed") for w in r.warnings)


# ------------------------------------------------------------------ cache and cost totals
def test_cost_totals_sum_every_call_and_never_report_unknown_cost_as_zero():
    from careerx import cost
    meta = {"extraction": dict(model="nvidia/x:free", usage=dict(prompt_tokens=1000, completion_tokens=2000), latency_s=3),
            "assessment": dict(model="nvidia/x:free", usage=dict(prompt_tokens=20000, completion_tokens=9000), latency_s=40),
            "fit": dict(model="nvidia/x:free", usage=dict(prompt_tokens=2000, completion_tokens=8000), latency_s=20)}
    t = cost.totals(meta)
    assert t["calls"] == 3 and t["prompt_tokens"] == 23000 and t["completion_tokens"] == 19000 and t["estimated_cost_usd"] == 0 and t["latency_s"] == 63
    paid = {k: dict(v, model="anthropic/claude-haiku-5.5") for k, v in meta.items()}
    assert cost.totals(paid)["estimated_cost_usd"] == pytest.approx((23000 * 0.1 + 19000 * 0.5) / 1e6, rel=1e-3)
    unknown = {k: dict(v, model="someone/unpriced-model") for k, v in meta.items()}
    assert cost.totals(unknown)["estimated_cost_usd"] is None


def test_final_engine_cache_makes_a_repeat_free_and_keys_on_every_input(monkeypatch):
    runs = []

    def fake(*a, **k):
        runs.append(1)
        return step1()
    monkeypatch.setattr(engines, "run_evidence", fake)
    cache, calls = {}, []
    chat = stub([row("A043", "strong"), row("A086")], calls=calls)
    kw = dict(defs=DEFS, personamap_text=report(), chat=chat, cache=cache)
    r1 = engines.run("final", "CV A", "n", **kw)
    r2 = engines.run("final", "CV A", "n", **kw)
    assert r2 is r1 and len(runs) == 1 and len(calls) == 1 and r2.run_meta["cache_hit"] is True and "totals" in r1.run_meta
    engines.run("final", "CV B", "n", **kw)                                   # different CV: new run
    engines.run("final", "CV A", "n", **dict(kw, personamap_text=report(balanced=False)))   # different report: new run
    engines.run("final", "CV A", "n", **dict(kw, hide=["Acme"]))                              # different masking: new run
    assert len(runs) == 4
    assert all(len(k) == 64 and "CV A" not in k for k in cache)               # only digests are kept as keys


def test_failed_results_are_never_cached(monkeypatch):
    monkeypatch.setattr(engines, "run_evidence", lambda *a, **k: step1(status="failed"))
    cache = {}
    engines.run("final", "cv", "n", defs=DEFS, personamap_text=report(), cache=cache)
    assert cache == {}

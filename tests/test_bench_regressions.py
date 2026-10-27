"""Phase 1 benchmark checks and frozen-baseline regression tests (offline, synthetic cases only).

* Case-file sanity: ids, splits, pairs and category coverage.
* Metric arithmetic.
* Rule engine: the known domain-confusion failures are recorded as strict xfail (they must keep failing until Phase 3 fixes them
  elsewhere; an unexpected pass is flagged); every other trap case must not get worse.
* Direct-LLM validator gaps (frozen code) recorded as strict xfail.
Passing tests here are not evidence of accuracy; they pin known behaviour.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from bench import metrics  # noqa: E402
from careerx import pipeline  # noqa: E402
from careerx.llm import areas, client, engine, validate  # noqa: E402

CASES = metrics.load_cases()
BY_ID = {c["id"]: c for c in CASES}
CAT = pipeline.get_catalogue()

# Cases where the rule engine shows a trap area in its top 10 (frozen baseline, bench/runs/career_rule_*.json).
RULE_KNOWN_TRAP_FAILURES = {
    "c01_hospital_app_developer", "c03_bank_app_developer", "c04_accountant", "c05_legal_chatbot_developer",
    "c06_lawyer", "c12_team_project_limited_contribution", "c13_explicit_negation", "c15_referee_titles"}


# ------------------------------------------------------------------ case file
def test_cases_are_well_formed():
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)) >= 20
    valid = set(CAT.area_id)
    for c in CASES:
        assert c["synthetic"] is True and c["split"] in ("tune", "holdout")
        refs = set(c["supported"]) | set(c.get("acceptable", [])) | set(c.get("traps", []))
        assert refs <= valid, (c["id"], refs - valid)
        assert not set(c["supported"]) & set(c.get("traps", [])), c["id"]
        assert not set(c.get("acceptable", [])) & set(c.get("traps", [])), c["id"]
        assert len(c["cv_text"].split()) >= 25
    groups = {}
    for c in CASES:
        if c.get("pair_group"):
            groups.setdefault(c["pair_group"], []).append(c["id"])
    assert groups and all(len(v) >= 2 for v in groups.values()), groups
    cats = {x for c in CASES for x in c["categories"]}
    for needed in ("domain_confusion", "genuine_positive", "negation", "listed_skill_only", "referee_titles",
                   "ambiguous_abbreviation", "incidental_domain_terms", "prompt_injection", "career_change",
                   "old_experience", "team_attribution", "mixed_evidence"):
        assert needed in cats, needed
    assert {"tune", "holdout"} <= {c["split"] for c in CASES}


# ------------------------------------------------------------------ metrics
def test_metric_arithmetic():
    c1 = dict(id="a", supported=["A1", "A2"], acceptable=["A3"], traps=["A9"], categories=["x"], split="tune")
    c2 = dict(id="b", supported=["A5"], acceptable=[], traps=[], categories=["x"], split="holdout")
    m1 = metrics.case_metrics(c1, ["A1", "A9", "A3", "A4"], k=3)
    assert m1["supported_found"] == ["A1"] and m1["supported_missed"] == ["A2"] and m1["trap_hits"] == ["A9"]
    assert m1["n_in_authored_ok_set"] == 2 and m1["top1_in_authored_ok_set"] and m1["rank_of_first_supported"] == 1
    m2 = metrics.case_metrics(c2, ["A7", "A8", "A5"], k=2)
    assert m2["supported_missed"] == ["A5"] and m2["rank_of_first_supported"] == 3 and not m2["top1_in_authored_ok_set"]
    agg = metrics.aggregate([c1, c2], {"a": m1, "b": m2}, k=3)["overall"]
    assert agg["domain_confusion_cases"] == "1/1" and agg["supported_recall"] == "1/3"
    assert agg["top1_in_authored_ok_set"] == "1/2" and agg["mean_areas_displayed"] == 2.5
    # an engine may show fewer areas, label traps as exploration, or abstain
    m3 = metrics.case_metrics(c1, ["A1"], k=3, exploration=["A9"])
    assert m3["trap_hits"] == [] and m3["trap_as_exploration"] == ["A9"] and m3["n_displayed"] == 1
    c3 = dict(id="c", supported=[], acceptable=["A3"], traps=[], categories=["y"], split="tune")
    m4 = metrics.case_metrics(c3, [], k=3)
    a2 = metrics.aggregate([c1, c3], {"a": m3, "c": m4}, k=3)["overall"]
    assert m4["abstained"] and a2["abstained_on_no_support_cases"] == "1/1" and a2["trap_cases_shown_only_as_exploration"] == 1
    assert a2["authored_ok_share_of_displayed_lower_bound"] == 1.0
    assert metrics.aggregate([c1, c2], {"a": m1, "b": m2}, k=3)["by_split"]["holdout"]["n_cases"] == 1


# ------------------------------------------------------------------ rule engine baseline
def _rule_top10(case):
    p = pipeline.build_profile("Participant", case["cv_text"], today=pipeline.REFERENCE_DATE)
    return list(pipeline.run(p)["scores"].sort_values("score", ascending=False).area_id[:10])


@pytest.mark.parametrize("cid", [c["id"] for c in CASES if c.get("traps")])
def test_rule_engine_trap_areas_not_displayed(cid):
    if cid in RULE_KNOWN_TRAP_FAILURES:
        pytest.xfail("known rule-engine domain confusion (frozen baseline); Phase 3 gate target")
    case = BY_ID[cid]
    assert not [a for a in _rule_top10(case) if a in case["traps"]]


@pytest.mark.parametrize("cid", sorted(RULE_KNOWN_TRAP_FAILURES))
def test_rule_engine_known_failures_still_reproduce(cid):
    """If a rule-engine change makes one of these pass, update the frozen baseline deliberately instead of silently."""
    case = BY_ID[cid]
    assert [a for a in _rule_top10(case) if a in case["traps"]], f"{cid} no longer shows a trap area"


def test_hospital_app_reproduces_nursing_paramedic_medicine():
    ids = _rule_top10(BY_ID["c01_hospital_app_developer"])
    names = {CAT.set_index("area_id").name[a] for a in ids}
    assert {"Nursing & midwifery", "Paramedic & emergency care", "Medicine"} <= names


# ------------------------------------------------------------------ frozen direct-LLM validator gaps
def _id(name):
    return next(i for i, n in areas.NAMES.items() if n == name)


def _answer(top_id: int, quote: str, evidence=True):
    scores = [dict(id=i, cv=90 if i == top_id else 5, style="neutral", style_reason="", level="ok", interest=None)
              for i in range(1, 95)]
    ev = [dict(quote=quote, supports="shows it")] if evidence else []
    return dict(participant_summary=dict(stage="early"), scores=scores,
                top10_detail=[dict(id=top_id, evidence=ev, missing=[], overlaps_with=[], style_note="", level_note="")])


HOSPITAL_CV = "Built a hospital patient management web application using Python, SQL and React."


@pytest.mark.xfail(strict=True, reason="validate.py only checks that the quote exists, not that it supports the area")
def test_validator_rejects_real_but_unrelated_quote_for_nursing():
    data = _answer(_id("Nursing & midwifery"), "Built a hospital patient management web application")
    fatal, quote_problems = validate.validate(data, HOSPITAL_CV)
    assert fatal or quote_problems


@pytest.mark.xfail(strict=True, reason="validate.py accepts cv>=50 with no evidence unless some quote also fails")
def test_validator_rejects_high_score_without_evidence():
    data = _answer(_id("Software & applications development"), "", evidence=False)
    fatal, quote_problems = validate.validate(data, HOSPITAL_CV)
    assert fatal or quote_problems


@pytest.mark.xfail(strict=True, reason="a detail row without an id raises KeyError instead of a handled failure")
def test_malformed_detail_row_is_a_handled_failure():
    data = _answer(_id("Software & applications development"), "Built a hospital patient management web application")
    data["top10_detail"][0].pop("id")
    chat = lambda s, u, c=None: json.dumps(data)  # noqa: E731
    payload = dict(stage="early", education_band="degree", years_experience=1.0, stated_interests=[], personality={},
                   cv_text=HOSPITAL_CV)
    with pytest.raises(client.LLMError):
        engine.run_match(payload, CAT, chat=chat, runs=1)

"""Offline checks for stage 2 (assessment verification, ranking, engine wiring) with fake models and synthetic records.

They show the backend rejects or downgrades unsupported claims and keeps genuine practitioners. They do not measure how well a
real model assesses careers; that is the benchmark's job.
"""
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from careerx import pipeline  # noqa: E402
from careerx.evidence import assess, client, engine, rank, schema, verify  # noqa: E402

AREAS = ["A018", "A019", "A033", "A043", "A058"]
NAMES = {"A018": "Medicine", "A019": "Nursing & midwifery", "A033": "Finance, accounting", "A043": "Software development",
         "A058": "Food & beverage service"}
REG = {"A018": ["physician", "doctor", "mbbs"], "A019": ["nurse", "nursing"], "A033": ["accountant", "accounting"]}


def rec(eid, etype="employment", role=None, actions=(), tools=(), domain=None, qual=None, contribution="own", neg=False,
        quote="Q text here", recency="recent"):
    return schema.EvidenceRecord(evidence_id=eid, passage_id="P001", section="experience", page=None, quote=quote,
                                 evidence_type=etype, role=role, candidate_actions=list(actions), candidate_responsibilities=[],
                                 tools_methods=list(tools), domain_context=domain, qualification=qual, contribution=contribution,
                                 dates=dict(start="2022", end="2026", duration_months=None, recency=recency), negation=neg,
                                 ambiguities=[], missing_info=[])


DEV = rec("E001", "project", actions=["built a web application", "wrote the REST API"], tools=["Python"], domain="healthcare",
          quote="Built a hospital patient management web application using Python, SQL and React.")
NURSE = rec("E002", "employment", role="Staff Nurse", actions=["administered medication"], domain="healthcare",
            quote="Administered medication and monitored patients.")
NURSE_EDU = rec("E003", "education", qual={"subject": "Nursing", "level": "Diploma"}, quote="Diploma in Nursing")
SKILLS = rec("E004", "listed_skill_only", tools=["Python"], contribution="unknown", quote="Python, SQL, Machine Learning")
INTEREST = rec("E005", "stated_interest", contribution="unknown", quote="Interested in teaching.")
TEAM = rec("E006", "project", actions=[], contribution="team_only", domain="banking", quote="The team built a loan app.")
NEG = rec("E007", "employment", contribution="unknown", neg=True, quote="No clinical experience.")
ALL = [DEV, NURSE, NURSE_EDU, SKILLS, INTEREST, TEAM, NEG]


def row(aid, cls="unsupported", rel=None, ev=(), why=None, gaps=(), unc="medium"):
    return dict(area_id=aid, support_class=cls, relevance=rel, evidence=[dict(evidence_id=e, basis=b) for e, b in ev],
                rationale=why, qualification_gaps=list(gaps), uncertainty=unc)


def data(**over):
    rows = {a: row(a) for a in AREAS}
    rows.update(over)
    return dict(assessments=[rows[a] for a in AREAS], notes=[])


def run(records=ALL, **over):
    return verify.verify(data(**over), records, AREAS, REG)


# ------------------------------------------------------------------ the core confusion cases
def test_hospital_app_developer_cannot_be_direct_nurse_or_doctor():
    v = run(A019=row("A019", "direct", 3, [("E001", "actions")], "built a hospital app"),
            A018=row("A018", "transferable", 2, [("E001", "tools")], "uses healthcare data"))
    for aid in ("A019", "A018"):
        a = v.rows[aid]
        assert a.support_class == "domain_exposure_only" and a.status == "repaired" and a.relevance is None
        assert any("regulated occupation" in c for c in a.changes) and [e for e, _ in a.evidence] == ["E001"]
    assert v.status == "repaired"


def test_genuine_nurse_passes_the_regulated_guard():
    v = run(A019=row("A019", "direct", 4, [("E002", "role"), ("E003", "qualification")], "Staff Nurse with a nursing diploma"))
    a = v.rows["A019"]
    assert a.support_class == "direct" and a.relevance == 4 and a.status == "accepted" and len(a.evidence) == 2


def test_nurse_who_built_a_tool_keeps_nursing_and_may_have_transferable_software():
    scheduler = rec("E010", "project", actions=["built a scheduling tool"], tools=["Excel"], domain="healthcare",
                    quote="Built a shift-scheduling spreadsheet tool in Excel")
    v = verify.verify(data(A019=row("A019", "direct", 4, [("E002", "role")], "nurse"),
                           A043=row("A043", "transferable", 1, [("E010", "tools")], "small tool")),
                      [NURSE, scheduler], AREAS, REG)
    assert v.rows["A019"].support_class == "direct" and v.rows["A043"].support_class == "transferable"
    assert v.status == "accepted"


def test_lawyer_and_accountant_pass_and_developer_gets_no_accounting():
    acct = rec("E020", "employment", role="Senior Accountant", actions=["prepared financial statements"])
    v = verify.verify(data(A033=row("A033", "direct", 4, [("E020", "role")], "accountant")), [acct], AREAS, REG)
    assert v.rows["A033"].support_class == "direct"
    bank = rec("E021", "project", actions=["developed REST APIs"], domain="banking", quote="Developed REST APIs for a bank")
    v = verify.verify(data(A033=row("A033", "direct", 3, [("E021", "actions")], "banking platform")), [bank], AREAS, REG)
    assert v.rows["A033"].support_class == "domain_exposure_only"


# ------------------------------------------------------------------ evidence-type rules
def test_listed_skills_interest_team_and_negation_cannot_support_positive_classes():
    v = run(A043=row("A043", "direct", 3, [("E004", "tools")], "has Python"),
            A058=row("A058", "transferable", 2, [("E006", "actions")], "team"),
            A033=row("A033", "direct", 2, [("E007", "role")], "no"))
    assert v.rows["A043"].support_class == "insufficient_info"          # only a skills list cited
    assert v.rows["A058"].support_class == "domain_exposure_only"        # team_only record that has a domain_context
    assert v.rows["A033"].support_class == "unsupported"                 # negated
    assert all(v.rows[a].status == "repaired" and v.rows[a].relevance is None for a in ("A043", "A058", "A033"))


def test_basis_field_must_exist_on_the_record():
    v = run(A043=row("A043", "direct", 3, [("E001", "role")], "no role on this record"))
    assert v.rows["A043"].support_class == "domain_exposure_only" and any("no role content" in c for c in v.rows["A043"].changes)


def test_domain_and_interest_basis_cannot_support_direct():
    v = run(A043=row("A043", "direct", 3, [("E001", "domain")], "domain"))
    assert v.rows["A043"].support_class == "domain_exposure_only"


def test_classes_only_move_down_never_up():
    v = run(A043=row("A043", "unsupported", None, [("E001", "actions")]))
    assert v.rows["A043"].support_class == "unsupported" and v.rows["A043"].evidence == []


def test_interest_and_domain_exposure_rows():
    v = run(A058=row("A058", "interest_only", None, [("E005", "interest")]), A033=row("A033", "interest_only", None, [("E001", "interest")]),
            A019=row("A019", "domain_exposure_only", None, [("E001", "domain")], "healthcare setting"),
            A018=row("A018", "domain_exposure_only", None, [("E004", "domain")]))
    assert v.rows["A058"].support_class == "interest_only" and v.rows["A058"].status == "accepted"
    assert v.rows["A033"].support_class == "unsupported"                 # cited record is not a stated interest
    assert v.rows["A019"].support_class == "domain_exposure_only"
    assert v.rows["A018"].support_class == "unsupported"                 # cited record has no domain_context


# ------------------------------------------------------------------ structure
def test_unknown_evidence_ids_are_dropped_and_relevance_rules():
    v = run(A043=row("A043", "direct", None, [("E001", "actions"), ("E999", "actions")], "dev"),
            A058=row("A058", "unsupported", 3, []))
    a = v.rows["A043"]
    assert a.support_class == "direct" and a.relevance == 1 and [e for e, _ in a.evidence] == ["E001"]
    assert any("E999" in c for c in a.changes) and any("lowest value" in c for c in a.changes)
    assert v.rows["A058"].relevance is None


@pytest.mark.parametrize("bad", [True, 5, -1, 2.5, "3"])
def test_bad_relevance_is_a_response_error(bad):
    v = run(A043=row("A043", "direct", bad, [("E001", "actions")]))
    assert v.status == "failed" and v.errors


def test_missing_duplicate_invalid_rows_and_shapes():
    d = data()
    d["assessments"].pop()
    assert "missing rows" in verify.verify(d, ALL, AREAS, REG).errors[0]
    d = data()
    d["assessments"].append(row("A019"))
    assert "duplicate" in verify.verify(d, ALL, AREAS, REG).errors[0]
    d = data()
    d["assessments"][0]["support_class"] = "probably"
    assert verify.verify(d, ALL, AREAS, REG).status == "failed"
    for bad in ([], "x", {"assessments": "x"}, {"nope": 1}):
        assert verify.verify(bad, ALL, AREAS, REG).status == "failed"
    d = data()
    d["assessments"][0]["area_id"] = "A999"
    assert verify.verify(d, ALL, AREAS, REG).status == "failed"


# ------------------------------------------------------------------ ranking
def test_ranking_is_deterministic_tiered_and_exploration_is_separate():
    old = rec("E030", "employment", role="Teacher", actions=["taught"], recency="old")
    v = verify.verify(data(
        A043=row("A043", "transferable", 4, [("E001", "actions")], "x"),
        A019=row("A019", "direct", 2, [("E002", "role")], "x"),
        A058=row("A058", "direct", 2, [("E030", "role")], "x"),
        A018=row("A018", "domain_exposure_only", None, [("E001", "domain")], "setting"),
        A033=row("A033", "interest_only", None, [("E005", "interest")])), [DEV, NURSE, old, INTEREST], AREAS,
        {"A019": ["nurse"], "A018": ["doctor"]})
    out = rank.rank(v.rows, [DEV, NURSE, old, INTEREST], NAMES)
    assert [s["area_id"] for s in out["supported"]] == ["A019", "A058", "A043"]   # direct (recent before old) then transferable
    assert [s["rank"] for s in out["supported"]] == [1, 2, 3]
    assert [e["area_id"] for e in out["exploration"]] == ["A033", "A018"] and all(e["label"] for e in out["exploration"])
    assert out["supported"][0]["explanation"].startswith("Direct evidence - Staff Nurse (2022 - 2026): ")
    assert out == rank.rank(v.rows, [DEV, NURSE, old, INTEREST], NAMES)


def test_nothing_supported_gives_an_empty_list_not_ten():
    out = rank.rank(run().rows, ALL, NAMES)
    assert out["supported"] == [] and out["exploration"] == []


# ------------------------------------------------------------------ definitions and regulated files
def test_real_regulated_and_definition_files_reference_valid_areas():
    reg = assess.load_regulated()
    valid = set(pipeline.get_catalogue().area_id)
    assert reg and set(reg) <= valid and all(isinstance(t, list) and t for t in reg.values())
    assert {"A018", "A019", "A033", "A046", "A030"} <= set(reg)
    if assess.DEFINITIONS_PATH.exists():
        d = assess.load_definitions()
        assert set(d["areas"]) == valid and d["status"] in ("draft_unreviewed", "reviewed")


# ------------------------------------------------------------------ engine wiring with fakes
DEFS = {"areas": {a: dict(name=NAMES[a], definition="d", typical_activities=["x"], evidence_examples=["y"],
                           qualification_gaps=[], common_contextual_confusions=["z"]) for a in AREAS}}
CV = ("SUMMARY\nStudent developer.\n\nPROJECTS\nHospital app (2025)\n- Built a hospital patient management web application "
      "using Python, SQL and React.\n- Wrote the REST API for appointment booking.\n")


def _extraction_payload(cv_ing=None):
    return dict(records=[dict(
        passage_id="P002", quote="Built a hospital patient management web application using Python, SQL and React.",
        evidence_type="project", role=None, candidate_actions=["built a web application"], candidate_responsibilities=[],
        tools_methods=["Python", "SQL", "React"], domain_context="healthcare", qualification=None, contribution="own",
        dates=dict(start="2025", end=None, duration_months=None, recency="unknown"), negation=False, ambiguities=[],
        missing_info=[])], extraction_notes=[])


def fake_chat(assess_data, finish="stop", extraction=None, calls=None):
    def chat(system, user, schema_, cfg=None):
        if calls is not None:
            calls.append((system[:20], user))
        if system.startswith("You extract"):
            return client.ChatResult(content=json.dumps(extraction or _extraction_payload()), finish_reason="stop", model="fake")
        return client.ChatResult(content=json.dumps(assess_data) if not isinstance(assess_data, str) else assess_data,
                                 finish_reason=finish, model="fake")
    return chat


def test_engine_end_to_end_hospital_developer():
    good = data(A043=row("A043", "direct", 3, [("E001", "actions")], "built and API-wired a web app"),
                A019=row("A019", "direct", 3, [("E001", "actions")], "hospital"))
    calls = []
    res = engine.run(CV, "Asha Perera", DEFS, fake_chat(good, calls=calls), regulated=REG)
    assert res["status"] == "repaired" and res["engine_id"] == "llm_evidence"
    assert [s["area_id"] for s in res["supported"]] == ["A043"]
    assert [e["area_id"] for e in res["exploration"]] == ["A019"] and res["exploration"][0]["support_class"] == "domain_exposure_only"
    log = {x["area_id"]: x for x in res["validation_log"]}
    assert log["A019"]["original_class"] == "direct" and log["A019"]["final_class"] == "domain_exposure_only"
    assert res["stages"]["extraction"]["records"][0]["domain_context"] == "healthcare"
    assert len(res["stages"]["assessment"]["raw_rows"]) == 5                       # raw assessor output kept for attribution
    user = calls[-1][1]                                                           # what the assessor saw
    assert "appointment booking" not in user and "personality" not in user.lower() and "Asha" not in user
    assert "common_contextual_confusions" not in user                             # off by default (holdout hygiene)
    assert "common_contextual_confusions" in assess.build_user([DEV], [], DEFS, use_confusions=True)


def test_engine_failure_paths_are_recorded_not_substituted():
    ok = data()
    assert engine.run(CV, "A", DEFS, fake_chat(ok, finish="length"), regulated=REG)["errors"][0].startswith("assessment truncated")
    assert "not valid JSON" in engine.run(CV, "A", DEFS, fake_chat("nope"), regulated=REG)["errors"][0]
    broken = data()
    broken["assessments"].pop()
    r = engine.run(CV, "A", DEFS, fake_chat(broken), regulated=REG)
    assert r["status"] == "failed" and r["supported"] == [] and "missing rows" in r["errors"][0]

    def boom(system, user, schema_, cfg=None):
        raise client.EvidenceLLMError("HTTP 404: no endpoint")
    r = engine.run(CV, "A", DEFS, boom, regulated=REG)
    assert r["status"] == "failed" and "extraction" in r["errors"][0]


def test_no_evidence_means_no_assessment_call_and_no_recommendations():
    calls = []
    res = engine.run(CV, "A", DEFS, fake_chat(data(), extraction=dict(records=[], extraction_notes=["garbled"]), calls=calls), regulated=REG)
    assert res["status"] == "no_evidence" and res["supported"] == [] and len(calls) == 1


# ------------------------------------------------------------------ added after the first tune run (free model)
def test_uncited_positive_row_triggers_one_targeted_reask_and_is_reverified():
    first = data(A043=row("A043", "direct", 3, [("E001", "actions")], "dev"), A019=row("A019", "direct", 4, [], "no citation"))
    second = dict(assessments=[row("A019", "direct", 4, [("E001", "actions")], "claims nursing from the project")], notes=[])
    seq, calls = [first, second], []

    def chat(system, user, schema_, cfg=None):
        calls.append(user)
        if system.startswith("You extract"):
            return client.ChatResult(content=json.dumps(_extraction_payload()), finish_reason="stop")
        return client.ChatResult(content=json.dumps(seq.pop(0)), finish_reason="stop")
    res = engine.run(CV, "A", DEFS, chat, regulated=REG)
    assert len(calls) == 3 and "instruction" in calls[-1] and "A019" in calls[-1] and "A058" not in calls[-1]
    assert res["stages"]["assessment"]["reask_areas"] == ["A019"]
    # the re-asked answer is checked like any other: a hospital project still cannot make a direct nurse
    log = {x["area_id"]: x for x in res["validation_log"]}
    assert log["A019"]["final_class"] == "domain_exposure_only" and "re-asked" in log["A019"]["changes"][0]
    assert [s["area_id"] for s in res["supported"]] == ["A043"]


def test_reask_failure_leaves_the_downgrade_and_is_recorded():
    first = data(A019=row("A019", "direct", 4, [], "no citation"))
    state = {"n": 0}

    def chat(system, user, schema_, cfg=None):
        if system.startswith("You extract"):
            return client.ChatResult(content=json.dumps(_extraction_payload()), finish_reason="stop")
        state["n"] += 1
        return client.ChatResult(content=json.dumps(first) if state["n"] == 1 else "garbage", finish_reason="stop")
    res = engine.run(CV, "A", DEFS, chat, regulated=REG)
    assert res["status"] == "repaired" and res["stages"]["assessment"]["reask_error"]
    assert {x["area_id"]: x["final_class"] for x in res["validation_log"]}["A019"] == "unsupported"


def test_no_reask_when_every_positive_row_is_cited():
    calls = []
    engine.run(CV, "A", DEFS, fake_chat(data(A043=row("A043", "direct", 3, [("E001", "actions")], "dev")), calls=calls), regulated=REG)
    assert len(calls) == 2


# ------------------------------------------------------------------ replay and the pilot page
def test_replay_reproduces_stored_runs_without_any_model_call():
    from careerx.evidence import replay
    defs, reg = assess.load_definitions(), assess.load_regulated()
    runs = [ROOT / "bench" / "runs" / n for n in (
        "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_tune_2026-10-27.json",
        "career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_holdout_2026-10-29.json")]
    checked = 0
    for p in runs:
        if not p.exists():
            continue
        run = json.loads(p.read_text(encoding="utf-8"))
        for cid, st in run["stages"].items():
            rb = replay.rebuild(st, defs, reg)
            assert rb["ok"], cid
            assert [s["area_id"] for s in rb["supported"]] == [t["area_id"] for t in run["top"][cid]], cid
            assert [e["area_id"] for e in rb["exploration"]] == [e["area_id"] for e in st["exploration"]], cid
            assert len(rb["classes"]) == 94
            checked += 1
    assert checked >= 10 or not any(p.exists() for p in runs)


def test_replay_of_an_unusable_run_is_not_ok():
    from careerx.evidence import replay
    assert replay.rebuild({"extraction": {"records": []}}, DEFS, REG)["ok"] is False


def test_pilot_page_loads_and_shows_recorded_examples():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app" / "pages" / "pilot.py"), default_timeout=180).run()
    assert not at.exception, at.exception
    assert any("Pilot for demonstration" in w.value for w in at.warning)
    assert [h.value for h in at.subheader][:3] == ["1. Career areas backed by the evidence", "2. Worth exploring (not backed by experience)",
                                                   "3. What the checker changed"]
    at.selectbox[0].select("c01_hospital_app_developer").run()
    assert not at.exception
    body = " ".join(m.value for m in at.markdown)
    assert "Software & applications development" in body
    at.radio[0].set_value("Try your own invented example text (live, 3-5 minutes)").run()
    assert not at.exception
    at.text_area[0].set_value("Jane Roe jane@example.com +94 77 123 4567 Nurse").run()
    assert any("email address, phone number or link" in e.value for e in at.error)


# ------------------------------------------------------------------ reviewer-based v2 files, in-progress study, scope notes
def test_study_still_in_progress_never_supports_direct_and_becomes_exploration():
    student = rec("E040", "education", qual={"subject": "Accounting", "level": "BCom"}, quote="BCom (Accounting), 2025 - present")
    student.dates = dict(start="2025", end="present", duration_months=None, recency="recent")
    v = verify.verify(data(A033=row("A033", "direct", 3, [("E040", "qualification")], "studying accounting")), [student], AREAS, REG)
    a = v.rows["A033"]
    assert a.support_class == "in_progress_study" and a.relevance is None and a.status == "repaired"
    assert any("still in progress" in c for c in a.changes) and [e for e, _ in a.evidence] == ["E040"]
    out = rank.rank(v.rows, [student], NAMES)
    assert out["supported"] == [] and out["exploration"][0]["support_class"] == "in_progress_study" and out["exploration"][0]["label"]
    # a completed degree still supports; a student who also worked in the area keeps the work-based support
    done = rec("E041", "education", qual={"subject": "Accounting", "level": "BCom"}, quote="BCom (Accounting), 2019")
    done.dates = dict(start="2016", end="2019", duration_months=None, recency="mid")
    assert verify.verify(data(A033=row("A033", "direct", 3, [("E041", "qualification")], "x")), [done], AREAS, REG).rows["A033"].support_class == "direct"
    intern = rec("E042", "internship", role="Accounting Intern", actions=["posted ledger entries"], quote="Accounting Intern, posted ledger entries")
    v = verify.verify(data(A033=row("A033", "direct", 2, [("E040", "qualification"), ("E042", "role")], "intern")), [student, intern], AREAS, REG)
    assert v.rows["A033"].support_class == "direct" and [e for e, _ in v.rows["A033"].evidence] == ["E042"]


def test_in_progress_study_row_must_cite_education_records():
    v = run(A033=row("A033", "in_progress_study", None, [("E001", "qualification")], "x"))
    assert v.rows["A033"].support_class == "unsupported"
    v = run(A033=row("A033", "in_progress_study", None, [("E003", "qualification")], "nursing diploma in progress"))
    assert v.rows["A033"].support_class == "in_progress_study"


def test_scope_notes_reach_the_assessor_and_v2_files_are_valid_and_versioned():
    valid = set(pipeline.get_catalogue().area_id)
    d2 = assess.load_definitions(ROOT / "data" / "processed" / "area_definitions_v2.yaml")
    r2 = assess.load_regulated(ROOT / "data" / "processed" / "regulated_areas_v2.yaml")
    d1 = assess.load_definitions(ROOT / "data" / "processed" / "area_definitions_v1.yaml")
    r1 = assess.load_regulated(ROOT / "data" / "processed" / "regulated_areas_v1.yaml")
    assert set(d2["areas"]) == valid == set(d1["areas"]) and set(r2) == set(r1)
    assert sum(1 for a in d2["areas"].values() if a.get("reviewer_scope_note")) == 44
    assert not any(a.get("reviewer_scope_note") for a in d1["areas"].values())         # v1 untouched
    assert all(set(r1[a]) <= set(r2[a]) for a in r1) and len(r2["A019"]) > len(r1["A019"])
    assert d1["areas"]["A018"]["formal_qualification_required"] is False and d2["areas"]["A018"]["formal_qualification_required"] is True
    note = d2["areas"]["A043"]["reviewer_scope_note"]
    user = json.loads(assess.build_user([DEV], [], d2))
    assert next(a for a in user["areas"] if a["area_id"] == "A043")["scope_note"] == note
    assert "scope_note" not in next(a for a in json.loads(assess.build_user([DEV], [], d1))["areas"] if a["area_id"] == "A043")
    assert assess.PROMPT_VERSION == "assess_v2" and "in_progress_study" in assess.system_prompt() and "scope_note" in assess.system_prompt()


# ------------------------------------------------------------------ one bounded retry on invalid JSON
def test_invalid_json_gets_one_recorded_retry_for_each_stage():
    good = data(A043=row("A043", "direct", 3, [("E001", "actions")], "dev"))
    seq = {"extract": ["not json", json.dumps(_extraction_payload())], "assess": ["{broken", json.dumps(good)]}
    calls = []

    def chat(system, user, schema_, cfg=None):
        kind = "extract" if system.startswith("You extract") else "assess"
        calls.append(kind)
        return client.ChatResult(content=seq[kind].pop(0), finish_reason="stop", model="fake")
    res = engine.run(CV, "A", DEFS, chat, regulated=REG)
    assert calls == ["extract", "extract", "assess", "assess"]
    assert res["status"] in ("accepted", "repaired") and [s["area_id"] for s in res["supported"]] == ["A043"]
    assert res["run_meta"]["extraction"]["json_retries"] == 1 and res["run_meta"]["assessment"]["json_retries"] == 1


def test_persistent_invalid_json_is_a_failure_after_exactly_one_retry():
    calls = []

    def chat(system, user, schema_, cfg=None):
        calls.append(system[:12])
        return client.ChatResult(content="still not json", finish_reason="stop", model="fake")
    res = engine.run(CV, "A", DEFS, chat, regulated=REG)
    assert res["status"] == "failed" and "after one retry" in res["errors"][0] and len(calls) == 2 and res["supported"] == []

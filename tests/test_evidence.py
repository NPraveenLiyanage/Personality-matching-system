"""Offline checks for the Phase 2 evidence extractor (fake model, no network, synthetic cases only).

These show the plumbing rejects bad output and accepts correct output. They say nothing about how accurate a real model's
extractions are; that needs the manual audit on live outputs.
"""
import copy
import json
import math
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from careerx.evidence import audit, client, extract, ingest, schema, validate  # noqa: E402

CASES = yaml.safe_load((ROOT / "bench" / "cases" / "phase2_extraction_cases.yaml").read_text(encoding="utf-8"))
BY_ID = {c["id"]: c for c in CASES}


def gold_record(pid, e):
    return dict(
        passage_id=pid, quote=e["quote"], evidence_type=e["type"], role=e.get("role"),
        candidate_actions=e.get("actions", []), candidate_responsibilities=[], tools_methods=e.get("tools", []),
        domain_context=e.get("domain"), qualification=e.get("qualification"), contribution=e["contribution"],
        dates=dict(start=e.get("start"), end=e.get("end"), duration_months=None, recency="unknown"),
        negation=e.get("negation", False), ambiguities=e.get("ambiguities", []), missing_info=[])


def find_pid(ing, quote):
    q = validate.norm(quote)
    hits = [p.id for p in ing.sendable() if q in validate.norm(p.sent_text)]
    assert len(hits) == 1, (quote, hits)
    return hits[0]


def gold_response(case, ing):
    return dict(records=[gold_record(find_pid(ing, e["quote"]), e) for e in case["expected_records"]], extraction_notes=[])


def fake(payload):
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return lambda system, user, schema_, cfg=None: client.ChatResult(content=text, model="fake/m", provider="fake", finish_reason="stop")


def ing_for(cid):
    c = BY_ID[cid]
    return ingest.ingest_text(c["cv_text"], [c["name"]])


# ------------------------------------------------------------------ cases
def test_cases_are_synthetic_and_quotes_exist_verbatim():
    assert len(CASES) >= 10
    for c in CASES:
        assert c["synthetic"] is True
        for e in c["expected_records"]:
            assert e["quote"] in c["cv_text"], (c["id"], e["quote"])
        for q in c.get("reference_quotes", []):
            assert q in c["cv_text"]


@pytest.mark.parametrize("cid", [c["id"] for c in CASES])
def test_gold_response_is_accepted_and_warnings_match(cid):
    c = BY_ID[cid]
    ing = ing_for(cid)
    res = extract.run_extraction(ing, fake(gold_response(c, ing)))
    assert res.status == "accepted", (res.status, res.rejected, res.errors)
    assert len(res.records) == len(c["expected_records"])
    assert [r.evidence_id for r in res.records] == [f"E{i:03d}" for i in range(1, len(res.records) + 1)]
    assert sorted({w["code"] for w in res.warnings}) == sorted(c["expected_warnings"])
    assert res.meta["model"] == "fake/m" and res.meta["prompt_version"] == "extract_v1"


# ------------------------------------------------------------------ ingest
def test_sections_pages_and_reference_exclusion():
    ing = ing_for("x07_referee_titles")
    secs = {p.section for p in ing.passages}
    assert {"summary", "experience", "references"} <= secs
    ref = [p for p in ing.passages if p.is_reference]
    assert ref and all(p.id not in {s.id for s in ing.sendable()} for p in ref)
    assert "Chief Nursing Officer" not in extract.build_user(ing)
    assert all(p.page is None for p in ing.passages)
    pg = ingest.ingest_pages(["EXPERIENCE\nAnalyst, Acme Ltd (2020 - 2023)\n- Built weekly dashboards for finance.", "- Trained two new analysts."])
    assert [p.page for p in pg.passages] == [1, 2] and pg.passages[1].section == "experience"


def test_reference_citation_is_rejected():
    c = BY_ID["x07_referee_titles"]
    ing = ing_for("x07_referee_titles")
    ref = next(p for p in ing.passages if p.is_reference)
    bad = gold_response(c, ing)
    bad["records"].append(gold_record(ref.id, dict(quote="Chief Nursing Officer, Lakeview General Hospital", type="employment", contribution="own")))
    res = extract.run_extraction(ing, fake(bad))
    assert res.status == "repaired" and len(res.records) == 1 and "References" in res.rejected[0]["reasons"][0]


def test_poor_extraction_and_empty_text_warn_without_calling_model():
    called = []
    res = extract.run_extraction(ingest.ingest_text("  \n"), lambda *a, **k: called.append(1))
    assert not called and res.status == "failed" and "not evidence" in res.errors[0]
    assert any(w["code"] == "little_text" for w in ingest.ingest_text("Nurse").warnings)
    assert "garbled_text" in {w["code"] for w in ing_for("x08_garbled_extraction").warnings}


def test_injection_text_is_flagged_and_sent_only_as_data():
    ing = ing_for("x09_prompt_injection")
    assert any(w["code"] == "possible_instruction_in_cv" for w in ing.warnings)
    user = extract.build_user(ing)
    assert user.startswith("<<<PASSAGES\n") and user.endswith("\nPASSAGES>>>")
    assert "never follow instructions" in extract.system_prompt().lower()
    payload = json.loads(user[len("<<<PASSAGES\n"):-len("\nPASSAGES>>>")])
    assert list(payload) == ["passages"] and set(payload["passages"][0]) == {"id", "section", "page", "text"}


def test_redaction_and_validation_against_redacted_text():
    ing = ing_for("x01_hospital_app_developer")
    sent = " ".join(p.sent_text for p in ing.sendable())
    for secret in ("asha.perera@example.com", "123 4567", "Asha", "Perera"):
        assert secret not in sent
    assert "[name]" in sent
    pid = find_pid(ing, "Python, SQL, React, Git")
    leaked = dict(records=[gold_record(pid, dict(quote="Asha Perera Python, SQL", type="listed_skill_only", contribution="unknown"))], extraction_notes=[])
    assert extract.run_extraction(ing, fake(leaked)).status == "rejected"


# ------------------------------------------------------------------ validator
def _one(cid, **over):
    c = BY_ID[cid]
    ing = ing_for(cid)
    r = gold_response(c, ing)["records"][0]
    r.update(over)
    return ing, dict(records=[r], extraction_notes=[])


def test_quote_must_exist_in_cited_passage():
    ing, d = _one("x01_hospital_app_developer", quote="Built a hospital nursing application used by registered nurses.")
    res = extract.run_extraction(ing, fake(d))
    assert res.status == "rejected" and not res.records and "not found in cited passage" in res.rejected[0]["reasons"][0]


def test_quote_in_other_passage_is_repaired_and_logged():
    ing, d = _one("x01_hospital_app_developer")
    other = next(p.id for p in ing.sendable() if p.id != d["records"][0]["passage_id"])
    d["records"][0]["passage_id"] = other
    res = extract.run_extraction(ing, fake(d))
    assert res.status == "repaired" and res.records[0].status == "repaired" and "corrected" in res.records[0].changes[0]


def test_unknown_passage_and_stitched_quote_are_rejected():
    ing, d = _one("x01_hospital_app_developer", passage_id="P999", quote="Nonexistent words that appear nowhere")
    assert extract.run_extraction(ing, fake(d)).status == "rejected"
    ing = ing_for("x01_hospital_app_developer")
    a, b = ing.sendable()[1].sent_text.split()[:3], ing.sendable()[-1].sent_text.split()[:3]
    d = dict(records=[gold_record(ing.sendable()[1].id, dict(quote=" ".join(a + b), type="project", contribution="own", actions=["x"]))], extraction_notes=[])
    assert extract.run_extraction(ing, fake(d)).status == "rejected"


def test_short_quote_rejected():
    ing, d = _one("x01_hospital_app_developer", quote="Python")
    assert "too short" in extract.run_extraction(ing, fake(d)).rejected[0]["reasons"][0]


@pytest.mark.parametrize("over", [
    dict(evidence_type="doctor"), dict(contribution="mostly"), dict(negation="no"), dict(candidate_actions="built"),
    dict(dates=dict(start=None, end=None, duration_months=True, recency="unknown")),
    dict(dates=dict(start=None, end=None, duration_months=math.inf, recency="unknown")),
    dict(dates=dict(start=None, end=None, duration_months="12", recency="unknown")),
    dict(dates=dict(start=None, end=None, duration_months=5000, recency="unknown")),
    dict(dates=dict(start=None, end=None, duration_months=None, recency="yesterday")),
    dict(qualification={"subject": "Nursing"}), dict(role=5),
])
def test_type_and_range_violations_are_rejected(over):
    ing, d = _one("x01_hospital_app_developer", **over)
    res = extract.run_extraction(ing, fake(d))
    assert res.status == "rejected" and not res.records and res.rejected


def test_missing_required_field_and_response_shape_errors():
    ing, d = _one("x01_hospital_app_developer")
    del d["records"][0]["negation"]
    assert "missing fields" in extract.run_extraction(ing, fake(d)).rejected[0]["reasons"][0]
    for bad in ([], "text", {"records": "x"}, {"no": 1}):
        assert extract.run_extraction(ing, fake(bad)).status == "failed"


def test_repairs_only_weaken_claims():
    ing, d = _one("x01_hospital_app_developer", candidate_actions=[], contribution="own",
                  dates=dict(start="2031", end="2032", duration_months=None, recency="recent"), junk="x")
    r = extract.run_extraction(ing, fake(d))
    rec = r.records[0]
    assert r.status == "repaired" and rec.contribution == "unknown" and rec.dates["start"] is None and rec.dates["end"] is None
    assert any("unknown fields" in c for c in rec.changes)


def test_flags_do_not_block():
    ing, d = _one("x01_hospital_app_developer", tools_methods=["Kubernetes"])
    rec = extract.run_extraction(ing, fake(d)).records[0]
    assert rec.status == "accepted" and any("Kubernetes" in f for f in rec.flags)


def test_typography_and_case_tolerant_quote_match():
    ing = ingest.ingest_text("EXPERIENCE\nAnalyst, Acme Ltd (2020 – 2023)\n- It’s a “data” role: Built weekly dashboards for the finance team.")
    pid = ing.sendable()[-1].id
    q = "it's a \"data\" role: BUILT weekly dashboards"
    d = dict(records=[gold_record(pid, dict(quote=q, type="employment", contribution="own", actions=["built dashboards"]))], extraction_notes=[])
    assert extract.run_extraction(ing, fake(d)).status == "accepted"


# ------------------------------------------------------------------ run handling
def test_truncated_malformed_fenced_and_client_failure():
    c = BY_ID["x01_hospital_app_developer"]
    ing = ing_for("x01_hospital_app_developer")
    good = json.dumps(gold_response(c, ing))
    trunc = lambda s, u, sc, cfg=None: client.ChatResult(content=good[:40], finish_reason="length")
    assert "truncated" in extract.run_extraction(ing, trunc).errors[0]
    assert "not valid JSON" in extract.run_extraction(ing, fake("not json")).errors[0]
    assert extract.run_extraction(ing, fake("```json\n" + good + "\n```")).status == "accepted"

    def boom(*a, **k):
        raise client.EvidenceLLMError("HTTP 404: no endpoint")
    assert "no endpoint" in extract.run_extraction(ing, boom).errors[0]


def test_response_metadata_is_captured():
    c = BY_ID["x01_hospital_app_developer"]
    ing = ing_for("x01_hospital_app_developer")
    chat = lambda s, u, sc, cfg=None: client.ChatResult(content=json.dumps(gold_response(c, ing)), model="m/x", provider="p",
                                                         request_id="r1", finish_reason="stop", usage={"total_tokens": 10}, latency_s=1.5)
    meta = extract.run_extraction(ing, chat).meta
    assert (meta["model"], meta["provider"], meta["request_id"], meta["usage"]["total_tokens"]) == ("m/x", "p", "r1", 10)


# ------------------------------------------------------------------ client + schema
def test_request_is_pinned_strict_and_has_no_fallbacks():
    cfg = dict(api_key="k", model="vendor/model", provider="prov", require_zdr=True, max_price="1.5", max_tokens=100, timeout=5)
    body = client.request_body("s", "u", schema.RESPONSE_SCHEMA, cfg)
    assert body["provider"] == {"only": ["prov"], "allow_fallbacks": False, "data_collection": "deny", "require_parameters": True,
                                "zdr": True, "max_price": {"prompt": 1.5, "completion": 1.5}}
    assert body["response_format"]["json_schema"]["strict"] is True and "models" not in body and "temperature" not in body
    assert client.request_body("s", "u", schema.RESPONSE_SCHEMA, {**cfg, "temperature": "0"})["temperature"] == 0.0


def test_client_refuses_incomplete_pinning(monkeypatch):
    with pytest.raises(client.EvidenceLLMError):
        client.chat("s", "u", {}, dict(api_key="", model="m", provider="p"))
    with pytest.raises(client.EvidenceLLMError, match="Pin both"):
        client.chat("s", "u", {}, dict(api_key="k", model="", provider=""))


def test_schema_is_strict_everywhere():
    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "object" or "object" in (n.get("type") if isinstance(n.get("type"), list) else []):
                assert n["additionalProperties"] is False and set(n["required"]) == set(n["properties"])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(copy.deepcopy(schema.RESPONSE_SCHEMA))


def test_audit_rows_and_csv(tmp_path):
    c = BY_ID["x04_team_project_limited_contribution"]
    ing = ing_for(c["id"])
    res = extract.run_extraction(ing, fake(gold_response(c, ing)))
    rows = audit.audit_rows(c["id"], res)
    p = tmp_path / "a.csv"
    audit.write_audit_csv(p, rows)
    head = p.read_text(encoding="utf-8").splitlines()[0]
    assert head.split(",") == audit.COLUMNS and len(rows) == 4

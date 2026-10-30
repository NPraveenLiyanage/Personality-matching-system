"""The shared result contract and registry: default is the rule engine, failures are explicit, no fallback."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from careerx import engines  # noqa: E402
from careerx.evidence import client  # noqa: E402

CV = "SUMMARY\nStudent.\n\nEXPERIENCE\nIntern, Acme (2025)\n- Built a web application in Python.\n"


def test_default_engine_is_rule_and_env_switch_works(monkeypatch):
    monkeypatch.delenv("CAREERX_ENGINE", raising=False)
    assert engines.selected_engine() == "rule"
    monkeypatch.setenv("CAREERX_ENGINE", "llm_evidence")
    assert engines.selected_engine() == "llm_evidence"
    monkeypatch.setenv("CAREERX_ENGINE", "bogus")
    assert engines.selected_engine() == "rule"


def test_rule_engine_returns_ten_areas_in_the_contract():
    r = engines.run("rule", CV)
    assert r.engine_id == "rule" and r.status == "accepted" and len(r.top()) == 10 and r.exploration == []


def test_unknown_engine_fails_explicitly():
    r = engines.run("nope", CV)
    assert r.status == "failed" and "unknown engine" in r.errors[0]


def test_evidence_failure_is_reported_and_never_replaced_by_the_rule_engine():
    def boom(system, user, schema_, cfg=None):
        raise client.EvidenceLLMError("HTTP 429")
    defs = {"areas": {"A043": dict(name="Software", definition="d", typical_activities=["x"], evidence_examples=["y"],
                                    qualification_gaps=[], common_contextual_confusions=["z"])}}
    r = engines.run("llm_evidence", CV, "A", defs=defs, chat=boom)
    assert r.engine_id == "llm_evidence" and r.status == "failed" and r.top() == [] and r.errors

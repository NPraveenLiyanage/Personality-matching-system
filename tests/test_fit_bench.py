"""Fit benchmark plumbing: frozen holdout, synthetic reports parse, offline scoring, and the live runner with a stubbed model."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench import run_fit_eval as R  # noqa: E402
from careerx.evidence import client  # noqa: E402

HOLDOUT_SHA256 = "d8cccb70b16e9b3720136d66b12f5a99a3d5b675b3ef3afedce5cb2417fdd183"        # the frozen holdout. Changing a holdout case changes this; do not "fix" the hash, write holdout_v2 instead.


def test_holdout_split_is_frozen():
    assert R.holdout_hash() == HOLDOUT_SHA256


def test_cases_are_synthetic_complete_and_every_report_parses_cleanly():
    cases = R.load_cases("all")
    assert len(cases) == 12 and {c["split"] for c in cases} == {"dev", "holdout"}
    assert len({c["id"] for c in cases}) == 12 and len({c["name"] for c in cases}) == 12
    for c in cases:
        pm = R.parse_case(c)
        assert pm.warnings == [] and len(pm.steps) == 4 and [s["rating"] for s in pm.steps] == c["ratings"]
        assert c["name"] not in pm.report_text() and set(c["expected"].values()) <= {"strong", "mixed", "stretch", "insufficient"}


def test_baseline_regression_floor_and_no_direction_flips():
    s = R.run_baseline(R.load_cases("all"))["score"]
    assert s["exact_rate"] >= 0.70 and s["strong_stretch_flips"] == 0 and s["claimed_fit_where_report_is_even"] == 0


def test_score_counts_flips_abstentions_and_even_report_claims():
    rows = [dict(expected="strong", got="stretch"), dict(expected="strong", got="insufficient"),
            dict(expected="insufficient", got="mixed"), dict(expected="mixed", got="mixed")]
    s = R.score(rows)
    assert s["exact"] == 1 and s["strong_stretch_flips"] == 1 and s["abstained_where_expected_clear"] == 1 and s["claimed_fit_where_report_is_even"] == 1


def test_live_runner_with_a_stub_model_checkpoints_resumes_and_summarises(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "RUNS", tmp_path)
    cases = R.load_cases("dev")[:2]
    calls = []

    def chat(system, user, schema, cfg=None):
        calls.append(1)
        body = json.loads(user[len("<<<REPORT_AND_AREAS\n"):-len("\nREPORT_AND_AREAS>>>")])
        quote = body["report"].split("\n")[3][:60]
        fits = [dict(area_id=a["area_id"], reasoning="r", fit_band="mixed", reasons=[dict(point="p", quote=quote)], watch_outs=[])
                for a in body["areas"]]
        return client.ChatResult(content=json.dumps(dict(fits=fits)), finish_reason="stop", model="m", provider="p",
                                 usage={"prompt_tokens": 3000, "completion_tokens": 900}, latency_s=2.0)
    out = R.run_live(cases, {}, "t", chat=chat)
    assert out["cases_run"] == 2 and len(calls) == 2 and out["mean_tokens_in"] == 3000 and out["model_score"]["n"] == len(out["rows"])
    assert 0 <= out["model_vs_baseline_agreement"] <= 1 and out["fit_call_cost_per_1000_users_usd_at_list_price"]["claude-haiku-5-5"] > 0
    R.run_live(cases, {}, "t", chat=chat)                      # resume: nothing is re-requested
    assert len(calls) == 2

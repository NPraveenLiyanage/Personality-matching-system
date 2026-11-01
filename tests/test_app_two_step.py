"""The two-step page loads and works headlessly (Streamlit AppTest). No model is called; invented text only."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
st_testing = pytest.importorskip("streamlit.testing.v1")

from careerx import engines  # noqa: E402
from test_personamap import report  # noqa: E402

PAGE = str(Path(__file__).resolve().parents[1] / "app" / "pages" / "two_step.py")
CV = ("SUMMARY\nSoftware engineering graduate.\n\nEXPERIENCE\nJunior Developer, Example Systems (2025 - 2026)\n"
      "- Built REST APIs in Python for a hospital booking system.\n- Wrote unit tests and fixed defects.\n\nEDUCATION\nBSc Software Engineering, 2021 - 2025\n")


def app():
    at = st_testing.AppTest.from_file(PAGE, default_timeout=60)
    at.run()
    return at


def test_page_loads_in_local_mode_without_errors():
    at = app()
    assert not at.exception and at.radio[0].value.startswith("Local check")
    assert any("no model is called" in s.value for s in at.success)


def test_local_check_shows_the_personamap_use_and_a_style_check_table():
    at = app()
    at.text_area(key="ts_cvp").set_value(CV)
    at.text_area(key="ts_pmp").set_value(report())
    at.run()
    assert not at.exception
    assert any("What the PersonaMap step uses" in e.label for e in at.expander)
    next(b for b in at.button if b.label == "Run local check").click()
    at.run()
    assert not at.exception and at.dataframe, "expected the local check table"
    df = at.dataframe[0].value
    assert list(df.columns) == ["rank", "area", "keyword_score", "style_check", "why"] and len(df) == 10
    for gone in ("Kasun", "Wijeratne", "Prepared for"):
        assert gone not in " ".join(e.proto.body if hasattr(e.proto, "body") else "" for e in at.markdown)


def test_live_mode_is_blocked_until_invented_text_is_confirmed_and_flags_pii():
    at = app()
    at.radio[0].set_value("Live two-step run (calls a free AI model; invented text only)")
    at.text_area(key="ts_cvp").set_value(CV + "\nContact: someone@example.com")
    at.text_area(key="ts_pmp").set_value(report())
    at.run()
    assert not at.exception and any("email address" in e.value for e in at.error)
    run_btn = next(b for b in at.button if b.label == "Run the two-step pipeline")
    assert run_btn.disabled


RENDER_SCRIPT = """
import sys
sys.path.insert(0, r"{src}")
import streamlit as st
from careerx import engines
ns = {{"__file__": r"{page}", "__name__": "two_step_funcs"}}
exec(compile(open(r"{page}", encoding="utf-8").read().split("# ------------------------------------------------------------------------------------------------ page", 1)[0], r"{page}", "exec"), ns)
sup = [dict(rank=1, area_id="A043", name="Software & applications development", support_class="direct", relevance=4,
            explanation="Direct evidence - Junior Developer", qualification_gaps=[], label=None)]
if "{case}" == "ok":
    fits = {{"A043": dict(area_id="A043", fit_band="mixed", reasons=[dict(point="Plans carefully.", quote="You plan and schedule thoroughly")],
                         watch_outs=[dict(point="Slow to close.", quote="slower to close the decision")], changes=["x"],
                         low_confidence=True, baseline=dict(band="strong", reasons=["r"]))}}
    fit = dict(status="accepted", fits=fits, errors=[])
else:
    fit = dict(status="failed", fits={{}}, errors=["fit call failed: HTTP 500"], baseline_only={{"A043": dict(band="stretch", reasons=["The work demands quick decisions."])}})
res = engines.EngineResult("final", "v", "accepted", sup, [], [], [], [], {{}}, fit=fit)
ns["render_final"](res)
"""


def render(case):
    src = str(Path(__file__).resolve().parents[1] / "src")
    at = st_testing.AppTest.from_string(RENDER_SCRIPT.format(src=src, page=PAGE, case=case), default_timeout=60)
    at.run()
    assert not at.exception
    return at


def test_render_final_shows_evidence_and_working_style_panels_with_quotes_and_flags():
    text = " ".join(m.value for m in render("ok").markdown) + " ".join(c.value for c in render("ok").caption)
    assert "From the CV (evidence)" in text and "From the PersonaMap (working style)" in text
    assert "Mixed" in text and "You plan and schedule thoroughly" in text and "slower to close" in text
    assert "Low confidence" in text and "removed 1 unsupported" in text and "Local style check" in text
    assert "not a hiring, selection or suitability judgment" in text


def test_render_final_labels_the_local_check_when_the_ai_step_failed():
    at = render("failed")
    assert any("did not complete" in w.value for w in at.warning)
    text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "Local style check only (the AI step did not complete)" in text and "quick decisions" in text

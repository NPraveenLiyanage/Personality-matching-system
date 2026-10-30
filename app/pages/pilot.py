"""Evidence-first career exploration: PILOT page (demonstration only).

Two modes: recorded examples (instant, no model call) and a live run on invented example text with a free AI model.
Nothing is stored; results live in this browser session only. Real participants' CVs must not be used here.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "src", ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pandas as pd
import streamlit as st

from careerx import pipeline as PL
from careerx.evidence import assess, client as ev_client, engine as ev_engine, replay
from careerx.llm.payload import redact

EXAMPLES_PATH = ROOT / "data" / "demo" / "pilot_examples.json"
PILOT_MODEL = os.environ.get("CAREERX_PILOT_MODEL", "nvidia/nemotron-3.5-super-vl:free")
PILOT_PROVIDER = os.environ.get("CAREERX_PILOT_PROVIDER", "nvidia")
BADGE = {"direct": "✅ Supported by evidence", "transferable": "✅ Supported (transferable skills)",
         "domain_exposure_only": "⚠️ Industry exposure only", "interest_only": "💭 Stated interest only",
         "in_progress_study": "📘 Study in progress",
         "unsupported": "➖ Not supported by the text", "insufficient_info": "❔ Not enough information"}
STRENGTH = {4: "very strong", 3: "strong", 2: "moderate", 1: "weak", 0: "none"}
SAMPLE = """Sample Person
SUMMARY
Software engineering graduate looking for a first developer role.

EXPERIENCE
Junior Developer, Example Systems (2025 - 2026)
- Built REST APIs in Python for a hospital appointment booking system.
- Wrote unit tests and fixed defects reported by the support team.

EDUCATION
BSc Software Engineering, Example University, 2021 - 2025
"""


@st.cache_data(show_spinner=False)
def load_examples() -> dict:
    if not EXAMPLES_PATH.exists():
        return {}
    return json.loads(EXAMPLES_PATH.read_text(encoding="utf-8"))


@st.cache_data(show_spinner=False)
def rule_top10(cv_text: str) -> list[dict]:
    prof = PL.build_profile("Participant", cv_text, today=PL.REFERENCE_DATE)
    sc = PL.run(prof)["scores"].sort_values("score", ascending=False).head(10)
    return [dict(area_id=r.area_id, name=r.name) for r in sc.itertuples()]


@st.cache_data(show_spinner=False)
def definitions(policy: str = "v2") -> tuple[dict, dict]:
    """v2 policy keeps the frozen v1 definitions; v3 uses area_definitions_v3 (with the A040/A044 scope notes)."""
    path = ROOT / "data" / "processed" / "area_definitions_v3.yaml" if policy == "v3" else None
    return assess.load_definitions(path), assess.load_regulated()


def plain_change(c: dict, names: dict) -> str:
    n = names.get(c["area_id"], c["area_id"])
    joined = " ".join(c["changes"])
    if c["final_class"] != c["original_class"]:
        why = ("the cited work did not show this occupation's own role or qualification" if "regulated" in joined
               else "the cited evidence was not enough to support it")
        return (f"**{n}**: the AI first suggested “{c['original_class'].replace('_', ' ')}”, the checker changed it to "
                f"“{c['final_class'].replace('_', ' ')}” because {why}.")
    return f"**{n}**: kept as “{c['final_class'].replace('_', ' ')}” after the checker removed a weak citation ({c['changes'][0]})."


def render(res: dict, cv_text: str, names: dict, direct_top10: list[dict] | None, meta: dict | None) -> None:
    classes = res.get("classes", {})
    st.subheader("1. Supported: career areas backed by the evidence")
    if not res["supported"]:
        st.info("No area is supported strongly enough by this text. That means the text gives too little evidence. "
                "It does not mean the person lacks skills or potential.")
    for s in res["supported"]:
        with st.container(border=True):
            st.markdown(f"**{s['rank']}. {s['name']}**  ·  {BADGE[s['support_class']]}  ·  evidence strength "
                        f"{s['relevance']}/4 ({STRENGTH.get(s['relevance'], '')})")
            st.write(s["explanation"])
            if s["qualification_gaps"]:
                st.caption("Not shown in the text: " + "; ".join(s["qualification_gaps"]))
            st.caption(f"Confidence in this reading: {s['uncertainty']}  ·  evidence IDs: {', '.join(s['evidence_ids'])}")
    st.caption("Evidence strength 0-4 is a rating of how well the text supports the area. It is not a probability of success, "
               "and it says nothing about hiring or suitability.")

    # Industry exposure is context about where the person worked or studied. It is never a career suggestion, so it is kept out of
    # the exploration list (policy v3 returns it as context_only; older v2 results hold it inside exploration and are split here).
    exposure = list(res.get("context_only") or []) + [e for e in res["exploration"] if e["support_class"] == "domain_exposure_only"]
    explore = [e for e in res["exploration"] if e["support_class"] != "domain_exposure_only"]
    st.subheader("2. Exploration pathways (study or interest, not backed by work)")
    if explore:
        for e in explore:
            st.markdown(f"- **{e['name']}**: {e['label']}.")
    else:
        st.caption("None.")

    st.subheader("3. Industry exposure (context only, not a career suggestion)")
    if exposure:
        st.caption("These fields appear only because the person's work or project served that industry. This is not evidence of "
                   "doing that occupation, and it is not a suggestion that the field suits them.")
        for e in exposure:
            st.markdown(f"- {e['name']}: industry exposure only.")
    else:
        st.caption("None.")

    st.subheader("4. What the checker changed")
    if res["validation_log"]:
        shown = [c for c in res["validation_log"] if c["original_class"] in ("direct", "transferable")]
        for c in shown:
            st.markdown("- " + plain_change(c, names))
        extra = len(res["validation_log"]) - len(shown)
        if not shown:
            st.caption("The checker made no changes to supported areas.")
        if extra:
            st.caption(f"{extra} further rows were tidied (for example cleared evidence on areas that were not supported).")
    else:
        st.caption("The checker made no changes.")

    st.subheader("5. Compared with the earlier engines on the same text")
    st.caption("Each area the earlier engines show is labelled with what the evidence-first pipeline concluded about it.")
    cols = st.columns(2 if direct_top10 else 1)

    def table(lst: list[dict]) -> pd.DataFrame:
        return pd.DataFrame([dict(rank=i, area=a["name"], evidence_check=BADGE.get(classes.get(a["area_id"], ""), "?"))
                             for i, a in enumerate(lst, 1)])
    with cols[0]:
        st.markdown("**Earlier rule-based engine (top 10)**")
        st.dataframe(table(rule_top10(cv_text)), hide_index=True, width="stretch")
    if direct_top10:
        with cols[1]:
            st.markdown("**Earlier direct AI prompt (top 10, recorded)**")
            st.dataframe(table(direct_top10), hide_index=True, width="stretch")

    st.subheader("6. Evidence extracted from the text")
    recs = res.get("records") or []
    if recs:
        st.dataframe(pd.DataFrame([dict(id=r["evidence_id"], type=r["evidence_type"], role=r["role"], contribution=r["contribution"],
                                        industry_context=r["domain_context"], quote=r["quote"]) for r in recs]),
                     hide_index=True, width="stretch")
    if res.get("warnings"):
        st.warning("Document warnings: " + ", ".join(res["warnings"]) + ". Missing evidence here does not mean missing experience.")
    with st.expander("Run details and limits"):
        if meta:
            st.json({k: v for k, v in meta.items() if v is not None})
        st.markdown(
            "- Pilot: invented example CVs only; one run per case; a free AI model (outputs can vary between runs).\n"
            "- The 94 career-area definitions and the list of regulated occupations are AI-drafted and **not yet reviewed** by a career expert.\n"
            "- Expected outcomes used in the benchmark were written by the project team and are not yet independently rated.\n"
            "- This tool supports career exploration. It does not make hiring, selection, promotion, competence or performance judgments.")


# ------------------------------------------------------------------------------------------------ page
st.title("Career exploration: evidence-first pilot")
st.warning("**Pilot for demonstration.** Use invented example text only, never a real person's CV. The recommendations are "
           "exploration suggestions based on what the text says the person did. They are not hiring, selection or ability judgments.",
           icon="🧪")
st.markdown("The system extracts **what the person actually did** from the CV text, assesses all 94 career areas against that "
            "evidence, and a checker rejects claims the evidence cannot support. For example, building a hospital app is treated as "
            "software work in a healthcare setting, not as nursing.")

data = load_examples()
names = data.get("area_names", {})
mode = st.radio("Mode", ["Recorded examples (instant)", "Try your own invented example text (live, 3-5 minutes)"], horizontal=True)

if mode.startswith("Recorded"):
    if not data.get("examples"):
        st.error("Recorded examples are missing. Run scripts/build_pilot_examples.py.")
        st.stop()
    ex = data["examples"]
    order = sorted(ex, key=lambda k: (ex[k]["split"] != "tune", k))
    pick = st.selectbox("Example", order, format_func=lambda k: ex[k]["title"])
    e = ex[pick]
    with st.expander("The example CV text", expanded=False):
        st.text(e["cv_text"])
    render(e, e["cv_text"], names, e["direct_top10"], e["run_meta"])
else:
    cfg = ev_client.settings()
    st.info(f"Live mode sends the text to OpenRouter and the free model `{PILOT_MODEL}` (provider `{PILOT_PROVIDER}`). Free "
            "endpoints may log prompts, so only invented text is allowed. Free models are slow and have a daily request limit.",
            icon="🔒")
    # Rollback switch: CAREERX_POLICY=v2 (the default) or v3. v3 is prepared as the future default but is NOT switched on here.
    policy_default = 1 if os.environ.get("CAREERX_POLICY", "v2") == "v3" else 0
    policy = st.radio("Pipeline version", ["v2 (frozen)", "v3 (exposure kept out of exploration, capped lists)"],
                      index=policy_default, horizontal=True).split()[0]
    text = st.text_area("Example CV text", value=SAMPLE, height=300)
    confirm = st.checkbox("This is invented example text. It is not a real person's CV.")
    leak = redact(text, None) != text
    if leak:
        st.error("The text appears to contain an email address, phone number or link. Remove it; live mode accepts invented text only.")
    if not cfg["api_key"]:
        st.warning("No OPENROUTER_API_KEY found (.env). Live mode is unavailable; recorded examples still work.")
    if st.button("Run the evidence-first pipeline", disabled=not (confirm and not leak and cfg["api_key"] and text.strip())):
        defs, reg = definitions(policy)
        run_cfg = dict(cfg, model=PILOT_MODEL, provider=PILOT_PROVIDER, data_collection="allow", max_tokens=60000,
                       temperature="", require_zdr=False, max_price="", api_key_2="")
        with st.spinner("Extracting evidence and assessing 94 areas (about 3-5 minutes on a free model)..."):
            try:
                res = ev_engine.run(text, text.strip().splitlines()[0], defs, cfg=run_cfg, regulated=reg, policy=policy)
            except Exception as ex_:                              # network or unexpected provider errors
                res = dict(status="failed", errors=[f"{type(ex_).__name__}: {str(ex_)[:160]}"], stages={})
        st.session_state["pilot_live"] = (text, res, policy)
    got = st.session_state.get("pilot_live")
    if got:
        cv_text, res, run_policy = got
        if res["status"] == "failed":
            st.error("The run failed and nothing was substituted: " + "; ".join(res["errors"]))
        else:
            defs, reg = definitions(run_policy)
            rb = replay.rebuild(res["stages"], defs, reg, run_policy) if res["stages"].get("assessment") else None
            full = dict(res, classes=rb["classes"] if rb and rb["ok"] else {}, records=[
                dict(evidence_id=r["evidence_id"], evidence_type=r["evidence_type"], role=r["role"], contribution=r["contribution"],
                     domain_context=r["domain_context"], quote=r["quote"]) for r in res["stages"]["extraction"]["records"]],
                warnings=[w["code"] for w in res.get("warnings", [])])
            if res["status"] == "no_evidence":
                st.info("No usable evidence could be extracted from this text. " + "; ".join(res["errors"]))
            m = res.get("run_meta", {})
            meta = dict(model=(m.get("assessment") or {}).get("model"), provider=(m.get("assessment") or {}).get("provider"),
                        engine_version=res.get("engine_version"), status=res["status"])
            render(full, cv_text, names, None, meta)

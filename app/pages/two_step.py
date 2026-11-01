"""Two-step career exploration: CV evidence first, then the PersonaMap work-style fit.

Step 1 reads the CV and decides which career areas the evidence supports. Step 2 reads the PersonaMap report and says how the
described working style meets each of those areas. Step 2 never changes which areas are supported or their order, and it is about
preferences, not ability.

Two modes:
  * Local check: works with real documents. Nothing leaves this computer and no model is called. It uses the local keyword engine to
    shortlist areas and the local style check, so it is NOT evidence-checked.
  * Live two-step run: calls a free model, so it accepts invented example text only.
Nothing is stored; results live in this browser session only.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (ROOT / "src", ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pandas as pd
import streamlit as st

from careerx import engines, personamap as PM, pipeline as PL, workstyle as W
from careerx.evidence import assess, client as ev_client
from careerx.llm.payload import redact
from careerx.profile import extract_pdf_text

PILOT_MODEL = os.environ.get("CAREERX_PILOT_MODEL", "nvidia/nemotron-3.5-super-vl:free")
PILOT_PROVIDER = os.environ.get("CAREERX_PILOT_PROVIDER", "nvidia")
BADGE = {"direct": "✅ Supported by evidence", "transferable": "✅ Supported (transferable skills)",
         "domain_exposure_only": "⚠️ Industry exposure only", "interest_only": "💭 Stated interest only",
         "in_progress_study": "📘 Study in progress"}
BAND = {"strong": "🟢 Good match with the working style your report describes",
        "mixed": "🟡 Mixed: some matches, some strains",
        "stretch": "🟠 Likely a stretch for the working style your report describes",
        "insufficient_info": "⚪ The report does not say enough to judge this area",
        "neutral": "⚪ Your preference results are too even to say"}
SAMPLE_CV = """Sample Person
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
def definitions(policy: str) -> tuple[dict, dict]:
    path = ROOT / "data" / "processed" / "area_definitions_v3.yaml" if policy == "v3" else None
    return assess.load_definitions(path), assess.load_regulated()


def read_text(upload, pasted: str) -> str:
    """Text from an uploaded PDF/TXT or the pasted box. Held in memory for this run only."""
    if upload is not None:
        data = upload.getvalue()
        return extract_pdf_text(data) if upload.name.lower().endswith(".pdf") else data.decode("utf-8", errors="replace")
    return pasted


def read_personamap(upload, pasted: str) -> PM.PersonaMap | None:
    if upload is not None:
        data = upload.getvalue()
        return PM.parse_pdf(data) if upload.name.lower().endswith(".pdf") else PM.parse_text(data.decode("utf-8", errors="replace"))
    return PM.parse_text(pasted) if pasted.strip() else None


def show_personamap_use(pm: PM.PersonaMap) -> None:
    with st.expander("What the PersonaMap step uses (the cover, page headers, date and your name are left out)", expanded=False):
        if pm.preferences:
            p = pm.preferences
            st.write(f"Preference results: E {p['E']:g}%, N {p['N']:g}%, F {p['F']:g}%, J {p['J']:g}%"
                     + (f" · balanced: {', '.join(p['balanced'])}" if p.get("balanced") else ""))
        if pm.readings:
            st.write("Type readings: " + " / ".join(f"{r['type']} ({r['label']})" for r in pm.readings))
        if pm.steps:
            st.write("Problem-solving steps: " + " · ".join(f"{s['step']}: {s['rating']}" for s in pm.steps))
        for w in pm.warnings:
            st.warning(f"Could not read part of the report ({w['code']}: {w['message']}). It is left out, not guessed.")
        st.caption(f"{len(pm.report_text())} characters would be used. Exactly this text:")
        st.text(pm.report_text())


def fit_block(row: dict | None, base: dict | None, label_only_local: bool = False) -> None:
    """The work-style panel for one area. Quotes come from the report and were checked against it."""
    if row:
        st.markdown(f"**{BAND.get(row['fit_band'], row['fit_band'])}**")
        for r in row["reasons"]:
            st.markdown(f"- {r['point']}  \n  _“{r['quote']}”_")
        for r in row["watch_outs"]:
            st.markdown(f"- ⚠️ {r['point']}  \n  _“{r['quote']}”_")
        if row.get("low_confidence"):
            st.caption("Low confidence: the AI reading and the local style check disagree by two levels.")
        if row["changes"]:
            st.caption(f"The checker removed {len(row['changes'])} unsupported statement(s) from the AI's answer.")
        base = row.get("baseline")
        if base:
            st.caption(f"Local style check: {BAND.get(base['band'], base['band'])}")
    elif base:
        st.markdown(f"**{BAND.get(base['band'], base['band'])}**")
        st.caption("Local style check only" + (" (the AI step did not complete)." if label_only_local else "."))
        for t in base["reasons"][:4]:
            st.markdown(f"- {t}")


def render_final(res: engines.EngineResult) -> None:
    st.caption(f"Engine: {res.label} · status: {res.status}")
    for w in res.warnings:
        st.info(w.replace("_", " ", 1))
    if res.status == "failed":
        st.error("The CV step failed and nothing was substituted: " + "; ".join(res.errors))
        return
    fits = (res.fit or {}).get("fits", {})
    only = (res.fit or {}).get("baseline_only", {})
    if res.fit and res.fit.get("status") == "failed":
        st.warning("The AI work-style step did not complete: " + "; ".join(res.fit.get("errors", [])) +
                   " Showing the local style check only, clearly separate from the AI reading.")
    st.subheader("Career areas the CV supports, with how your working style meets each")
    if not res.supported:
        st.info("No area is supported strongly enough by this CV text. That means the text gives too little evidence. "
                "It does not mean the person lacks skills or potential.")
    for s in res.supported:
        with st.container(border=True):
            st.markdown(f"### {s['rank']}. {s['name']}  ·  {BADGE.get(s['support_class'], '')}")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**From the CV (evidence)**")
                st.write(s.get("explanation", ""))
                if s.get("qualification_gaps"):
                    st.caption("Not shown in the text: " + "; ".join(s["qualification_gaps"]))
            with c2:
                st.markdown("**From the PersonaMap (working style)**")
                if s["area_id"] in fits or s["area_id"] in only:
                    fit_block(fits.get(s["area_id"]), only.get(s["area_id"]), label_only_local=bool(only))
                else:
                    st.caption("Not assessed.")
    if res.exploration:
        st.subheader("Exploration pathways (study or interest, not backed by work)")
        for e in res.exploration:
            with st.container(border=True):
                st.markdown(f"**{e['name']}**: {e.get('label') or ''}")
                if e["area_id"] in fits or e["area_id"] in only:
                    fit_block(fits.get(e["area_id"]), only.get(e["area_id"]), label_only_local=bool(only))
    st.caption("The working-style panel describes preferences, not ability or qualification. It does not change which areas the CV "
               "supports or their order, and it is not a hiring, selection or suitability judgment.")
    t = res.run_meta.get("totals") or {}
    if res.run_meta.get("cache_hit"):
        st.caption("Same inputs as an earlier run in this session: shown from memory, no new model calls.")
    elif t:
        cost = "free model" if t.get("estimated_cost_usd") == 0 else ("unknown" if t.get("estimated_cost_usd") is None
                                                                      else f"about US${t['estimated_cost_usd']:.4f} at list price")
        st.caption(f"This run: {t['calls']} model calls, {t['prompt_tokens']:,} tokens in, {t['completion_tokens']:,} out, "
                   f"{t['latency_s']:.0f} s, cost: {cost}.")
    with st.expander("Run details"):
        st.json({k: v for k, v in res.run_meta.items()})


# ------------------------------------------------------------------------------------------------ page
st.title("Two-step career exploration: CV, then working style")
st.markdown("**Step 1** reads the CV and finds the career areas the evidence supports. **Step 2** reads the PersonaMap report and "
            "shows how the working style it describes meets each of those areas. The second step never changes the first.")
mode = st.radio("Mode", ["Local check (real documents are fine; nothing leaves this computer)",
                         "Live two-step run (calls a free AI model; invented text only)"])
local = mode.startswith("Local")
if local:
    st.success("Local check: no model is called and nothing is sent anywhere. The shortlist comes from the local keyword engine, "
               "so it is **not evidence-checked**; use it to see the PersonaMap step, not as the final result.", icon="🔒")
else:
    st.warning("Live mode sends the text to OpenRouter and the free model "
               f"`{PILOT_MODEL}`. Free endpoints may log prompts, so use **invented example text only**, never a real person's documents.",
               icon="🧪")

c1, c2 = st.columns(2)
with c1:
    st.markdown("**1. CV**")
    cv_up = st.file_uploader("CV (PDF or TXT)", type=["pdf", "txt"], key="ts_cv")
    cv_paste = st.text_area("…or paste CV text", value="" if local else SAMPLE_CV, height=220, key="ts_cvp")
with c2:
    st.markdown("**2. PersonaMap report**")
    pm_up = st.file_uploader("PersonaMap report (PDF or TXT)", type=["pdf", "txt"], key="ts_pm")
    pm_paste = st.text_area("…or paste report text (pages separated by a form-feed line)", value="", height=220, key="ts_pmp")

cv_text = read_text(cv_up, cv_paste)
pm = read_personamap(pm_up, pm_paste)
if pm is not None:
    show_personamap_use(pm)

if local:
    if st.button("Run local check", disabled=not (cv_text.strip() and pm is not None)):
        prof = W.load_profiles()
        top = PL.run(PL.build_profile("Participant", cv_text, today=PL.REFERENCE_DATE))["scores"].sort_values(
            "score", ascending=False).head(10)
        rows = []
        for r in top.itertuples():
            b = W.baseline_fit(pm, prof[r.area_id]["demands"])
            rows.append(dict(rank=len(rows) + 1, area=r.name, keyword_score=round(float(r.score), 1),
                             style_check=BAND.get(b["band"], b["band"]), why="; ".join(b["reasons"][:2])))
        st.session_state["ts_local"] = rows
    if st.session_state.get("ts_local"):
        st.subheader("Local check result")
        st.caption("Keyword shortlist (not evidence-checked) with the local style check beside it. The style check is a draft rule "
                   "set on unreviewed area profiles and says nothing about ability.")
        st.dataframe(pd.DataFrame(st.session_state["ts_local"]), hide_index=True, width="stretch")
else:
    cfg = ev_client.settings()
    name = st.text_input("Participant name to hide (optional)")
    hide = [x.strip() for x in st.text_input("Other words to hide, comma separated (employers, schools, referees)").split(",") if x.strip()]
    policy = st.radio("Pipeline version", ["v2 (frozen)", "v3 (capped lists, exposure kept out of exploration)"], horizontal=True).split()[0]
    if cv_text.strip():
        with st.expander("What will be sent to the model (CV after masking)"):
            st.text(redact(cv_text, [name] if name else None, hide, orgs=True))
    confirm = st.checkbox("Both documents are invented example text. They are not a real person's.")
    leak = bool(cv_text.strip()) and redact(cv_text, None) != cv_text
    if leak:
        st.error("The CV text appears to contain an email address, phone number, ID or link. Remove it; live mode accepts invented text only.")
    if not cfg["api_key"]:
        st.warning("No OPENROUTER_API_KEY found (.env). Live mode is unavailable; the local check still works.")
    if st.button("Run the two-step pipeline", disabled=not (confirm and not leak and cfg["api_key"] and cv_text.strip() and pm is not None)):
        defs, reg = definitions(policy)
        run_cfg = dict(cfg, model=PILOT_MODEL, provider=PILOT_PROVIDER, data_collection="allow", max_tokens=60000,
                       temperature="", require_zdr=False, max_price="", api_key_2="")
        with st.spinner("Step 1: extracting evidence and assessing 94 areas. Step 2: working-style fit (several minutes on a free model)..."):
            try:
                res = engines.run("final", cv_text, name.strip(), defs=defs, personamap=pm, regulated=reg, cfg=run_cfg,
                                  policy=policy, hide=hide, mask_orgs=True, cache=st.session_state.setdefault("ts_cache", {}))
            except Exception as ex_:                      # network or unexpected provider errors
                res = engines.EngineResult("final", "n/a", "failed", errors=[f"{type(ex_).__name__}: {str(ex_)[:160]}"])
        st.session_state["ts_live"] = res
    got = st.session_state.get("ts_live")
    if got:
        render_final(got)

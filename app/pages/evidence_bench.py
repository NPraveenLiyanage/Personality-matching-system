"""Evidence-first test bench: the same step-by-step flow as the rule-based Test bench, with the evidence pipeline as the engine.

Upload a CV (PDF) and a PersonaMap report (PDF), or pick an invented example, then watch each step: profile, evidence
extraction, assessment of all 94 areas, the checker, and the Top 10. The model is a PROMPTED free model (nothing is fine-tuned yet).
Results live in this browser session only.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "app"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pandas as pd
import streamlit as st

from careerx.evidence import assess, client as ev_client, engine as ev_engine, ingest, replay
from careerx.profile import build_profile, dominant_pole
from common import label, participants_panel, sig_of, store

DEFS_PATH = ROOT / "data" / "processed" / "area_definitions_v2.yaml"
REG_PATH = ROOT / "data" / "processed" / "regulated_areas_v2.yaml"
MODEL = os.environ.get("CAREERX_PILOT_MODEL", "nvidia/nemotron-3.5-super-vl:free")
PROVIDER = os.environ.get("CAREERX_PILOT_PROVIDER", "nvidia")
BADGE = {"direct": "✅ Supported by evidence", "transferable": "✅ Supported (transferable skills)",
         "domain_exposure_only": "⚠️ Industry exposure only", "interest_only": "💭 Stated interest only",
         "in_progress_study": "📘 Study in progress", "unsupported": "➖ Not supported by the text",
         "insufficient_info": "❔ Not enough information"}
STRENGTH = {4: "very strong", 3: "strong", 2: "moderate", 1: "weak", 0: "none"}


@st.cache_data(show_spinner=False)
def definitions() -> tuple[dict, dict]:
    return assess.load_definitions(DEFS_PATH), assess.load_regulated(REG_PATH)


def run_pipeline(text: str, name: str) -> dict:
    defs, reg = definitions()
    cfg = dict(ev_client.settings(), model=MODEL, provider=PROVIDER, data_collection="allow", max_tokens=60000, timeout=900,
               temperature="", require_zdr=False, max_price="", api_key_2="")
    try:
        res = ev_engine.run(text, name, defs, cfg=cfg, regulated=reg)
    except Exception as e:                                   # network or unexpected provider errors
        return dict(status="failed", errors=[f"{type(e).__name__}: {str(e)[:160]}"], stages={})
    rb = replay.rebuild(res["stages"], defs, reg) if res.get("stages", {}).get("assessment") else None
    res["classes"] = rb["classes"] if rb and rb["ok"] else {}
    res["records"] = [dict(r) for r in res.get("stages", {}).get("extraction", {}).get("records", [])]
    return res


def top10(res: dict) -> list[dict]:
    """Evidence-backed areas first, then labelled exploration areas. May hold fewer than 10: nothing is padded with guesses."""
    rows = [dict(r, section="Backed by evidence") for r in res["supported"]]
    rows += [dict(r, section="Worth exploring (study or interest, not backed by work)") for r in res["exploration"]
             if r["support_class"] != "domain_exposure_only"]
    rows += [dict(r, section="Industry exposure only (context, not a career suggestion)") for r in list(res.get("context_only") or []) +
             [e for e in res["exploration"] if e["support_class"] == "domain_exposure_only"]]
    return rows[:10]


# ------------------------------------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("🧭 Career Exploration")
    st.caption("Evidence-first test bench · CV + PersonaMap → Top 10 career areas")
    st.markdown("**How the Top 10 is produced**\n\n"
                "1. Read the CV and the PersonaMap report\n"
                "2. AI extracts **what the person did**, each item tied to an exact quote\n"
                "3. AI assesses **all 94** career areas against that evidence only\n"
                "4. A software **checker** rejects claims the evidence cannot support\n"
                "5. Areas are ranked by rule (no AI scores) and the Top 10 is shown, with the reasons")
    st.info("**Prompted model, not fine-tuned.** No fine-tuned model exists yet. This uses a free model "
            f"(`{MODEL}`) with strict prompts and checks. Results are a prototype, not validated accuracy.", icon="🧪")

st.title("Career Exploration Engine: evidence-first test bench")
st.write("The same flow as the rule-based Test bench, but the engine reads the CV for what the person actually **did**, so a "
         "project built *for* a hospital counts as software work, not nursing.")

specs = store()
pick = st.selectbox("Whose profile?", list(specs), format_func=lambda k: label(specs[k]), key="ev_pick")
spec = specs[pick]
participants_panel("ev")
name, cv_text, pm_text = spec["name"], spec["cv_text"], spec.get("pm_text") or ""
personality = spec.get("personality")
profile = build_profile(name, cv_text, pm_text or None, personality=personality, today=spec.get("ref_date"))
sig = sig_of(pick, name, len(cv_text), cv_text[:60])
cache = st.session_state.setdefault("ev_results", {})
res = cache.get(sig)
is_demo = bool(spec.get("demo"))

tabs = st.tabs(["1 · Inputs", "2 · Evidence extracted", "3 · All 94 areas + checker", "4 · Top 10 report", "5 · Run details"])

# ================================================================== 1. inputs
with tabs[0]:
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("CV text")
        with st.expander("Show the CV text the engine reads", expanded=is_demo):
            st.text(cv_text)
        ing = ingest.ingest_text(cv_text, [name])
        st.caption(f"Split into {len(ing.passages)} passages in sections: "
                   + ", ".join(sorted({p.section for p in ing.passages})))
        if ing.warnings:
            st.warning("Document warnings: " + ", ".join(w["code"] for w in ing.warnings) +
                       ". Missing evidence here does not mean missing experience.")
    with right:
        st.subheader("PersonaMap (work style)")
        if profile.personality:
            st.caption(f"PersonaMap code **{profile.personality_code or 'n/a'}**")
            cols = st.columns(4)
            for i, d in enumerate("ENFJ"):
                v = profile.personality[d]
                side, strength = dominant_pole(d, v)
                cols[i].metric(side, f"{strength:.0f}%")
            st.caption("Work style is shown for context. It is **not evidence** and does not change which areas are "
                       "supported or how they are ranked in this engine. The report text stays on this server and is "
                       "never sent to the AI.")
        else:
            st.caption("No personality data given.")

    st.divider()
    st.subheader("Run the engine")
    if is_demo:
        st.caption("This is an invented example, safe to send to the AI.")
        ok = True
    else:
        st.warning("This looks like a real participant's CV. Live mode sends the **CV text only** (contact details removed) to "
                   f"OpenRouter and the free model `{MODEL}`. Free endpoints may log prompts. The PersonaMap report is never sent.",
                   icon="🔒")
        ok = st.checkbox("The participant has agreed that their CV text may be sent to this AI service.", key=f"consent_{sig}")
    cfg = ev_client.settings()
    if not cfg["api_key"]:
        st.error("No OPENROUTER_API_KEY configured: the live run is unavailable.")
    if st.button("Run the evidence-first engine (3-5 minutes)", type="primary", disabled=not (ok and cfg["api_key"])):
        with st.spinner("Step 1/2: extracting evidence... Step 2/2: assessing 94 areas (free model, please wait)..."):
            cache[sig] = run_pipeline(cv_text, name)
        st.rerun()
    if res is None:
        st.info("No run yet for this profile. Press the button above; the other tabs fill in when it finishes.")

# ================================================================== helpers for the remaining tabs
def need_run() -> bool:
    if res is None:
        st.info("Run the engine in tab 1 first.")
        return True
    if res["status"] == "failed":
        st.error("The run failed and nothing was substituted: " + "; ".join(res["errors"]))
        return True
    return False


# ================================================================== 2. evidence
with tabs[1]:
    st.subheader("Step 1 · What the CV says the person did")
    if not need_run():
        recs = res["records"]
        if res["status"] == "no_evidence":
            st.info("No usable evidence could be extracted. " + "; ".join(res["errors"]))
        st.caption("Each row is a quote from the CV with its type, role, whether it was the person's own work, and the "
                   "industry the work served. Industry is context, never a profession.")
        if recs:
            st.dataframe(pd.DataFrame([dict(id=r["evidence_id"], type=r["evidence_type"], role=r["role"],
                                            own_work=r["contribution"], industry_context=r["domain_context"],
                                            actions="; ".join(r.get("candidate_actions") or []), quote=r["quote"])
                                       for r in recs]), hide_index=True, width="stretch", height=420)
        ex = res["stages"].get("extraction", {})
        if ex.get("rejected"):
            st.warning(f"{len(ex['rejected'])} extracted items were rejected by the local quote check (the quote was not "
                       "found in the CV).")

# ================================================================== 3. assessment + checker
with tabs[2]:
    st.subheader("Step 2 · All 94 career areas assessed, then checked")
    if not need_run():
        classes = res["classes"]
        if classes:
            counts = pd.Series(classes).value_counts()
            cols = st.columns(4)
            cols[0].metric("Areas assessed", len(classes))
            cols[1].metric("Backed by evidence", int(counts.get("direct", 0) + counts.get("transferable", 0)))
            cols[2].metric("Exploration only", int(counts.get("domain_exposure_only", 0) + counts.get("interest_only", 0)
                                                    + counts.get("in_progress_study", 0)))
            cols[3].metric("Not supported", int(counts.get("unsupported", 0) + counts.get("insufficient_info", 0)))
        st.markdown("#### What the checker changed")
        st.caption("The checker overrules the AI when a cited item is missing, is only a skills list or stated interest, "
                   "is negated, is study still in progress, or does not match a regulated occupation.")
        log = res["validation_log"]
        shown = [c for c in log if c["original_class"] in ("direct", "transferable")]
        if shown:
            names = {aid: d["name"] for aid, d in definitions()[0]["areas"].items()}
            for c in shown:
                n = names.get(c["area_id"], c["area_id"])
                if c["final_class"] != c["original_class"]:
                    st.markdown(f"- **{n}**: the AI first said “{c['original_class'].replace('_', ' ')}”, the checker changed "
                                f"it to “{c['final_class'].replace('_', ' ')}”. Reason: {c['changes'][-1]}")
                else:
                    st.markdown(f"- **{n}**: kept as “{c['final_class'].replace('_', ' ')}” after removing a weak citation.")
        else:
            st.caption("The checker made no changes to areas the AI called supported.")
        with st.expander("Every area and its final class"):
            names = {aid: d["name"] for aid, d in definitions()[0]["areas"].items()}
            st.dataframe(pd.DataFrame([dict(area=names[a], result=BADGE[c]) for a, c in classes.items()])
                         .sort_values("result"), hide_index=True, width="stretch", height=420)

# ================================================================== 4. top 10
with tabs[3]:
    st.subheader(f"Top 10 career areas for {name}")
    if not need_run():
        items = top10(res)
        by_eid = {r["evidence_id"]: r for r in res["records"]}
        if not res["supported"]:
            st.info("No area is supported strongly enough by this text. That means the text gives too little evidence. "
                    "It does not mean the person lacks skills or potential.")
        last = None
        for i, r in enumerate(items, 1):
            if r["section"] != last:
                st.markdown(f"#### {r['section']}")
                last = r["section"]
            with st.container(border=True):
                h1, h2 = st.columns([4, 1])
                h1.markdown(f"### {i}. {r['name']}")
                h1.caption(BADGE[r["support_class"]])
                if r["relevance"] is not None:
                    h2.metric("evidence strength", f"{r['relevance']}/4", help="A rating of how well the text supports the "
                              "area. It is not a probability of success.")
                if r["support_class"] in ("direct", "transferable"):
                    st.markdown("**Why:** " + r["explanation"])
                    for eid in r["evidence_ids"][:3]:
                        if eid in by_eid:
                            st.caption(f"{eid}: “{by_eid[eid]['quote']}”")
                    if r["qualification_gaps"]:
                        st.caption("Not shown in the text: " + "; ".join(r["qualification_gaps"]))
                else:
                    st.markdown(r["label"] + ".")
        st.caption(f"Showing {len(items)} of a possible 10. The list is never padded with guesses: areas without evidence are "
                   "left out. This tool supports career exploration; it makes no hiring, selection or ability judgments.")
        md = [f"# Career areas for {name}", "", "Evidence-first prototype (prompted model, not fine-tuned).", ""]
        for i, r in enumerate(items, 1):
            md += [f"## {i}. {r['name']}", f"*{r['section']} · {BADGE[r['support_class']]}*", "", r["label"] or r["explanation"], ""]
        st.download_button("⬇ Download report (Markdown)", "\n".join(md), f"evidence_report_{name.replace(' ', '_')}.md")

# ================================================================== 5. run details
with tabs[4]:
    st.subheader("Run details and limits")
    if res is not None and res.get("run_meta"):
        m = res["run_meta"]
        st.json({k: {kk: vv for kk, vv in v.items() if kk in ("model", "provider", "latency_s", "finish_reason", "prompt_version")}
                 for k, v in m.items() if isinstance(v, dict)} | {"engine_version": res.get("engine_version"), "status": res["status"]})
    st.markdown(
        "- A free prompted model, one run; outputs can vary between runs.\n"
        "- The 94 area definitions and the regulated-occupation list are AI-drafted with reviewer notes, not yet expert-approved.\n"
        "- Benchmark results so far are on invented cases with team-written expectations, not independent ratings.\n"
        "- Results exist only in this browser session. Nothing is saved.")

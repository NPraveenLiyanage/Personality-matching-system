"""Test bench: the step-by-step tool a tester uses (profile, map, shortlist, narrowing, Top 10, feedback).

Opened from the router in app/streamlit_app.py (page "Test bench").
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "app"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np
import pandas as pd
import streamlit as st

from careerx import feedback, narrowing, report, scoring
from careerx import pipeline as PL
from careerx.profile import DIM_NAMES, build_profile
from common import EDU_OPTIONS, label, lexicon_choice, participants_panel, scorer, sig_of, store


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.title("🧭 Career Exploration")
    st.caption("Phase 1 research prototype · CV + PersonaMap → Top 10 career areas")
    st.markdown(
        "**How it works**\n\n"
        "1. Read the CV, the PersonaMap report and a short interests intake\n"
        "2. Score **every** ISCO-based career area (nobody rates 100 items)\n"
        "3. Run the *selectivity gate* (is the map too generous?)\n"
        "4. Show two short lists, then narrow with the participant's own reactions\n"
        "5. Output the Top 10 + collect tester accuracy feedback"
    )
    with st.expander("Calibration (for the supervisor demo)"):
        interest_strength = st.slider("Stated-interest strength", 0.0, 1.0, 0.60, 0.05,
                                      help="How much a stated passion alone can lift an area the CV never mentions.")
        influence = st.slider("Work-style influence", 0.0, 0.6, 0.35, 0.05,
                              help="How much PersonaMap can re-order relevant areas. It can never lift an irrelevant one.")
        max_share = st.slider("Selectivity gate: max share of areas 'suitable'", 0.05, 0.5, 0.25, 0.05)
        diversity = st.slider("Top-10 diversity", 0.0, 0.5, 0.25, 0.05,
                              help="0 = pure score order. Higher = fewer near-duplicate areas in the Top 10.")
        lex = lexicon_choice("bench_lex")
    st.info("Internal testing only. PersonaMap data is confidential to the participant and is not used for "
            "selection decisions.", icon="🔒")

sc = scorer(lex)
weights = dict(interest_strength=interest_strength, personality_influence=influence)   # per call; scorer is shared

st.title("Career Exploration Engine, Phase 1 test bench")
st.write("From a CV and a personality profile to a short, explainable list of career **areas** "
         "(not job titles), built on the ISCO-08 occupation classification.")

tabs = st.tabs(["1 · Profile", "2 · Full map & gate", "3 · Shortlist", "4 · Narrow down", "5 · Top 10 report",
                "6 · Tester feedback"])

# ================================================================== 1. profile
with tabs[0]:
    specs = store()
    pick = st.selectbox("Whose profile?", list(specs), format_func=lambda k: label(specs[k]), key="bench_pick")
    spec = specs[pick]
    participants_panel("bench")
    name, cv_text = spec["name"], spec["cv_text"]
    pm_text, manual_pers, ref_date = spec.get("pm_text") or "", spec.get("personality"), spec.get("ref_date")
    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("Interests intake")
        opts = PL.interest_options()
        chosen = st.multiselect("Areas you are genuinely passionate about (beyond what is on your CV)",
                                list(opts), format_func=lambda k: opts[k])
        passions = st.text_area("In your own words: what do you love doing, even if you never studied it?",
                                height=80, placeholder="e.g. I play the guitar and want to build a startup")

    pre = build_profile(name, cv_text, pm_text or None, personality=manual_pers, today=ref_date, lexicon=lex)

    with left:
        st.subheader("Level and experience")
        edu = st.selectbox("Education level", list(EDU_OPTIONS), index=list(EDU_OPTIONS).index(pre.education_band),
                           format_func=lambda k: EDU_OPTIONS[k], help=pre.education_note)
        years = st.number_input("Years of work experience", 0.0, 60.0,
                                float(min(max(pre.years_experience, 0.0), 60.0)), 0.5,
                                help="Estimated as the calendar time covered by dated roles (overlapping roles "
                                     "are merged, part-time roles count). Edit if wrong.")

    profile = build_profile(name, cv_text, pm_text or None, personality=manual_pers, interest_ids=chosen,
                            passions_text=passions, education_band=edu, years_experience=years, today=ref_date,
                            lexicon=lex)
    # sig_profile: who the participant is (feedback survives calibration changes)
    # sig: also the calibration sliders (the narrowing editor is positional, so it must reset when scores move)
    sig_profile = sig_of(pick, name, len(cv_text), pm_text[:40], manual_pers, tuple(chosen), passions, edu, years, lex)
    sig = sig_of(sig_profile, interest_strength, influence)

    with right:
        st.subheader("What the engine read")
        if profile.personality:
            st.caption(f"PersonaMap code **{profile.personality_code or 'n/a'}**")
            cols = st.columns(4)
            for i, d in enumerate("ENFJ"):
                v = profile.personality[d]
                bal = abs(v - 50) < 1
                cols[i].metric(DIM_NAMES[d] + (" (balanced)" if bal else ""), f"{v:.0f}%",
                               help="Balanced dimensions get zero weight, as the report itself advises." if bal else None)
        else:
            st.caption("No personality data: work-style is ignored (neutral).")
        rows = [dict(concept=sc.concept_labels[k], strength=v["strength"], evidence=", ".join(v["hits"]))
                for k, v in sorted(profile.cv_concepts.items(), key=lambda kv: -kv[1]["strength"])]
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=360,
                     column_config={"strength": st.column_config.ProgressColumn("CV strength", min_value=0,
                                                                                 max_value=1, format="%.2f")})
        if profile.interests:
            st.caption("Stated interests: " + ", ".join(sc.concept_labels[k] for k in profile.interests))
        else:
            st.caption("No interests given yet: the interests component is skipped, not guessed.")

# ---------------------------------------------------------------- compute
scores = sc.score(profile, weights=weights)
gate = scoring.sanity_gate(scores, max_share=max_share)
sl = narrowing.shortlist(scores)

# ================================================================== 2. map & gate
with tabs[1]:
    st.subheader("Every career area, scored")
    m = st.columns(5)
    m[0].metric("Areas scored", gate["n_areas"])
    m[1].metric("Highly / moderately suitable", f"{gate['n_high']} / {gate['n_moderate']}")
    m[2].metric("Share suitable", f"{gate['share_suitable']:.0%}", f"limit {gate['max_share']:.0%}",
                delta_color="off")
    m[3].metric("Median score", f"{gate['spread']['median']:.0f}")
    m[4].metric("Selectivity gate", "PASSED ✅" if gate["passed"] else "FAILED ❌")
    (st.success if gate["passed"] else st.error)(gate["message"])
    st.caption("The gate answers the consultant's test: if the system matches someone to most of the list, "
               "something is wrong and the map must not be shown.")

    a, b = st.columns([1, 2])
    with a:
        hist, edges = np.histogram(scores.score, bins=np.arange(0, 101, 10))
        st.bar_chart(pd.DataFrame({"areas": hist}, index=[f"{int(e)}-{int(e) + 10}" for e in edges[:-1]]))
        st.caption("Distribution of scores across all areas")
        cl = scores.groupby("cluster").score.agg(["count", "max"]).sort_values("max", ascending=False)
        st.dataframe(cl.rename(columns={"count": "areas", "max": "best score"}).round(0), width="stretch")
    with b:
        pick = st.multiselect("Filter by field", sorted(scores.cluster.unique()))
        view = scores if not pick else scores[scores.cluster.isin(pick)]
        tbl = view[["rank", "name", "cluster", "score", "cv", "interests", "modifier", "readiness"]].rename(
            columns={"rank": "#", "name": "career area", "cv": "CV evidence", "interests": "interest",
                     "modifier": "work-style ×", "readiness": "readiness ×"})
        st.dataframe(tbl, hide_index=True, width="stretch", height=420,
                     column_config={"score": st.column_config.ProgressColumn("score", min_value=0, max_value=100,
                                                                              format="%.0f"),
                                    "CV evidence": st.column_config.NumberColumn(format="%.2f"),
                                    "interest": st.column_config.NumberColumn(format="%.2f"),
                                    "work-style ×": st.column_config.NumberColumn(format="%.2f"),
                                    "readiness ×": st.column_config.NumberColumn(format="%.2f")})
    st.subheader("Why did an area get its score?")
    area = st.selectbox("Pick any area (including low-scored ones, to spot false negatives)", scores.name)
    r = scores[scores.name == area].iloc[0]
    st.markdown(f"**#{r['rank']} · {r.score:.0f}%** · {r.cluster}")
    e1, e2 = st.columns(2)
    e1.markdown(f"**CV evidence:** {r.why_cv}\n\n**Work-style:** {r.why_personality}")
    e2.markdown(f"**Level:** {r.why_readiness}\n\n**Typical but not on the CV:** {r.missing or 'nothing notable'}")
    st.caption("Example roles in this area: " + (", ".join(r.examples) or "n/a"))

# ================================================================== 3. shortlist
with tabs[2]:
    st.subheader("Two short lists instead of one long one")
    for title, key in [("Highly suitable (top 10)", "Highly suitable"),
                       ("Moderately suitable (next 10)", "Moderately suitable"),
                       ("You told us you are interested in these", "You told us you are interested in this")]:
        sub = sl[sl.list == key]
        if sub.empty:
            continue
        st.markdown(f"#### {title}")
        t = sub[["name", "cluster", "score", "why_cv"]].rename(columns={"name": "career area", "why_cv": "why"})
        st.dataframe(t, hide_index=True, width="stretch",
                     column_config={"score": st.column_config.ProgressColumn("match", min_value=0, max_value=100,
                                                                              format="%.0f")})
    if not profile.interests:
        st.info("No interests were given, so passion-driven areas (the 'music' case) cannot appear yet. "
                "Add interests in tab 1 to see them surface.")

# ================================================================== 4. narrowing
with tabs[3]:
    st.subheader("Narrow down with your own reactions (about 3 minutes)")
    st.caption("Moving a calibration slider changes the scores, so the reactions below start again. "
               "The tester feedback in tab 6 is kept.")
    cc = narrowing.cluster_counts(sl)
    st.markdown("**Round 1. Which fields draw you?** Leave empty to keep everything.")
    keep = st.multiselect("Fields", list(cc.cluster), key=f"keep_{sig}")
    d1 = narrowing.apply_clusters(sl, keep)

    st.markdown(f"**Round 2. React to {len(d1)} areas.** One tap each, plus a few words on why or why not.")
    edit_df = d1[["area_id", "name", "score", "list"]].copy()
    edit_df["reaction"] = "maybe"
    edit_df["why"] = ""
    ed = st.data_editor(
        edit_df, hide_index=True, width="stretch", key=f"r2_{sig}_{len(d1)}",
        disabled=["area_id", "name", "score", "list"],
        column_config={"area_id": None,
                       "name": st.column_config.TextColumn("career area"),
                       "score": st.column_config.NumberColumn("match", format="%.0f"),
                       "reaction": st.column_config.SelectboxColumn("your reaction",
                                                                    options=["like", "maybe", "no"],
                                                                    required=True),
                       "why": st.column_config.TextColumn("why / why not")})
    ratings = {r.area_id: dict(pref=r.reaction, reason=r.why) for r in ed.itertuples()}
    d2 = narrowing.apply_ratings(d1, ratings)

    st.markdown("**Round 3. Pick one.** A few tie-breakers right around the cut-off.")
    groups = narrowing.duel_groups(d2)
    names = dict(zip(d2.area_id, d2.name))
    picks = []
    for i, g in enumerate(groups):
        choice = st.radio(f"Which would you explore first? ({i + 1})", ["(no preference)"] + g,
                          format_func=lambda a: names.get(a, a), horizontal=True, key=f"duel_{sig}_{i}")
        if choice != "(no preference)":
            picks.append(choice)

    sim = narrowing.area_similarity(sc.X, list(d2.area_id), list(PL.get_catalogue().area_id))
    top = narrowing.final_top(d2, duel_picks=picks, sim=sim, diversity=diversity)
    top["reason"] = top["reason"].fillna("")
    st.session_state["top"] = top
    st.caption(f"{len(d1)} areas considered, {sum(1 for r in ratings.values() if r['pref'] == 'no')} dropped, "
               f"{len(picks)} tie-breaks used → {len(top)} areas in your Top 10.")

# ================================================================== 5. report
with tabs[4]:
    top = st.session_state.get("top")
    st.subheader(f"Top 10 career areas for {profile.name}")
    if top is None or top.empty:
        st.info("Go through tab 4 first.")
    else:
        for _, r in top.iterrows():
            with st.container(border=True):
                h1, h2 = st.columns([4, 1])
                h1.markdown(f"### {int(r.final_rank)}. {r['name']}")
                h1.caption(r.cluster + ("  ·  from your stated interests" if r.get("is_wildcard") else ""))
                h2.metric("match", f"{r.score:.0f}%")
                st.markdown(f"**Why (CV):** {r.why_cv}")
                st.markdown(f"**Work-style:** {r.why_personality}")
                if r.reason:
                    st.markdown(f"**You said:** {r.reason}")
                if r.missing:
                    st.markdown(f"**Common here, not yet on your CV:** {r.missing}")
                st.caption(f"Level: {r.why_readiness}")
                st.caption("Example roles: " + ", ".join(r.examples[:6]))
        md = report.build_markdown(profile, top, scores, gate)
        c1, c2 = st.columns(2)
        c1.download_button("⬇ Download report (Markdown)", md, f"career_report_{profile.name.replace(' ', '_')}.md")
        c2.download_button("⬇ Download Top 10 (CSV)",
                           top[["final_rank", "name", "cluster", "score", "reason"]].to_csv(index=False),
                           "top10.csv")

# ================================================================== 6. feedback
with tabs[5]:
    st.subheader("Tester validation: how accurate is the full map?")
    st.markdown("Rate each line **1–5** (5 = highly accurate). A comment is required unless it is "
                "*highly accurate*. This includes low scores you think are **wrong**, e.g. a passion that is "
                "not on your CV.")
    fk = f"fb_{sig_profile}"
    if fk not in st.session_state:
        st.session_state[fk] = feedback.feedback_template(scores)
        st.session_state[fk + "_v"] = 0
    ver = st.session_state[fk + "_v"]
    # if calibration moved the scores, refresh the shown score but keep ratings and comments (matched by area_id)
    st.session_state[fk]["match_score"] = (
        st.session_state[fk].area_id.map(scores.set_index("area_id").score).values)
    edited = st.data_editor(
        st.session_state[fk], hide_index=True, width="stretch", height=460, key=f"{fk}_{ver}",
        disabled=["no", "area_id", "career_area", "cluster", "match_score"],
        column_config={"area_id": None,
                       "career_area": "career area", "match_score": st.column_config.NumberColumn("score", format="%.0f"),
                       "accuracy": st.column_config.SelectboxColumn("accuracy", options=[1, 2, 3, 4, 5]),
                       "comment": st.column_config.TextColumn("comment (why not highly accurate?)", width="large")})
    st.session_state[fk] = edited

    b1, b2 = st.columns([2, 1])
    with b1:
        bulk = st.selectbox("Bulk-confirm a whole field as highly accurate (unrated rows only)",
                            ["-"] + sorted(scores.cluster.unique()))
    with b2:
        st.write("")
        if st.button("Confirm field") and bulk != "-":
            fb = edited.copy()
            mask = (fb.cluster == bulk) & fb.accuracy.isna()
            fb.loc[mask, "accuracy"] = 5
            st.session_state[fk] = fb
            st.session_state[fk + "_v"] = ver + 1
            st.rerun()

    miss = feedback.missing_comments(edited)
    summ = feedback.summarise(edited)
    if summ.get("rated"):
        k = st.columns(4)
        k[0].metric("Rated", f"{summ['rated']} / {summ['total']}")
        k[1].metric("Mean accuracy", summ["mean_accuracy"])
        k[2].metric("% accurate (4–5)", f"{summ['pct_accurate']}%", f"target {summ['target_pct']:.0f}%",
                    delta_color="off")
        k[3].metric("Comments missing", len(miss))
        st.markdown("**Accuracy by score band**")
        st.dataframe(summ["by_band"], width="stretch")
        if len(summ["false_positives"]):
            st.markdown("**Shown as suitable, rated inaccurate (false positives)**")
            st.dataframe(summ["false_positives"], hide_index=True, width="stretch")
        if len(summ["false_negatives"]):
            st.markdown("**Shown as unsuitable, rated inaccurate (false negatives)**")
            st.dataframe(summ["false_negatives"], hide_index=True, width="stretch")
    if len(miss):
        st.warning(f"{len(miss)} rows below 'highly accurate' still need a comment: "
                   + ", ".join(f"#{n}" for n in miss.no.head(12)))
    st.download_button("⬇ Download feedback (CSV)", edited.to_csv(index=False),
                       f"feedback_{profile.name.replace(' ', '_')}.csv", disabled=bool(len(miss)),
                       help="Enabled once every row below 'highly accurate' has a comment.")

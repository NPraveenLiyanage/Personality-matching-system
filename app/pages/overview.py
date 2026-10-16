"""Your career directions: a short, visual report for the person reading it.

Opened from the router in app/streamlit_app.py (landing page). It shows only what helps someone get an idea of
which career areas to explore. It is a recommendation to think about, not a decision. Works on whoever is chosen at
the top: made-up demo people, or a real CV and personality report added during the session (held in memory only,
never saved).
"""
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "app"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import pandas as pd
import streamlit as st

import viz
from careerx import diagnostics as D, insights as I
from careerx import pipeline as PL
from common import EDU_OPTIONS, label, participants_panel, scorer, store

LEX = "v2"
SECTIONS = [("glance", "At a glance"), ("you", "About you"), ("fit", "Directions to explore"),
            ("why", "Why an area fits")]


def card(title: str, value: str, text: str) -> None:
    with st.container(border=True):
        st.caption(title)
        st.markdown(f"<div style='font-size:22px;font-weight:500;line-height:1.25'>{html.escape(value)}</div>",
                    unsafe_allow_html=True)
        st.write(text)


def how_to_read(text: str) -> None:
    st.caption("How to read this: " + text)


def short(name: str) -> str:
    return name.split(" (")[0]


# ------------------------------------------------------------------------------------------------ sidebar
with st.sidebar:
    st.markdown("**On this page**")
    st.markdown("\n".join(f"- [{t}](#{a})" for a, t in SECTIONS))

# ------------------------------------------------------------------------------------------------ header
st.title("Your career directions")
st.write("A few career areas (fields of work, not job titles) that fit what your CV and your working style point "
         "to. Use them as ideas to explore. They are a starting point, not a decision.")

specs = store()
a, b = st.columns([2, 3])
with a:
    pick = st.selectbox("Whose results?", list(specs), format_func=lambda k: label(specs[k]), key="ov_pick")
with b:
    participants_panel("ov")

spec = specs[pick]
sc = scorer(LEX)
profile = PL.profile_from_spec(spec, LEX)
base = sc.score(profile)
field, n_field = I.top_field(base)
mix = I.cluster_mix(base)
top = base.iloc[0]

# ------------------------------------------------------------------------------------------------ at a glance
st.header("At a glance", anchor="glance")
st.write(f"Your strongest direction is **{field}**, and your best single match is **{top['name']}**.")
left, right = st.columns([2, 3])
with left:
    st.markdown(f"<div style='font-size:72px;font-weight:500;line-height:1.05;margin-top:12px'>{top.score:.0f}%</div>",
                unsafe_allow_html=True)
    st.write(f"match with **{top['name']}**")
    st.caption("A match compares areas with each other. It is not a promise.")
with right:
    st.markdown(f"**Your top 10 by field: {n_field} are in {field}**")
    viz.show_donut(mix, center=f"{n_field} of 10", key="glance")
    how_to_read("each slice is a field. The number in the middle is the biggest field's share of your top 10.")

# ------------------------------------------------------------------------------------------------ about you
st.header("About you", anchor="you")
st.write(f"From the CV we found **{len(profile.cv_concepts)} strengths**, about **{profile.years_experience:g} years** of "
         f"experience, and read your education as **{EDU_OPTIONS[profile.education_band].split(' (')[0].lower()}**.")
c1, c2 = st.columns([3, 2])
with c1:
    st.markdown("**Strengths found in your CV**")
    strengths = pd.DataFrame([dict(strength=sc.concept_labels[k], strength_pct=round(v["strength"] * 100),
                                   found=", ".join(v["hits"])) for k, v in
                              sorted(profile.cv_concepts.items(), key=lambda kv: -kv[1]["strength"])])
    if strengths.empty:
        st.info("We could not find career phrases in this CV. Try pasting the text of the CV instead.")
    else:
        viz.show(viz.simple_bars(strengths.head(10), "strength", "strength_pct", highlight=set(strengths.head(3).strength),
                                 fmt=".0f", extra=["found"], domain=[0, 100]), strengths, key="strengths")
        how_to_read("a longer bar means more of your CV is about it. Hover to see the phrases we found. Your top 3 are blue.")
with c2:
    st.markdown("**How you like to work**")
    rows = I.personality_spectrum(profile)
    if rows:
        st.altair_chart(viz._style(viz.spectrum_bars(rows)), use_container_width=True, theme=None)
        how_to_read("the dot shows which side you lean to. A grey dot means no clear preference.")
    else:
        st.info("No personality report was added, so working style is left out.")


# ------------------------------------------------------------------------------------------------ directions + why
@st.fragment
def explore(spec: dict) -> None:
    sc = scorer(LEX)
    p0 = PL.profile_from_spec(spec, LEX)
    base = sc.score(p0)
    opts = PL.interest_options()
    passions = st.multiselect("Is there something you love that is not on your CV? Add it and see what changes.",
                              list(opts), format_func=lambda k: opts[k], key="ex_pass")
    new = sc.score(D.with_interests(p0, passions)) if passions else base
    if passions:
        mv = D.rank_movers(base, new, top=12)
        up = mv[mv.move > 0].sort_values("move", ascending=False).head(2)
        bits = [f"{r.area} rises from #{int(r.before)} to #{int(r.after)}" for r in up.itertuples()]
        st.markdown("**What changed:** " + ("; ".join(bits) + "." if bits else "your top areas stay the same."))
    st.markdown("**Your best-matching areas**")
    viz.show(viz.ranked_bars(new, extra_tooltip=["cluster"]), new.head(15)[["rank", "name", "cluster", "score"]],
             key="ex_rank", table_cols=["rank", "name", "cluster", "score"])
    how_to_read("blue bars are your top 10, grey ones are the next best. A longer bar is a better match.")

    st.header("Why an area fits", anchor="why")
    choice = st.selectbox("Pick an area to understand", list(new.head(15).name), key="ex_area")
    row = new[new.name == choice].iloc[0]
    meters = [("Evidence in your CV", float(row.cv), I.evidence_label(row.cv)),
              ("Fits how you like to work", float(row.personality) if p0.personality else 0.5, I.fit_label(row.modifier)),
              ("Matches your level", float(row.readiness), I.level_label(row.readiness))]
    m1, m2 = st.columns([3, 2])
    with m1:
        st.altair_chart(viz._style(viz.three_meters(meters)), use_container_width=True, theme=None)
    with m2:
        st.markdown(f"**{choice}** ({row.cluster})")
        st.write(f"Evidence: {row.why_cv}")
        if row.missing:
            st.write(f"Common in this area but not on your CV yet: {row.missing}.")
        st.caption("Example roles: " + ", ".join(row.examples[:5]))


st.header("Directions to explore", anchor="fit")
explore(spec)
st.caption("These suggestions come from a simple, explainable comparison of your CV and working style with a "
           "standard list of career areas. They are ideas to think about, not advice or a prediction.")

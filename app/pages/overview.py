"""Overview report: what we built and what we found, in plain English, with live charts you can play with.

Opened from the router in app/streamlit_app.py (landing page). Works on whoever is chosen at the top: made-up demo
people, or real CVs and personality reports added during the session (held in memory only, never saved).
"""
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "app"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np
import pandas as pd
import streamlit as st

import viz
from careerx import catalogue, diagnostics as D, findings as F, insights as I, isco, narrowing, report, scoring
from careerx import pipeline as PL
from careerx.profile import detect_concepts, strip_references
from common import EDU_OPTIONS, label, lexicon_choice, participants_panel, scorer, store

STATUS_ICON = {"done": "✅ Done", "partly": "🟡 Partly", "open": "⬜ Open"}
INFLUENCE = {"Ignore it": 0.0, "A little": 0.2, "As built": 0.35, "A lot": 0.6}
SECTIONS = [("glance", "At a glance"), ("asked", "What we were asked"), ("why", "Why not match every job"),
            ("catalogue", "The catalogue"), ("person", "Who is this person?"), ("play", "Where do they fit? (play)"),
            ("compare", "How do people compare?"), ("broke", "What broke and what it taught"),
            ("accuracy", "How accurate is it?"), ("findings", "Findings and next steps"), ("export", "Take it with you")]


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
    st.divider()
    lex = lexicon_choice("ov_lex")
    st.caption("Everything here is computed live. Change the person, the keyword list or any control and the "
               "charts follow.")

# ------------------------------------------------------------------------------------------------ header
st.title("Career exploration: what we built and what we found")
st.write("From a CV and a personality report to a short, explainable list of **career areas** (fields of work, "
         "not job titles). Read it top to bottom, or jump around. The sections marked **play** are meant to be tried.")
with st.expander("How to read this page, and the words we use"):
    st.markdown("Each section starts with the answer in one sentence, then a chart, then a line on how to read it. "
                "Hover any bar for detail. Every chart has a **Show as table** switch.")
    for term, meaning in F.GLOSSARY.items():
        st.markdown(f"**{term}**: {meaning}")

specs = store()
a, b = st.columns([2, 3])
with a:
    pick = st.selectbox("Who are we looking at?", list(specs), format_func=lambda k: label(specs[k]), key="ov_pick")
with b:
    participants_panel("ov")

spec = specs[pick]
sc = scorer(lex)
profile = PL.profile_from_spec(spec, lex)
base = sc.score(profile)
gate = scoring.sanity_gate(base)
pe = D.personality_effect(profile, sc)
hl = I.headline(base, gate, pe)
mix = I.cluster_mix(base)

# ------------------------------------------------------------------------------------------------ 0. at a glance
st.header("At a glance", anchor="glance")
st.write(f"**{short(spec['name'])}**: the strongest direction is **{hl['field']}**, and the best single match is "
         f"**{hl['top_area']}**.")
left, right = st.columns([2, 3])
with left:
    st.markdown(f"<div style='font-size:72px;font-weight:500;line-height:1.05;margin-top:12px'>{hl['top_score']:.0f}%</div>",
                unsafe_allow_html=True)
    st.write(f"best match: **{hl['top_area']}**")
    st.caption("A match is a comparison across areas, not a promise. Treat the top 10 as directions to explore.")
with right:
    st.markdown(f"**The top 10 by field: {hl['n_in_field']} are in {hl['field']}**")
    viz.show_donut(mix, center=f"{hl['n_in_field']} of 10", key="glance")
    how_to_read("each slice is a field. The number in the middle is the biggest field's share of the top 10.")
cols = st.columns(len(hl["cards"]))
for col, c in zip(cols, hl["cards"]):
    with col:
        card(c["title"], c["value"], c["text"])

# ------------------------------------------------------------------------------------------------ 1. asked
st.header("What we were asked to do", anchor="asked")
done = sum(1 for r in F.REQUIREMENTS if r[2] == "done")
st.write(f"The consultant's brief had {len(F.REQUIREMENTS)} parts. **{done} are done**, "
         f"{sum(1 for r in F.REQUIREMENTS if r[2] == 'partly')} are partly done and "
         f"{sum(1 for r in F.REQUIREMENTS if r[2] == 'open')} have not started.")
st.dataframe(pd.DataFrame([dict(No=r[0], Ask=r[1], Status=STATUS_ICON[r[2]], Notes=r[3]) for r in F.REQUIREMENTS]),
             hide_index=True, width="stretch")

# ------------------------------------------------------------------------------------------------ 2. why not 150
st.header("Why not match every job to every person?", anchor="why")
st.write("The computer scores **every** area in a blink. The limit is the human: nobody can sensibly react to "
         "94 options. So we score everything, show about 20, and ask for reactions to those.")
stages = [("Areas scored by the computer", gate["n_areas"]), ("Shortlisted to react to", 20), ("Shown as the top list", 10)]
viz.show(viz.funnel(stages), pd.DataFrame(stages, columns=["stage", "areas"]), key="funnel")
how_to_read("the wide bar is what the computer handles, the narrow blue bar is what a person sees.")

st.subheader("Why we did not simply drill down by sector")
st.write("ISCO groups jobs by **kind and level of work** (managers, professionals, technicians...), not by field. "
         "So one field is split across several 'sectors'. Pick a field:")
field = st.selectbox("Field", list(F.FIELD_GROUPS), key="why_field")
mg = isco.minor_groups()
kinds = isco.load_structure()
kinds = kinds[kinds.level == 1].set_index("code").title.to_dict()
sub = mg[mg.code.isin(F.FIELD_GROUPS[field])].copy()
sub["Major group"] = sub.code.str[0].map(lambda c: f"Group {c}: {kinds.get(c, '')}")
per = sub.groupby("Major group").size().rename("job groups").reset_index()
st.write(f"**{field}** spreads across **{per.shape[0]} different major groups**. "
         + ("A drill-down by major group would treat them as separate sectors." if per.shape[0] > 1 else "This one happens to sit in one."))
viz.show(viz.simple_bars(per, "Major group", "job groups", highlight=set(per["Major group"]), fmt=".0f", domain=[0, max(4, int(per["job groups"].max()) + 1)]),
         per, key="why_field")
with st.expander("See the job groups"):
    st.dataframe(sub[["code", "title", "Major group"]].rename(columns={"code": "ISCO code", "title": "Job group"}),
                 hide_index=True, width="stretch")

# ------------------------------------------------------------------------------------------------ 3. catalogue
st.header("The catalogue", anchor="catalogue")
cat = PL.get_catalogue()
rows = []
for cl, g in cat.groupby("cluster"):
    minors = {m for s in g[g.kind == "isco"].isco_minor for m in s.split(",")}
    rows.append(dict(field=cl, areas=len(g), isco_groups=len(minors)))
fld = pd.DataFrame(rows)
fld["areas per ISCO group"] = (fld.areas / fld.isco_groups).round(2)
hi, lo = fld.sort_values("areas per ISCO group").iloc[-1], fld.sort_values("areas per ISCO group").iloc[0]
st.write(f"We built **{len(cat)} career areas in {cat.cluster.nunique()} fields**. They are not evenly detailed: "
         f"**{hi.field}** gets {hi['areas per ISCO group']:.2f} areas per ISCO group, **{lo.field}** only "
         f"{lo['areas per ISCO group']:.2f}. That can make technology look bigger in a technical person's top 10.")
viz.show(viz.simple_bars(fld, "field", "areas per ISCO group", highlight={hi.field, lo.field}, fmt=".2f"), fld,
         key="catalogue", table_cols=["field", "areas", "isco_groups", "areas per ISCO group"])
how_to_read("longer bar = the field is sliced into more, finer areas. Blue marks the finest and the coarsest.")
q = st.text_input("Search the catalogue", placeholder="e.g. nursing, music, finance", key="cat_search")
view = cat if not q else cat[cat.name.str.contains(q, case=False) | cat.cluster.str.contains(q, case=False)]
st.dataframe(view.assign(Origin=np.where(view.kind == "lens", "Extra modern area", "From ISCO"))[
    ["name", "cluster", "Origin", "isco_minor"]].rename(columns={"name": "Career area", "cluster": "Field", "isco_minor": "ISCO codes"}),
    hide_index=True, width="stretch", height=260)

# ------------------------------------------------------------------------------------------------ 4. person
st.header("Who is this person?", anchor="person")
st.write(f"From the CV the engine found **{len(profile.cv_concepts)} career strengths**, about "
         f"**{profile.years_experience:g} years** of experience, and read the education as "
         f"**{EDU_OPTIONS[profile.education_band].split(' (')[0].lower()}**.")
c1, c2 = st.columns([3, 2])
with c1:
    st.markdown("**Strengths found in the CV**")
    strengths = pd.DataFrame([dict(strength=sc.concept_labels[k], strength_pct=round(v["strength"] * 100),
                                   found=", ".join(v["hits"])) for k, v in
                              sorted(profile.cv_concepts.items(), key=lambda kv: -kv[1]["strength"])])
    if strengths.empty:
        st.info("No career phrases were recognised in this CV. See the vocabulary check on the right.")
    else:
        top3 = set(strengths.head(3).strength)
        viz.show(viz.simple_bars(strengths.head(10), "strength", "strength_pct", highlight=top3, fmt=".0f", extra=["found"],
                                 domain=[0, 100]), strengths, key="strengths")
        how_to_read("longer bar = more phrases about it in the CV. Hover to see the phrases found. The top 3 are blue.")
with c2:
    st.markdown("**How they like to work**")
    spec_rows = I.personality_spectrum(profile)
    if spec_rows:
        st.altair_chart(viz._style(viz.spectrum_bars(spec_rows)), use_container_width=True, theme=None)
        how_to_read("the dot shows which side they lean to. A grey dot means no clear preference, so it gets no weight.")
    else:
        st.info("No personality report for this person, so working style is left out (neutral).")
cov = D.lexicon_coverage(profile.cv_text, sc, lex)
st.markdown("**Does the engine understand this CV?**")
c3, c4 = st.columns([2, 3])
with c3:
    dd = pd.DataFrame([("Recognised", cov["recognised_pct"]), ("Not recognised", round(100 - cov["recognised_pct"], 1))],
                      columns=["field", "pct"])
    viz.show_donut(dd, count="pct", center=f"{cov['recognised_pct']:.0f}%", value_fmt="{:.0f}%", key="coverage")
with c4:
    st.write(f"{cov['recognised_pct']:.0f}% of the career-related words in this CV match a phrase on the keyword list.")
    if cov["blind_spots"]:
        st.write("Frequent words the engine **ignores**: " + ", ".join(f"{w} ({n})" for w, n in cov["blind_spots"][:8]) + ".")
        st.caption("A career built on words that are not on the list is invisible to the engine. This is how we found a gap.")


# ------------------------------------------------------------------------------------------------ 5. playground
@st.fragment
def playground(spec: dict, lex: str) -> None:
    sc = scorer(lex)
    p0 = PL.profile_from_spec(spec, lex)
    base = sc.score(p0)
    opts = PL.interest_options()
    defaults = dict(pg_pass=[], pg_infl="As built", pg_formula="final", pg_level=True, pg_strength=0.6)
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

    def preset(**kw):
        st.session_state.update({**defaults, **kw})

    st.write("Try a what-if. The list on the left re-ranks instantly, and the chart underneath shows exactly what moved.")
    b = st.columns(4)
    b[0].button("Start again", on_click=preset, use_container_width=True)
    b[1].button("They love music", on_click=preset, kwargs=dict(pg_pass=["music_arts"]), use_container_width=True)
    b[2].button("Ignore working style", on_click=preset, kwargs=dict(pg_infl="Ignore it"), use_container_width=True)
    b[3].button("Use our first formula", on_click=preset, kwargs=dict(pg_formula="additive"), use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        passions = st.multiselect("What if they are passionate about...", list(opts), format_func=lambda k: opts[k], key="pg_pass")
        infl_name = st.select_slider("How much should working style matter?", list(INFLUENCE), key="pg_infl")
    with c2:
        formula = st.radio("How are the parts combined?", ["final", "average", "additive"],
                           format_func=lambda k: D.FORMULA_LABELS[k], key="pg_formula")
        level = st.toggle("Take education and experience into account", key="pg_level")
    with st.expander("More controls"):
        strength = st.slider("How far can a passion alone lift an area?", 0.0, 1.0, step=0.05, key="pg_strength")

    p = D.with_interests(p0, passions) if passions else p0
    wts = dict(personality_influence=INFLUENCE[infl_name], interest_strength=strength)
    new = sc.score(p, weights=wts, formula=formula, use_readiness=level)
    g = scoring.sanity_gate(new)
    changed = bool(passions) or infl_name != "As built" or formula != "final" or not level
    mv = D.rank_movers(base, new, top=12)

    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Best-matching areas**")
        viz.show(viz.ranked_bars(new, extra_tooltip=["cluster"]), new.head(15)[["rank", "name", "cluster", "score"]],
                 key="play_rank", table_cols=["rank", "name", "cluster", "score"])
        how_to_read("blue bars are the top 10, grey ones are the next best. Longer = better match.")
    with right:
        st.markdown("**Is the map too generous?**")
        pct = 100 * g["share_suitable"]
        st.altair_chart(viz._style(viz.meter(pct, 100 * g["max_share"], g["passed"])), use_container_width=True, theme=None)
        (st.success if g["passed"] else st.error)(
            ("✅ " if g["passed"] else "❌ ") + I.generosity_sentence(g))
        mix_n = I.cluster_mix(new)
        st.markdown("**Top 10 by field**")
        viz.show_donut(mix_n, center=f"{int(mix_n.areas.max())} of 10", key="play_mix")

    if changed:
        big = mv.reindex(mv.move.abs().sort_values(ascending=False).index).head(2)
        bits = [f"{r.area} {'rises' if r.move > 0 else 'falls'} from #{int(r.before)} to #{int(r.after)}" for r in big.itertuples() if r.move != 0]
        st.markdown("**What changed:** " + ("; ".join(bits) + "." if bits else "nothing moved in the top 12."))
        if len(mv) and (mv.move != 0).any():
            viz.show(viz.dumbbell(mv, "Starting point", "Your what-if"), mv, key="play_move")
            how_to_read("each row is an area. The hollow dot is where it started, the filled dot where it is now. Blue = moved up, red = moved down.")
    else:
        st.caption("Change a control above to see what moves.")

    st.markdown("**Why did an area get its score?**")
    choice = st.selectbox("Pick an area", list(new.head(15).name), key="pg_area")
    row = new[new.name == choice].iloc[0]
    fit_v = float(row.personality) if p.personality else 0.5
    meters = [("Evidence in the CV", float(row.cv), I.evidence_label(row.cv)),
              ("Fits how they like to work", fit_v, I.fit_label(row.modifier)),
              ("Level fit", float(row.readiness), I.level_label(row.readiness))]
    m1, m2 = st.columns([3, 2])
    with m1:
        st.altair_chart(viz._style(viz.three_meters(meters)), use_container_width=True, theme=None)
    with m2:
        for lab, word, text in I.why_sentences(row):
            st.markdown(f"**{lab}: {word}.** {text}")
        if row.missing:
            st.markdown(f"**Common here but not on the CV:** {row.missing}.")
        st.caption("Example roles: " + ", ".join(row.examples[:5]))


st.header("Where do they fit? (play)", anchor="play")
playground(spec, lex)


# ------------------------------------------------------------------------------------------------ 6. compare
@st.fragment
def compare(lex: str) -> None:
    specs = store()
    ids = st.multiselect("Who to compare", list(specs), default=list(specs)[:4], format_func=lambda k: label(specs[k]), key="cmp_ids")
    if len(ids) < 2:
        st.info("Pick at least two people.")
        return
    names, results = [], {}
    for k in ids:
        nm = short(specs[k]["name"])
        nm = nm if nm not in results else f"{nm} ({k[-3:]})"
        names.append(nm)
        results[nm] = PL.run(PL.profile_from_spec(specs[k], lex), lexicon=lex)
    cmp = D.compare_profiles(results, catalogue.CLUSTERS)
    st.write(I.compare_sentence(cmp, names))
    heat = cmp["heat"].reset_index().melt(id_vars="index", var_name="Field", value_name="score").rename(columns={"index": "Person"})
    viz.show(viz.heatmap(heat, "Field", "Person", "score", catalogue.CLUSTERS, names), heat, key="cmp_heat")
    how_to_read("darker = a better match in that field. Numbers show only the strong matches (50 and above).")
    shown = st.columns(min(len(names), 4))
    for col, nm in zip(shown, names):
        with col:
            st.markdown(f"**{nm}**")
            for i, r in enumerate(results[nm]["scores"].head(10).itertuples(), 1):
                st.write(f"{i}. {r.name}")
    if cmp["shared_all"]:
        st.success("In everyone's top 10: " + ", ".join(cmp["shared_all"]))


st.header("How do people compare?", anchor="compare")
compare(lex)


# ------------------------------------------------------------------------------------------------ 7. what broke
@st.fragment
def broke(spec: dict, lex: str) -> None:
    sc = scorer(lex)
    p0 = PL.profile_from_spec(spec, lex)
    tabs = st.tabs([f"{i + 1}. {w[0]}" for i, w in enumerate(F.WHAT_BROKE)])
    for tab, (_, headline, saw, why, did) in zip(tabs, F.WHAT_BROKE):
        with tab:
            st.subheader(headline)
            st.markdown(f"**What we saw.** {saw}  \n**Why.** {why}  \n**What we did.** {did}")
    with tabs[0]:
        fc = D.formula_comparison(p0, sc)
        for f in ("additive", "average", "final"):
            g = fc[f]["gate"]
            st.markdown(f"**{D.FORMULA_LABELS[f]}**: {round(100 * g['share_suitable'])}% of areas look suitable "
                        + ("✅" if g["passed"] else "❌ too generous"))
            st.altair_chart(viz._style(viz.meter(100 * g["share_suitable"], 25, g["passed"])), use_container_width=True, theme=None)
        how_to_read("the line is our 25% limit. Adding the parts together fills the bar for almost any person.")
    with tabs[1]:
        txt = st.text_area("Try your own dated roles (edit me)", key="br_years", height=130,
                           value="\n".join(["WORK EXPERIENCE", "Founder | Jan 2010 - Dec 2012", "Director | Jan 2011 - Dec 2013",
                                            "Advisor | Jun 2012 - Dec 2015", "EDUCATION"]))
        r = D.naive_vs_merged_years(txt, PL.REFERENCE_DATE)
        yr = pd.DataFrame([("Adding up each role", r["naive_years"]), ("Calendar time covered", r["merged_years"])], columns=["measure", "years"])
        viz.show(viz.simple_bars(yr, "measure", "years", highlight={"Calendar time covered"}, fmt=".1f"), yr, key="br_years_t")
        mine = D.naive_vs_merged_years(p0.raw_cv_text, spec.get("ref_date"))
        if mine["n_roles"]:
            st.caption(f"For the person chosen above: {mine['n_roles']} dated roles add up to {mine['naive_years']} years but cover "
                       f"{mine['merged_years']} calendar years.")
    with tabs[2]:
        snippet = st.text_area("A CV with a references block (made up, edit me)", key="br_refs", height=130,
                               value="\n".join(["Primary school coordinator 2018 - 2022. Plans timetables and school events.", "",
                                                "REFERENCES", "Dr A. Perera, Professor of Education and Founder of a training academy"]))
        with_r, without_r = detect_concepts(snippet), detect_concepts(strip_references(snippet))
        leaked = sorted(set(with_r) - set(without_r))
        names_ = {c: sc.concept_labels.get(c, c) for c in with_r}
        st.write("Strengths if the references are **read**: " + (", ".join(names_[c] for c in with_r) or "none"))
        st.write("Strengths if they are **ignored** (what we do): " + (", ".join(names_.get(c, c) for c in without_r) or "none"))
        if leaked:
            st.warning("Leaked in from the referee: " + ", ".join(names_[c] for c in leaked))
    with tabs[3]:
        p1, p2 = PL.profile_from_spec(spec, "v1"), PL.profile_from_spec(spec, "v2")
        s1, s2 = scorer("v1").score(p1), scorer("v2").score(p2)
        c1, c2 = D.lexicon_coverage(p1.cv_text, scorer("v1"), "v1"), D.lexicon_coverage(p2.cv_text, scorer("v2"), "v2")
        x, y = st.columns(2)
        for col, name_, cov_ in ((x, "Version 1", c1), (y, "Version 2", c2)):
            with col:
                st.markdown(f"**{name_}** understands")
                dd = pd.DataFrame([("Recognised", cov_["recognised_pct"]), ("Not recognised", round(100 - cov_["recognised_pct"], 1))], columns=["field", "pct"])
                viz.show_donut(dd, count="pct", center=f"{cov_['recognised_pct']:.0f}%", value_fmt="{:.0f}%", key="br_cov_" + name_)
        mv = D.rank_movers(s1, s2, top=12)
        if (mv.move != 0).any():
            st.write("**What changed in the ranking** (version 1 to version 2):")
            viz.show(viz.dumbbell(mv, "Version 1", "Version 2"), mv, key="br_lex")
        else:
            st.info("For this person the two versions rank the top areas the same. Try someone with a learning, consulting or media career.")
        if c1["blind_spots"]:
            st.caption("Words version 1 ignored here: " + ", ".join(f"{w} ({n})" for w, n in c1["blind_spots"][:8]))
    with tabs[4]:
        opts = PL.interest_options()
        pid = st.selectbox("A passion with nothing on the CV", list(opts), index=list(opts).index("music_arts"),
                           format_func=lambda k: opts[k], key="br_hobby")
        pp = D.with_interests(p0, [pid])
        s_avg, s_fin = sc.score(pp, formula="average"), sc.score(pp, formula="final")
        top_area = base_top = sc.score(p0).iloc[0]
        a_v = float(s_avg[s_avg.name == base_top["name"]].score.iloc[0])
        f_v = float(s_fin[s_fin.name == base_top["name"]].score.iloc[0])
        st.write(f"The best CV area, **{base_top['name']}**, scores {base_top.score:.0f}% with no passion, "
                 f"**{a_v:.0f}%** when we average, and **{f_v:.0f}%** with either-or.")
        x, y = st.columns(2)
        with x:
            st.markdown("**Averaging (what we tried)**")
            st.altair_chart(viz._style(viz.ranked_bars(s_avg, n_top=8, n_context=0)), use_container_width=True, theme=None)
        with y:
            st.markdown("**Either-or (what we use)**")
            st.altair_chart(viz._style(viz.ranked_bars(s_fin, n_top=8, n_context=0)), use_container_width=True, theme=None)
        how_to_read("with averaging every score shrinks. With either-or the CV areas stay put and the passion can only add.")
    with tabs[5]:
        eff = D.personality_effect(p0, sc)
        if not p0.personality:
            st.info("This person has no personality report, so there is nothing to compare.")
        else:
            st.markdown(("✅ **The same ten areas** are in the top 10 with or without working style."
                         if eff["same_members"] else
                         f"The list changed: in {', '.join(eff['entering']) or 'nothing'}, out {', '.join(eff['leaving']) or 'nothing'}."))
            mv = D.rank_movers(eff["off"], eff["on"], top=12)
            if (mv.move != 0).any():
                viz.show(viz.dumbbell(mv, "Ignoring working style", "With working style"), mv, key="br_pers")
                how_to_read("only neighbouring places swap. Working style cannot lift an area the CV does not support.")
    with tabs[6]:
        nd = D.near_duplicates(base, sc)
        nd["pair"] = nd.area_a + "  +  " + nd.area_b
        nd["similarity %"] = (nd.similarity * 100).round(0)
        viz.show(viz.simple_bars(nd, "pair", "similarity %", highlight={nd.pair.iloc[0]}, fmt=".0f", domain=[0, 100]), nd, key="br_dups",
                 table_cols=["pair", "similarity %"])
        how_to_read("100% would be the same area. Pairs above about 75% are near-copies.")
        dv = D.diversity_table(base, sc)
        dv["enters"] = dv.enters.map(lambda x: ", ".join(x) or "-")
        dv["leaves"] = dv.leaves.map(lambda x: ", ".join(x) or "-")
        st.dataframe(dv.rename(columns={"diversity": "Variety setting", "fields": "Fields in top 10", "enters": "Comes in", "leaves": "Drops out"}),
                     hide_index=True, width="stretch")
        st.caption("More variety swaps near-copies for areas with weaker CV evidence. How much is a decision for the consultant.")


st.header("What broke and what it taught", anchor="broke")
st.write("Seven things went wrong on the way. Each one is reproduced live below, on the person chosen at the top.")
broke(spec, lex)

# ------------------------------------------------------------------------------------------------ 8. accuracy
st.header("How accurate is it?", anchor="accuracy")
fbs = [v for k, v in st.session_state.items() if k.startswith("fb_") and not k.endswith("_v") and isinstance(v, pd.DataFrame)]
rated = pd.concat([f[f.accuracy.notna()] for f in fbs]) if fbs else pd.DataFrame()
if rated.empty:
    st.info("Nobody has rated the map yet, so there is no accuracy to show, and we will not invent any. "
            "Testers rate each area 1 to 5 in the **Test bench** (tab 6). Their ratings appear here as a chart "
            "centred on the middle, with red for 'inaccurate', blue for 'accurate', and our 90% target.")
else:
    rated = rated.assign(accuracy=rated.accuracy.astype(int))
    rated["band"] = pd.cut(rated.match_score, [-1, 30, 50, 70, 101], labels=["Under 30", "30 to 50", "50 to 70", "70 and over"])
    counts = rated.groupby(["band", "accuracy"], observed=True).size().unstack(fill_value=0).reindex(columns=[1, 2, 3, 4, 5], fill_value=0)
    counts = counts.reset_index().rename(columns={"band": "band"})
    counts["band"] = counts["band"].astype(str)
    pct = 100 * (rated.accuracy >= 4).mean()
    st.write(f"**{pct:.0f}%** of {len(rated)} ratings say accurate or highly accurate. Our target is 90%.")
    viz.show(viz.diverging_stack(counts, "band"), counts, key="acc")
    how_to_read("each bar is a score band, centred on 'partly accurate'. More blue to the right is better.")

# ------------------------------------------------------------------------------------------------ 9. findings
st.header("Findings, limits and what is next", anchor="findings")
x, y = st.columns(2)
with x:
    st.subheader("What we can say")
    st.markdown("- The idea works end to end: read a CV and a personality report, score every area, run the "
                "'too generous' check, shortlist, narrow, and explain every number.\n"
                "- The check caught a real flaw in our first formula.\n"
                "- A stated passion can surface an area the CV never mentions.\n"
                "- Version 2 of the keyword list brought a missed career into view without changing a second, very "
                "different CV's top 10 (measured locally on two real CVs).")
with y:
    st.subheader("What we cannot say yet")
    st.markdown("- That any of it is **accurate**. No tester has rated it, so the 90% target is untested.\n"
                "- That the keyword list works for everyone. It was tuned after seeing a few CVs.\n"
                "- That personality adds value. So far it only swaps neighbouring places.\n"
                "- Anything about Sri Lanka's job market.")
st.subheader("Known limits")
st.dataframe(pd.DataFrame(F.LIMITATIONS, columns=["Limit", "What it means"]), hide_index=True, width="stretch")
st.subheader("Decisions we made, and the alternative we turned down")
st.dataframe(pd.DataFrame(F.DECISIONS, columns=["No", "We chose", "Instead of", "Because"]), hide_index=True, width="stretch")
st.subheader("Next steps")
st.markdown("\n".join(f"{i}. {s}" for i, s in enumerate(F.NEXT_STEPS, 1)))

# ------------------------------------------------------------------------------------------------ 10. export
st.header("Take it with you", anchor="export")
top10 = narrowing.final_top(narrowing.apply_ratings(narrowing.shortlist(base), {}), k=10).head(10)
lines = [f"# Career exploration overview: {spec['name']}", "", f"> {report.CONFIDENTIAL}", "", "## At a glance",
         f"- Strongest direction: {hl['field']} ({hl['n_in_field']} of the top 10)",
         f"- Best single match: {hl['top_area']} ({hl['top_score']:.0f}%)"] + [f"- {c['title']}: {c['text']}" for c in hl["cards"]]
lines += ["", "## Top 10 career areas"] + [f"{i}. {r['name']} ({r.score:.0f}%): {r.why_cv}" for i, r in top10.iterrows()]
lines += ["", "## What broke and what it taught"] + [f"- {w[1]}. {w[4]}" for w in F.WHAT_BROKE]
lines += ["", "## Known limits"] + [f"- {a}: {b}" for a, b in F.LIMITATIONS]
lines += ["", "## Next steps"] + [f"{i}. {s}" for i, s in enumerate(F.NEXT_STEPS, 1)]
st.warning("This summary contains personal information from this session. Share it only with the person it is about and the project team.")
st.download_button("Download a summary (Markdown)", "\n".join(lines), file_name="career_overview.md")

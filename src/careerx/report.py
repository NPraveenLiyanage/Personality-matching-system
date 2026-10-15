"""Plain-text (Markdown) Career Exploration Report for one participant."""
from __future__ import annotations

from datetime import date

import pandas as pd

from .narrowing import reason_text
from .profile import DIM_NAMES, Profile

CONFIDENTIAL = ("CONFIDENTIAL. This report is built from the participant's own CV and personality profile, "
                "for their self-exploration only. It must not be used for selection, promotion or any decision "
                "affecting employment.")


def build_markdown(profile: Profile, top: pd.DataFrame, scores: pd.DataFrame, gate: dict) -> str:
    L = []
    L.append(f"# Career Exploration Report: {profile.name}")
    L.append(f"_Generated {date.today():%d %B %Y} - Phase 1 research prototype_\n")
    L.append(f"> {CONFIDENTIAL}\n")
    L.append("## About this report")
    L.append("These are **career areas** (fields of work), not job titles. Every area comes from the ISCO-08 "
             f"occupation classification; {gate['n_areas']} areas were scored against your CV, your PersonaMap "
             "work-style profile and your stated interests (if you gave any), and the ten below are the "
             "strongest matches. Several areas overlap, so read them as a few directions rather than ten "
             "separate ones. Treat them as questions to explore, not conclusions.\n")
    L.append("## Your profile in brief")
    L.append(f"- Education level used: skill band {profile.education_band} ({profile.education_note})")
    L.append(f"- Experience: about {profile.years_experience:g} years")
    if profile.personality:
        bits = [f"{DIM_NAMES[d]} {profile.personality[d]:.0f}%" for d in "ENFJ"]
        L.append(f"- Work style (PersonaMap {profile.personality_code or ''}): " + ", ".join(bits))
    if profile.interests:
        L.append("- Stated interests: " + ", ".join(sorted(profile.interests)))
    else:
        L.append("- Stated interests: none provided yet, so interests did not influence the match")
    L.append("")
    L.append("## Your top 10 career areas")
    for _, r in top.iterrows():
        L.append(f"### {int(r.final_rank)}. {r['name']}  ({r.score:.0f}% match)")
        L.append(f"*Field: {r.cluster}*  ")
        if r.get("why_cv"):
            L.append(f"- **Why it fits (CV):** {r.why_cv}")
        if r.get("why_personality"):
            L.append(f"- **Work style:** {r.why_personality}")
        if r.get("reason"):
            L.append(f"- **What you told us:** {r.reason}")
        if r.get("missing"):
            L.append(f"- **Common in this area, not yet on your CV:** {r.missing}")
        L.append(f"- **Level:** {r.why_readiness}")
        ex = r.get("examples") or []
        if ex:
            L.append(f"- **Example roles:** {', '.join(ex[:6])}")
        L.append("- **Next step:** study path / professional path (to be linked in Phase 2)\n")
    L.append("## How reliable is this?")
    L.append(f"- {gate['n_suitable_text']}" if "n_suitable_text" in gate else
             f"- {gate['n_high'] + gate['n_moderate']} of {gate['n_areas']} areas scored as suitable "
             f"({gate['share_suitable']:.0%}); selectivity check: {'passed' if gate['passed'] else 'FAILED'}.")
    L.append("- The scoring is rule-based and has not yet been validated against participants' own judgement; "
             "your accuracy ratings in the feedback form are what will refine it.")
    return "\n".join(L)

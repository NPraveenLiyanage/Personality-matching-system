"""Shared UI pieces: the in-session participants store and the 'add a participant' form.

Privacy by construction: participants live only in `st.session_state` (server memory for this browser session).
Nothing is written to disk, logged, cached with st.cache, or bundled with the app. The three built-in people are
made up (data/demo). Real CVs and PersonaMap reports only arrive through the upload form below.
"""
from __future__ import annotations

import hashlib
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import streamlit as st

from careerx import pipeline as PL
from careerx.lexicon import DEFAULT_LEXICON, LEXICON_LABELS
from careerx.profile import DIM_NAMES, extract_pdf_text, parse_personamap

EDU_OPTIONS = {3: "Degree level (ISCO skill levels 3-4)", 2: "Diploma / vocational / A-level (skill level 2)",
               1: "School level (skill level 1)"}
MAX_PARTICIPANTS = 8


def sig_of(*parts) -> str:
    return hashlib.md5(repr(parts).encode()).hexdigest()[:10]


@st.cache_resource(show_spinner=False)
def scorer(lexicon: str = "v2"):
    """Shared, read-only scorer (public ISCO data only; never mutated, so sessions cannot affect each other)."""
    return PL.get_scorer(lexicon)


# ---------------------------------------------------------------------------------- store
def store() -> dict[str, dict]:
    new = st.session_state.pop("_new_pick", None)        # select a just-added participant before the pickers draw
    if new:
        for k in ("bench_pick", "ov_pick"):
            st.session_state[k] = new
    if "participants" not in st.session_state:
        st.session_state["participants"] = {s["id"]: s for s in PL.demo_specs()}
    return st.session_state["participants"]


def label(spec: dict) -> str:
    return spec["name"] + ("" if spec.get("demo") else "  (yours)")


def clear_added() -> None:
    st.session_state["participants"] = {k: v for k, v in store().items() if v.get("demo")}


def _pdf_text(uploaded) -> tuple[str, str | None]:
    try:
        text = extract_pdf_text(uploaded.getvalue())
    except Exception:                                          # corrupt or encrypted file
        return "", "That file could not be opened as a PDF."
    if len(text.strip()) < 40:
        return "", "That PDF has no readable text (it may be a scan). Paste the text instead."
    return text, None


def participants_panel(key: str = "pp", expanded: bool = False) -> None:
    """Add real participants (upload or paste) and manage the list. Held in this session only."""
    st.caption("Held in this browser session only. Nothing is saved, logged or shared, and it is gone when you close the page.")
    msg = st.session_state.pop("_pp_msg", None)
    if msg:
        getattr(st, msg[0])(msg[1])
    with st.expander("Add a participant (CV + personality report)", expanded=expanded):
        with st.form(f"{key}_form", clear_on_submit=True):
            name = st.text_input("Name or code", placeholder="e.g. Tester 1")
            cvf = st.file_uploader("CV (PDF)", type="pdf", key=f"{key}_cv")
            cv_paste = st.text_area("...or paste the CV text", height=110)
            pmf = st.file_uploader("PersonaMap report (PDF, optional)", type="pdf", key=f"{key}_pm")
            st.caption("No report? Set the four preferences by hand (percent toward the first word):")
            c = st.columns(4)
            manual = {d: c[i].slider(DIM_NAMES[d], 0, 100, 50, key=f"{key}_{d}") for i, d in enumerate("ENFJ")}
            go = st.form_submit_button("Add participant")
        if go:
            cv, err = ("", None)
            if cvf is not None:
                cv, err = _pdf_text(cvf)
            elif cv_paste.strip():
                cv = cv_paste
            pm_text = None
            if pmf is not None:
                pm_text, perr = _pdf_text(pmf)
                err = err or perr
            if err:
                st.error(err)
            elif not cv.strip():
                st.error("Add a CV first: upload a PDF or paste the text.")
            elif len(store()) >= MAX_PARTICIPANTS:
                st.error(f"At most {MAX_PARTICIPANTS} participants at a time. Remove one first.")
            else:
                parsed = parse_personamap(pm_text) if pm_text else None
                sid = "p_" + uuid.uuid4().hex[:6]
                store()[sid] = dict(id=sid, name=(name.strip() or f"Participant {len(store()) + 1}"), cv_text=cv,
                                    pm_text=pm_text if parsed else None,
                                    personality=None if parsed else manual, demo=False, ref_date=None)
                if pm_text and not parsed:
                    msg = ("warning", "Added, but the PersonaMap report could not be read, so the sliders (default 50%) were used.")
                elif parsed and len(parsed["found"]) < 4:
                    miss = ", ".join(DIM_NAMES[d] for d in "ENFJ" if d not in parsed["found"])
                    msg = ("warning", f"Added, but the report had no readable value for: {miss}. Those show as 50%.")
                else:
                    msg = ("success", "Added and selected below.")
                st.session_state["_pp_msg"] = msg
                st.session_state["_new_pick"] = sid
                st.rerun()
    added = [s for s in store().values() if not s.get("demo")]
    if added:
        st.write("Your participants: " + ", ".join(s["name"] for s in added))
        if st.button("Remove all participants I added", key=f"{key}_clear"):
            clear_added()
            st.rerun()


def lexicon_choice(key: str = "lex") -> str:
    opts = list(LEXICON_LABELS)
    return st.radio("Keyword list", opts, index=opts.index(DEFAULT_LEXICON), format_func=lambda k: LEXICON_LABELS[k],
                    key=key, help="v1 is the first version. v2 adds categories v1 could not see at all.")

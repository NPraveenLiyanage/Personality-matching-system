"""Career Exploration: router.

Run:  streamlit run app/streamlit_app.py

Landing page = the evidence-first PILOT (recorded examples, plus a live mode on invented text). Other pages: the Overview
report (live charts you can play with) and the Test bench (the step-by-step tool a tester uses). This file stays the app's
entry point so a deployment does not need changing.
"""
import streamlit as st

st.set_page_config(page_title="Career Exploration", page_icon="🧭", layout="wide")

pages = [
    st.Page("pages/pilot.py", title="Evidence-first pilot", icon="🔬", default=True),
    st.Page("pages/evidence_bench.py", title="Evidence test bench", icon="🧭"),
    st.Page("pages/overview.py", title="Overview report", icon="📊"),
    st.Page("pages/bench.py", title="Test bench", icon="🧪"),
]
st.navigation(pages).run()

# Career Exploration Engine: Phase 1

From a participant's **CV + PersonaMap report (+ interests intake)** to a short, explainable **Top 10 list of
career areas**, built on the ISCO-08 occupation classification. Internal research prototype for the
principal consultant's validation rounds.

## What is here

| Path | What it is |
|---|---|
| `notebooks/01_career_exploration_phase1.ipynb` | **The process record**: every step, decision, failed attempt and finding. Start here. |
| `app/streamlit_app.py` | **Test app**: profile → full map & selectivity gate → shortlist → narrowing → Top 10 → tester feedback form |
| `src/careerx/` | The engine (see below) |
| `tests/test_pipeline.py` | 10 checks that mirror the plan's verification list |
| `data/raw/` | Inputs: two ISCO workbooks, the transcript, and the sample participant's CV / PersonaMap |
| `data/processed/career_area_catalogue.csv` | The numbered catalogue of 94 career areas |
| `outputs/` | Full map, feedback form and model-only Top 10 for the sample participant |

## Run it

```bash
pip install -r requirements.txt
python tests/test_pipeline.py                 # verification
streamlit run app/streamlit_app.py            # test app
python notebooks/build_notebook.py            # regenerate + execute the notebook
```

## How it works (one paragraph)

ISCO-08's 127 in-scope minor groups are merged across skill levels and renamed to field nouns, plus 9
clearly flagged "lens" areas (data science, AI/ML, UX, IoT, ...) → **94 career areas in 9 field clusters**.
Every area is scored 0-100 for a participant: `relevance (CV evidence OR stated interests) × work-style
modifier (PersonaMap) × readiness (education vs ISCO skill band)`. A **selectivity gate** fails the map if
more than 25% of areas look "suitable". The participant then sees two short lists, picks fields, reacts
like/maybe/no with a reason, takes a few forced choices, and gets a Top 10. Testers separately rate the full
numbered map 1-5 with a required comment unless "highly accurate".

## Engine modules (`src/careerx/`)

| Module | Role |
|---|---|
| `isco.py` | Load structure/definitions and the skill-level workbook |
| `catalogue.py` | Merge / rename / lens rules → the Career Area Catalogue |
| `lexicon.py` | Editable concept lexicon (CV phrases ↔ ISCO vocabulary) and work-style cues |
| `profile.py` | CV concept evidence, PersonaMap parsing, education & experience |
| `scoring.py` | Transparent scorer, explanations, selectivity gate |
| `narrowing.py` | Shortlist, wildcards, reactions, duels, diversity-aware Top 10 |
| `feedback.py` | Numbered feedback form and validation summary |
| `report.py` | Markdown Career Exploration Report |

## Status and caveats

* One participant has been run; **no human validation has happened yet**. The 90% accuracy target is untested.
* The lexicon was adjusted after looking at the sample CV, so the other testers are the real test.
* For the sample participant, personality only swaps neighbouring ranks and never changed Top-10
  membership; its value is unproven (notebook §9).
* ISCO-08 predates several modern fields; lens-area supplement text is explicit and should be reviewed.
* No interests intake has been collected for the sample participant yet. The PersonaMap report's
  leadership-style section is present but **not yet used by the engine**.
* Phase 2 (vacancies, employer outreach, apply flow) is intentionally **not built**.

## Data protection

`data/raw/` holds a real CV and a confidential PersonaMap report. Keep this folder private. PersonaMap
output is for the participant's own exploration and **must not be used for selection decisions**, as
the report itself states; do not pass it to employers in Phase 2.

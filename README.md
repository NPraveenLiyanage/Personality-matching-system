# Career Exploration Engine: Phase 1

From a participant's **CV + personality report (+ interests)** to a short, explainable **Top 10 list of career
areas**, built on the ISCO-08 occupation classification. Internal research prototype for the principal
consultant's validation rounds.

## Run it

```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py        # opens the Overview report; "Test bench" is in the sidebar
python tests/test_pipeline.py             # 20 checks
```

## What is in the app

| Page | For whom | What it is |
|---|---|---|
| **Overview report** (landing page) | Anyone, including non-technical readers | What we built and what we found, as live charts you can play with: at a glance, why not match every job, the catalogue, who the person is, a what-if playground, comparing people, what broke and what it taught, accuracy, findings and next steps |
| **Test bench** | Testers | The step-by-step tool: profile, full map, shortlist, narrowing, Top 10, accuracy feedback form |

Both pages work on whoever you choose. Three **made-up demo people** are built in. Real CVs and personality reports are
added during the session (upload a PDF or paste text) and are held **in that browser session's memory only**.

## Real data is never stored

* Nothing real is bundled with the app or committed: `data/demo/` holds made-up people only.
* Real participants enter only through the upload form, and disappear when the session ends.
* For local work, real files live in `private_data/`, which is **git-ignored** (as are `outputs/` and the process notebook,
  because they contain results from real documents). A test fails if a PDF, `private_data/` or a notebook is tracked.
* A personality report is confidential to its owner and **must not be used for selection decisions**.

## How it works (one paragraph)

ISCO-08's 127 in-scope minor groups are merged across skill levels and renamed to field nouns, plus 9 clearly flagged
extra modern areas (data science, AI/ML, UX, ...) → **94 career areas in 9 fields**. Every area is scored 0-100:
`relevance (CV evidence OR stated interests) × working-style modifier (personality) × level fit (education vs ISCO skill band)`.
A **"is the map too generous?" check** fails the map if more than 25% of areas look suitable. A person then sees two short lists,
picks fields, reacts like/maybe/no, takes a few forced choices, and gets a Top 10. Testers separately rate the full numbered map
1-5 with a comment required unless "highly accurate". No machine learning: the scoring is rule-based and every number traces back
to a CV phrase, a report percentage or a line of ISCO text.

## LLM match (experimental, test bench tab 7)

`src/careerx/llm/` runs the Calybrate career-area prompt (`prompt_v1.md`) on a free OpenRouter model
(default `nvidia/nemotron-3-super-120b-a12b:free`, fallbacks `google/gemma-4-31b-it:free`, `openrouter/free`), 3 runs at
temperature 0, validates quotes and ids, takes the median and computes `final = cv x style x level`. Copy `.env.example` to
`.env` and set `OPENROUTER_API_KEY`. CV text leaves the machine (identifiers removed) and free models may log prompts, so the
tab asks for the participant's agreement. Tests: `python tests/test_llm.py` (offline; live check runs when a key is set).

## Folders

| Path | What |
|---|---|
| `app/streamlit_app.py` | Router (entry point) |
| `app/pages/overview.py`, `app/pages/bench.py` | The two pages |
| `app/viz.py`, `app/common.py` | Chart kit (validated palette, light and dark) and the in-session participants store |
| `src/careerx/` | The engine: `isco`, `catalogue`, `lexicon` (keyword list v1 and v2), `profile`, `scoring`, `narrowing`, `feedback`, `diagnostics`, `insights`, `findings`, `report`, `pipeline` |
| `data/raw/` | The two ISCO workbooks (public data) |
| `data/demo/` | Made-up demo people |
| `data/processed/career_area_catalogue.csv` | The numbered catalogue of 94 areas |
| `notebooks/build_notebook.py` | Builds the process notebook from local real documents (output is git-ignored) |
| `tests/test_pipeline.py` | Checks, including the privacy check |

## Status and caveats

* **No human validation yet.** The 90% accuracy target is untested.
* The keyword list was adjusted after looking at a few CVs; v2 added categories v1 could not see. Other testers are the real test.
* The catalogue is finer in technology than elsewhere, which can inflate technology in a technical person's top 10.
* Personality has so far only swapped neighbouring places in a top 10; its value is unproven.
* The personality report's leadership-style section is present but **not yet used by the engine**.
* Phase 2 (vacancies, employer outreach, applying) is intentionally **not built**.

## Open decisions

* Make the GitHub repository private, and whether to remove real files from its **git history** (they were published before
  this cleanup and stay in history until rewritten with a force-push).
* Catalogue changes: split engineering and sciences, move chefs, sports placement, how to treat managers, stable area IDs.
* How the personality report's leadership section should feed the match.

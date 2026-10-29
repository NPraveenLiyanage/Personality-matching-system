# Independent review guide

Purpose: the project's expected outcomes, career-area definitions and regulated-occupation term lists were written or drafted by the project team and an AI model. Nothing has been independently checked. A reviewer (ideally a career-guidance practitioner, not the author) fills the sheets in `docs/review/`. Open them in Excel; they contain only invented CVs and public catalogue text. Estimated time: 2-3 hours for all four sheets.

| Order | File (docs/review/) | What to do | Time |
|---|---|---|---|
| 1 | `4_rubric_calibration_pairs.csv` | For each of 10 short invented CV snippets, choose one class for the career area named (classes defined in `docs/RUBRIC.md` section 3: direct, transferable, domain_exposure_only, interest_only, unsupported, insufficient_info). Do this FIRST and do not open the answer key. | 15 min |
| 2 | `1_case_expectations_review.csv` | For each of 34 invented CVs, say whether the areas marked "should be recommended" are right, what to add or remove, and whether the "must not be recommended as supported" list is right. | 60-90 min |
| 3 | `2_area_definitions_review.csv` | Check the 94 AI-drafted definitions, example evidence, confusions and qualification requirements. Mark yes / edit / wrong and give corrected wording. | 60-90 min |
| 4 | `3_regulated_terms_review.csv` | For the 17 occupations that need formal qualifications or registration, say which role or qualification words should count as genuine practice. | 15 min |
| after 1 | `answer_key_do_not_open_first.csv` | Compare with the project's own labels and note where you differ. Disagreements are discussed and the rubric is refined. | 10 min |

## Ground rules for the reviewer
- Judge only what the text says the person personally did or holds. Industry alone is not experience (building software for a hospital is not nursing).
- This is career exploration. Do not judge hiring suitability, ability or performance.
- Use "should be recommended" for areas a careful adviser would put in a short list from this text alone. "Also acceptable" areas are reasonable but not required.
- Write comments freely; they are more useful than a perfect form.

## What happens with the results
The project owner enters corrections into `bench/cases/*.yaml`, `data/processed/area_definitions_v1.yaml` and `data/processed/regulated_areas_v1.yaml`, records the reviewer and date, and re-freezes the baselines. Agreement between the reviewer and the author on the calibration pairs is reported. Until this is done, all benchmark numbers are labelled as "against author-written expectations".

## Two independent raters (later)
The brief asks for two independent raters on a shared subset of about 20 cases. These sheets are the starting point: give the same sheet 1 and 4 to two reviewers and compare.

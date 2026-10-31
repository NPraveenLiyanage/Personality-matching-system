# Reviewer brief: career-area review of invented CVs (draft, 2026-10-31; no reviewer recruited yet)

**Purpose of this note:** to invite a career-guidance or occupational specialist to review a research prototype. It can be sent as written once the owner has chosen the reviewer and agreed any terms.

## 1. The project in plain words
We are testing a prototype that reads a CV and suggests career areas to explore, out of a fixed list of 94. It is built for **career exploration only**. It does not select, rank or judge people for jobs, and it makes no claim about competence or eligibility.

The prototype is designed to avoid two mistakes: recommending a field because of the *industry* a person worked in (software written for a hospital is not nursing), and treating an *unfinished degree* as professional experience. We need an independent expert to tell us whether our expected answers are sensible. At present only the project team, helped by AI tools, has judged them.

## 2. What we ask of you
Review **invented CVs** (no real person's data) and, for each one:
1. List the areas where the CV shows the person has actually **done the work** (`supported`).
2. List areas worth exploring from **study or interest only** (`exploration_only`).
3. List areas that **must not** be recommended as supported (`must_not_be_supported`).
4. Add a confidence (high / medium / low) and a short comment where the CV is ambiguous or the area boundaries are unclear.

Rules to apply: industry is not profession; study in progress is exploration, not work experience; a claimed regulated role (doctor, nurse, lawyer, etc.) is a self-report and registration is never assumed.

## 3. What you receive
- `docs/review/blind_review_pack_cases_v1.csv`: 62 invented CVs with empty reviewer columns.
- `docs/review/area_catalogue_for_reviewers.csv`: the 94 area IDs and names.
- Area descriptions: `data/processed/area_definitions_v3.yaml` (reference).
- You do **not** receive our expected answers or any model output until you have finished, so your judgments stay independent. Comparison comes afterwards.

## 4. Who we are looking for
- Career guidance practitioner, occupational analyst or HR/occupational-classification specialist; ideally familiar with ISCO-08 or a national equivalent. Familiarity with Sri Lankan occupations (SLSCO, TVEC, SLMC and similar) is a plus but not required.
- **One or two independent reviewers**, working separately. Disagreements go to an adjudication step; we do not average them.

## 5. Time and recognition (to be filled by the owner)
- Estimated effort: to be measured on a 5-case trial; not yet known.
- Compensation / acknowledgement: **owner to decide** (✏️ _______). No budget is approved for this in the project documents.
- Deadline: ✏️ _______.

## 6. Data, consent and credit
- All CVs are invented by the project team; none is a real person. No personal data is exchanged.
- Your review will be recorded with your role, expertise and date, and kept as part of the project's evidence. Tell us if you would rather be credited by role only.
- Your judgments will be used to correct our expected answers and to report how far the prototype agrees with an independent expert. They will not be used to train a model unless you agree in writing.

## 7. What your review will and will not show
It will show whether our labels and area boundaries are reasonable on invented cases. It does **not** validate the prototype on real CVs; that needs separate consent and a second step (Phase 5, with two independent raters on a larger set).

## 8. For the project owner before sending
- [ ] Choose reviewer(s) and agree compensation and deadline (section 5).
- [ ] Confirm that the `author_key_do_not_open_before_review_cases_v1.csv` file is **not** in what you send.
- [ ] Decide whether to add a 5-case trial first to measure effort.
- [ ] Record reviewer identity and date in `docs/PROJECT_REVIEW.md` when the review is returned; do not mark a gate passed until then.

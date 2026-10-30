# Blind review pack for human domain reviewers (prepared 2026-10-30; NOT yet reviewed by anyone)

**Status: unreviewed.** Nothing here means any Phase 0/1/2/5 gate has passed. AI-assisted desk reviews exist (see `docs/PROJECT_REVIEW.md`), but they are not a human domain-specialist review.

**Files**
- `blind_review_pack_cases_v1.csv`: 62 invented CVs (sets `synth_dev_v1`, `swap_v1`, `synth_dev_v2`, `holdout_v4`) with empty reviewer columns. Give this to the reviewer.
- `area_catalogue_for_reviewers.csv`: the 94 career-area IDs and names (frozen `catalogue_v1`). Give this too; area descriptions are in `docs/review/` and `data/processed/area_definitions_v3.yaml`.
- `author_key_do_not_open_before_review_cases_v1.csv`: the author's expected labels. **Keep this from the reviewer until they have finished**, so their judgments are independent. Compare afterwards.

**Instructions for the reviewer** (one or two reviewers, working separately)
1. For each CV, list the areas the CV shows the person has actually done the work of (`supported`), areas worth exploring from study or interest only (`exploration_only`), and areas that must not be recommended as supported (`must_not_be_supported`). Use area IDs. It is fine to leave a list empty.
2. Industry alone is not a profession: software for a hospital is not nursing. A degree in progress is education-based exploration, not work experience. A CV claim of a regulated role is a self-reported claim; do not treat registration as verified.
3. Give a confidence (high/medium/low) and a short comment where the CV text is ambiguous, or where the catalogue's area boundaries are unclear.
4. Do not look at model outputs or the author's key before finishing.

**Record for each reviewer:** name or ID, role and relevant expertise, date, and that the review was done blind. Disagreements between reviewers go to an adjudication step, not to an average.

The fixtures are invented, not copies of real CVs. Their task wording was paraphrased from public occupational references (`docs/SYNTHETIC_DATA_METHOD.md`).

# Synthetic CV fixtures: method, sources and licence notes (2026-10-30)

**Status: provisional.** All labels are author-written with AI assistance and are **not** reviewed by a human domain specialist. They are not ground truth and do not pass any review gate.

## Files
| File | Cases | Purpose |
|---|---|---|
| `bench/cases/career_cases_synth_v1.yaml` | 14 | From `docs/PROJECT_REVIEW.md` section 9b; development set |
| `bench/cases/career_cases_swap_v1.yaml` | 4 | Healthcare-app domain-swap diagnostic; development set |
| `bench/cases/career_cases_synth_v2.yaml` | 32 | Broad coverage fixtures (this document); development set; fingerprint of the file at creation `388f38810c48f5d4` |
| `bench/cases/career_cases_holdout_v4.yaml` | 12 | Frozen held-out set; already seen once (retired as fresh) |

Coverage of `synth_dev_v2`: 9 students or school leavers, 8 experienced workers or professionals, 5 career changers or old experience, 5 regulated occupations, 5 ambiguous, sparse or adversarial cases (prompt injection, exaggerated title, referee titles, explicit negation, skills list only).

## Generation method
1. Choose an occupation or situation, and the contrast it tests (for example mechanic vs driver, pharmacy assistant vs pharmacist, student vs practitioner, current vs older role).
2. Look up the occupation in public references and note typical **tasks**: ILO ISCO-08 unit-group descriptions, O*NET OnLine task lists, UK National Careers Service job profiles. Each case lists its references in `refs` (ISCO-08 code, O*NET code or NCS profile).
3. Write an **original** CV from scratch: invented name, employer, dates and first-person duties in plain words. No sentence is copied from a reference or from any real CV. Task statements are paraphrased and simplified.
4. Set the labels from the project's frozen catalogue (`catalogue_v1`, A001-A094): `supported`, `acceptable`, `exploration_only`, `traps`. The labels follow the rubric (`docs/RUBRIC.md`) and the owner rules: industry is not profession, in-progress study is exploration, team-only or unspecified contribution is not individual evidence, a regulated role is a self-reported claim.
5. Check mechanically: area IDs exist, label sets do not overlap, IDs are unique, the case file loads, the test suite passes.
6. Freeze: edit no expectation after seeing model output. Add a new version instead.

## Source and licence notes
- **ILO ISCO-08**: "available online free of charge and can be used without prior authorization" (ILO ISCO FAQ, https://isco.ilo.org/en/faq/). The page says nothing about attribution or redistribution, so we cite the code and write our own text.
- **O*NET OnLine**: content is CC BY 4.0 with exceptions for external sources; credit O*NET OnLine and USDOL/ETA, link the licence, and mark changes (https://www.onetonline.org/help/license). Our task wording is **changed**, so it must not be presented as approved or tested by USDOL/ETA. The licence page does not mention machine-learning training; ask the O*NET programme before using its data directly for training.
- **UK National Careers Service**: used to learn what an occupation does. No text is reproduced. UK licensing and qualification rules are not applied to Sri Lanka.
- **Sri Lankan regulators** (for example the Sri Lanka Medical Council): needed before any claim about legal eligibility. None of the fixtures asserts registration, and the tool never verifies it.

## Known limits
- The fixtures are short and tidy. Real CVs are longer, messier, multilingual and often PDFs. This set says nothing about those.
- Names and organisations are invented; any resemblance to a real person or organisation is coincidence. They carry Sri Lankan-style names but no real personal data.
- The author wrote both the CVs and the labels, so they share the same blind spots. Human blind review is needed (`docs/review/BLIND_REVIEW_PACK_README.md`).
- ISCO mapping of areas to occupations has not been cross-checked case by case against `career_area_catalogue.csv`; area boundaries (for example A010 vs A062, A056 vs A058) need reviewer judgment.

# Phase 3 results: evidence-first pipeline on the development cases (2026-10-27 to 2026-10-29)

Status: **gate not passed; evidence is mixed.** All numbers are against author-written, unreviewed expectations on 22 synthetic cases, one run per case, one free reasoning model (`nvidia/nemotron-3.5-super-vl:free`, provider `nvidia`, `data_collection: allow` because free endpoints require it; synthetic and public catalogue text only). Definitions and the regulated-term list are LLM-drafted and unreviewed.

## Protocol followed
- Trap definition and metrics (v2) fixed before any evidence-engine output; baselines re-scored under v2 with no change.
- Prompts, verifier and fixes were iterated on the 12 `tune` cases only. Pipeline then frozen (file hashes in each run's metadata) and the 10 `holdout` cases run once. The run was interrupted by low-memory kills three times; progress was kept by per-case checkpoints (`--resume`), and nothing was changed or looked at between attempts.
- After the holdout run I diagnosed its two empty cases (below) and made one fix. **The holdout split is therefore used and can no longer be an untouched test for the fixed pipeline.**

## Results by split (top shown; baselines always show 10 areas)
| | Rule engine | Direct LLM (Haiku 5.5, 1 run) | Evidence pipeline (free Nemotron) |
|---|---|---|---|
| **Tune** cases with a trap shown as supported | 7 / 8 | 5 / 8 | **0 / 8** (11 of 12 cases completed) |
| Tune supported areas found | 13 / 14 | 14 / 14 | 11 / 12 |
| **Holdout** cases with a trap shown as supported | 1 / 10 | 2 / 10 | **0 / 10** (10 of 10 completed) |
| Holdout supported areas found | 12 / 12 | 12 / 12 | **8 / 12** |
| Holdout cases with all authored areas found | 10 / 10 | 10 / 10 | 7 / 10 |
| Holdout top shown in authored ok set | 9 / 10 | 9 / 10 | 8 / 10 |
| Mean areas shown | 10.0 | 10.0 | 1.1 - 1.3 |
| Authored-ok share of areas shown (lower bound) | 0.30 - 0.36 | 0.42 - 0.46 | 0.86 - 1.0 |

## What this does and does not show
- **Domain confusion:** the evidence pipeline never showed a trap area as supported (0 of 18 trap cases across both splits). Healthcare, banking, legal and education areas appeared only as labelled exploration for the app-developer cases. The nurse, consultant physician, accountant, lawyer, teacher, electrician and career-changer kept their own areas.
- **But the holdout baselines were already good on trap avoidance** (1 and 2 of 10), so the holdout shows a small trap advantage, not a large one. Most of the baseline failures sit in the tune cases the pipeline was tuned on.
- **Recall is lower on holdout (8 of 12 vs 12 of 12)** and the pipeline shows far fewer areas. Fewer areas shown lowers the chance of a trap by itself, so the trap numbers are not a like-for-like win. The honest summary is higher precision and lower recall, not a clear improvement.
- Reliability: 1 of 22 cases returned invalid JSON on the first try in the tune run (a rerun worked). One re-ask path was built but never triggered live.

## Why holdout missed 4 areas (diagnosis, by stage)
- **c09 (disease-classifier student) and c18 (prompt-injection marketing assistant) returned nothing supported.** Cause is in extraction: the model quoted two adjacent bullets as one sentence without the "- " marker, the quote check rejected the record, and the assessor then had no evidence. The check behaved as designed (no unsupported quote passed) but cost recall. Fix made after seeing this: leading bullet markers are ignored when matching quotes, with a test that quotes still cannot span passages. This fix is untested live and was prompted by the holdout.
- **c16 (PLC ambiguity)** found Electrical installation (A075) but not Machinery mechanics (A072), and added two engineering areas as direct; the authored sets list A015 and A016 as acceptable, so only A072 counts as a miss. The "PLC" ambiguity was not flagged as an ambiguity in the assessed rows.
- c17 (Ayurvedic terms): marketing area shown, no medicine/traditional-medicine area shown even as exploration.

## Next steps
1. Fresh held-out cases in domains not used so far (agriculture, hospitality, construction, public sector, creative, sparse and poor-extraction CVs), written before the next run, and a second reviewer for all expected outcomes.
2. Re-run the fixed pipeline on tune; run the fresh holdout once.
3. Human review of the 94 area definitions and the regulated-term list.
4. Decide, with a reviewer, how many areas the product should show; the current pipeline's conservatism may need an explicit recall target.
5. Phase 4: compare models (paid models only if you approve), repeat-run agreement, cost.

## Addendum 2026-10-29: fresh held-out set v2 (12 cases, written after the first holdout was used; fixed pipeline, one run)
Run: `bench/runs/career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_holdout_v2_2026-10-29.json` (account 1, 12 of 12 completed). Rule engine on the same cases: `bench/runs/career_rule_holdout_v2_2026-10-29.json`. The direct AI prompt was not run (paid model).

| | Rule engine | Evidence pipeline |
|---|---|---|
| Trap cases with a trap shown as supported | 8 / 10 | **1 / 10** |
| Expected areas found | 8 / 11 | 8 / 11 |
| Top area in expected/acceptable set | 6 / 11 | 9 / 11 |
| Share of shown areas in the expected/acceptable set (lower bound) | 0.24 | 0.72 |
| Mean areas shown | 10 | 1.5 |
| Abstained on no-support cases | 0 / 3 | 2 / 3 |

The industry-swap triple (same developer; hospital, bank, school client) gave Software as the only supported area in all three. Failures and caveats are listed in `docs/PROJECT_REVIEW.md` section 2. One run per case; expectations unreviewed; the first live use of the targeted re-ask worked (v2_11).


## Tune re-run under the reviewer-based pipeline (2026-10-29, later; account 2, free Nemotron)
Changes: area_definitions_v2 (44 reviewer scope notes), regulated_areas_v2 (57 added words), assess_v2 prompt with the new in_progress_study class, in-progress-study rule in the verifier. Scored against cases v3 (reviewer expectations).
Tune split, 12 of 12 completed (c05 first truncated at the 60,000-token limit and was re-run from the checkpoint): trap cases 0/8, expected areas found 13/14, overclaims 0/9, mean areas shown 1.17, top area in expected set 11/11, abstained on the no-support case 1/1.
Caveats: tune cases were used to design these changes; expectations are the reviewer-based v3 ones (set after outputs were known); one run per case. NOT yet run: the fresh held-out set v3 (bench/cases/career_cases_holdout_v3.yaml, 12 cases, expectations fixed before any run). Run it once, after account 1's free quota resets, with --definitions data/processed/area_definitions_v2.yaml --regulated data/processed/regulated_areas_v2.yaml --label pipe2.

## Fresh held-out set v3: first and only run (2026-10-29, account 2, free Nemotron, pipeline v2 frozen before the run)
Expectations in `bench/cases/career_cases_holdout_v3.yaml` were written before any run; one run per case; no change was made after seeing output.
**9 of 12 cases completed; 3 FAILED and are recorded as failures (no substitute):** v3_04 heavy-truck driver (extraction: response not valid JSON), v3_08 bus-depot mechanical technician (extraction: not valid JSON), v3_11 law-firm legal secretary (assessment: not valid JSON). The three non-degree/technical cases are the ones missing, so these results say nothing about them.
On the 9 completed cases: trap cases shown as supported 0/9 (3 cases showed a trap area only as labelled exploration), expected areas found 7/7, overclaims 0/5, mean areas shown 1.11, top area in the expected set 7/9, abstained on the 2 no-support cases (nursing student, school leaver wanting to be a doctor).
Caveats: 25% of runs failed, so reliability is a real problem on the free model; 9 cases is small; expectations are author-written and not independently reviewed; the pipeline design was informed by earlier sets, though not by these cases. The old rule-engine and direct-prompt baselines have not been run on this set (direct needs a paid model).
Not done: retry of the 3 failed cases (would use free quota and is a second attempt, so it must be reported as a retry); decision pending with the user.
Run file: `bench/runs/career_llm_evidence_nvidia_nemotron-3.5-super-vl_free_holdout_v3_pipe2_2026-10-29.json`.

### Update: v3 held-out set after retrying the 3 failures (2026-10-29)
First attempt: 9 of 12 completed, 3 failed (saved as `..._pipe2_2026-10-29_attempt1.json`). Retry, with no change to the pipeline: v3_04 completed on account 2; v3_08 and v3_11 hit HTTP 429 on account 2 and completed on account 1 (`..._attempt2.json` holds the intermediate state). **v3_04, v3_08 and v3_11 are second-attempt results, not clean first runs.**
Final, 12 of 12 completed: trap cases shown as supported 0/12 (4 showed a trap only as labelled exploration), expected areas found 10/10, overclaims 0/6, mean areas shown 1.33, top area in the expected set 10/12, abstained on the 2 no-support cases 2/2. Caveats unchanged: author-written unreviewed expectations, small n, free model with a 25% first-attempt failure rate, no baselines run on this set.

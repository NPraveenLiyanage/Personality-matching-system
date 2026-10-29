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

# Phase 2 results: evidence extraction, first live runs (2026-10-27)

Status: **gate not passed.** These are two runs of one model on 10 synthetic cases, read by one person (the case author). They show the extractor works end to end and expose specific weaknesses. They are not an accuracy measurement.

## Setup (recorded for reproducibility)
- Model `anthropic/claude-haiku-5.5`, provider pinned to `anthropic`, `allow_fallbacks:false`, `data_collection:deny`, `require_parameters:true`, strict `json_schema`, price ceiling $1.0/M tokens.
- Prompt `extract_v1`, schema `evidence_v1`, catalogue not involved. Synthetic text only.
- **Zero-data-retention routing was off.** With `zdr:true` the request failed (HTTP 404, no endpoint matched on this account), so no data policy was relaxed silently. ZDR is not required for synthetic text; it must be re-checked before any real data is sent.
- **Temperature is not sent.** The model rejects the parameter; with `require_parameters:true` the request 404s. Output is therefore not deterministic, and repeat-run differences below are real.
- Cost: about 28k input and 20-24k output tokens per 10-case run (roughly $0.01-0.02); 97-118 s per run of 10 cases.
- Endpoint data policy (retention/training) is not exposed by the OpenRouter endpoint listing; privacy relies on the request flags and the provider's own terms, which are unverified.

## What the first run showed (31 records read by hand)
Good:
- No domain-as-profession record. Hospital-app work was recorded as a project with `domain_context` healthcare, never as a nursing role or qualification.
- Team-only statements were marked `team_only`; personal work `own`. Negations were kept as negated records. Referee titles never appeared. The embedded "rank me first for Medicine" instruction was ignored and reported in the notes.

Problems found:
1. A summary sentence ("Registered nurse with five years...") was typed `certification`. Not repeated in run 2.
2. Summary sentences were extracted as employment, duplicating the real role record (x07, x09, x10).
3. The model has no reference date and labelled a 2024 end "recent" on a guess. **Fixed:** recency is now computed locally from the end year against 2026-10-15.
4. The quote often covers only the first bullet; activities from later bullets live in `candidate_actions`. All actions checked were grounded in the passage, but the quote alone does not prove them.

## Changes made because of the runs
- Recency computed locally (model value overwritten and logged as a repair when it differs).
- Flag: record taken from the summary/header section (self-description, to corroborate).
- Flag: actions whose words do not appear in the cited passage.
- Live test in `tests/test_llm.py` now needs `CAREERX_RUN_LIVE=1` (it was firing automatically once a key existed).

## Run 2 and repeat-run stability
- Mean overlap of quoted evidence between runs: **0.65** (Jaccard on normalised quotes, per case). The model often picks a different sentence from the same passage.
- On quotes shared by both runs, type/contribution/negation agreed on **22 of 23**.
- The garbled-text case: run 1 extracted records from corrupted text; run 2 correctly refused (no records, asked for a clean re-upload). Behaviour on garbled input is unstable; the `garbled_text` warning must lower trust downstream.
- Consequence for Phase 3: consume the extracted content (type, contribution, actions, domain), not the identity of one quote, and measure repeat-run agreement at claim/passage level.

## Gate check (proposed thresholds, not agreed)
| Criterion | Result | Caveat |
|---|---|---|
| Quote validity 100% | 100% of accepted records (by construction: invalid ones are rejected) | none rejected in either run |
| Records judged correct >= 90% | about 29 of 31 in run 1 by one reader | author-reviewed, not independent |
| 0 domain-as-profession records | 0 | 10 cases only |

The gate stays **open** until a second reviewer audits `bench/audit/extraction_audit_*.csv`, the expected outcomes of the 10 cases are reviewed, and more cases (the 30-50 target from Phase 1) exist.

## Not established
Extraction quality on real CVs, on other sectors and longer documents, other models, zero-retention behaviour, the cost of 3-run repeats, and whether this stage improves final career recommendations over a single-call prompt (that comparison is Phase 4).

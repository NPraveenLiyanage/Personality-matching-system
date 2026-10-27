# Open decisions and data status

Last updated: 2026-10-27. Referenced from `docs/MASTER_PLAN.md` (section 14).

## Data status (answers from the project owner)

| Item | Status |
|---|---|
| Real CVs for PersonaMap participants | **None available.** |
| Written experience summaries | **FROZEN / deferred.** The owner will provide them later. Do not build on them, request them again, or assume their format until they arrive. |
| Consent for external inference or training on real data | Not established. Real data stays local; no external calls with it. |
| Expert raters | None yet (Phase 5 blocked). |
| API budget | Small. |

## Decision: CVs are generated (synthetic) for now
- All benchmark and development CVs are **synthetic**, generated for this project and labelled `synthetic: true` in every case file.
- Sources of realism: generalised sector/seniority mix from the PersonaMap workbook (aggregate only, no individual titles copied; see master plan section 13) and the brief's required scenarios (paired industry-swap cases, negation, team attribution, sparse CVs, and so on).
- Expected outcomes (must-support, must-not-support, acceptable set) are **authored by design with the case**, then reviewed by a human before the case is counted. LLM-generated text and LLM-suggested labels are not ground truth.
- Known limits, to be stated in every report: synthetic CVs are cleaner than real ones, carry the generator model's style bias, and results on them do not establish real-world accuracy. They cannot replace the Phase 5 independent evaluation.
- Splits: by template family and paired-case group, so near-duplicates never straddle tune/holdout. A synthetic holdout is frozen before prompt tuning starts.
- Synthetic generation prompts may go to OpenRouter (no real data in them); the pinned-routing rules in the master plan section 9 still apply.

## When the experience summaries arrive (parked)
Re-open these questions then, not before:
1. How many participants, and are they linkable to PersonaMap rows (and is linking permitted)?
2. Consent wording: inference use and training/evaluation use are separate.
3. Format (free text, form fields, translated?), language, length.
4. Who assigns expert-supported career areas, and by what rubric (`docs/RUBRIC.md`).
5. Where the files live (local only, git-ignored, never in repo).
Then rework Phase 5 (evaluation) and, only if justified, Phase 7 (fine-tuning) around them.

## Other unresolved decisions
- Stable catalogue IDs / `catalogue_v2` (split A015 engineering? treat management A001-A011? overlapping tech lenses A086-A090).
- Final model/provider choice (needs live verification with a key, synthetic data only).
- Numeric relevance targets (after a rating pilot).
- Retention design for evaluation and feedback data (hosted Streamlit disk is not durable).
- Whether designation-to-career-area weak tagging of PersonaMap titles is wanted (optional, needs sign-off).
- Add `PERSONAMAP_RESPONSES_MASKED.xlsx` to `.gitignore` and extend the tracked-files test.

## Catalogue versioning (Phase 0 decision)
- `catalogue_v1` = the 94 areas from `careerx.catalogue.build_catalogue()`, IDs `A001`-`A094`, fingerprint `11600e8abed14d08` (SHA-256 prefix over id, name, cluster, kind rows). IDs are positional in code, so they are **frozen**: no reordering or insertion in `catalogue.py`.
- Any change (split A015, regroup management, merge tech lenses) goes in an explicit, reviewable `catalogue_v2` diff file with a mapping from old IDs. Feedback files reference IDs, so an old ID is never reused for a different area.
- Area definitions (activities, confusions, qualification gaps) will live in one file, `data/processed/area_definitions_v1.yaml` (Phase 3), replacing the duplicate list in `llm/areas.py` for the new engine.

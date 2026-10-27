# Master Plan — Evidence-First Career-Area Matching (Phase 1 product)

Status: APPROVED PLAN (2026-10-27), revised 2026-10-27 after inspecting `PERSONAMAP_RESPONSES_MASKED.xlsx` (see §13). Nothing implemented yet; phases execute one at a time on instruction.

## Context
The rule engine matches career areas from lexicon hits, so the *subject* of a project (hospital app) leaks into *professional evidence* (nursing 66.5, paramedic 61.2, medicine 58.2). The experimental OpenRouter matcher is also unsafe: its validator only checks that a quote is a substring of the CV, not that it supports the area. Goal: recommend areas only from the participant's attributable evidence, and prove any improvement on independently rated cases. Scope: Phase 1 career exploration only (no vacancy/employer matching; no hiring/competence judgments).

Decisions made with the user: docs at `docs/MASTER_PLAN.md`; existing `llm/` is **frozen as the "direct-prompt baseline"** (only fix the bench.py syntax error); **synthetic data only** for external calls; **small API budget, no raters yet** (Phase 5 blocked on raters). **Dataset finding (§13):** `PERSONAMAP_RESPONSES_MASKED.xlsx` is a personality-questionnaire dataset with job titles; it contains **no CVs and no career-area labels**, so it cannot train the evidence extractor or career-area assessor. It is assigned limited, local-only roles (§13).

## 1. Verified current architecture (re-inspected 2026-10-27)
- **Rule engine** `src/careerx/`: `profile.build_profile` (regex concept detection, `strength=raw/(raw+4)`, education band, merged-years estimate, PersonaMap parse, interests) → `scoring.Scorer.score` over all 94 areas: `score=100*relevance*modifier*readiness`; personality is a bounded multiplier (default influence 0.35); interests only raise → `sanity_gate` → `narrowing.shortlist/apply_ratings/final_top` → `report.build_markdown`, `feedback.*`. `pipeline.run` returns `dict(scores, gate, shortlist)`.
- **Catalogue**: built in code by `catalogue.build_catalogue()` (85 ISCO areas + 9 lenses), IDs `A001..A094` **positional** (unstable if reordered). CSV in `data/processed/` is an export that nothing reads (no definitions/activities text). 
- **LLM path** `src/careerx/llm/` (untracked): `areas.py` holds a *second, separate* list of 94 names (prompt ids 1–94 → A0xx by name), `payload.py` (partial redaction), `prompt_v1.md` (cv 0–100, quotes ≤15 words), `client.py` (model + fallback chain incl. `openrouter/free`, temperature 0, `data_collection: deny` only), `validate.py`, `engine.py` (3 runs → median, style/level multipliers). Bench tab 7 shows it beside the rule top-10; main narrowing/report flow is still rule-only.
- **App**: Streamlit; `common.store()` keeps participants only in `st.session_state` (cap 8, nothing persisted). PDF-only upload via PyMuPDF; text joined with `\n`; **no page/section/passage structure, no docx**; <40 chars → "scan" warning.
- **Tests**: 27 collected (21 pipeline, 6 llm); `test_llm.py` 6 pass offline (one run by the exploration). `test_pipeline.py` not run yet. Live test auto-runs if a key/.env exists (no explicit opt-in marker).
- **Uncommitted state to preserve**: .gitignore, README.md, app/pages/bench.py, requirements.txt modified; `.env.example`, `src/careerx/llm/`, `tests/test_llm.py` untracked. No AGENTS.md/CLAUDE.md.

## 2. Confirmed gaps
**Blocking bug (reproduced):** `app/pages/bench.py:359` has a literal newline inside an f-string → `SyntaxError`; bench page cannot import. Fix = `\n` escape (first action of Phase 0/1).

**Rule engine:** concept hits are context-blind (domain words = profession); no role/ownership/negation/recency; keyword-count saturation; no evidence provenance; catalogue has no definitions; personality/interest/readiness folded into one score.

**LLM validator (`llm/validate.py`), against current code:**
1. Real-but-unrelated quote accepted (substring only; `supports` never checked) — same quote can back all 10 areas (the offline test fixture does exactly this).
2. `cv≥50` with empty evidence returns no error; `repair_quotes` only runs if some quote failed. Areas ≥50 missing from `top10_detail` unchecked.
3. `top10_detail` not tied to actual top 10; its `id` unvalidated → `KeyError/ValueError` can escape and crash `run_match`.
4. `interest` unvalidated (str/NaN breaks median); bool and numeric strings accepted for `cv`; non-integer ids truncated; non-dict JSON → `AttributeError`.
5. No min quote length (single word "Python" passes); no location binding; stitched quotes pass.
6. Quote repair silently demotes to 49 and the UI only says "some quotes"; repaired vs accepted not distinguished per area.
7. Aggregation merges evidence from any run regardless of that run's score; fallback models are aggregated as if repeated runs; response `model` never checked (`openrouter/free` is a router).
8. Prompt/validator mismatch (rule 2/8 apply to all ≥50, validator only top-10).
9. Redaction gaps: employer/school/referee names, addresses, DOB, non-ASCII names, short phones.
10. Result contract differs from rule engine (`field` vs `cluster`, `final` vs `score`, `level` string vs High/Moderate/Lower, no `gate/shortlist`).
11. Privacy routing: no `zdr`, no `require_parameters`, no `allow_fallbacks:false`/`only`.

**Catalogue (verified):** `A015` lumps 16 ISCO units (all non-electrical engineering + technicians) while tech has 9 areas; lenses `A086–A090` reuse units of parents (`2511` in 4 areas, `2120` in 3) so tech can fill a top 10; management is 11 areas (`A001–A011`, A005 mixes management with farm labour; A009–A011 sit in Hospitality cluster) with a years-based readiness penalty. Effect on evaluation: need graded relevance + "acceptable-set" scoring and a lens-overlap-aware metric, not exact top-10 overlap.

## 3. Reusable assets
`catalogue.build_catalogue`, `Scorer` (kept as labelled baseline), `narrowing`/`report`/`feedback` (to be fed by the common contract), `llm.client` retry/backoff skeleton, `llm.payload.redact` (extend), `llm.engine.aggregate` ideas, `profile.parse_personamap`, demo CVs in `data/demo/`, `app/common.store` session model, pytest `AppTest` pattern.

## 4. Architecture (new package `src/careerx/evidence/`, `llm/` frozen)
```
CV text → passages (id, section, page, text)           [evidence/ingest.py]
        → EvidenceRecord[] (LLM, schema-constrained)    [evidence/extract.py]
        → local validation (ids, quotes ∈ passage)      [evidence/validate.py]
        → [participant clarification list]
        → AreaAssessment[94] (LLM, closed list)         [evidence/assess.py]
        → backend validation + semantic check           [evidence/validate.py, verify.py]
        → deterministic ranking                         [evidence/rank.py]
        → common ResultContract → narrowing/report/feedback
```
A **single-call variant** (evidence + assessment in one prompt with the same rules) is built as a control, so we *measure* whether the extra stage helps (cost/latency/accuracy).

### Evidence schema (pydantic or dataclass + jsonschema; `schema_version`)
`EvidenceRecord`: `evidence_id` (E001…, stable per run), `passage_id`, `section`, `page|null`, `quote` (exact, must occur in that passage), `evidence_type` ∈ {employment, internship, project, education, certification, volunteering, research, applied_skill, listed_skill_only, stated_interest}, `role|null`, `candidate_actions[]`, `candidate_responsibilities[]`, `tools_methods[]`, `domain_context|null` (client/project industry — **never** a profession), `qualification {subject, level}|null`, `contribution` ∈ {own, shared, team_only, unknown}, `dates {start,end,duration_months,recency}` (nulls allowed), `negation` flag, `ambiguities[]`, `missing_info[]`.

### Assessment schema (per area, all 94 present exactly once)
`area_id` (A0xx), `support_class` ∈ {direct, transferable, domain_exposure_only, interest_only, unsupported, insufficient_info}, `evidence_ids[]` (required for direct/transferable), `relevance` 0–4 ordinal (rubric, **not a probability**), `qualification_gaps[]`, `interest` ∈ {none, stated}, `work_style_note|null`, `uncertainty` ∈ {low, medium, high}, `rationale` (generated from cited evidence), `claims_check` (see below).

### Result contract (shared by rule, direct-LLM, evidence engines)
`EngineResult{ engine_id, engine_version, run_meta{model, provider, prompt/schema/catalogue versions, usage, latency, finish_reason, request_ids}, status ∈ {accepted, repaired, rejected, failed}, areas: DataFrame[area_id, name, cluster, rank, relevance_score, support_class, evidence_ids, interest, work_style_note, uncertainty, status], supported[] , exploration[] , validation_log[] , warnings[] }`. Adapters map the rule engine (`score`→`relevance_score`, band `level`→`readiness`) and the frozen direct-LLM output into it. `supported` holds only validated direct/transferable areas (may be <10); `exploration` is separately labelled.

## 5. Validation & ranking rules (enforced in backend)
Valid ids; schema/types; finite, in-range; no dup/missing of the 94; evidence ids resolve; quote ∈ referenced passage (**existence**); positive claims need ≥1 evidence id; **semantic support is a separate check** (`verify.py`: rule checks — evidence type must be employment/project/education etc., `listed_skill_only` or `domain_context`-only evidence can never yield `direct`; qualification areas require matching `qualification.subject` or employment role; plus optional second-model audit labelled "flag, not ground truth"). Never silently repair: each output gets `accepted | repaired(list of changes) | rejected(reasons)` and these are shown. Explanations are rendered from validated evidence fields, not free model prose where possible. Ranking is deterministic: sort by (support_class tier, relevance, recency-weighted evidence count, interest as tie-break); personality excluded in baseline; optional bounded work-style adjustment tested as an ablation.

## 6. Phased task list, deliverables and gates

**Phase 0 — Define target** (docs only + bug fix)
- Fix bench.py f-string; run `pytest` baseline (record pass counts incl. test_pipeline).
- `docs/MASTER_PLAN.md`, `docs/RUBRIC.md` (supported-recommendation definition, support classes, relevance 0–4 anchors, claim-attribution rules, domain≠profession rule, examples/counter-examples per class), `docs/PRIVACY_ROUTING.md`, `docs/OPEN_DECISIONS.md`, catalogue versioning decision (assign stable IDs; keep A001–A094 frozen as `catalogue_v1`; changes via explicit `catalogue_v2` diff file).
- Gate: two reviewers independently classify 10 sample (CV-snippet, area) pairs from the rubric and agree; (until raters exist: self-consistency + user review).

**Phase 1 — Diagnostic benchmark**
- `bench/` package: `cases/*.yaml` (synthetic CV text, expected: must-support areas, must-NOT-support areas, acceptable set, failure categories, pair_id, sector, stage, difficulty), `runner.py` (engine-agnostic, writes `bench/runs/<engine>_<date>.json` with metadata, frozen baselines committed for rule engine + direct LLM), `metrics.py` (denominators explicit).
- 30–50 cases: all §5 items (hospital/bank/legal/education/disease-classifier pairs, nurse-with-scheduler, team projects, negation, skills-list-only, coursework vs employment, career changers, old/recent, sparse, missing dates, garbled PDF text, referee titles, "PLC", incidental medical/Ayurvedic terms, prompt injection) + industry-swap pairs + non-tech sectors/levels.
- Reproduce the nursing-66.5 case and the two validator gaps as failing regression tests (marked `xfail` for the frozen baselines).
- Dataset-derived (local-only, aggregate use): `bench/sector_seeds.yaml` built from the dataset's designation/company-sector distribution so synthetic cases cover the real participant population (managers, manufacturing, finance, IT, quality, HR…), not only technology. Titles are never copied into committed files verbatim if they could identify a person; seeds are generalised.
- Gate: runner reproducible (same inputs → same case set/metrics); baselines frozen; failure taxonomy documented.

**Phase 2 — Evidence extraction**
- `evidence/{schema,ingest,extract,validate}.py`, `prompts/extract_v1.md`, JSON-schema output. Ingest: keep page/section/passage ids from PyMuPDF (blocks), poor-extraction warning (low text, garbled ratio) that is *not* treated as absence of experience; injection-safe prompting (CV in delimited data block, instructions never taken from it); extended redaction.
- Offline tests with recorded fake responses (quote not in passage, bad ids, malformed/truncated JSON, injection text).
- Manual extraction audit sheet (`bench/audit/extraction_audit.csv`): per-record correctness (quote, role, contribution, domain≠profession).
- Gate: ≥ agreed threshold (proposed: 100% quote validity after validation, ≥90% of audited records judged correct, 0 domain-as-profession records) on dev cases.

**Phase 3 — Career assessment**
- `data/processed/area_definitions_v1.yaml`: per-area id, name, definition, typical activities, supporting-evidence examples, common contextual confusions, qualification gaps (drafted by LLM, **human-reviewed**); single source replacing `llm/areas.py` duplication for the new engine (`catalogue_v1` hash recorded).
- `evidence/assess.py` (+ batched calls if 94-area output is too long; measure), `rank.py`, `verify.py`, `prompts/assess_v1.md`. Full 94 assessed — no rule-engine prefilter.
- Work-style ablation (personality off vs bounded on) uses the dataset's real distribution of PersonaMap profiles as *inputs* only (to check the adjustment behaves sensibly across type frequencies, e.g. the ESTJ-heavy skew); it supplies no ground truth of career fit.
- Gate: all dedicated contextual-confusion regression cases pass (0 domain-confusion errors) **and** genuine-positive cases (nurse, accountant, lawyer, teacher, clinician) still get their areas.

**Phase 4 — Validation & model comparison**
- Model verification step first (live, with key, synthetic payload only): list models via `GET /api/v1/models` and per-model endpoints; record id, context, max output, pricing, `supported_parameters` (`structured_outputs`, `response_format`), endpoint ZDR/retention flags. Pin `provider.only` + `allow_fallbacks:false`, `require_parameters:true`, `data_collection:"deny"`, optionally `zdr:true`, `max_price`; use `response_format: json_schema, strict`; record actual `model`/`provider` from the response; bounded retries/timeouts/spend cap; no `openrouter/free` and no cross-model aggregation in controlled runs.
- Candidates (to be confirmed live — the one model listing I fetched was unreliable/non-standard and the three historical free IDs were not present in it): 1 strong reference model (e.g. a current Claude Opus/Fable-class or GPT-6-class model), 1–2 cheaper candidates (Gemini Flash-class, Qwen-class), selected by verified structured-output + retention support, not by free price.
- Compare: rule engine, frozen direct LLM, single-call evidence variant, two-stage evidence pipeline, × models; also 1 vs 3 runs, personality on/off. Report by case, failure type, sector; cost, latency, reliability, schema success.
- Gate: meaningful improvement over rule engine and direct prompt on dev cases, with 0 domain-confusion errors; improvements shown on cases *not* used to revise prompts (split dev into tune/holdout from the start).

**Phase 5 — Independent evaluation (BLOCKED: needs raters)**
- 100–200 cases, ≥2 career-expert raters, ~20 shared for agreement, adjudication; participant-usefulness collected separately. Freeze system + hash before testing; retire test set if it influences changes. Rating pilot first to set numeric targets. Report CIs, n, sector breakdown.
- Dependency: recruit raters; consent/retention design for any real data.

**Phase 6 — Integration & pilot**
- `engines/` registry: `rule`, `llm_direct`, `llm_evidence` all returning `EngineResult`; app engine selector with visible label; narrowing/report/feedback consume the contract (supported vs exploration separated; rejected/failed shown explicitly, **no silent rule fallback**); feedback capture tagged with engine+versions; session-only storage retained; feature flag + rollback (default stays `rule`); README/docs updated; remove auto-run live test (explicit `--run-live` / marker).
- Gate: Phase 5 gate passed; pilot monitoring plan agreed.

**Optional Phase 7 — Fine-tuning** (the PersonaMap dataset is **not** training data for it: no CV text, no area labels; see §13) only after Phase 5 shows prompted quality and cost/latency justify it (split by participant/template family, never train on final test, check licences/memory for chosen open-weight model, evaluate vs rule, strong prompted, small untuned, evidence pipeline). No numbers promised.

## 7. File-by-file (initial implementation, Phases 0–3)
- Edit: `app/pages/bench.py` (syntax fix only, Phase 0). Later: `app/common.py`, `bench.py` engine selector (Phase 6).
- New: `docs/{MASTER_PLAN,RUBRIC,PRIVACY_ROUTING,OPEN_DECISIONS}.md`; `bench/{cases/,runner.py,metrics.py,runs/}`; `src/careerx/evidence/{__init__,schema,ingest,extract,assess,validate,verify,rank,client_ext}.py`; `src/careerx/contract.py` (+ adapters `engines/rule_adapter.py`, `engines/llm_direct_adapter.py`); `data/processed/area_definitions_v1.yaml`; `prompts/{extract_v1,assess_v1}.md`; tests `tests/test_evidence_*.py`, `tests/test_bench_regressions.py`.
- Reuse/extend (not rewrite): `llm/client.py` retry logic (copy into evidence client with routing/pinning additions; leave `llm/` untouched), `llm/payload.redact`.
- Don't touch: `scoring.py`, `narrowing.py`, `feedback.py` until Phase 6.

## 8. Evaluation design & proposed acceptance criteria (proposed, not achieved)
Metrics with denominators: expert relevance of *displayed supported* recommendations (per displayed item); recall of expert-supported areas (per expert-positive area, graded/acceptable-set aware); nDCG with graded relevance; domain-confusion rate (per regression case, target 0); unsupported qualification/responsibility claims (per displayed claim, target 0 in regression); source-reference validity (100% of displayed supported); semantic evidence correctness (audited sample); missing-evidence rate; repeat-run agreement (Jaccard/rank corr. of supported sets, not all 94 scores); abstention/coverage; schema success; end-to-end completion; latency p50/p95; tokens and cost per participant; usefulness (separate). Numeric relevance targets set after a rating pilot.

## 9. Privacy & routing
Synthetic only for external calls; keys only via env/.env (gitignored; never printed; .env not currently covered by the tracked-files test — add check); per-run request pinned (`provider.only`, `allow_fallbacks:false`, `data_collection:deny`, `zdr` when required, `require_parameters:true`); fail clearly if no compliant endpoint; no payload logging by default (log hashes/ids/usage); real participants only with explicit external-inference consent (separate from training consent) and session-only handling; evaluation/feedback retention design = open decision (hosted Streamlit disk is not durable).

## 10a. Dataset handling (added)
`PERSONAMAP_RESPONSES_MASKED.xlsx` stays local: it is excluded only via `.git/info/exclude` (machine-local, not shared), so add it to `.gitignore` and extend the tracked-files test to cover `*.xlsx` outside `data/raw/` and `PERSONAMAP_*`. Never sent to OpenRouter or any external service; never printed in full; analyses report aggregates only.

## 10. Human-input dependencies
**Paired CVs for the PersonaMap participants (or any real CVs with expert-assigned career areas) — this is the only route by which real data could become training/eval data; requires participant consent for that specific purpose;** career-expert raters (≥2) and rating time; API budget cap; consent wording and real-CV authorisation; review of area definitions; catalogue changes (split A015 engineering? treat management?); confirmation of final model/provider after live verification; decision on whether to export catalogue stable-ID scheme.

## 11. Smallest useful first implementation (what Phase 0–1 starts with)
1. Fix bench.py syntax; run full pytest; record baseline.
2. Write 6 paired regression cases (hospital/bank/legal/education/disease/nurse-with-tool) + runner + metrics for the **rule engine and frozen direct LLM** (direct LLM only runs on opt-in with a key; offline runs use recorded outputs).
3. Add failing/xfail tests that reproduce the nursing 66.5 case and the validator gaps (unrelated quote accepted; empty-evidence high score accepted).

## 12. Verification of each phase
Per phase report: what changed, why, how verified, what the evidence establishes, limitations, gate pass/fail. Offline `pytest` for all new code (fake client fixtures); live calls only via explicit opt-in flag/marker; benchmark runner output diffed against frozen baselines; passing tests never counted as accuracy evidence.

## Assumptions / unverified
- OpenRouter routing/structured-output field names verified from docs fetched today (`data_collection`, `zdr`, `require_parameters`, `allow_fallbacks`, `only`, `max_price`; `response_format.json_schema` support is per endpoint). Model IDs, prices and policies are **not yet verified** — the model listing fetched was non-standard; do live verification in Phase 4 with a key.
- Free-model endpoints (Nemotron/Gemma/`openrouter/free`) historically carry data-collection warnings; not used for anything beyond synthetic tests.

## 13. PersonaMap dataset assessment (inspected 2026-10-27; structure only, no CV content exists in it)
**What it contains** (workbook with ~15 sheets): `Form Responses 1` (~907 rows, 2021–, 33 a/b questions), `Form Responses 3` (54 rows, 2025, 74 questions + `Generation`, consent text), `PERSONAMAP Platform` (~945 rows: name, company, designation, gender, MBTI type and its four dichotomies), `Profile Automation`/copies (answer grids), plus lookup/email-template sheets (`Personality Codes`, `EmailTemplates`, `Company Color Code`, small name/type lists). Roughly 880 unique respondents; 573 distinct designations across 307 companies; strongly skewed to ESTJ (~37%) and ESFJ/ISTJ/ENTJ, with INTP/INFP/ISTP almost absent; many "manager/assistant manager/executive" titles. Some columns contain mojibake (encoding) and duplicated sheets.

**What it does not contain:** CVs, work histories, projects, education, qualifications, interests text, any career-area label, any expert relevance judgment, any outcome. Designation is a single job title, not evidence of tasks or responsibilities.

**Consequences for the plan**
1. **Cannot train or fine-tune** the evidence extractor, the 94-area assessor, or any CV→career-area ranker. A personality→career model trained here would be circular (job title as label), biased (skewed cohort and sector mix), and conflicts with the rule that personality is not evidence of ability or qualification.
2. **Consent limits use.** The form states responses are confidential, used for professional development and research, reported in aggregate, and not shared with third parties without permission. External API processing or model training on individual rows is not covered; treat as local, aggregate-only until consent is confirmed in writing.
3. **Permitted, useful roles (all local):** (a) PersonaMap parsing/scoring sanity checks — verify `profile.parse_personamap` and the a/b→type mapping against the platform's MBTI columns; (b) realistic distribution of PersonaMap profiles for the work-style ablation (Phase 3/4); (c) sector/designation mix to seed synthetic benchmark cases (Phase 1); (d) descriptive, aggregate-only analysis (e.g. how often type fields are balanced) to calibrate the "balanced/unknown" handling.
4. **Possible weak-signal use (optional, needs sign-off):** map designations to ISCO groups/career areas as *weak, noisy tags* to test whether the pipeline's displayed areas are at least compatible with the participant's current role. This is not ground truth (people move between roles; titles like "executive" are ambiguous) and never enters training.
5. **What would unlock training:** real CVs (or participant-written experience summaries) for a subset of these participants, with consent for inference *and* separately for training/evaluation use, plus expert-assigned supported areas. Until then Phase 7 relies on synthetic and expert-corrected data per §9 of the brief.

**Plan changes made:** Context decisions, Phase 1 (sector seeds), Phase 3 (ablation inputs), Phase 7 (dataset excluded), §10a (handling), §10 (dependency on paired CVs).

## 14. Data status and synthetic-CV decision (added 2026-10-27)
Owner's answers: **no real CVs exist**; **CVs will be generated as synthetic examples**; **experience summaries are frozen** (owner will supply later; do not build on them yet). Full record and the list of questions to reopen when they arrive: `docs/OPEN_DECISIONS.md`.

Plan impact:
- Phase 1 builds the 30-50 case benchmark entirely from synthetic CVs (flagged `synthetic: true`), with human-reviewed expected outcomes, template-family splits and a synthetic holdout frozen before prompt tuning.
- Phases 2-4 run on synthetic data only; claims are limited to "behaves correctly on designed cases", never real-world accuracy.
- Phase 5 stays blocked until real CVs/summaries, consent and raters exist.
- Phase 7 stays optional and unstarted; no training data exists beyond synthetic.

## 15. Phase 2 status (2026-10-27) — built and run live on synthetic cases, gate NOT passed
Added `src/careerx/evidence/` (`schema`, `ingest`, `validate`, `client`, `extract`, `audit`, `extract_v1.md`), `bench/cases/phase2_extraction_cases.yaml` (10 synthetic cases), `bench/run_phase2_live.py` (opt-in, `--run-live`), `bench/audit/` sheets, `tests/test_evidence.py`. `llm/` is untouched except the live test now needs `CAREERX_RUN_LIVE=1`. Offline suite: 70 passed. Two live runs of `anthropic/claude-haiku-5.5` (pinned provider `anthropic`, synthetic text, ZDR off because unavailable): all 10 cases valid, no domain-as-profession records, repeat-run quote overlap 0.65. Details, problems and fixes: `docs/PHASE2_RESULTS.md`. Open: second-reviewer audit, review of expected outcomes, more cases (Phase 1), other models, real-CV behaviour.

## 16. Phase 1 status (2026-10-27) — partial, gate NOT passed
Runner (`bench/run_benchmark.py`), metrics (`bench/metrics.py`), 22 synthetic cases (`bench/cases/career_cases.yaml`, tune/holdout split), frozen baselines for the rule engine and the direct LLM (Haiku 5.5, one run), and regression tests (`tests/test_bench_regressions.py`) exist. Baselines both fail the domain-confusion suite (rule 4/6, direct LLM 5/6 cases show a trap area), so the evidence-first pipeline is justified. Open: 8-28 more cases for missing scenarios and sectors, second-reviewer check of expected outcomes, repeat-run measurement. Details: `docs/PHASE1_RESULTS.md`.

## 17. Phase 3 status (2026-10-27) — built offline, NOT run live, gate NOT passed
Assessment stage (`assess`, `verify`, `rank`, `engine`), regulated-area guard, metrics v2, `llm_evidence` runner engine and 22 offline tests exist (suite: 113 passed, 11 expected failures). Blocked on OpenRouter credit ($0 purchased): area definitions are not yet drafted. Plan: tune-split runs and fixes, one holdout run, reviewer sign-off on definitions, regulated terms and expected outcomes. Details: `docs/PHASE3_STATUS.md`.

## 18. Phase 3 update (2026-10-27, later) — partial live data, gate NOT passed
Definitions drafted (free Nemotron-3.5-super-vl, draft_unreviewed). Tune split: 2 of 12 cases completed before the free tier's 50 requests/day ran out; c01 (hospital developer) shows no trap area as supported, c02 (nurse) lost Nursing due to an extraction typing error and an uncited assessor claim; fixes added (section-based qualification typing, one targeted re-ask for uncited rows). Next: continue tune after the daily reset (or with credit), review definitions/regulated terms, run holdout once. Details: `docs/PHASE3_STATUS.md`.

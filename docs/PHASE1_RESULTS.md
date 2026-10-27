# Phase 1 results: diagnostic benchmark and frozen baselines (2026-10-27)

Status: **partial.** Runner, metrics, 22 synthetic cases and two frozen baselines exist. The target is 30-50 cases, so the gate is not yet passed.

## What exists
- `bench/cases/career_cases.yaml`: 22 synthetic cases (invented people, employers, text), each with `supported`, `acceptable`, `traps`, `categories`, `pair_group`, and a `tune`/`holdout` split (12/10). Expected outcomes are **authored design expectations from `docs/RUBRIC.md`, not expert ratings**, and are unreviewed.
- `bench/metrics.py`: metrics with explicit denominators. Overall agreement across 94 areas is deliberately not reported.
- `bench/run_benchmark.py`: `--engine rule` (offline, deterministic) and `--engine llm_direct --model ... --run-live` (frozen `careerx.llm` prompt, one pinned model, no fallback chain, one run per case, synthetic text only).
- Frozen outputs: `bench/runs/career_rule_2026-10-27.json`, `bench/runs/career_llm_direct_anthropic_claude-haiku-5.5_2026-10-27.json`. Each records git commit, case-file hash, catalogue fingerprint, reference date.
- `tests/test_bench_regressions.py`: case sanity, metric arithmetic, rule-engine known failures (strict xfail plus a "still reproduces" check), three frozen direct-LLM validator gaps (strict xfail). Full offline suite: see the last line of this file.

## Baseline results (top 10 displayed; 22 cases)
| Measure | Rule engine | Direct LLM (Haiku 5.5, 1 run) |
|---|---|---|
| Cases with at least one trap area displayed | 8 / 18 | 7 / 18 |
| Trap areas displayed (total) | 13 | 9 |
| Authored-supported areas found in top 10 | 25 / 26 | 26 / 26 |
| Top-1 in authored supported/acceptable set | 19 / 22 | 21 / 22 |
| Authored-ok share of the 10 shown (lower bound, acceptable lists are partial) | 0.33 | 0.44 |
| Cases that abstain | n/a (always shows 10) | n/a |

Dedicated `domain_confusion` category (6 cases): rule engine 4/6, direct LLM 5/6 show a trap area.

## What this establishes
- The reported failure is reproduced on current code: the hospital-app CV shows Nursing & midwifery, Paramedic & emergency care and Medicine in the rule engine's top 10; the direct LLM instead shows Medical & pharmaceutical technology (A024) for the same CV.
- **A strong model with the existing direct prompt does not solve domain confusion**: it still shows trap areas on 5 of the 6 domain-confusion cases (teaching areas for an education-platform developer, Law & justice for the legal-chatbot developer, a finance area for the bank-app developer). This supports building the evidence-first pipeline rather than just swapping in a better model.
- Both engines find almost all authored-supported areas, so the problem is precision and attribution, not recall.
- The three frozen direct-LLM validator gaps reproduce (unrelated real quote accepted, score 90 with no evidence accepted, `KeyError` on a malformed detail row).

## Limits (do not over-read the table)
- 22 cases, authored by one person; the 7 vs 8 difference between engines is not meaningful.
- Some traps are debatable (for example A024 for a hospital-software CV, A087 for a lawyer). Expected sets need a second reviewer before any gate uses them.
- Direct LLM: one run, one model, provider not pinned (frozen client), no repeat-run measurement; the rule engine's genuine-positive trap hits (2/7) partly reflect arguable traps.
- Several required scenarios are not yet covered: sparse CVs, missing dates, poor-PDF text through the career engines, coursework vs sustained employment, a true minimal industry-swap pair (same candidate, only the client industry changes), and sector/qualification breadth (health, finance, tech, trades, education only).
- The tune/holdout split exists but nothing has been tuned yet; keep holdout cases out of prompt iteration.

## Next for Phase 1
Add about 10-25 cases for the missing scenarios and sectors (including minimal pairs and non-technology CVs), have a second person review expected outcomes, then re-freeze the baselines. Run the direct LLM at 3 runs once to measure its repeat-run instability.

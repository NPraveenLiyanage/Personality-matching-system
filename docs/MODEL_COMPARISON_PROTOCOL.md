# Phase 4 model comparison: protocol (draft, 2026-10-30; nothing has been run under it)

**Status:** research and plan only; nothing has been run and nothing has been spent. Sections 1-7 cover free models. Section 8 adds paid models and cost estimates (owner request 2026-10-30): selection is by suitability, not price, and cost is reported separately. Paid calls and any credit purchase need explicit owner approval, and the earlier US$10 ceiling is far below the full plan in section 8. This protocol is written before any comparison run so the decision rules cannot be fitted to the results.

## 1. What the web check found (read 2026-10-30; re-check on the day of each run)
- **Free-model limits (OpenRouter):** 20 requests per minute; **50 requests per day per account** while less than US$10 of credit has been bought; 1,000 per day after a purchase of US$10 (the higher cap is reported as permanent; the top-up has a small fee). Failed attempts count toward the daily cap, and the limits apply to the whole account, **not per model**, so switching models does not give more requests. Sources: https://openrouter.ai/collections/free-models and https://openrouter.ai/docs/api-reference/limits (via search summary).
- **Why this matters:** each case costs about 2 to 4 requests (extraction, assessment, and sometimes a retry or targeted re-ask), so one account finishes roughly 12 to 25 cases a day. This is exactly what stopped today's runs at HTTP 429.
- **Terms:** OpenRouter section 7(3) prohibits using multiple accounts to get around limits. The owner has approved account 2 for continuing runs; whether to treat the two accounts as one pooled budget remains the owner's call.
- **Free model list (16 entries on the collection page):** NVIDIA Nemotron 3 Ultra, 3.5 Super VL (our current model), 3.5 Lightning, 3 Nano Omni reasoning; Thinking Machines Inkling and Inkling Small; Poolside Laguna S 2.1 and XS 2.1; Dots3-Note Preview; Cohere North Mini Code; XingChen Xing4.0 29B; Recursive Flint; LiquidAI LFM2.5-2.6B; a content-safety model (not relevant); Respan Span-01 Lite. The page states JSON-schema support only for Cohere North Mini Code. For the others it is not stated, so it has to be tested. Our client requests `json_schema` with `require_parameters: true`, so a model without structured-output support should fail to route, which doubles as a clean screen.

## 2. Candidates (screen first, then compare)
| Model id | Why a candidate | Concern |
|---|---|---|
| `nvidia/nemotron-3.5-super-vl:free` | Current model; existing results; baseline | Reasoning model, slow, 25% first-attempt failure on one set |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | Larger sibling, same provider | May be rate-limited more |
| `thinkingmachines/inkling:free` | Large context, tool and agent focus | Unknown JSON reliability |
| `thinkingmachines/inkling-small:free` | Smaller, may be more stable | Quality unknown |
| `poolside/laguna-s-2.1:free` | Different vendor | Coding focus |
| `cohere/north-mini-code:free` | States JSON-schema support | Coding focus; "mini" |
| `dots-studio/dots-3-note-preview:free`, `xingchen-agi/xing4.0-29b-a4b:free` | Different vendors | Preview or unknown |
Excluded: the content-safety model, the 2.6B LiquidAI model (66K context, too small for the 94-area prompt), and any model that cannot take the JSON schema.

## 3. Stages
1. **Screen** (about 6 requests per model): 3 fixed invented cases (`swap01_dev_clinic_app`, `syn14_clinic_app_developer_negation`, `s2_06_media_student_campus_newsletter`), policy v3. Pass = valid JSON at both stages on the first attempt for all 3, and no trap shown as supported. Failed screens are reported, not retried silently.
2. **Development comparison** on the survivors plus the baseline: `synth_dev_v2` (32) + `swap_v1` (4) = 36 cases, one run each. Used only to find problems and drop clearly bad models. **No winner is chosen here.**
3. **Final comparison** on a new frozen held-out set `holdout_v5` (about 12 cases, written and hashed before any run, covering the weak spots found in stages 1 and 2) for the best 2 or 3 models, **3 repeat runs each**, to measure run-to-run variation.
4. **Report** all models side by side, including failures, with first attempts separate from retries.

## 4. Measures (decided now; no single composite score)
Hard gate: trap areas shown as supported must be 0 on `swap_v1` and `holdout_v5` (any model failing it is not eligible, whatever its other numbers). Then compare: expected supported areas found; top area in the expected set; correct abstention on no-support cases; overclaims (exploration-only shown as supported); industry-exposure items reaching exploration (should be 0); mean areas shown; **first-attempt failure rate** and invalid-JSON rate at each stage; consistency across the 3 repeats (same supported set in how many cases); requests, tokens and latency per case. Differences of one or two cases on about 12 are noise and must be reported as ties.

## 5. Budget (free tier, one account at 50 per day)
Screen about 36 requests (7 models), development about 3 models x 36 cases x 2.5 = 270, final about 3 models x 3 repeats x 12 cases x 2.5 = 270, plus retries: roughly **600 requests, about 12 account-days at 50 per day**, or about 1 day after a US$10 purchase (which is within the future US$10 ceiling the owner mentioned but **is not approved**). A smaller version (baseline plus 2 candidates) is about half that.

## 6. Rules
- Same pipeline code, prompts (v3), definitions v3 and regulated v2 for every model; the model id and provider are pinned with no fallbacks; each run gets a distinct `--label`; checkpoints and `--resume` are used for quota interruptions, and resumed or retried cases are marked as such.
- Invented text only; free endpoints may log prompts (`data_collection: allow`), recorded in each run.
- Do not edit labels or code after seeing a model's output; changes after seeing results retire the held-out set.
- Nothing here passes a review gate. Expectations are author-written and AI-assisted.

## 7. Open decisions for the owner
1. Approve the screen (about 36 requests) now, or wait for more quota?
2. Treat accounts 1 and 2 as one pooled free budget, with account 2 used only after account 1's limit?
3. Is a US$10 credit purchase (1,000 free requests per day, reported permanent) acceptable as a one-off, or must everything stay on the 50 per day limit? This is not assumed.
4. Which candidates to include or drop.
5. Whether a paid baseline (for example Haiku or Sonnet) is ever wanted; it stays blocked until approved.


## 8. Paid models: suitability first, cost estimated separately (research 2026-10-30; no paid call has been made)

### 8.1 What "most suitable" means for this pipeline (price ignored)
1. **Strict JSON that validates**, twice per case: extraction, then an assessment of all 94 areas (about 22,000 input tokens and a large structured output). The client sends a strict `json_schema` with `require_parameters`.
2. **Faithful evidence quotes.** Our verifier rejects any citation that is not an exact span of the CV, so paraphrasing models fail.
3. **Following negative rules**: industry is not profession, unfinished study is exploration, no neighbouring-area inference, abstain when evidence is thin.
4. **Stability across runs** (the free model failed about one case in four on first attempt and varied between runs).
5. **Data handling for later real CVs**: whether zero-data-retention is available matters. Claude Fable 5.1 is reported not to be available under zero data retention unless Anthropic authorises it; check every candidate before any real CV is ever sent. Today only invented text is used.
6. **Fit with later fine-tuning**: open-weight models (DeepSeek, Kimi, Qwen) can be a base or teacher for a smaller model; closed models can only act as teacher or judge, and their terms on training other models must be checked.

### 8.2 Candidate paid models and prices
Per million tokens, USD. **Anthropic prices were read today from Anthropic's pricing page; all other prices come from OpenRouter's listing or third-party aggregators that disagree on model names, so treat them as unverified and re-check on the provider page before any spend.**

| Model | Input | Output | Source | Why a candidate |
|---|---|---|---|---|
| Claude Fable 5.1 (`claude-fable-5-1`) | 10 | 50 | Anthropic page | Most capable widely released Claude; thinking always on; no ZDR unless authorised |
| Claude Opus 5.5 (`claude-opus-5-5`) | 4 | 20 | Anthropic page | Strong, cheaper than Fable; thinking cannot be disabled |
| Claude Opus 5 (`claude-opus-5`) | 5 | 25 | Anthropic page | Previous Opus; probably superseded by 5.5, low priority |
| Claude Sonnet 5.5 (`claude-sonnet-5-5`) | 2 | 10 | Anthropic page | Mid-tier everyday model |
| Claude Haiku 5.5 (`claude-haiku-5-5`) | 0.10 | 0.50 | Anthropic page (prompts up to 100K tokens) | Tests whether a small cheap model is enough; relevant to the later small-model plan |
| Claude Haiku 4.5 | 1 | 5 | Anthropic page | Previously used here (the earlier $0.16 spend); reference point |
| OpenAI GPT-6.1 Terra Pro | 1 | 5 | OpenRouter listing | Non-Anthropic strong model at moderate price |
| OpenAI GPT-6.1 Sol / GPT-6 Astra | 2 / 10 in, 10 / 50 out for Sol and Astra respectively as listed by aggregators | | aggregators (names conflict) | Top OpenAI tiers; confirm names and prices first |
| Moonshot Kimi K3.1 Pro | 2 | 10 | OpenRouter listing | Strong open-weight family |
| Google Gemini 3.1 Pro | 2 | 12 | aggregator | Strong long-context model |
| Google Gemini 3.5 Flash / 3.7 Flash | 1.50 / 0.75 | 9 / 3.75 | aggregator | Cheaper Gemini tiers |
| Qwen3.7 Max | 2.50 | 7.50 | aggregator | Open-weight family |
| DeepSeek V4 Pro / V4 Flash | 0.43 / 0.14 | 0.87 / 0.28 | aggregator | Very cheap, open weights, good teacher or base candidates |
| xAI Grok 4.7 | 2 | 6 | aggregator | Different vendor |

### 8.3 How the cost was estimated
- **Measured, from our saved runs (41 completed cases on the free Nemotron model):** about **1,140 input tokens** for extraction and **21,900** for assessment, so about **23,100 input tokens per case**. Output was about 7,000 (extraction) plus 12,700 (assessment) = **19,800 output tokens per case**, but that figure includes the hidden reasoning of a reasoning model.
- **Two output scenarios:** *lean* (a non-reasoning model writes only the JSON: about 1,500 + 7,000 = **8,500** tokens per case, my estimate, not measured) and *high* (the measured 19,800, a reasoning model). Real cost for each model lies somewhere in this range; Claude models with adaptive thinking would sit nearer the high end. Both include no caching and no retries.
- **Case-runs in the protocol:** 3 (screen) + 36 (development, one run each) + 36 (final: 12 held-out cases x 3 repeats) = **75 case-runs per model that goes all the way**.
- Cost per case = input tokens x input price + output tokens x output price. Anthropic's Batch API halves both prices, but it is asynchronous and does not suit retries, so batch is only a lower bound. Prompt caching of the shared 22,000-token definitions part could cut input cost further but is not assumed.

### 8.4 Estimated cost per model (USD; lean to high scenario)
| Model | Per case | Screen (3 cases) | Full path (75 case-runs) |
|---|---|---|---|
| Claude Fable 5.1 | 0.66 - 1.22 | 1.97 - 3.66 | **49 - 92** |
| Claude Opus 5.5 | 0.26 - 0.49 | 0.79 - 1.46 | **20 - 37** |
| Claude Opus 5 | 0.33 - 0.61 | 0.98 - 1.83 | 25 - 46 |
| Claude Sonnet 5.5 | 0.13 - 0.24 | 0.39 - 0.73 | **10 - 18** |
| Claude Haiku 5.5 | 0.007 - 0.012 | 0.02 - 0.04 | **0.5 - 0.9** |
| Claude Haiku 4.5 | 0.07 - 0.12 | 0.20 - 0.37 | 5 - 9 |
| GPT-6.1 Terra Pro | 0.07 - 0.12 | 0.20 - 0.37 | 5 - 9 |
| GPT-6.1 Sol (unverified, 2 / 10) | 0.13 - 0.24 | 0.39 - 0.73 | 10 - 18 |
| GPT-6 Astra (unverified, 10 / 50) | 0.66 - 1.22 | 1.97 - 3.66 | 49 - 92 |
| Kimi K3.1 Pro | 0.13 - 0.24 | 0.39 - 0.73 | 10 - 18 |
| Gemini 3.1 Pro | 0.15 - 0.28 | 0.44 - 0.85 | 11 - 21 |
| Gemini 3.5 Flash | 0.11 - 0.21 | 0.33 - 0.64 | 8 - 16 |
| Gemini 3.7 Flash | 0.05 - 0.09 | 0.15 - 0.27 | 4 - 7 |
| Qwen3.7 Max | 0.12 - 0.21 | 0.36 - 0.62 | 9 - 15 |
| DeepSeek V4 Pro | 0.017 - 0.027 | 0.05 - 0.08 | 1.3 - 2.0 |
| DeepSeek V4 Flash | 0.006 - 0.009 | 0.02 - 0.03 | 0.4 - 0.7 |
| Grok 4.7 | 0.10 - 0.17 | 0.29 - 0.49 | 7 - 12 |

### 8.5 Staged budget (what a sensible paid comparison costs)
| Tier | What it covers | Estimated cost |
|---|---|---|
| **A: Screen only** | 3 cases on about 9 paid models (Fable 5.1, Opus 5.5, Sonnet 5.5, Haiku 5.5, GPT-6.1 Terra Pro, GPT-6.1 Sol, Kimi K3.1 Pro, Gemini 3.1 Pro, DeepSeek V4 Pro) | **about $5 - $9**, within the earlier US$10 ceiling. The real token use and cost per call it records replace these estimates. |
| **B: Standard** | A, then the 36-case development set for 4 survivors (for example Opus 5.5, Sonnet 5.5, GPT-6.1 Sol, Gemini 3.1 Pro), then the held-out set with 3 repeats for the best 2 | about **$45 - $80** |
| **C: Full** | Every candidate above through all stages, including Fable 5.1 and Astra | about **$110 - $190** |

The US$10 ceiling the owner mentioned covers tier A only. None of this is approved.

### 8.6 Conclusions and recommendation
- Without regard to price, the most capable and therefore most likely suitable models are **Claude Fable 5.1**, **Claude Opus 5.5** and the top OpenAI, Google and Kimi models. Which is *actually* most suitable for this pipeline cannot be known from specifications: it needs the screen and the comparison, because quote faithfulness, JSON reliability and rule-following differ between models in ways the price list does not show.
- **Recommended path:** run tier A (about $5 to $9), read the measured cost and failure data, then decide on B with the real numbers. Include **Haiku 5.5** and **DeepSeek V4 Pro** in the screen even though they are cheap: if a small model passes the same hard gate, that shapes the fine-tuning plan.
- **Run the free-model comparison (sections 1-7) in parallel**, as a baseline; it costs nothing.
- Same hard gate for paid models: any trap area shown as supported on `swap_v1` or `holdout_v5` disqualifies a model whatever its other scores.

### 8.7 Caveats
Prices change; non-Anthropic prices and names are unverified; token counts for other models will differ from Nemotron's; the "lean" output figure is an estimate; model ids on OpenRouter (or on each provider's API) must be checked before use. Our client currently talks to OpenRouter, so a paid run needs OpenRouter credit (the same US$10 top-up that lifts the free limit, plus its fee) or a separate provider key. OpenRouter may log prompts depending on provider: only invented text may be used until data handling is cleared.

### 8.8 Decisions needed
1. Approve tier A (about $5 - $9), and how to pay for it (OpenRouter credit, which also raises the free limit, or a direct Anthropic key for the Claude models).
2. Confirm that tiers B and C need a separate, explicit approval and a budget ceiling.
3. Confirm the candidate list for the screen.

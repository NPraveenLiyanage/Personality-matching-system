# Privacy and model-routing requirements (v0.1)

Applies to every external model call (OpenRouter).

## Data rules
- **Synthetic data only** for external calls until written consent and a compliant endpoint exist.
- Real CVs, PersonaMap responses and `PERSONAMAP_RESPONSES_MASKED.xlsx` stay local. Their consent text covers professional development and research, aggregate reporting, and no third-party sharing without permission. External processing or training is not covered.
- Removing a name does not anonymise a CV. Redaction is a minimisation step, not anonymisation. Known gaps in the current `llm/payload.py`: employer/school/referee names, addresses, date of birth, non-ASCII names, short phone numbers.
- Real participant documents stay session-only (as in `app/common.py`). No durable store without a separate agreed design; hosted Streamlit disk is not durable.
- Inference consent and training consent are separate. Retained evaluation/feedback data needs an explicit consent, access and retention approach.
- Never print or commit API keys. `.env` and `.streamlit/secrets.toml` are git-ignored; a test checks that `.env` and `PERSONAMAP_*` files are untracked.
- Do not log full participant payloads. Log hashes, IDs, versions and usage.

## Request routing (controlled runs)
Per request, in the `provider` object: `only` (pinned provider slug), `allow_fallbacks: false`, `data_collection: "deny"`, `require_parameters: true`, `zdr: true` when zero retention is required, and `max_price` as a spending ceiling. Use `response_format` with `json_schema` (strict) where the endpoint supports it, and validate locally regardless. Field names were checked against OpenRouter docs on 2026-10-27; support varies per endpoint.
- No model fallback chain and no `openrouter/free` in controlled comparisons.
- Record the actual model and provider returned, request IDs, finish reason, usage, latency, and prompt/schema/catalogue versions.
- If no endpoint meets the requirements, **fail clearly**. Never relax privacy settings to get a free model working.
- Bounded retries and timeouts; per-run and per-day spend caps.
- Do not aggregate outputs from different models as if they were repeat runs.

## Unverified until Phase 4 (needs a key and a synthetic payload)
Current model IDs, context/output limits, pricing, rate limits, per-endpoint retention/training policies, structured-output support. The historical IDs (Nemotron free, Gemma free, `openrouter/free`) are configuration history, not recommendations. The Nemotron free endpoint previously warned against confidential or personal data.

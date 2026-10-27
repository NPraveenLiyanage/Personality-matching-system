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

## Observed on this account (2026-10-27)
- `zdr:true` with `anthropic/claude-haiku-5.5` pinned to provider `anthropic` returned HTTP 404 (no endpoint matched). The synthetic-only runs used `data_collection:deny` without ZDR. Real data must not be sent until a ZDR-capable pinned endpoint is confirmed or consent covers the provider's retention.
- Some models reject `temperature`; with `require_parameters:true` this 404s. Temperature is therefore omitted by default (`CAREERX_TEMPERATURE` to set it).
- The OpenRouter endpoint listing does not expose retention/training policy; confirm in the provider's terms and the account privacy settings.
- The API key was first pasted into the tracked `.env.example`; it now lives in the git-ignored `.env`. Rotate it when testing ends.
- Free endpoints: `data_collection: deny` yields HTTP 404 on free models (no endpoint matches). A synthetic-only run may set `CAREERX_DATA_COLLECTION=allow` / `--data-collection allow`; the setting is stored in the run metadata and defaults to `deny`. Never use it with real participant data.
- Second account: `OPENROUTER_API_KEY_2` in `.env` (git-ignored) is used only when account 1 returns 401 (invalid key) or 402 (out of credit). A 429 rate or daily limit is never answered by switching accounts. Run metadata records the account index (1 or 2), never the key.

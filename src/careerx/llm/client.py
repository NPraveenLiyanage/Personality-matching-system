"""OpenRouter chat client (free models). Reads its settings from the environment / a git-ignored .env file.

OPENROUTER_API_KEY          required
OPENROUTER_MODEL            default nvidia/nemotron-3-super-120b-a12b:free
OPENROUTER_FALLBACK_MODELS  comma list, default google/gemma-4-31b-it:free,openrouter/free
OPENROUTER_DENY_DATA_COLLECTION  "1" (default) asks OpenRouter to route only to providers that do not store prompts.
                            Some free models cannot honour this; set "0" if every model answers 404.
CAREERX_LLM_RUNS            default 3
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import requests

URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
DEFAULT_FALLBACKS = "google/gemma-4-31b-it:free,openrouter/free"


class LLMError(RuntimeError):
    pass


def load_env() -> None:
    """Load .env from the project root if python-dotenv is installed (real environment variables win)."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)


def settings() -> dict:
    load_env()
    fb = os.environ.get("OPENROUTER_FALLBACK_MODELS", DEFAULT_FALLBACKS)
    return dict(api_key=os.environ.get("OPENROUTER_API_KEY", "").strip(),
                model=os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL).strip(),
                fallbacks=[m.strip() for m in fb.split(",") if m.strip()],
                deny_collection=os.environ.get("OPENROUTER_DENY_DATA_COLLECTION", "1") != "0",
                runs=int(os.environ.get("CAREERX_LLM_RUNS", "3")))


def chat(system: str, user: str, cfg: dict | None = None, max_tokens: int = 12000, timeout: int = 240) -> str:
    """One completion, temperature 0, JSON mode. Tries the main model, then the fallbacks. Returns the text."""
    cfg = cfg or settings()
    if not cfg["api_key"]:
        raise LLMError("OPENROUTER_API_KEY is not set (add it to .env or the environment).")
    errors = []
    for model in [cfg["model"], *cfg["fallbacks"]]:
        body = {"model": model, "temperature": 0, "max_tokens": max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if cfg["deny_collection"]:
            body["provider"] = {"data_collection": "deny"}
        headers = {"Authorization": f"Bearer {cfg['api_key']}", "X-Title": "Calybrate Me career matching"}
        for attempt in range(3):
            try:
                r = requests.post(URL, json=body, headers=headers, timeout=timeout)
            except requests.RequestException as e:
                errors.append(f"{model}: {type(e).__name__}")
                time.sleep(3 * (attempt + 1))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                wait = float(r.headers.get("Retry-After", 0) or 0) or 8 * 2 ** attempt
                errors.append(f"{model}: HTTP {r.status_code}")
                time.sleep(min(wait, 60))
                continue
            if r.status_code != 200:
                errors.append(f"{model}: HTTP {r.status_code} {r.text[:160]}")
                break                                          # not retryable: next model
            try:
                text = r.json()["choices"][0]["message"].get("content") or ""
            except (KeyError, IndexError, ValueError):
                errors.append(f"{model}: unreadable response")
                break
            if text.strip():
                return text
            errors.append(f"{model}: empty answer")
            break
    raise LLMError("All models failed: " + " | ".join(errors[-6:]))

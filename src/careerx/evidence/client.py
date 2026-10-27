"""OpenRouter client for controlled runs: one pinned model and provider, no fallbacks, strict JSON Schema, full metadata.

Unlike `careerx.llm.client` there is no model chain and no relaxing of privacy settings. If the configuration is incomplete the
call fails with a clear error. Never log the payload.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import requests

from ..llm.client import load_env

URL = "https://openrouter.ai/api/v1/chat/completions"


class EvidenceLLMError(RuntimeError):
    pass


@dataclass
class ChatResult:
    content: str
    model: str | None = None
    provider: str | None = None
    request_id: str | None = None
    finish_reason: str | None = None
    usage: dict = field(default_factory=dict)
    latency_s: float = 0.0


def settings() -> dict:
    load_env()
    g = os.environ.get
    return dict(
        api_key=g("OPENROUTER_API_KEY", ""),
        model=g("CAREERX_EVIDENCE_MODEL", ""),
        provider=g("CAREERX_EVIDENCE_PROVIDER", ""),          # pinned provider slug
        require_zdr=g("CAREERX_REQUIRE_ZDR", "0") == "1",
        max_price=g("CAREERX_MAX_PRICE_PER_M", ""),           # USD per million tokens, applied to prompt and completion
        temperature=g("CAREERX_TEMPERATURE", ""),            # empty = omit; some models reject the parameter
        max_tokens=int(g("CAREERX_MAX_TOKENS", "8000")),
        timeout=int(g("CAREERX_TIMEOUT_S", "180")),
    )


def request_body(system: str, user: str, schema: dict, cfg: dict) -> dict:
    prov: dict = {"only": [cfg["provider"]], "allow_fallbacks": False, "data_collection": "deny",
                  "require_parameters": True}
    if cfg.get("require_zdr"):
        prov["zdr"] = True
    if cfg.get("max_price"):
        prov["max_price"] = {"prompt": float(cfg["max_price"]), "completion": float(cfg["max_price"])}
    body = {"model": cfg["model"], "max_tokens": cfg["max_tokens"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "evidence_v1", "strict": True, "schema": schema}},
            "provider": prov}
    if str(cfg.get("temperature", "")) != "":
        body["temperature"] = float(cfg["temperature"])
    return body


def chat(system: str, user: str, schema: dict, cfg: dict | None = None, attempts: int = 2) -> ChatResult:
    cfg = cfg or settings()
    if not cfg["api_key"]:
        raise EvidenceLLMError("OPENROUTER_API_KEY is not set.")
    if not cfg["model"] or not cfg["provider"]:
        raise EvidenceLLMError("Pin both CAREERX_EVIDENCE_MODEL and CAREERX_EVIDENCE_PROVIDER; controlled runs allow no fallback.")
    body = request_body(system, user, schema, cfg)
    last = ""
    for k in range(attempts):
        t0 = time.time()
        try:
            r = requests.post(URL, json=body, timeout=cfg["timeout"],
                              headers={"Authorization": f"Bearer {cfg['api_key']}", "X-Title": "careerx-evidence"})
        except requests.RequestException as e:
            last = f"network error: {type(e).__name__}"
            time.sleep(3 * (k + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            last = f"HTTP {r.status_code}"
            time.sleep(min(60, 8 * 2 ** k))
            continue
        if r.status_code != 200:
            raise EvidenceLLMError(f"HTTP {r.status_code}: {r.text[:160]} (no compliant endpoint? privacy settings are not relaxed)")
        try:
            j = r.json()
            ch = j["choices"][0]
            content = ch["message"]["content"] or ""
        except (KeyError, IndexError, ValueError) as e:
            raise EvidenceLLMError(f"unreadable response: {type(e).__name__}") from e
        return ChatResult(content=content, model=j.get("model"), provider=j.get("provider"), request_id=j.get("id"),
                          finish_reason=ch.get("finish_reason"), usage=j.get("usage") or {}, latency_s=round(time.time() - t0, 2))
    raise EvidenceLLMError(f"request failed after {attempts} attempts ({last})")

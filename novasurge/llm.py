"""
Minimal LLM client for the Chaos Planner agent.

Providers (both expose an OpenAI-compatible chat-completions endpoint, so one
code path serves both):
    groq    https://console.groq.com     default model llama-3.3-70b-versatile
    gemini  https://aistudio.google.com  default model gemini-2.5-flash

Configuration — environment variables, or KEY=VALUE lines in
NOVASURGE_HOME/llm.env (written by `python -m novasurge agent-key`; it lives
outside the repository so a key can never be committed):
    GROQ_API_KEY / GEMINI_API_KEY      the key
    NOVASURGE_LLM_PROVIDER             groq | gemini | none   (default: first provider with a key)
    NOVASURGE_LLM_MODEL                override the model
    NOVASURGE_LLM_DAILY_CAP            safety cap on calls per day (default 500)

The planner makes one call per campaign round. Every failure mode (no key,
timeout, rate limit, malformed answer) raises LLMUnavailable and the caller
falls back to its rule-based choice.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date

import httpx

from novasurge import config

PROVIDERS = {
    "groq": {"url": "https://api.groq.com/openai/v1/chat/completions",
             "model": "llama-3.3-70b-versatile", "key": "GROQ_API_KEY"},
    "gemini": {"url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
               "model": "gemini-2.5-flash", "key": "GEMINI_API_KEY"},
}
ENV_FILE = config.NOVASURGE_HOME / "llm.env"
TIMEOUT_S = 20.0


class LLMUnavailable(RuntimeError):
    pass


@dataclass
class LLMConfig:
    provider: str
    model: str
    url: str
    api_key: str
    daily_cap: int


def _file_env() -> dict[str, str]:
    out = {}
    try:
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    except OSError:
        pass
    return out


def _get(name: str, file_env: dict[str, str]) -> str | None:
    return os.environ.get(name) or file_env.get(name)


def load_config() -> LLMConfig | None:
    env = _file_env()
    provider = (_get("NOVASURGE_LLM_PROVIDER", env) or "").lower()
    if provider == "none":
        return None
    candidates = [provider] if provider in PROVIDERS else [p for p in PROVIDERS if _get(PROVIDERS[p]["key"], env)]
    for p in candidates:
        key = _get(PROVIDERS[p]["key"], env)
        if key:
            return LLMConfig(provider=p, model=_get("NOVASURGE_LLM_MODEL", env) or PROVIDERS[p]["model"],
                             url=PROVIDERS[p]["url"], api_key=key,
                             daily_cap=int(_get("NOVASURGE_LLM_DAILY_CAP", env) or 500))
    return None


def save_key(provider: str, key: str) -> None:
    """Store a key in NOVASURGE_HOME/llm.env (outside the repo)."""
    env = _file_env()
    env[PROVIDERS[provider]["key"]] = key.strip()
    env["NOVASURGE_LLM_PROVIDER"] = provider
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("".join(f"{k}={v}\n" for k, v in env.items()), encoding="utf-8")


def usage_today() -> int:
    from novasurge import state_db
    return int(state_db.kv_get("llm_usage", {}).get(date.today().isoformat(), 0))


def _count_call() -> None:
    from novasurge import state_db
    usage = state_db.kv_get("llm_usage", {})
    today = date.today().isoformat()
    state_db.kv_set("llm_usage", {today: int(usage.get(today, 0)) + 1})


def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)     # tolerate ```json fences / prose
        if m:
            return json.loads(m.group(0))
        raise


def chat_json(system: str, user: str, cfg: LLMConfig | None = None, max_tokens: int = 300) -> tuple[dict, str]:
    """One chat completion that must return a JSON object. Returns (object, 'provider/model')."""
    cfg = cfg or load_config()
    if cfg is None:
        raise LLMUnavailable("no LLM API key configured")
    if usage_today() >= cfg.daily_cap:
        raise LLMUnavailable(f"daily LLM call cap reached ({cfg.daily_cap})")
    body = {
        "model": cfg.model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    try:
        _count_call()
        resp = httpx.post(cfg.url, json=body, headers=headers, timeout=TIMEOUT_S)
        if resp.status_code == 400 and "response_format" in resp.text:
            body.pop("response_format")
            resp = httpx.post(cfg.url, json=body, headers=headers, timeout=TIMEOUT_S)
    except httpx.HTTPError as exc:
        raise LLMUnavailable(f"{cfg.provider} unreachable: {type(exc).__name__}") from exc
    if resp.status_code == 429:
        raise LLMUnavailable(f"{cfg.provider} rate limit reached (HTTP 429)")
    if resp.status_code in (401, 403):
        raise LLMUnavailable(f"{cfg.provider} rejected the API key (HTTP {resp.status_code})")
    if resp.status_code != 200:
        raise LLMUnavailable(f"{cfg.provider} returned HTTP {resp.status_code}: {resp.text[:160]}")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
        return _parse_json(content), f"{cfg.provider}/{cfg.model}"
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise LLMUnavailable(f"{cfg.provider} returned an unparseable answer") from exc

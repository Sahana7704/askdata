"""Thin LLM abstraction so the agent is provider-agnostic and testable."""
from __future__ import annotations

import re
import time
from typing import Protocol

from .config import get_settings


class LLMNotConfigured(RuntimeError):
    pass


class LLM(Protocol):
    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str: ...


class AnthropicLLM:
    def __init__(self, api_key: str | None = None, model: str | None = None):
        s = get_settings()
        key = api_key or s.anthropic_api_key
        if not key:
            raise LLMNotConfigured("ASKDATA_ANTHROPIC_API_KEY is not set")
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model or s.model
        self.max_tokens = s.llm_max_tokens
        self._send_temperature = True

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        kwargs = dict(model=self.model, max_tokens=max_tokens or self.max_tokens, system=system,
                      messages=[{"role": "user", "content": user}])
        try:
            resp = self.client.messages.create(**kwargs, **({"temperature": 0} if self._send_temperature else {}))
        except self._anthropic.BadRequestError as e:
            # some models do not accept an explicit temperature; retry once without it
            if self._send_temperature and "temperature" in str(e).lower():
                self._send_temperature = False
                resp = self.client.messages.create(**kwargs)
            else:
                raise
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


class GeminiLLM:
    """Google Gemini via its REST API (free tier available from Google AI Studio)."""

    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        s = get_settings()
        key = api_key or s.gemini_api_key
        if not key:
            raise LLMNotConfigured("ASKDATA_GEMINI_API_KEY is not set")
        import httpx

        self._httpx = httpx
        self.client = httpx.Client(timeout=httpx.Timeout(60, connect=10), headers={"x-goog-api-key": key})
        self.model = model or s.gemini_model
        # used when the main model is overloaded (free-tier 503s are common) or times out
        self.fallback_model = s.gemini_fallback_model if not model else ""
        self.max_tokens = s.llm_max_tokens

    def complete(self, system: str, user: str, max_tokens: int | None = None) -> str:
        # Thinking models spend part of maxOutputTokens on reasoning, so leave headroom.
        budget = max(8192, 4 * (max_tokens or self.max_tokens))
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": budget},
        }
        models = [self.model] + ([self.fallback_model] if self.fallback_model and self.fallback_model != self.model else [])
        for i, model in enumerate(models):
            last = i == len(models) - 1
            try:
                # don't wait long on the main model when a fallback exists
                resp = self._post(model, body, retries=3 if last else 0, timeout=60 if last else 30)
            except self._httpx.TimeoutException:
                if last:
                    raise RuntimeError(f"Gemini model {model} timed out") from None
                continue
            if resp.status_code in (429, 500, 503) and not last:
                continue  # overloaded / rate limited: try the fallback model
            break
        if resp.status_code != 200:
            try:
                msg = resp.json()["error"]["message"]
            except Exception:
                msg = resp.text[:300]
            raise RuntimeError(f"Gemini API error {resp.status_code}: {msg}")
        data = resp.json()
        cands = data.get("candidates") or []
        if not cands:
            raise RuntimeError(f"Gemini returned no answer: {data.get('promptFeedback', data)}")
        parts = (cands[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()


    def _post(self, model: str, body: dict, retries: int, timeout: float = 60):
        url = self.URL.format(model=model)
        for attempt in range(retries + 1):
            resp = self.client.post(url, json=body, timeout=timeout)
            # free tier is rate limited: back off and retry on 429 / transient 5xx
            if resp.status_code in (429, 500, 503) and attempt < retries:
                time.sleep(_retry_delay(resp, default=3 * (attempt + 1)))
                continue
            return resp
        return resp


def _retry_delay(resp, default: float) -> float:
    try:
        for d in resp.json()["error"].get("details", []):
            if "retryDelay" in d:
                return min(60.0, float(str(d["retryDelay"]).rstrip("s")) + 1)
    except Exception:
        pass
    return default


_SQL_BLOCK = re.compile(r"```(?:sql|postgresql|postgres)?\s*(.*?)```", re.S | re.I)


def extract_sql(text: str) -> tuple[str | None, str | None]:
    """Return (sql, cannot_answer_reason). Exactly one of them is non-None on success."""
    t = (text or "").strip()
    m = re.search(r"CANNOT_ANSWER:\s*(.+)", t, re.S)
    if m and not _SQL_BLOCK.search(t):
        return None, m.group(1).strip().splitlines()[0]
    b = _SQL_BLOCK.search(t)
    if b:
        # a language tag the fence regex missed ("``` sql", "```\nsql\n") must not end up in the query
        inner = re.sub(r"(?i)^(?:sql|postgresql|postgres)\b\s*", "", b.group(1).strip())
        # some models wrap the refusal itself in a code block
        c = re.match(r"CANNOT_ANSWER:\s*(.+)", inner, re.S)
        if c:
            return None, c.group(1).strip().splitlines()[0]
        return inner, None
    if re.match(r"(?is)^\s*(with|select)\b", t):
        return t, None
    return None, None


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = GeminiLLM() if get_settings().active_provider == "gemini" else AnthropicLLM()
    return _llm


def llm_status() -> dict:
    s = get_settings()
    return {"configured": s.llm_configured, "model": s.active_model, "provider": s.active_provider}

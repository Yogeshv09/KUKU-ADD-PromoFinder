"""Model-agnostic LLM client. Swap models with env vars / CLI flags only.

Providers
  none        -> rules only (default, free, offline)
  openai      -> any OpenAI-compatible /chat/completions endpoint:
                 Gemini (free tier), Groq (free tier), OpenRouter, Ollama (local), OpenAI, vLLM ...
  anthropic   -> Anthropic Messages API
  mock        -> offline fake used by tests to exercise the full LLM code path

Env vars: LLM_PROVIDER, LLM_MODEL, LLM_BASE_URL, LLM_API_KEY
Presets (LLM_PROVIDER=gemini|groq|ollama|openrouter) fill in base URL + a default model.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

PRESETS = {
    "gemini": ("openai", "https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash", "GEMINI_API_KEY"),
    "groq": ("openai", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", "GROQ_API_KEY"),
    "openrouter": ("openai", "https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free", "OPENROUTER_API_KEY"),
    "ollama": ("openai", "http://localhost:11434/v1", "qwen2.5:7b-instruct", None),
    "openai": ("openai", "https://api.openai.com/v1", "gpt-4o-mini", "OPENAI_API_KEY"),
    "anthropic": ("anthropic", "https://api.anthropic.com/v1", "claude-haiku-4-5", "ANTHROPIC_API_KEY"),
}


class LLM:
    def __init__(self, provider: str | None = None, model: str | None = None, base_url: str | None = None,
                 api_key: str | None = None, cache_dir: str | None = ".llm_cache", temperature: float = 0.2):
        provider = (provider or os.getenv("LLM_PROVIDER") or "none").lower()
        self.name = provider
        kind, url, mdl, key_env = PRESETS.get(provider, (provider, None, None, None))
        self.kind = kind
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or url or "").rstrip("/")
        self.model = model or os.getenv("LLM_MODEL") or mdl or ""
        self.api_key = api_key or os.getenv("LLM_API_KEY") or (os.getenv(key_env) if key_env else None) or ""
        self.temperature = temperature
        self.cache = Path(cache_dir) if cache_dir else None
        if self.cache:
            self.cache.mkdir(parents=True, exist_ok=True)
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0

    @property
    def enabled(self) -> bool:
        return self.kind not in ("none", "")

    def describe(self) -> str:
        return "rules-only" if not self.enabled else f"{self.name}:{self.model}"

    # ------------------------------------------------------------------
    def chat_json(self, system: str, user: str, retries: int = 3) -> dict:
        key = hashlib.sha256(f"{self.describe()}|{system}|{user}".encode()).hexdigest()[:24]
        if self.cache and (self.cache / f"{key}.json").exists():
            return json.loads((self.cache / f"{key}.json").read_text())
        last = None
        for attempt in range(retries):
            try:
                text = self._call(system, user)
                data = parse_json(text)
                if self.cache:
                    (self.cache / f"{key}.json").write_text(json.dumps(data, indent=1))
                return data
            except Exception as e:  # network / rate limit / bad JSON -> back off and retry
                last = e
                time.sleep(2 ** attempt * 2)
        raise RuntimeError(f"LLM call failed after {retries} tries: {last}")

    def _call(self, system: str, user: str) -> str:
        self.calls += 1
        if self.kind == "mock":
            return mock_response(user)
        if self.kind == "openai":
            body = {"model": self.model, "temperature": self.temperature,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
            hdr = {"Content-Type": "application/json"}
            if self.api_key:
                hdr["Authorization"] = f"Bearer {self.api_key}"
            out = _post(f"{self.base_url}/chat/completions", body, hdr)
            u = out.get("usage") or {}
            self.tokens_in += u.get("prompt_tokens", 0)
            self.tokens_out += u.get("completion_tokens", 0)
            return out["choices"][0]["message"]["content"]
        if self.kind == "anthropic":
            body = {"model": self.model, "max_tokens": 1200, "temperature": self.temperature, "system": system,
                    "messages": [{"role": "user", "content": user}]}
            hdr = {"Content-Type": "application/json", "x-api-key": self.api_key, "anthropic-version": "2023-06-01"}
            out = _post(f"{self.base_url}/messages", body, hdr)
            u = out.get("usage") or {}
            self.tokens_in += u.get("input_tokens", 0)
            self.tokens_out += u.get("output_tokens", 0)
            return "".join(b.get("text", "") for b in out["content"])
        raise ValueError(f"Unknown LLM provider '{self.name}'")


def _post(url: str, body: dict, headers: dict, timeout: int = 90) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:300]}") from e


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def mock_response(user: str) -> str:
    """Deterministic stand-in: keeps the proposed cut, echoes first/last line IDs."""
    ids = re.findall(r"^\[(E\d+-\d+)\]\s+IN", user, re.M)
    return json.dumps({"hook_score": 7, "cliff_score": 7, "standalone_score": 7,
                       "start_id": ids[0] if ids else None, "end_id": ids[-1] if ids else None,
                       "hook": "mock hook", "cliffhanger": "mock cliffhanger", "why": "mock why",
                       "issues": []})

"""Chat-style LLM interface with tool calling, plus the Gemini adapter.

Messages use a small neutral format so agents can be tested with a scripted fake:
  {"role": "user", "text": str}
  {"role": "model", "text": str | None, "calls": [{"name", "args"}], "raw": <provider content, optional>}
  {"role": "tool", "results": [{"name", "result"}]}
Gemini 3 models attach "thought signatures" to function calls, so the adapter keeps the provider's own
content object in "raw" and sends it back unchanged.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Protocol

log = logging.getLogger("absorb.llm")
RETRY_STATUS = {429, 500, 503, 504}


class ChatLLM(Protocol):
    model: str

    def step(self, *, system: str, messages: list[dict], tools: list[dict] | None,
             temperature: float = 0.2) -> dict: ...

    def structured(self, *, system: str, prompt: str, schema, temperature: float = 0.2): ...


class GeminiChat:
    def __init__(self, api_key: str | None = None, model: str | None = None, fallback_model: str | None = None,
                 attempts: int = 3, base_delay_s: float = 2.0):
        from google import genai
        from google.genai import types

        from api.agents.gemini_client import DEFAULT_FALLBACK, DEFAULT_MODEL, REQUEST_TIMEOUT_MS

        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.model = model or os.environ.get("GEMINI_MODEL") or DEFAULT_MODEL
        self.fallback_model = fallback_model or os.environ.get("GEMINI_FALLBACK_MODEL") or DEFAULT_FALLBACK
        self.attempts, self.base_delay_s = attempts, base_delay_s
        self._types = types
        self._client = genai.Client(api_key=key, http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)))

    # ------------------------------------------------------------------ helpers
    def _with_retry(self, fn):
        from google.genai import errors

        models = [self.model] + ([self.fallback_model] if self.fallback_model != self.model else [])
        last = None
        for i, model in enumerate(models):
            for attempt in range(self.attempts):
                try:
                    return fn(model)
                except errors.APIError as e:
                    last = e
                    if getattr(e, "code", None) not in RETRY_STATUS:
                        raise
                    log.warning("Gemini %s returned %s (attempt %d)", model, e.code, attempt + 1)
                    if attempt + 1 < self.attempts:
                        time.sleep(self.base_delay_s * 2 ** attempt)
            # Tool-calling history carries model-specific signatures, so only plain prompts may switch model.
            if i == 0 and getattr(fn, "pinned", False):
                break
        raise last

    def _contents(self, messages: list[dict]):
        t = self._types
        out = []
        for m in messages:
            if m["role"] == "user":
                out.append(t.Content(role="user", parts=[t.Part(text=m["text"])]))
            elif m["role"] == "model":
                if m.get("raw") is not None:
                    out.append(m["raw"])
                else:
                    parts = [t.Part(text=m["text"])] if m.get("text") else []
                    parts += [t.Part(function_call=t.FunctionCall(name=c["name"], args=c["args"])) for c in m.get("calls", [])]
                    out.append(t.Content(role="model", parts=parts))
            elif m["role"] == "tool":
                out.append(t.Content(role="user", parts=[
                    t.Part.from_function_response(name=r["name"], response={"result": r["result"]}) for r in m["results"]]))
        return out

    # ------------------------------------------------------------------ interface
    def step(self, *, system: str, messages: list[dict], tools: list[dict] | None, temperature: float = 0.2) -> dict:
        t = self._types
        cfg = t.GenerateContentConfig(
            system_instruction=system, temperature=temperature,
            tools=[t.Tool(function_declarations=[
                t.FunctionDeclaration(name=s["name"], description=s["description"], parameters_json_schema=s["parameters"])
                for s in tools])] if tools else None,
            automatic_function_calling=t.AutomaticFunctionCallingConfig(disable=True),
        )
        contents = self._contents(messages)
        has_history_calls = any(m["role"] == "model" and m.get("raw") is not None for m in messages)

        def call(model):
            return self._client.models.generate_content(model=model, contents=contents, config=cfg)
        call.pinned = has_history_calls

        resp = self._with_retry(call)
        calls = [{"name": fc.name, "args": dict(fc.args or {})} for fc in (resp.function_calls or [])]
        raw = resp.candidates[0].content if resp.candidates else None
        # Read text parts directly (resp.text warns when the reply also contains function calls).
        text = "".join(p.text for p in (raw.parts or []) if getattr(p, "text", None) and not getattr(p, "thought", False)) \
            if raw is not None else None
        return {"text": (text or "").strip() or None, "calls": calls, "raw": raw}

    def structured(self, *, system: str, prompt: str, schema, temperature: float = 0.2):
        t = self._types
        cfg = t.GenerateContentConfig(system_instruction=system, temperature=temperature,
                                      response_mime_type="application/json", response_schema=schema)

        def call(model):
            return self._client.models.generate_content(model=model, contents=prompt, config=cfg)

        resp = self._with_retry(call)
        return resp.parsed if getattr(resp, "parsed", None) is not None else schema.model_validate_json(resp.text)

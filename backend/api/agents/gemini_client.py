"""Thin wrapper around the Gemini API so the intake pipeline can be tested with a fake client.

Handles temporary overload: retries 429/500/503 with exponential back-off, then tries GEMINI_FALLBACK_MODEL
(if set) before giving up.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_FALLBACK = "gemini-3.1-flash-lite"
REQUEST_TIMEOUT_MS = 60_000
RETRY_STATUS = {429, 500, 503, 504}
log = logging.getLogger("absorb.gemini")


class JsonModel(Protocol):
    def generate(self, *, system: str, prompt: str, schema: type[T], image: bytes | None = None,
                 mime_type: str = "image/jpeg", temperature: float = 0.2) -> T: ...


class GeminiClient:
    """Calls Gemini with structured (JSON schema) output and parses it into a Pydantic model."""

    def __init__(self, api_key: str | None = None, model: str | None = None, fallback_model: str | None = None,
                 attempts: int = 4, base_delay_s: float = 2.0):
        from google import genai  # imported lazily so tests do not need the SDK configured

        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set (see backend/.env.example)")
        self.model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)
        self.fallback_model = fallback_model or os.environ.get("GEMINI_FALLBACK_MODEL") or DEFAULT_FALLBACK
        self.attempts, self.base_delay_s = attempts, base_delay_s
        self.last_model_used: str | None = None
        from google.genai import types

        # SDK retries off: our loop below retries visibly and can switch to the fallback model.
        self._client = genai.Client(api_key=key, http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)))

    def _call(self, model: str, system: str, prompt: str, schema: type[T], image: bytes | None,
              mime_type: str, temperature: float) -> T:
        from google.genai import types

        parts = []
        if image is not None:
            parts.append(types.Part.from_bytes(data=image, mime_type=mime_type))
        parts.append(prompt)
        resp = self._client.models.generate_content(
            model=model,
            contents=parts,
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=temperature,
            ),
        )
        self.last_model_used = model
        if getattr(resp, "parsed", None) is not None:
            return resp.parsed
        return schema.model_validate_json(resp.text)

    def generate(self, *, system: str, prompt: str, schema: type[T], image: bytes | None = None,
                 mime_type: str = "image/jpeg", temperature: float = 0.2) -> T:
        from google.genai import errors

        models = [self.model] + ([self.fallback_model] if self.fallback_model and self.fallback_model != self.model else [])
        last: Exception | None = None
        for model in models:
            for attempt in range(self.attempts):
                try:
                    return self._call(model, system, prompt, schema, image, mime_type, temperature)
                except errors.APIError as e:
                    last = e
                    if getattr(e, "code", None) not in RETRY_STATUS:
                        raise
                    delay = self.base_delay_s * (2 ** attempt)
                    log.warning("Gemini %s returned %s; retry %d/%d in %.0fs", model, e.code, attempt + 1,
                                self.attempts, delay)
                    if attempt + 1 < self.attempts:
                        time.sleep(delay)
            log.warning("Gemini %s still unavailable; %s", model, "trying fallback" if model != models[-1] else "giving up")
        assert last is not None
        raise last

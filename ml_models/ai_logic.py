import json
from typing import Any

from google import genai
from google.genai import types

import logging
import time

import httpx
from google.genai import errors as genai_errors

from app.config import (
    API_KEY_GEMINI,
    GEMINI_TIMEOUT_SECONDS,
    GEMINI_TOTAL_BUDGET_SECONDS,
    MODEL,
    MODEL_COOLDOWN_SECONDS,
    MODEL_FALLBACKS,
)

logger = logging.getLogger(__name__)


client = genai.Client(api_key=API_KEY_GEMINI)


SYSTEM_INSTRUCTION = (
    "You are Clarity, an AI that returns pollution-related explanations "
    "in strict JSON format with keys: object, causes, effects. "
    "Always use less words, and use simpler and understandable words. "
    "Always assume pollutant units as:\n"
    "- CO: ppb\n"
    "- NO2: ppb\n"
    "- O3: µg/m³\n"
    "- PM10: µg/m³\n"
    "- PM2.5: µg/m³"
)


# model name -> monotonic time before which it is skipped (it hit its quota)
_cooldown_until: dict[str, float] = {}


def _models() -> list[str]:
    seen: list[str] = []
    for m in [MODEL, *MODEL_FALLBACKS]:
        if m and m not in seen:
            seen.append(m)
    return seen


def _should_fall_back(exc: Exception) -> bool:
    """True when another model could succeed where this one failed."""
    if isinstance(exc, (httpx.TransportError, TimeoutError)):
        return True
    if isinstance(exc, genai_errors.APIError):
        code = exc.code or 0
        # 404: model retired; 408/429: timeout/quota; 5xx: Google-side failure.
        return code in (404, 408, 429) or code >= 500
    return False


def _call_model(model, prompt, system_instruction, timeout_s):
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            ),
        ],
        config=types.GenerateContentConfig(
            system_instruction=system_instruction or SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            # The SDK takes the timeout in milliseconds.
            http_options=types.HttpOptions(timeout=int(timeout_s * 1000)),
        ),
    )
    return response.text


def ask_gemini(
    prompt: str,
    system_instruction: str | None = None,
) -> dict[str, Any]:
    """Send ``prompt`` to Gemini and return the parsed JSON reply.

    Tries ``MODEL`` then each ``MODEL_FALLBACKS`` entry. A model that fails with
    a quota, server, timeout, connection or not-found error is skipped in
    favour of the next; a model that hit its quota (429) is skipped for
    ``MODEL_COOLDOWN_SECONDS``. Other errors (bad request, bad key) are raised
    at once. If every model fails, the last error is raised. The whole call is
    bounded by ``GEMINI_TOTAL_BUDGET_SECONDS``.

    ``system_instruction`` replaces the default instruction for this call only.
    """
    models = _models()
    now = time.monotonic()
    ready = [m for m in models if _cooldown_until.get(m, 0) <= now]
    # If every model is cooling down, still try them all rather than fail blind.
    candidates = ready or models
    deadline = now + GEMINI_TOTAL_BUDGET_SECONDS
    last_exc: Exception | None = None
    content = None

    for model in candidates:
        remaining = deadline - time.monotonic()
        if remaining <= 1 and last_exc is not None:
            break
        timeout_s = max(1.0, min(GEMINI_TIMEOUT_SECONDS, remaining))
        try:
            content = _call_model(model, prompt, system_instruction, timeout_s)
        except Exception as exc:
            if not _should_fall_back(exc):
                raise
            last_exc = exc
            if getattr(exc, "code", None) == 429:
                _cooldown_until[model] = time.monotonic() + MODEL_COOLDOWN_SECONDS
            logger.warning("Gemini model %s failed (%s); trying next", model, type(exc).__name__)
            continue
        if model != models[0]:
            logger.info("Gemini answered with fallback model %s", model)
        break
    else:
        assert last_exc is not None
        raise last_exc

    if content is None:
        assert last_exc is not None
        raise last_exc

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {
            "error": "Failed to parse AI response as JSON",
            "raw_output": content,
        }

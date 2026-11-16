"""Policy impact analysis for /predict_policy.

NOTE: healthcare savings, quality-of-life gain and life-expectancy gain remain ungrounded model output and are disabled by default (config.SHOW_UNSOURCED_HEALTH_OUTPUTS).

Asks Gemini for the estimated impact of a policy, validates the reply against
``EstimatedImpact``, retries once with the validation errors if it fails, and
raises ``PolicyModelError`` if the second attempt also fails.

This module does not import FastAPI. ``analyse_policy`` takes the model call as
a parameter so tests can replace it.
"""

import json
import logging
from typing import Any, Callable

from pydantic import ValidationError

from app import config as app_config
from app.data.state_population import get_state_population
from app.services.health_impact import respiratory_impact
from app.errors import UnknownStateError  # noqa: F401  (re-exported for callers)
from app.models.datamodel1 import (
    UNSOURCED_HEALTH_FIELDS,
    EstimatedImpact,
    MeasuredConditions,
    PopulationFacts,
    PollutantReadings,
    PolicyAnalysisResponse,
    PredictPolicyRequest,
)
from ml_models.ai_logic import ask_gemini
from ml_models.utils import calculate_overall_aqi

logger = logging.getLogger("app.policy_impact")

_LOG_REPLY_CHARS = 1000
_MAX_ERRORS_IN_RETRY_PROMPT = 10
_MAX_ERRORS_IN_DETAIL = 5
_ATTEMPTS = 2

POLICY_SYSTEM_INSTRUCTION = (
    "You are Clarity, an AI that estimates the effect of pollution-control "
    "policies in India. Reply with exactly one JSON object and no other text. "
    "Every pollutant concentration, in the input and in your reply, is in "
    "micrograms per cubic metre (ug/m3). Use plain numbers, never strings with "
    "units. These are planning estimates, not measurements."
)


class PolicyModelError(Exception):
    """The model could not produce a valid analysis after the allowed attempts."""

    def __init__(self, error_class: str, detail: str):
        super().__init__(f"{error_class}: {detail}")
        self.error_class = error_class
        self.detail = detail


# Keys the model may still send out of habit. They are dropped, never trusted.
_POPULATION_KEYS = (
    "total_population",
    "urban_percent",
    "rural_percent",
    "respiratory_cases_reduction_percent",  # now server-derived, never trusted
)


def _prompt_schema(include_unsourced: bool) -> dict:
    """EstimatedImpact's JSON Schema as the model should see it.

    The ``*_unsourced`` flags are server-set, so they are never shown. The three
    ungrounded health fields are shown (and required) only when
    ``include_unsourced`` is true.
    """
    schema = EstimatedImpact.model_json_schema()
    props = schema["properties"]
    required = schema["required"]
    for name in UNSOURCED_HEALTH_FIELDS:
        props.pop(f"{name}_unsourced", None)
        if include_unsourced:
            # Optional in the model, but required of the model when shown.
            branches = [b for b in props[name].get("anyOf", []) if b.get("type") != "null"]
            props[name] = {**props[name], **(branches[0] if branches else {})}
            props[name].pop("anyOf", None)
            props[name].pop("default", None)
            required.append(name)
        else:
            props.pop(name, None)
    return schema


def build_prompt(
    request: PredictPolicyRequest,
    aqi: int,
    population: dict,
    include_unsourced: bool = False,
) -> str:
    """Prompt for the first attempt.

    The schema is generated from ``EstimatedImpact`` so the prompt and the
    validator cannot drift apart.
    """
    schema = json.dumps(_prompt_schema(include_unsourced), indent=1)
    unsourced_units = (
        "healthcare_savings_crore_per_year is rupees crore per year;\n"
        "life_expectancy_gain_years is years; "
        if include_unsourced
        else ""
    )
    return f"""Estimate the likely impact of this pollution policy.

Policy: {request.policy}
Location: {request.location}
Current AQI: {aqi}

Fixed facts about {request.location} (Census {population["year"]}). Population: {population["population"]}, urban {population["urban_pct"]}%, rural {population["rural_pct"]}% — do not change these, and do not include population or urban/rural fields in your reply.

Current pollutant levels (ug/m3):
- PM2.5: {request.pm25}
- PM10: {request.pm10}
- NO2: {request.no2}
- O3: {request.o3}
- CO: {request.co}

Return one JSON object that matches this JSON Schema exactly. Every field is
required. Units: estimated_cost_crore is rupees crore;
{unsourced_units}new_pollutants are ug/m3 after the policy;
total_benefited is a head count of people in {request.location} who benefit and
must not exceed the fixed population above.

{schema}
"""


def _clean_reply(reply: dict, show_unsourced: bool) -> dict:
    """Drop what the server owns; mark what the server does not trust."""
    drop = set(_POPULATION_KEYS)
    drop.update(f"{n}_unsourced" for n in UNSOURCED_HEALTH_FIELDS)  # server-set
    if not show_unsourced:
        drop.update(UNSOURCED_HEALTH_FIELDS)
    out = {k: v for k, v in reply.items() if k not in drop}
    if show_unsourced:
        for name in UNSOURCED_HEALTH_FIELDS:
            if out.get(name) is not None:
                out[f"{name}_unsourced"] = True
    return out


def build_retry_prompt(prompt: str, errors: list[str]) -> str:
    """The original prompt plus why the last reply was rejected.

    The rejected reply itself is deliberately not repeated.
    """
    lines = "\n".join(f"- {e}" for e in errors[:_MAX_ERRORS_IN_RETRY_PROMPT])
    return (
        f"{prompt}\n"
        "Your previous reply was rejected for these reasons:\n"
        f"{lines}\n"
        "Return the full corrected JSON object only."
    )


def _format_errors(exc: ValidationError) -> list[str]:
    out = []
    for err in exc.errors():
        path = ".".join(str(part) for part in err["loc"]) or "(reply)"
        out.append(f"{path}: {err['msg']}")
    return out


def _reply_excerpt(reply: Any) -> str:
    if isinstance(reply, dict) and "raw_output" in reply:
        text = str(reply["raw_output"])
    else:
        try:
            text = json.dumps(reply, default=str)
        except (TypeError, ValueError):
            text = repr(reply)
    return text[:_LOG_REPLY_CHARS]


def analyse_policy(
    request: PredictPolicyRequest,
    ask: Callable[..., Any] | None = None,
) -> PolicyAnalysisResponse:
    """Run the analysis. Raises ``PolicyModelError`` after two failed attempts.

    ``ask`` defaults to ``ask_gemini``, looked up at call time so tests can
    replace either the argument or the module attribute.
    """
    ask = ask or ask_gemini
    aqi = calculate_overall_aqi(
        request.pm25, request.pm10, request.no2, request.co, request.o3
    )
    if aqi is None:  # unreachable: the request model only admits finite numbers
        raise ValueError("AQI could not be computed from the request")

    # Raises UnknownStateError before any model call is made.
    table = get_state_population(request.location)
    population = PopulationFacts(
        total_population=table["population"],
        urban_percent=table["urban_pct"],
        rural_percent=table["rural_pct"],
        source=table["source"],
        year=table["year"],
    )

    measured = MeasuredConditions(
        location=request.location,
        population=population,
        aqi=aqi,
        pollutants=PollutantReadings(
            pm25=request.pm25,
            pm10=request.pm10,
            no2=request.no2,
            o3=request.o3,
            co=request.co,
        ),
    )

    show_unsourced = app_config.SHOW_UNSOURCED_HEALTH_OUTPUTS
    first_prompt = build_prompt(request, aqi, table, show_unsourced)
    prompt = first_prompt
    error_class = "model_reply_invalid"
    errors: list[str] = []

    for attempt in range(1, _ATTEMPTS + 1):
        reply: Any = None
        try:
            reply = ask(prompt, system_instruction=POLICY_SYSTEM_INSTRUCTION)
        except Exception as exc:  # network, quota, timeout: all "unavailable"
            error_class = "model_unavailable"
            errors = [f"The model request failed ({type(exc).__name__})."]
            reply_for_log = f"<exception {type(exc).__name__}>"
            retry_errors: list[str] = []  # nothing to tell the model
        else:
            if isinstance(reply, dict) and "error" in reply and "raw_output" in reply:
                error_class = "model_reply_not_json"
                errors = ["The model's reply was not valid JSON."]
                reply_for_log = _reply_excerpt(reply)
                retry_errors = errors
            else:
                try:
                    if isinstance(reply, dict):
                        # The model's population numbers are discarded.
                        reply = _clean_reply(reply, show_unsourced)
                    estimated = EstimatedImpact.model_validate(
                        reply,
                        context={
                            "total_population": population.total_population,
                            "require_unsourced": show_unsourced,
                        },
                    )
                except ValidationError as exc:
                    error_class = "model_reply_invalid"
                    errors = _format_errors(exc)
                    reply_for_log = _reply_excerpt(reply)
                    retry_errors = errors
                else:
                    # Server-derived (not model-generated). The other three
                    # health outputs stay model-generated; out of scope here.
                    measured.respiratory = respiratory_impact(
                        table["state"], request.pm25, estimated.new_pollutants.pm25
                    )
                    return PolicyAnalysisResponse(
                        measured=measured, estimated=estimated
                    )

        logger.warning(
            "predict_policy attempt %d failed: %s; reply: %s",
            attempt,
            error_class,
            reply_for_log,
        )
        prompt = (
            build_retry_prompt(first_prompt, retry_errors)
            if retry_errors
            else first_prompt
        )

    raise PolicyModelError(error_class, "; ".join(errors[:_MAX_ERRORS_IN_DETAIL]))

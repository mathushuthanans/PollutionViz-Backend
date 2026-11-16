"""analyse_policy: validation, the single retry, and the three error classes."""

import copy

import pytest

from app.models.datamodel1 import EstimatedImpact, PredictPolicyRequest
from app.services.policy_impact import (
    POLICY_SYSTEM_INSTRUCTION,
    PolicyModelError,
    analyse_policy,
)

NOT_JSON = {"error": "Failed to parse AI response as JSON", "raw_output": "oops {"}


@pytest.fixture
def request_obj(valid_request):
    return PredictPolicyRequest(**valid_request)


def test_valid_reply_returns_measured_and_estimated(
    request_obj, valid_estimate, fake_ask
):
    ask = fake_ask(valid_estimate)
    result = analyse_policy(request_obj, ask=ask)

    assert ask.calls == 1
    assert ask.system_instructions == [POLICY_SYSTEM_INSTRUCTION]
    assert result.measured.location == "Maharashtra"
    assert result.measured.units == "ug/m3"
    assert result.measured.pollutants.co == 900.0
    assert isinstance(result.measured.aqi, int)
    assert result.estimated.estimated_cost_crore == 450


def test_extra_keys_in_the_reply_are_dropped(request_obj, valid_estimate, fake_ask):
    valid_estimate["old_aqi"] = 9999  # the model must not supply measured values
    valid_estimate["surprise"] = "x"
    result = analyse_policy(request_obj, ask=fake_ask(valid_estimate))
    dumped = result.model_dump()
    assert "surprise" not in dumped["estimated"]
    assert "old_aqi" not in dumped["estimated"]


def test_health_benefits_is_case_insensitive(request_obj, valid_estimate, fake_ask):
    valid_estimate["health_benefits"] = " High "
    result = analyse_policy(request_obj, ask=fake_ask(valid_estimate))
    assert result.estimated.health_benefits == "high"


def test_not_json_then_valid_retries_once(request_obj, valid_estimate, fake_ask):
    ask = fake_ask(NOT_JSON, valid_estimate)
    result = analyse_policy(request_obj, ask=ask)
    assert ask.calls == 2
    assert "not valid JSON" in ask.prompts[1]
    assert "oops {" not in ask.prompts[1]  # the rejected reply is not repeated
    assert result.estimated.timeline_months == 24


def test_invalid_then_valid_puts_the_errors_in_the_second_prompt(
    request_obj, valid_estimate, fake_ask
):
    bad = copy.deepcopy(valid_estimate)
    bad["new_aqi"] = -1
    ask = fake_ask(bad, valid_estimate)
    analyse_policy(request_obj, ask=ask)
    assert ask.calls == 2
    assert "new_aqi" in ask.prompts[1]


def test_invalid_twice_raises_model_reply_invalid(request_obj, valid_estimate, fake_ask):
    bad = copy.deepcopy(valid_estimate)
    del bad["timeline_months"]
    ask = fake_ask(bad, bad)
    with pytest.raises(PolicyModelError) as caught:
        analyse_policy(request_obj, ask=ask)
    assert ask.calls == 2
    assert caught.value.error_class == "model_reply_invalid"
    assert "timeline_months" in caught.value.detail


def test_not_json_twice_raises_model_reply_not_json(request_obj, fake_ask):
    ask = fake_ask(NOT_JSON, NOT_JSON)
    with pytest.raises(PolicyModelError) as caught:
        analyse_policy(request_obj, ask=ask)
    assert ask.calls == 2
    assert caught.value.error_class == "model_reply_not_json"
    assert "oops" not in caught.value.detail


def test_exception_twice_raises_model_unavailable(request_obj, fake_ask):
    ask = fake_ask(TimeoutError("slow"), ConnectionError("down"))
    with pytest.raises(PolicyModelError) as caught:
        analyse_policy(request_obj, ask=ask)
    assert ask.calls == 2
    assert caught.value.error_class == "model_unavailable"
    assert "ConnectionError" in caught.value.detail
    assert "down" not in caught.value.detail  # no raw exception text


def test_exception_then_valid_succeeds_on_the_same_prompt(
    request_obj, valid_estimate, fake_ask
):
    ask = fake_ask(TimeoutError("slow"), valid_estimate)
    analyse_policy(request_obj, ask=ask)
    assert ask.calls == 2
    assert ask.prompts[0] == ask.prompts[1]  # nothing to tell the model


def test_final_error_class_is_that_of_the_second_failure(
    request_obj, valid_estimate, fake_ask
):
    bad = copy.deepcopy(valid_estimate)
    bad["new_aqi"] = -1
    ask = fake_ask(bad, TimeoutError("slow"))
    with pytest.raises(PolicyModelError) as caught:
        analyse_policy(request_obj, ask=ask)
    assert caught.value.error_class == "model_unavailable"


@pytest.mark.parametrize("reply", [[1, 2, 3], "text", 42, None])
def test_non_object_json_is_model_reply_invalid(request_obj, fake_ask, reply):
    with pytest.raises(PolicyModelError) as caught:
        analyse_policy(request_obj, ask=fake_ask(reply, reply))
    assert caught.value.error_class == "model_reply_invalid"


def _mutate(estimate, **changes):
    out = copy.deepcopy(estimate)
    for key, value in changes.items():
        if value is ...:
            del out[key]
        else:
            out[key] = value
    return out


RULE_CASES = [
    ("effects_of_policy", []),
    ("effects_of_policy", ["x"] * 7),
    ("effects_of_policy", ["   "]),
    ("effects_of_policy", ["x" * 301]),
    ("new_aqi", -1),
    ("aqi_improvement_percent", 101),
    ("aqi_improvement_percent", -1),
    ("health_benefits", "medium"),
    ("timeline_months", 0),
    ("timeline_months", 241),
    ("estimated_cost_crore", 0),
    ("estimated_cost_crore", 1_000_001),
    ("estimated_cost_crore", "Rs 450 Cr"),
    ("short_term_steps", []),
    ("medium_term_steps", ["x"] * 7),
    ("long_term_steps", ["x" * 201]),
    ("new_pollutants", {"pm25": 1, "pm10": 1, "no2": 1, "o3": 1}),
    ("new_pollutants", {"pm25": -1, "pm10": 1, "no2": 1, "o3": 1, "co": 1}),
    ("total_benefited", -1),
]


GATED_RULE_CASES = [
    ("healthcare_savings_crore_per_year", -1),
    ("healthcare_savings_crore_per_year", 100_001),
    ("quality_of_life_increase_percent", 101),
    ("life_expectancy_gain_years", 11),
    ("life_expectancy_gain_years", "+1.2 years"),
    ("life_expectancy_gain_years", ...),
]


@pytest.mark.parametrize("field, value", RULE_CASES)
def test_each_field_rule_rejects_a_bad_value(
    request_obj, valid_estimate, fake_ask, field, value
):
    bad = _mutate(valid_estimate, **{field: value})
    with pytest.raises(PolicyModelError) as caught:
        analyse_policy(request_obj, ask=fake_ask(bad, bad))
    assert caught.value.error_class == "model_reply_invalid"
    assert field in caught.value.detail


@pytest.mark.parametrize("field, value", GATED_RULE_CASES)
def test_each_gated_field_rule_rejects_a_bad_value_when_the_flag_is_on(
    unsourced_on, request_obj, valid_estimate, fake_ask, field, value
):
    bad = _mutate(valid_estimate, **{field: value})
    with pytest.raises(PolicyModelError) as caught:
        analyse_policy(request_obj, ask=fake_ask(bad, bad))
    assert caught.value.error_class == "model_reply_invalid"
    assert field in caught.value.detail


def test_total_benefited_above_total_population_is_rejected(
    request_obj, valid_estimate, fake_ask
):
    bad = _mutate(valid_estimate, total_benefited=200_000_000)  # Maharashtra is 112,374,333
    with pytest.raises(PolicyModelError) as caught:
        analyse_policy(request_obj, ask=fake_ask(bad, bad))
    assert "total_benefited must not exceed total_population" in caught.value.detail


def test_the_prompt_embeds_the_models_own_schema_and_units(request_obj, valid_estimate, fake_ask):
    ask = fake_ask(valid_estimate)
    analyse_policy(request_obj, ask=ask)
    prompt = ask.prompts[0]
    assert "estimated_cost_crore" in prompt  # generated from EstimatedImpact
    assert "ug/m3" in prompt
    assert "Maharashtra" in prompt

"""The three ungrounded health outputs are gated by SHOW_UNSOURCED_HEALTH_OUTPUTS."""

import pytest
from fastapi.testclient import TestClient

from app import config as app_config
import app.services.policy_impact as policy_impact
from app.main import app
from app.models.datamodel1 import UNSOURCED_HEALTH_FIELDS, PredictPolicyRequest
from app.services.policy_impact import analyse_policy

FLAGS = [f"{n}_unsourced" for n in UNSOURCED_HEALTH_FIELDS]


@pytest.fixture
def request_obj(valid_request):
    return PredictPolicyRequest(**valid_request)


def test_the_flag_defaults_to_false():
    assert app_config.SHOW_UNSOURCED_HEALTH_OUTPUTS is False


def test_default_config_omits_the_three_fields_entirely(
    request_obj, valid_estimate, fake_ask
):
    # The fake model still sends them; they must not reach the response.
    ask = fake_ask(valid_estimate)
    result = analyse_policy(request_obj, ask=ask)
    dumped = result.model_dump()["estimated"]
    for key in (*UNSOURCED_HEALTH_FIELDS, *FLAGS):
        assert key not in dumped  # absent, not null
    assert "respiratory_cases_reduction_percent" in dumped  # others untouched
    assert ask.calls == 1


def test_default_prompt_does_not_ask_for_the_three_fields(
    request_obj, valid_estimate, fake_ask
):
    ask = fake_ask(valid_estimate)
    analyse_policy(request_obj, ask=ask)
    for key in (*UNSOURCED_HEALTH_FIELDS, *FLAGS):
        assert key not in ask.prompts[0]


def test_default_http_response_has_no_such_keys_not_even_null(
    monkeypatch, fake_ask, valid_request, valid_estimate
):
    monkeypatch.setattr(policy_impact, "ask_gemini", fake_ask(valid_estimate))
    body = TestClient(app).post("/predict_policy", json=valid_request).json()
    for key in (*UNSOURCED_HEALTH_FIELDS, *FLAGS):
        assert key not in body["estimated"]


def test_flag_on_includes_the_fields_with_unsourced_true(
    unsourced_on, request_obj, valid_estimate, fake_ask
):
    valid_estimate["life_expectancy_gain_years_unsourced"] = False  # model cannot set it
    ask = fake_ask(valid_estimate)
    result = analyse_policy(request_obj, ask=ask)
    dumped = result.model_dump()["estimated"]
    assert dumped["healthcare_savings_crore_per_year"] == 120
    assert dumped["quality_of_life_increase_percent"] == 12
    assert dumped["life_expectancy_gain_years"] == 1.2
    for flag in FLAGS:
        assert dumped[flag] is True
    for key in UNSOURCED_HEALTH_FIELDS:  # prompt logic kept behind the flag
        assert key in ask.prompts[0]


def test_flag_on_http_response_carries_the_flags(
    unsourced_on, monkeypatch, fake_ask, valid_request, valid_estimate
):
    monkeypatch.setattr(policy_impact, "ask_gemini", fake_ask(valid_estimate))
    body = TestClient(app).post("/predict_policy", json=valid_request).json()
    for flag in FLAGS:
        assert body["estimated"][flag] is True


def test_flag_on_a_missing_field_is_rejected_and_retried(
    unsourced_on, request_obj, valid_estimate, fake_ask
):
    bad = dict(valid_estimate)
    del bad["life_expectancy_gain_years"]
    ask = fake_ask(bad, valid_estimate)
    analyse_policy(request_obj, ask=ask)
    assert ask.calls == 2
    assert "life_expectancy_gain_years" in ask.prompts[1]

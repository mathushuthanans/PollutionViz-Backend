"""Claimed AQI improvement must match the server's AQI numbers (tolerance band)."""

import copy

import pytest
from fastapi.testclient import TestClient

import app.services.policy_impact as policy_impact
from app import config as app_config
from app.main import app
from app.models.datamodel1 import PredictPolicyRequest
from app.services.policy_impact import PolicyModelError, analyse_policy

# The valid request has current AQI 125 (computed by the server).


@pytest.fixture
def request_obj(valid_request):
    return PredictPolicyRequest(**valid_request)


def _with(estimate, **changes):
    out = copy.deepcopy(estimate)
    out.update(changes)
    return out


def test_default_tolerance_is_ten():
    assert app_config.AQI_IMPROVEMENT_TOLERANCE_PCT == 10


def test_consistent_reply_passes_without_retry(request_obj, valid_estimate, fake_ask):
    ask = fake_ask(valid_estimate)  # implied 33.6, claimed 33.6
    analyse_policy(request_obj, ask=ask)
    assert ask.calls == 1


def test_difference_inside_the_band_passes(request_obj, valid_estimate, fake_ask):
    ask = fake_ask(_with(valid_estimate, aqi_improvement_percent=43.0))  # 9.4 pts off
    analyse_policy(request_obj, ask=ask)
    assert ask.calls == 1


def test_inconsistent_reply_triggers_one_retry_naming_the_mismatch(
    request_obj, valid_estimate, fake_ask
):
    bad = _with(valid_estimate, aqi_improvement_percent=60.0)  # implied 33.6
    ask = fake_ask(bad, valid_estimate)
    analyse_policy(request_obj, ask=ask)
    assert ask.calls == 2
    retry = ask.prompts[1]
    assert "you claimed 60.0%" in retry and "imply 33.6%" in retry
    assert "reconcile or correct" in retry


def test_tolerance_is_configurable(monkeypatch, request_obj, valid_estimate, fake_ask):
    monkeypatch.setattr(app_config, "AQI_IMPROVEMENT_TOLERANCE_PCT", 1.0)
    ask = fake_ask(_with(valid_estimate, aqi_improvement_percent=40.0), valid_estimate)
    analyse_policy(request_obj, ask=ask)
    assert ask.calls == 2


def test_inconsistent_twice_raises_model_reply_inconsistent(
    request_obj, valid_estimate, fake_ask
):
    bad = _with(valid_estimate, aqi_improvement_percent=60.0)
    with pytest.raises(PolicyModelError) as exc:
        analyse_policy(request_obj, ask=fake_ask(bad, bad))
    assert exc.value.error_class == "model_reply_inconsistent"


def test_route_returns_502_and_never_the_raw_reply(
    monkeypatch, fake_ask, valid_request, valid_estimate
):
    bad = _with(valid_estimate, aqi_improvement_percent=60.0)
    bad["effects_of_policy"] = ["SECRET-RAW-REPLY-MARKER"]
    monkeypatch.setattr(policy_impact, "ask_gemini", fake_ask(bad, bad))
    response = TestClient(app).post("/predict_policy", json=valid_request)
    assert response.status_code == 502
    body = response.json()
    assert set(body) == {"error_class", "detail"}
    assert body["error_class"] == "model_reply_inconsistent"
    assert "SECRET-RAW-REPLY-MARKER" not in response.text


def test_raw_reply_is_logged_not_returned(
    caplog, request_obj, valid_estimate, fake_ask
):
    bad = _with(valid_estimate, aqi_improvement_percent=60.0)
    with caplog.at_level("WARNING", logger="app.policy_impact"):
        with pytest.raises(PolicyModelError):
            analyse_policy(request_obj, ask=fake_ask(bad, bad))
    assert "model_reply_inconsistent" in caplog.text
    assert '"aqi_improvement_percent": 60.0' in caplog.text

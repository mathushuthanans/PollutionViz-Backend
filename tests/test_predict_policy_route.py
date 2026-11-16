"""/predict_policy through FastAPI, with the Gemini call replaced."""

import copy

import pytest
from fastapi.testclient import TestClient

import app.services.policy_impact as policy_impact
import app.services.response_service as response_service_module
from app.main import app

client = TestClient(app)


@pytest.fixture
def use_ask(monkeypatch):
    """Replace the Gemini call used by /predict_policy; returns the fake."""

    def install(fake):
        monkeypatch.setattr(policy_impact, "ask_gemini", fake)
        return fake

    return install


def test_post_success_has_measured_and_estimated(use_ask, fake_ask, valid_request, valid_estimate):
    use_ask(fake_ask(valid_estimate))
    response = client.post("/predict_policy", json=valid_request)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"measured", "estimated"}
    assert body["measured"]["location"] == "Maharashtra"
    assert body["measured"]["units"] == "ug/m3"
    assert isinstance(body["measured"]["aqi"], int)
    assert body["estimated"]["estimated_cost_crore"] == 450


def test_get_returns_the_same_body_as_post(use_ask, fake_ask, valid_request, valid_estimate):
    use_ask(fake_ask(valid_estimate, copy.deepcopy(valid_estimate)))
    post = client.post("/predict_policy", json=valid_request)
    get = client.get("/predict_policy", params=valid_request)
    assert get.status_code == 200
    assert get.json() == post.json()


@pytest.mark.parametrize(
    "change",
    [
        {"pm25": None},  # removed below
        {"policy": ""},
        {"policy": "   "},
        {"policy": "x" * 2001},
        {"location": ""},
        {"co": -1},
        {"co": "high"},
    ],
)
def test_post_bad_request_is_422_and_gemini_is_not_called(
    use_ask, fake_ask, valid_request, change
):
    fake = use_ask(fake_ask())
    payload = dict(valid_request)
    for key, value in change.items():
        if value is None:
            payload.pop(key)
        else:
            payload[key] = value
    response = client.post("/predict_policy", json=payload)
    assert response.status_code == 422
    assert fake.calls == 0


def test_get_missing_parameter_is_422(use_ask, fake_ask, valid_request):
    fake = use_ask(fake_ask())
    params = dict(valid_request)
    del params["no2"]
    response = client.get("/predict_policy", params=params)
    assert response.status_code == 422
    assert fake.calls == 0


def test_two_bad_replies_give_502_with_the_error_body(use_ask, fake_ask, valid_request, valid_estimate):
    bad = copy.deepcopy(valid_estimate)
    bad["timeline_months"] = 0
    fake = use_ask(fake_ask(bad, bad))
    response = client.post("/predict_policy", json=valid_request)

    assert response.status_code == 502
    body = response.json()
    assert set(body) == {"error_class", "detail"}
    assert body["error_class"] == "model_reply_invalid"
    assert fake.calls == 2


def test_error_body_never_contains_the_raw_reply(use_ask, fake_ask, valid_request):
    raw = {"error": "Failed to parse AI response as JSON", "raw_output": "SECRET-RAW-TEXT"}
    use_ask(fake_ask(raw, raw))
    response = client.post("/predict_policy", json=valid_request)
    assert response.status_code == 502
    assert response.json()["error_class"] == "model_reply_not_json"
    assert "SECRET-RAW-TEXT" not in response.text


def test_gemini_failure_gives_502_model_unavailable(use_ask, fake_ask, valid_request):
    use_ask(fake_ask(TimeoutError("t"), TimeoutError("t")))
    response = client.post("/predict_policy", json=valid_request)
    assert response.status_code == 502
    assert response.json()["error_class"] == "model_unavailable"


def test_cors_preflight_is_answered_by_the_served_app():
    response = client.options(
        "/predict_policy",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_health_risks_now_gets_a_real_aqi_for_ug_m3_input(monkeypatch):
    seen = {}

    def fake_gemini(prompt, *args, **kwargs):
        seen["prompt"] = prompt
        return {"children": "a", "adults": "b", "elderly": "c"}

    monkeypatch.setattr(response_service_module, "ask_gemini", fake_gemini)
    response = client.post(
        "/health_risks",
        json={"pm25": 20, "pm10": 40, "no2": 40, "co": 20000, "o3": 50},
    )
    assert response.status_code == 200
    # CO of 20000 ug/m3 is the maximum sub-index (214); the old function gave
    # None or a lower value because it read CO as ppm.
    assert "AQI: 214" in seen["prompt"]

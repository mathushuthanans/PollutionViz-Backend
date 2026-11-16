"""Shared test setup. No test here calls Gemini or any network service."""

import os

# Must run before anything imports app.config. ENV=production stops config from
# loading the project's real .env; the dummy values satisfy its required-variable
# check, and genai.Client() makes no network call when it is built.
os.environ["ENV"] = "production"
for _name in (
    "API_KEY_GEMINI",
    "MODEL",
    "OPENWEATHER_API_KEY",
    "OPENWEATHER_CURRENT_AIR_URL",
    "OPENWEATHER_FORECAST_AIR_URL",
    "OPENWEATHER_CURRENT_WEATHER_URL",
    "OPENWEATHER_REVERSE_GEO_URL",
):
    os.environ[_name] = "test-value"

import copy

import pytest


VALID_ESTIMATE = {
    "effects_of_policy": ["Fewer diesel buses", "Lower NO2", "Less PM2.5"],
    "new_aqi": 100,
    "aqi_improvement_percent": 33.3,
    "health_benefits": "high",
    "timeline_months": 24,
    "estimated_cost_crore": 450,
    "short_term_steps": ["Audit fleet", "Announce ban"],
    "medium_term_steps": ["Expand metro"],
    "long_term_steps": ["Plant green belt"],
    "new_pollutants": {"pm25": 30, "pm10": 60, "no2": 20, "o3": 40, "co": 500},
    "total_benefited": 36_000_000,
    "respiratory_cases_reduction_percent": 18,
    "healthcare_savings_crore_per_year": 120,
    "quality_of_life_increase_percent": 12,
    "life_expectancy_gain_years": 1.2,
}

VALID_REQUEST = {
    "policy": "Ban diesel buses in the city centre",
    "location": "Maharashtra",
    "pm25": 45.2,
    "pm10": 90.1,
    "no2": 30.5,
    "o3": 50.0,
    "co": 900.0,
}


@pytest.fixture
def valid_estimate():
    return copy.deepcopy(VALID_ESTIMATE)


@pytest.fixture
def valid_request():
    return dict(VALID_REQUEST)


class FakeAsk:
    """Stands in for ask_gemini. Each reply is returned, or raised if it is an
    exception. Records every prompt and system instruction it was called with."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts = []
        self.system_instructions = []

    def __call__(self, prompt, system_instruction=None):
        self.prompts.append(prompt)
        self.system_instructions.append(system_instruction)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    @property
    def calls(self):
        return len(self.prompts)


@pytest.fixture
def fake_ask():
    return FakeAsk


# --- Guards: make an unmocked Gemini or network call fail loudly -------------

import socket
import sys


class UnmockedGeminiCall(AssertionError):
    pass


@pytest.fixture(autouse=True)
def block_real_gemini(monkeypatch):
    """Replace ask_gemini everywhere it is bound with a stub that raises.

    Covers ml_models.ai_logic and every already-imported module that did
    ``from ml_models.ai_logic import ask_gemini``. Tests that need a reply
    patch it themselves (their patch runs after this one and wins).
    """
    import ml_models.ai_logic as ai_logic

    original = ai_logic.ask_gemini

    def _blocked(*args, **kwargs):
        raise UnmockedGeminiCall(
            "ask_gemini was called without being mocked in this test"
        )

    for module in list(sys.modules.values()):
        if getattr(module, "ask_gemini", None) is original:
            monkeypatch.setattr(module, "ask_gemini", _blocked)


@pytest.fixture(autouse=True)
def block_network(monkeypatch):
    """No test may open a real socket (TestClient is in-process)."""

    def _blocked(*args, **kwargs):
        raise RuntimeError("network access is blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)

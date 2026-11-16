"""Server-derived respiratory impact (stage 1). Hand-computed expectations."""

import math

import pytest

from app.data.health_coefficients import (
    HEALTH_COEFFICIENTS,
    NATIONAL_ARI_PREVALENCE,
    STATE_ARI_PREVALENCE,
)
from app.data.state_population import STATE_POPULATION
from app.models.datamodel1 import PredictPolicyRequest
from app.services.health_impact import respiratory_impact
from app.services.policy_impact import analyse_policy

OR = 1.11


def _expected(base_pct, delta):
    p0 = base_pct / 100
    odds1 = p0 / (1 - p0) * OR ** (delta / 10)
    return (p0 - odds1 / (1 + odds1)) * 100_000


def test_coefficient_record_is_fully_documented():
    rec = HEALTH_COEFFICIENTS["pm25_respiratory"]
    assert rec["coefficient"] == OR
    assert rec["source_url"].startswith("https://")
    assert isinstance(rec["source_year"], int) and rec["notes"]


def test_state_table_matches_population_table_exactly():
    assert set(STATE_ARI_PREVALENCE) == set(STATE_POPULATION)


def test_known_delta_gives_the_expected_number():
    # Maharashtra baseline 3.2% (CI 2.9-3.4); PM2.5 90 -> 60 (delta -30).
    r = respiratory_impact("Maharashtra", 90.0, 60.0)
    assert r.baseline_basis == "state" and r.baseline_prevalence_percent == 3.2
    assert r.fewer_respiratory_cases_per_100k_under5 == pytest.approx(
        _expected(3.2, -30), abs=1e-3
    )
    assert math.isclose(r.fewer_respiratory_cases_per_100k_under5, 839.9, abs_tol=0.1)
    assert r.direction == "reduction"
    assert r.new_prevalence_percent < r.baseline_prevalence_percent


def test_zero_delta_gives_zero():
    r = respiratory_impact("Delhi", 80.0, 80.0)
    assert r.fewer_respiratory_cases_per_100k_under5 == 0.0
    assert r.direction == "no_change"
    assert r.new_prevalence_percent == r.baseline_prevalence_percent


def test_worse_policy_is_negative_and_labelled_not_clamped():
    r = respiratory_impact("Maharashtra", 60.0, 90.0)
    assert r.fewer_respiratory_cases_per_100k_under5 < 0
    assert r.fewer_respiratory_cases_per_100k_under5 == pytest.approx(
        _expected(3.2, +30), abs=1e-3
    )
    assert r.direction == "increase"


def test_imprecise_state_estimate_falls_back_to_national():
    r = respiratory_impact("Chandigarh", 80.0, 60.0)  # CI lower bound 0.0
    assert r.baseline_basis == "national"
    assert r.baseline_prevalence_percent == NATIONAL_ARI_PREVALENCE[0]
    assert "too imprecise" in r.coefficient_caveat


def test_caveat_and_sources_are_always_present():
    r = respiratory_impact("Bihar", 70.0, 50.0)
    assert "under five" in r.coefficient_caveat and "model estimate" in r.coefficient_caveat
    assert r.coefficient_source_url.startswith("https://")
    assert r.baseline_source_url.startswith("https://")


def test_analyse_policy_puts_it_in_measured_and_ignores_the_model_value(
    valid_request, valid_estimate, fake_ask
):
    valid_estimate["respiratory_cases_reduction_percent"] = 99  # must be ignored
    result = analyse_policy(PredictPolicyRequest(**valid_request), ask=fake_ask(valid_estimate))
    body = result.model_dump()
    assert "respiratory_cases_reduction_percent" not in body["estimated"]
    resp = body["measured"]["respiratory"]
    # request pm25 45.2 -> model new pm25 30, Maharashtra
    assert resp["current_pm25"] == 45.2 and resp["new_pm25"] == 30
    assert resp["fewer_respiratory_cases_per_100k_under5"] == pytest.approx(
        _expected(3.2, 30 - 45.2), abs=1e-3
    )
    assert resp["coefficient_caveat"]

"""calculate_overall_aqi takes ug/m3 and never drops a pollutant."""

import itertools
import math

import pytest

from ml_models.utils import calculate_overall_aqi as aqi

# (pm25, pm10, no2, co, o3) in ug/m3 -> expected AQI.
# Expected values were produced by running the unmodified
# ResponseService._calculate_aqi (the function /get_location uses) over these
# inputs before ml_models/utils.py was changed.
ORACLE = [
    ((10, 20, 10, 300, 40), 42),
    ((45.2, 90.1, 30.5, 900, 50), 125),
    ((45.2, 90.1, 60, 800, 70), 125),
    ((80, 120, 40, 500, 60), 164),
    ((150, 260, 80, 1200, 90), 200),
    ((30, 420, 50, 400, 60), 294),  # PM10 is the maximum
    ((20, 40, 400, 300, 50), 122),  # NO2 is the maximum
    ((20, 40, 40, 300, 300), 251),  # O3 is the maximum
    ((20, 40, 40, 20000, 50), 214),  # CO is the maximum (~17.5 ppm)
    ((600, 900, 40, 300, 50), 500),  # above every PM band
    ((0, 0, 0, 0, 0), 0),
    ((35.5, 155, 101 * 1.88, 4.5 * 1145, 55 * 1.96), 101),  # exact band edges
    ((5, 30, 50, 100, 20), 28),
]


@pytest.mark.parametrize("inputs, expected", ORACLE)
def test_matches_calculate_aqi_used_by_get_location(inputs, expected):
    assert aqi(*inputs) == expected


def test_co_in_ug_m3_is_counted():
    # 20000 ug/m3 CO is about 17.5 ppm. The old function read it as ppm, found
    # it above its table, and dropped CO from the maximum.
    assert aqi(20, 40, 40, 20000, 50) == 214


def test_value_in_a_breakpoint_gap_is_not_dropped():
    # PM2.5 of 12.05 sits between the 12.0 and 12.1 bands. It takes the start
    # of the next band (51). The old function scored it 0, giving 37 here.
    assert aqi(12.05, 40, 40, 300, 50) == 51


def test_above_the_last_band_is_500():
    assert aqi(9999, 9999, 9999, 99999, 9999) == 500


def test_negative_values_score_zero():
    assert aqi(-5, -5, -5, -5, -5) == 0


def test_never_none_for_a_grid_of_numeric_inputs():
    grid = [0, 11.95, 12.05, 54.5, 100, 354.45, 600, 5000, 100000]
    for combo in itertools.product(grid, repeat=3):
        result = aqi(combo[0], combo[1], combo[2], combo[0] * 10, combo[1])
        assert isinstance(result, int)
        assert 0 <= result <= 500


@pytest.mark.parametrize(
    "bad",
    [None, "45", float("nan"), float("inf"), True, [1]],
)
def test_non_numeric_input_returns_none(bad):
    for position in range(5):
        args = [10, 10, 10, 10, 10]
        args[position] = bad
        assert aqi(*args) is None
    assert not math.isnan(aqi(10, 10, 10, 10, 10))


# --- /get_location and /health_impact use this same function -----------------

def test_response_service_has_no_second_aqi_calculator():
    from app.services.response_service import ResponseService

    assert not hasattr(ResponseService, "_calculate_aqi")


def test_get_location_scores_a_gap_value_in_the_next_band(monkeypatch):
    """PM2.5 = 12.05 is in a gap; /get_location used to report 0 for it."""
    import app.services.response_service as rs

    class Fake:
        status_code = 200

        def __init__(self, body):
            self._body = body

        def json(self):
            return self._body

    air = {
        "list": [
            {
                "dt": 1_700_000_000,
                "main": {"aqi": 1},
                "components": {"pm2_5": 12.05, "pm10": 0, "no2": 0, "co": 0, "o3": 0},
            }
        ]
    }

    def fake_get(url, params=None, timeout=None):
        if "limit" in params:  # reverse geocode
            return Fake([])
        if "units" in params:  # weather
            return Fake({"main": {"temp": 20}, "weather": []})
        return Fake(air)  # current and forecast air

    monkeypatch.setattr(rs.requests, "get", fake_get)
    result = rs.response_service._fetch_location(1.0, 2.0, {})
    assert result["data"]["pollution"]["aqi"] == 51

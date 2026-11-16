"""AQI calculation.

Every pollutant passed to :func:`calculate_overall_aqi` is a concentration in
micrograms per cubic metre (ug/m3), which is what OpenWeather and
``/get_location`` return. NO2, O3 and CO are converted to the units their AQI
tables use (ppb, ppb and ppm) before the tables are applied.
"""

import math

# (concentration low, concentration high, index low, index high)
_Band = tuple[float, float, int, int]

_PM25_BANDS: list[_Band] = [
    (0.0, 12.0, 0, 50),
    (12.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 150.4, 151, 200),
    (150.5, 250.4, 201, 300),
    (250.5, 350.4, 301, 400),
    (350.5, 500.4, 401, 500),
]

_PM10_BANDS: list[_Band] = [
    (0.0, 54.0, 0, 50),
    (55.0, 154.0, 51, 100),
    (155.0, 254.0, 101, 150),
    (255.0, 354.0, 151, 200),
    (355.0, 424.0, 201, 300),
    (425.0, 504.0, 301, 400),
    (505.0, 604.0, 401, 500),
]

# ppb
_NO2_BANDS: list[_Band] = [
    (0.0, 53.0, 0, 50),
    (54.0, 100.0, 51, 100),
    (101.0, 360.0, 101, 150),
    (361.0, 649.0, 151, 200),
    (650.0, 1249.0, 201, 300),
    (1250.0, 1649.0, 301, 400),
    (1650.0, 2049.0, 401, 500),
]

# ppb
_O3_BANDS: list[_Band] = [
    (0.0, 54.0, 0, 50),
    (55.0, 70.0, 51, 100),
    (71.0, 85.0, 101, 150),
    (86.0, 105.0, 151, 200),
    (106.0, 200.0, 201, 300),
]

# ppm
_CO_BANDS: list[_Band] = [
    (0.0, 4.4, 0, 50),
    (4.5, 9.4, 51, 100),
    (9.5, 12.4, 101, 150),
    (12.5, 15.4, 151, 200),
    (15.5, 30.4, 201, 300),
    (30.5, 40.4, 301, 400),
    (40.5, 50.4, 401, 500),
]

# ug/m3 -> the unit each table uses (same factors as
# ResponseService._calculate_aqi).
_NO2_UGM3_PER_PPB = 1.88
_O3_UGM3_PER_PPB = 1.96
_CO_UGM3_PER_PPM = 1145.0


def _sub_index(value: float, bands: list[_Band]) -> float:
    """AQI sub-index for one pollutant.

    Inside a band the index is interpolated linearly. A value that falls in the
    gap between two bands takes the starting index of the next band up, so the
    pollutant is never dropped. A value above the last band scores 500, and a
    value below the first band scores 0.
    """
    if value < bands[0][0]:
        return 0.0
    for low_c, high_c, low_i, high_i in bands:
        if value <= high_c:
            if value < low_c:
                return float(low_i)
            return (high_i - low_i) / (high_c - low_c) * (value - low_c) + low_i
    return 500.0


def _is_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def calculate_overall_aqi(pm25, pm10, no2, co, o3) -> int | None:
    """Overall AQI (0-500) from five concentrations in ug/m3.

    The result is the highest of the five sub-indexes, rounded to an int.
    Returns ``None`` only when an input is missing, not a number, or not finite.
    """
    if not all(_is_number(v) for v in (pm25, pm10, no2, co, o3)):
        return None

    sub_indexes = (
        _sub_index(pm25, _PM25_BANDS),
        _sub_index(pm10, _PM10_BANDS),
        _sub_index(no2 / _NO2_UGM3_PER_PPB, _NO2_BANDS),
        _sub_index(o3 / _O3_UGM3_PER_PPB, _O3_BANDS),
        _sub_index(co / _CO_UGM3_PER_PPM, _CO_BANDS),
    )
    return int(round(max(sub_indexes)))

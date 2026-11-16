# app/services

## Overview
Business logic for the backend. `response_service.py` holds the `ResponseService` class (exposed as the module singleton `response_service`) that fetches OpenWeather data, computes AQI and trends, runs the scikit-learn models, and calls Gemini for AI-written content. `cache.py` provides a TTL cache with optional Redis backing. Two small helpers resolve filesystem and IP locations.

## Interface
`response_service.py`
- `response_service`: module-level `ResponseService()` instance used by [`../api/routes`](../api/routes/EGM.md).
- `router`: module-local `APIRouter`; `ResponseService.__init__` registers `/get_location` and `/get_trends` on it. `main.py` does not include this router.
- Dashboard methods: `get_location(lat, lon)`, `get_trends(lat, lon, range="weekly")` (`weekly`, `monthly`, `yearly`), `get_scenario_presets(lat, lon)`, `get_citizen_actions(lat, lon)`, `get_health_impact(lat, lon)`, `get_vehicle_density(hour=None)`, `get_industrial_impact(lat, lon)`.
- ML methods: `predict_health_risk(data)`, `predict_region_class(data)`, `bridge_predict(lat, lon, asthma=0, heart_disease=0)`.
- Clarity AI methods (call `ask_gemini`): `help_info`, `explain_pollution(pollutant)`, `predict_policy(policy, location, pm25, pm10, no2, co, o3)` (delegates to `policy_impact.analyse_policy`; readings are ug/m3), `compare_locations(...)`, `health_risks(...)`, `suggest_policies(...)`, `citizen_actions(...)`, `daily_tip()`, `myth_buster(claim)`, `reduce_pollution_plan(goal, location)`.
- `groq_reply(scenario_text)`: posts to the Groq chat-completions endpoint using model `llama3-70b-8192`.
- `suggest_policies` contains a local `debug_policy_suggestions = False`; if it were truthy the method would return a fixed list instead of calling Gemini.

`policy_impact.py`
- `analyse_policy(request, ask=None) -> PolicyAnalysisResponse`: builds the prompt, calls the model (`ask_gemini` by default), validates the reply as `EstimatedImpact`, retries once with the validation errors, and raises `PolicyModelError(error_class, detail)` if the second attempt also fails.
- `build_prompt`, `build_retry_prompt`, `POLICY_SYSTEM_INSTRUCTION`, `PolicyModelError`. Does not import FastAPI.

`cache.py`
- `get_or_compute(key, compute, should_cache=lambda v: True, ttl=CACHE_TTL_SECONDS)`: return cached JSON value or compute, store, and return it.
- `status() -> dict`: `{"backend": "memory", "ttl_seconds"}` or `{"backend": "redis", "reachable", "ttl_seconds"}`.
- `clear()`: drop in-memory entries.

`extract_locations.py`
- `extract() -> pathlib.Path`: directory of the `ml_models` package.

`gettingloc.py`
- `addr() -> str`: IP-based reverse-geocoded address (geocoder + Nominatim); not imported by other modules in `app/`.

## Invariants
- [cache.py:get_or_compute] Values must be JSON-serializable (`json.dumps`/`json.loads`). A cached `None` is treated as a miss.
- [cache.py:get_or_compute] Concurrent misses on one key are serialized by a per-key `threading.Lock`, with a second lookup after acquiring it.
- [cache.py:_get, _set] Redis failures never raise; they degrade to the in-process dict.
- [cache.py:_redis] When `REDIS_URL` is empty, or Redis is unreachable at import, the in-memory backend is used.
- [response_service.py:_get_conditions] Cache key is `conditions:{lat:.2f}:{lon:.2f}`; results containing `"error"` in `response` are not cached (`should_cache`).
- [response_service.py:get_trends] Any `range` other than `weekly`, `monthly`, `yearly` (case-insensitive) returns an `{"error": ...}` dict.
- [response_service.py:_fetch_location] The four OpenWeather requests (air, forecast, weather, reverse geocode) run concurrently on `_io_pool` (`ThreadPoolExecutor`, `max_workers=16`), each with `timeout=10`; request failures are returned as `{"error": ...}` rather than raised.
- [response_service.py:bridge_predict] Returns `{"error": ...}` when location data has an error or any pollutant is `None`.
- [response_service.py:_live_pm_for_place] Derives the geocoding URL by replacing `/reverse` with `/direct` in `OPENWEATHER_REVERSE_GEO_URL`.
- [policy_impact.py:analyse_policy] At most two model calls per request. An exception from the model call is `model_unavailable`; the `{error, raw_output}` shape from `ask_gemini` is `model_reply_not_json`; any other failed validation is `model_reply_invalid`. The error class returned is that of the second attempt. The rejected reply is logged (first 1000 chars) and never returned or repeated in the retry prompt.
- [response_service.py:groq_reply] Raises `ValueError` if env var `GEN_AI` is unset and `RuntimeError` on a non-200 response.

## Side Effects
- Import of `response_service.py` runs `extract_locations.extract()` (prints `MODEL_DIR`) and `joblib.load`s `health_risk_model.pkl` and `region_model.pkl` from `ml_models/`; a missing file fails import. It also imports `app.config`, which raises `EnvironmentError` when required variables are missing.
- Network: OpenWeather (air, forecast, weather, reverse/direct geocoding), Google Gemini via `ml_models.ai_logic.ask_gemini`, Groq via `groq_reply`, Redis via `cache.py`.
- Randomness: `random.uniform` (trend variation) and `random.randint` (vehicle density) make some outputs non-deterministic.
- `cache.py` logs the selected backend to `uvicorn.error` at import and pings Redis if configured.
- `gettingloc.addr` performs an IP geolocation lookup and Nominatim request, and prints coordinates.

## Verification
- Run: `<test-command>` (no tests exist in this repository)

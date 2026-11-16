# PollutionViz Backend Blueprint

## System Overview
FastAPI backend for PollutionViz. Request flow: `app/main.py` mounts the router in `app/api/routes`, whose handlers delegate to the `response_service` singleton in `app/services`. That service fetches air-quality, weather, and geocoding data from OpenWeather (cached by `app/services/cache.py`, Redis-backed when `REDIS_URL` is set, otherwise in-memory), runs the scikit-learn models stored in `ml_models/`, and asks Gemini (`ml_models/ai_logic.py`) for AI-written explanations and recommendations. The existing human-maintained [README.md](./README.md) is left untouched.

## Local Interface & Invariants
- `setup.py`: `setup(name="backend_prototype", packages=find_packages())`, which packages the `app` and `ml_models` packages.
- `requirements.txt` pins runtime dependencies (FastAPI, uvicorn, google-genai, scikit-learn, joblib, redis, requests, and others).
- `render.yaml`: Render blueprint with a `keyvalue` Redis service and a `web` service started by `uvicorn app.main:app --host 0.0.0.0 --port 10000`; sets `ENV=production` and `REDIS_URL`.
- `docker-compose.yml`: local `redis:7-alpine` on port 6379 with `maxmemory 64mb` and `allkeys-lru`.
- Invariant: `app.config` fails import unless the Gemini and OpenWeather environment variables are set (listed in [app/EGM.md](./app/EGM.md)).

## Subdirectories & System Boundaries
- app: [./app/EGM.md](./app/EGM.md) - FastAPI application package: entrypoint, environment config, and the `api`, `models`, `services` subpackages.
  - api: [./app/api/EGM.md](./app/api/EGM.md) - HTTP layer grouping.
    - routes: [./app/api/routes/EGM.md](./app/api/routes/EGM.md) - endpoint definitions delegating to `response_service`.
  - models: [./app/models/EGM.md](./app/models/EGM.md) - Pydantic request/response schemas.
  - services: [./app/services/EGM.md](./app/services/EGM.md) - business logic, cache, location helpers.
- ml_models: [./ml_models/EGM.md](./ml_models/EGM.md) - trained models, training scripts, AQI calculator, Gemini wrapper.

## Global Invariants
- Required configuration (`API_KEY_GEMINI`, `MODEL`, `OPENWEATHER_API_KEY`, and four `OPENWEATHER_*_URL` values) must be present before any `app.*` or `ml_models.ai_logic` import succeeds.
- `app/services/response_service.py` loads `ml_models/health_risk_model.pkl` and `ml_models/region_model.pkl` at import; both files must exist.
- Model feature order is fixed: health `[pm25, pm10, no2, o3, co, asthma, heart_disease]`, region `[pm25, pm10, no2, o3, co]`.
- Cached values must be JSON-serializable; error responses are not cached for location conditions.

## Global Side Effects
- External network: OpenWeather, Google Gemini, Groq (`groq_reply`), Nominatim/IP geolocation (`gettingloc.addr`), Redis.
- Disk: model training in `ml_models/model.py` overwrites the `.pkl` files.
- Console output at import and during requests (`MODEL_DIR`, cache backend logging).

## System Verification
- Run: `<test-command>` (no tests exist in this repository)

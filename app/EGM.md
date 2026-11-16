# app

## Overview
The FastAPI application package. `main.py` builds the ASGI app and mounts the router from [`api/routes`](./api/routes/EGM.md); `config.py` reads environment configuration. Schemas live in [`models`](./models/EGM.md) and logic in [`services`](./services/EGM.md).

## Interface
- `main.py:app`: `FastAPI()` instance with `CORSMiddleware` and `main_routes.router` included. Allowed origins come from the comma-separated `CORS_ORIGINS` environment variable (default `*`); credentials are off. Served as `app.main:app` (see `render.yaml` startCommand).
- `config.py` constants (all read from environment): `API_KEY_GEMINI`, `REDIS_URL`, `CACHE_TTL_SECONDS` (int, default `600`), `GEMINI_TIMEOUT_SECONDS` (int, default `30`, optional), `MODEL`, `OPENWEATHER_API_KEY`, `OPENWEATHER_CURRENT_AIR_URL`, `OPENWEATHER_FORECAST_AIR_URL`, `OPENWEATHER_CURRENT_WEATHER_URL`, `OPENWEATHER_REVERSE_GEO_URL`.
- Subdirectories:
  - [api](./api/EGM.md) - HTTP layer grouping.
  - [models](./models/EGM.md) - Pydantic schemas.
  - [services](./services/EGM.md) - business logic, cache, location helpers.

## Invariants
- [config.py] Importing it raises `EnvironmentError("Missing required environment variables")` unless `API_KEY_GEMINI`, `MODEL`, `OPENWEATHER_API_KEY`, and the four `OPENWEATHER_*_URL` values are all non-empty. `REDIS_URL` is optional.
- [config.py] `.env` is loaded via `python-dotenv` only when `ENV != "production"`.
- [main.py:app] `CORSMiddleware` is the only middleware; `allow_credentials` is `False` because `*` with credentials is invalid and the API has no cookies or auth.

## Side Effects
- Import of `config.py` reads environment variables and may read a `.env` file.
- Import of `main.py` imports the routes and services, which load the ML pickles and construct the Gemini client (see [services](./services/EGM.md)).

## Verification
- Run: `<test-command>` (no tests exist in this repository)

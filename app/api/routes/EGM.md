# app/api/routes

## Overview
Defines the HTTP surface of the backend as a FastAPI `APIRouter`. Each handler is a thin adapter that forwards parameters to the `response_service` singleton in [`../../services`](../../services/EGM.md) and returns its result unchanged. Request bodies use the Pydantic models from [`../../models`](../../models/EGM.md).

## Interface
Module: `main_routes.py`. Exports `router` (included by `app/main.py`) and an `app` object (see Invariants).

| Method | Path | Handler | Delegates to |
| --- | --- | --- | --- |
| GET | `/cache_status` | `cache_status` | `cache.status()` |
| GET | `/get_location` | `get_location(lat, lon)` | `response_service.get_location` |
| GET | `/get_trends` | `get_trends(lat, lon, range="weekly")` | `response_service.get_trends` |
| GET | `/get_scenario_presets` | `get_scenario_presets(lat, lon)` | `response_service.get_scenario_presets` |
| POST | `/citizen_actions` | `citizen_scenario_actions(lat, lon)` | `response_service.get_citizen_actions` |
| GET | `/health_impact` | `get_health_impact(lat, lon)` | `response_service.get_health_impact` |
| POST | `/predict_health_risk` | `predict_health_risk(HealthRiskRequest)` | `response_service.predict_health_risk` |
| POST | `/predict_region_class` | `predict_region_class(RegionClassRequest)` | `response_service.predict_region_class` |
| GET | `/bridge_predict` | `bridge_predict(lat, lon, asthma=0, heart_disease=0)` | `response_service.bridge_predict` |
| GET | `/help` | `help_info` | `response_service.help_info` |
| GET | `/explain` | `explain_pollution(pollutant)` | `response_service.explain_pollution` |
| POST | `/predict_policy` | `predict_policy_post(PredictPolicyRequest)` | `response_service.predict_policy` |
| GET | `/predict_policy` | `predict_policy_get(PredictPolicyRequest as query params)` | `response_service.predict_policy` |
| POST | `/compare_locations` | `compare_locations(CompareLocationsRequest)` | `response_service.compare_locations` |
| POST | `/health_risks` | `health_risks(HealthRisksRequest)` | `response_service.health_risks` |
| POST | `/suggest_policies` | `suggest_policies(SuggestPoliciesRequest)` | `response_service.suggest_policies` |
| POST | `/citizen_actions` | `citizen_actions(CitizenActionsRequest)` | `response_service.citizen_actions` |
| GET | `/myth_buster` | `myth_buster(claim)` | `response_service.myth_buster` |
| POST | `/reduce_pollution_plan` | `reduce_pollution_plan(ReducePollutionPlanRequest)` | `response_service.reduce_pollution_plan` |

## Invariants
- [main_routes.py:router] Handlers hold no business logic; all behavior lives in `response_service`.
- [main_routes.py:citizen_scenario_actions, citizen_actions] Two handlers are registered on `POST /citizen_actions` (one takes `lat`/`lon` query params, one takes a `CitizenActionsRequest` body). FastAPI routes the path to the first registered, `citizen_scenario_actions`; `citizen_actions` is shadowed.
- [main_routes.py] This module no longer creates a `FastAPI()` app or configures CORS; `app/main.py` attaches `CORSMiddleware` to the served app.
- [main_routes.py:predict_policy_get, predict_policy_post] `/predict_policy` is available as both GET (query params, parsed as a `PredictPolicyRequest` query model) and POST (body). Both call `_analyse`, declare `response_model=PolicyAnalysisResponse` and return the same body: `{measured, estimated}`.
- [main_routes.py:_analyse] A `PolicyModelError` from the service becomes HTTP 502 with body `{error_class, detail}`; the raw model reply is never in the body. Invalid request values return 422 before Gemini is called.

## Side Effects
- Importing the module imports `app.services.response_service`, which loads the ML model pickles and requires configuration (see [`../../services`](../../services/EGM.md)).
- Handlers trigger outbound HTTP calls, Gemini calls, and cache reads/writes via `response_service`.

## Verification
- Run: `<test-command>` (no tests exist in this repository)

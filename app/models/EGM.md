# app/models

## Overview
Pydantic request/response schemas and a typed dict shared by the routes and the response service. Contains a single module, `datamodel1.py`.

## Interface
- `HealthRiskRequest(BaseModel)`: `pm25`, `pm10`, `no2`, `o3`, `co` (float), `asthma`, `heart_disease` (int).
- `RegionClassRequest(BaseModel)`: `pm25`, `pm10`, `no2`, `o3`, `co` (float).
- `PollutionBaseModel(BaseModel)`: `pm25`, `pm10`, `no2`, `co`, `o3` (float); base for the models below.
- `PredictPolicyRequest(PollutionBaseModel)`: adds `policy` (stripped, 1-2000 chars), `location` (stripped, 1-100 chars); the five pollutants (ug/m3) must each be 0-100000. These rules apply to this class only.
- `CompareLocationsRequest(BaseModel)`: `location1`, `location2` (str); optional `pm25_1`, `pm10_1`, `pm25_2`, `pm10_2` (`float | None`, default `None`).
- `HealthRisksRequest(PollutionBaseModel)`: no extra fields.
- `SuggestPoliciesRequest(PollutionBaseModel)`: adds `location` (str), `aqi` (int).
- `CitizenActionsRequest(PollutionBaseModel)`: no extra fields.
- `MythBusterRequest(BaseModel)`: `claim` (str).
- `ReducePollutionPlanRequest(BaseModel)`: `goal`, `location` (str).
- `HealthImpactResponse(BaseModel)`: `risk_level`, `risk_description`, `sensitive_groups`, `exposure_duration`, `recommended_actions` (all str).
- `IndustrialZone(TypedDict)`: `distance` (float), `direction` (str), `impact` (float).
- `/predict_policy` response: `PollutantReadings` (five concentrations, 0-100000), `MeasuredConditions` (`location`, `aqi` 0-500, `pollutants`, `units="ug/m3"`; filled by the server), `EstimatedImpact` (every field the model must return; see Invariants), `PolicyAnalysisResponse` (`measured`, `estimated`), `PolicyErrorBody` (`error_class` in `model_unavailable` | `model_reply_not_json` | `model_reply_invalid`, `detail`).

## Invariants
- [datamodel1.py:PollutionBaseModel] Pollutant fields are required floats on every model that derives from it.
- [datamodel1.py:CompareLocationsRequest] The four PM fields are optional; when omitted the service looks the values up from the location names (see [`../services`](../services/EGM.md)).
- [datamodel1.py:EstimatedImpact] All fields are required; extra keys are ignored. Lists have 1-6 items (effects 1-300 chars each, steps 1-200); percentages 0-100; `timeline_months` 1-240; `estimated_cost_crore` > 0 and <= 1,000,000; `healthcare_savings_crore_per_year` 0-100,000; `life_expectancy_gain_years` 0-10; `health_benefits` is `low` or `high` (case-insensitive). Cross-field: `total_benefited <= total_population`, and `urban_percent + rural_percent` within 0.5 of 100.
- [datamodel1.py:HealthRiskRequest] Does not derive from `PollutionBaseModel` and carries `asthma` and `heart_disease` as ints.

## Side Effects
- None. The module only defines types.

## Verification
- Run: `pytest -q` from the repository root (install `requirements.txt` and `requirements-dev.txt`). The `/predict_policy` models are covered by `tests/test_policy_impact.py`.

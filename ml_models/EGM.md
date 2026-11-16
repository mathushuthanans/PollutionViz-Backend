# ml_models

## Overview
Machine-learning assets and AI helpers: training scripts for two scikit-learn `GradientBoostingClassifier` models, their datasets and serialized pickles, an AQI calculator, and the Gemini client wrapper. The runtime API consumes `ai_logic.ask_gemini`, `utils.calculate_overall_aqi`, and the two `.pkl` files.

## Interface
- `ai_logic.py`
  - `client`: `genai.Client(api_key=API_KEY_GEMINI)` created at import.
  - `SYSTEM_INSTRUCTION`: system prompt telling Gemini to answer in JSON with fixed pollutant units.
  - `ask_gemini(prompt: str, system_instruction: str | None = None) -> dict[str, Any]`: calls `client.models.generate_content` with model `MODEL`, `response_mime_type="application/json"` and a `GEMINI_TIMEOUT_SECONDS` HTTP timeout (the SDK takes milliseconds); `system_instruction` replaces `SYSTEM_INSTRUCTION` for that call only; returns the parsed JSON, or `{"error": "Failed to parse AI response as JSON", "raw_output": ...}` on `json.JSONDecodeError`.
- `utils.py`
  - `calculate_overall_aqi(pm25, pm10, no2, co, o3) -> int | None`: all five inputs are ug/m3 (as returned by `/get_location`). NO2, O3 and CO are converted to ppb, ppb and ppm; the result is the maximum of five sub-indexes, rounded. Returns `None` only for a missing, non-numeric or non-finite input.
- `model.py`
  - `train_health_risk_model()`: fits on `health_risk.csv` (features `pm25, pm10, no2, o3, co, asthma, heart_disease`, target `danger_scale`), saves `health_risk_model.pkl`.
  - `train_region_model()`: fits on `regionCategory.csv` (features `pm25, pm10, no2, o3, co`, target `region_class`), saves `region_model.pkl`.
  - `predict_health_and_region(pm25, pm10, no2, o3, co, asthma, heart_disease) -> dict`: returns `{"danger_scale", "region_class"}`.
  - `__main__` block trains both models and runs a sample prediction.
- `regionCatgeory.py`: standalone script (note the filename spelling) that trains a region classifier at import time.
- `assist_clarity_ai.py`: standalone FastAPI `app` with Clarity routes (`/help`, `/explain`, `/predict_policy`, `/compare_locations`, `/health_risks`, `/get_scenario_presets`, `/suggest_policies`, `/citizen_actions`, `/daily_tip`, `/myth_buster`, `/reduce_pollution_plan`). It is not included by `app/main.py`.
- Data/artifacts (not source): `health_risk.csv`, `regionCategory.csv`, `health_risk_model.pkl`, `region_model.pkl`.

## Invariants
- [model.py:train_health_risk_model, train_region_model] `train_test_split(test_size=0.2, random_state=42)`; health model uses `learning_rate=0.2, max_depth=5, n_estimators=50`; region model uses `learning_rate=0.01, max_depth=3, n_estimators=50`.
- [model.py:predict_health_and_region, app/services/response_service.py] The health model input order is `[pm25, pm10, no2, o3, co, asthma, heart_disease]` and the region model input order is `[pm25, pm10, no2, o3, co]`; callers must keep this order.
- [utils.py:calculate_overall_aqi] A concentration between two breakpoints takes the starting index of the next band up; above the last band scores 500; below the first scores 0. This differs from `ResponseService._calculate_aqi` only for concentrations that fall in those gaps (that function scores a gap value 0).
- [ai_logic.py:ask_gemini] The return type is always a dict on JSON parse failure, but a successfully parsed JSON value may be any JSON type (for example a list or string).
- [assist_clarity_ai.py] Imports `from ai_logic import ask_gemini` (non-package import), so it only resolves when `ml_models/` is on `sys.path`; the package-style import used by the app is `ml_models.ai_logic`.
- [regionCatgeory.py] Reads `regionCategory.csv` relative to the current working directory.

## Side Effects
- `ai_logic.py` import constructs the Gemini client (requires `app.config`, which raises if environment variables are missing); `ask_gemini` makes a network call to Gemini.
- `model.py` training functions read CSVs and overwrite the `.pkl` files in this directory; `predict_health_and_region` loads both pickles on every call.
- `regionCatgeory.py` trains a model and prints at import; `utils.calculate_overall_aqi` does not print.
- Loading `.pkl` files uses `joblib`, which executes pickle deserialization; only trusted files should be placed here.

## Verification
- Run: `<test-command>` (no tests exist in this repository)

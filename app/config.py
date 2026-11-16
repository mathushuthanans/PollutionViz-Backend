import os

if os.getenv("ENV") != "production":
    from dotenv import load_dotenv

    load_dotenv()


API_KEY_GEMINI: str = os.getenv("API_KEY_GEMINI", "")

# Optional: when REDIS_URL is unset the cache falls back to in-process memory.
REDIS_URL: str = os.getenv("REDIS_URL", "")
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "600"))
# Per-request timeout for each Gemini call (optional; not a required variable).
GEMINI_TIMEOUT_SECONDS: int = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))
MODEL: str = os.getenv("MODEL", "")
# Dev/demo only. healthcare_savings_crore_per_year, quality_of_life_increase_percent
# and life_expectancy_gain_years are invented by the model with no source. While
# this is False (the default) they are not requested and never sent to clients.
SHOW_UNSOURCED_HEALTH_OUTPUTS: bool = os.getenv(
    "SHOW_UNSOURCED_HEALTH_OUTPUTS", ""
).strip().lower() in ("1", "true", "yes")
# /predict_policy: the model's claimed aqi_improvement_percent must be within
# this many percentage points of the improvement implied by the server's current
# AQI and the model's new_aqi, or the reply is rejected and retried once.
AQI_IMPROVEMENT_TOLERANCE_PCT: float = float(
    os.getenv("AQI_IMPROVEMENT_TOLERANCE_PCT", "10")
)
# Optional comma-separated fallback models, tried in order when MODEL fails with
# a quota (429), server (5xx), timeout, connection, or model-not-found error.
MODEL_FALLBACKS: list[str] = [
    m.strip() for m in os.getenv("MODEL_FALLBACKS", "").split(",") if m.strip()
]
# How long a model that hit its quota (429) is skipped before it is retried.
MODEL_COOLDOWN_SECONDS: int = int(os.getenv("MODEL_COOLDOWN_SECONDS", "300"))
# Upper bound on one ask_gemini() call across all models it tries.
GEMINI_TOTAL_BUDGET_SECONDS: int = int(os.getenv("GEMINI_TOTAL_BUDGET_SECONDS", "40"))
OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
OPENWEATHER_CURRENT_AIR_URL: str = os.getenv("OPENWEATHER_CURRENT_AIR_URL", "")
OPENWEATHER_FORECAST_AIR_URL: str = os.getenv("OPENWEATHER_FORECAST_AIR_URL", "")
OPENWEATHER_CURRENT_WEATHER_URL = os.getenv(
    "OPENWEATHER_CURRENT_WEATHER_URL", ""
)

OPENWEATHER_REVERSE_GEO_URL: str = os.getenv("OPENWEATHER_REVERSE_GEO_URL", "")


if not API_KEY_GEMINI or not MODEL or not OPENWEATHER_API_KEY or not OPENWEATHER_CURRENT_AIR_URL or not OPENWEATHER_FORECAST_AIR_URL or not OPENWEATHER_CURRENT_WEATHER_URL or not OPENWEATHER_REVERSE_GEO_URL:
    raise EnvironmentError("Missing required environment variables")

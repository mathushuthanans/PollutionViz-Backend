from pydantic import (
    BaseModel,
    Field,
    ValidationInfo,
    StringConstraints,
    field_validator,
    model_validator,
)
from typing import Annotated, Any, Literal, TypedDict, cast

# ML Model for health risk prediction
class HealthRiskRequest(BaseModel):
    pm25: float
    pm10: float
    no2: float
    o3: float
    co: float
    asthma: int
    heart_disease: int

class IndustrialZone(TypedDict):
    distance: float
    direction: str
    impact: float

# ML Model for region class prediction
class RegionClassRequest(BaseModel):
    pm25: float
    pm10: float
    no2: float
    o3: float
    co: float

# Common base for pollutant values
class PollutionBaseModel(BaseModel):
    pm25: float
    pm10: float
    no2: float
    co: float
    o3: float

class PredictPolicyRequest(PollutionBaseModel):
    """Request for /predict_policy. All pollutants are ug/m3.

    The rules below are on this class only, because the other request models
    share PollutionBaseModel and must not change.
    """

    policy: str
    location: str

    @field_validator("policy")
    @classmethod
    def _policy_length(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 2000:
            raise ValueError("must be 1 to 2000 characters")
        return value

    @field_validator("location")
    @classmethod
    def _location_length(cls, value: str) -> str:
        value = value.strip()
        if not 1 <= len(value) <= 100:
            raise ValueError("must be 1 to 100 characters")
        return value

    @field_validator("pm25", "pm10", "no2", "co", "o3")
    @classmethod
    def _reading_range(cls, value: float) -> float:
        # NaN fails this comparison too.
        if not 0 <= value <= 100_000:
            raise ValueError("must be between 0 and 100000")
        return value

class CompareLocationsRequest(BaseModel):
    location1: str
    location2: str
    # Optional: when omitted, the backend geocodes the names and fetches live values.
    pm25_1: float | None = None
    pm10_1: float | None = None
    pm25_2: float | None = None
    pm10_2: float | None = None

class HealthRisksRequest(PollutionBaseModel):
    pass

class SuggestPoliciesRequest(PollutionBaseModel):
    location: str
    aqi: int

class CitizenActionsRequest(PollutionBaseModel):
    pass

class MythBusterRequest(BaseModel):
    claim: str

class ReducePollutionPlanRequest(BaseModel):
    goal: str
    location: str

class HealthImpactResponse(BaseModel):
    risk_level: str
    risk_description: str
    sensitive_groups: str
    exposure_duration: str
    recommended_actions: str


# --- /predict_policy response -------------------------------------------------

_Text200 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
_Text300 = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]
_Percent = Annotated[float, Field(ge=0, le=100)]
_Concentration = Annotated[float, Field(ge=0, le=100_000)]
_Steps = Annotated[list[_Text200], Field(min_length=1, max_length=6)]


class PollutantReadings(BaseModel):
    pm25: _Concentration
    pm10: _Concentration
    no2: _Concentration
    o3: _Concentration
    co: _Concentration


class PopulationFacts(BaseModel):
    """Fixed population facts for the state, from app/data/state_population.py."""

    total_population: int = Field(gt=0)
    urban_percent: _Percent
    rural_percent: _Percent
    source: str
    year: int


class MeasuredConditions(BaseModel):
    """Values the server knows from the request. The model never produces these."""

    location: str
    population: PopulationFacts
    aqi: int = Field(ge=0, le=500)
    pollutants: PollutantReadings
    units: Literal["ug/m3"] = "ug/m3"


class EstimatedImpact(BaseModel):
    """Everything the model produced. Every field is required.

    Population fields are not here: they are server-known (see PopulationFacts).
    """

    effects_of_policy: Annotated[list[_Text300], Field(min_length=1, max_length=6)]
    new_aqi: float = Field(ge=0)
    aqi_improvement_percent: _Percent
    health_benefits: Literal["low", "high"]
    timeline_months: int = Field(ge=1, le=240)
    estimated_cost_crore: float = Field(gt=0, le=1_000_000)
    short_term_steps: _Steps
    medium_term_steps: _Steps
    long_term_steps: _Steps
    new_pollutants: PollutantReadings
    total_benefited: int = Field(ge=0)
    respiratory_cases_reduction_percent: _Percent
    healthcare_savings_crore_per_year: float = Field(ge=0, le=100_000)
    quality_of_life_increase_percent: _Percent
    life_expectancy_gain_years: float = Field(ge=0, le=10)

    @field_validator("health_benefits", mode="before")
    @classmethod
    def _normalise_health_benefits(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _cross_field_rules(self, info: ValidationInfo) -> "EstimatedImpact":
        # Population is server-known, so it arrives as validation context
        # ({"total_population": int}) rather than as a model-supplied field.
        population = (info.context or {}).get("total_population")
        if population is not None and self.total_benefited > population:
            raise ValueError("total_benefited must not exceed total_population")
        return self


class PolicyAnalysisResponse(BaseModel):
    measured: MeasuredConditions
    estimated: EstimatedImpact


class PolicyErrorBody(BaseModel):
    error_class: Literal[
        "model_unavailable", "model_reply_not_json", "model_reply_invalid"
    ]
    detail: str

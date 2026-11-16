from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.models.datamodel1 import HealthRiskRequest, RegionClassRequest
from app.models.datamodel1 import (
    PolicyAnalysisResponse, PolicyErrorBody,
    PredictPolicyRequest, CompareLocationsRequest, HealthRisksRequest,
    SuggestPoliciesRequest, CitizenActionsRequest, MythBusterRequest,
    ReducePollutionPlanRequest
)
from app.services.response_service import response_service
from app.errors import UnknownStateError
from app.services.policy_impact import PolicyModelError
from app.services import cache




router = APIRouter()



@router.get("/cache_status")
def cache_status():
    return cache.status()


# === Dashboard Routes ===

# Done
@router.get("/get_location")
def get_location(lat: float, lon: float):
    return response_service.get_location(lat, lon)


@router.get("/get_trends")
def get_trends(
    lat: float,
    lon: float,
    range: str = "weekly",
):
    return response_service.get_trends(lat, lon, range)


@router.get("/get_scenario_presets")
def get_scenario_presets(lat: float, lon: float):
    return response_service.get_scenario_presets(lat, lon)


@router.post("/citizen_actions")
def citizen_scenario_actions(lat: float, lon: float):
    return response_service.get_citizen_actions(lat, lon)


@router.get("/health_impact")
def get_health_impact(lat: float, lon: float):
    return response_service.get_health_impact(lat, lon)



# === ML Service Routes ===

@router.post("/predict_health_risk")
def predict_health_risk(data: HealthRiskRequest):
    return response_service.predict_health_risk(data)

@router.post("/predict_region_class")
def predict_region_class(data: RegionClassRequest):
    return response_service.predict_region_class(data)

@router.get("/bridge_predict")
def bridge_predict(lat: float, lon: float, asthma: int = 0, heart_disease: int = 0):
    return response_service.bridge_predict(lat, lon, asthma, heart_disease)



# === Clarity AI Routes ===

@router.get("/help")
def help_info():
    return response_service.help_info()

@router.get("/explain")
def explain_pollution(pollutant: str):
    return response_service.explain_pollution(pollutant)

_POLICY_RESPONSES = {
    502: {
        "model": PolicyErrorBody,
        "description": "The model failed or returned an invalid reply twice.",
    },
    422: {"description": "The location is not a known state or union territory."},
}


def _analyse(request: PredictPolicyRequest):
    try:
        return response_service.predict_policy(
            request.policy, request.location, request.pm25, request.pm10,
            request.no2, request.co, request.o3
        )
    except UnknownStateError as error:
        return JSONResponse(
            status_code=422,
            content={"error_class": "unknown_state", "detail": str(error)},
        )
    except PolicyModelError as error:
        return JSONResponse(
            status_code=502,
            content={"error_class": error.error_class, "detail": error.detail},
        )


@router.post(
    "/predict_policy",
    response_model=PolicyAnalysisResponse,
    responses=_POLICY_RESPONSES,
)
def predict_policy_post(request: PredictPolicyRequest):
    return _analyse(request)


@router.get(
    "/predict_policy",
    response_model=PolicyAnalysisResponse,
    responses=_POLICY_RESPONSES,
)
def predict_policy_get(request: Annotated[PredictPolicyRequest, Query()]):
    return _analyse(request)


@router.post("/compare_locations")
def compare_locations(request: CompareLocationsRequest):
    return response_service.compare_locations(
        request.location1, request.location2,
        request.pm25_1, request.pm10_1, request.pm25_2, request.pm10_2
    )

@router.post("/health_risks")
def health_risks(request: HealthRisksRequest):
    return response_service.health_risks(
        request.pm25, request.pm10, request.no2, request.co, request.o3
    )

@router.post("/suggest_policies")
def suggest_policies(request: SuggestPoliciesRequest):
    return response_service.suggest_policies(
        request.location, request.aqi,
        request.pm25, request.pm10, request.no2, request.co, request.o3
    )

@router.post("/citizen_actions")
def citizen_actions(request: CitizenActionsRequest):
    return response_service.citizen_actions(
        request.pm25, request.pm10, request.no2, request.co, request.o3
    )

@router.get("/myth_buster")
def myth_buster(claim: str):
    return response_service.myth_buster(claim)


@router.post("/reduce_pollution_plan")
def reduce_pollution_plan(request: ReducePollutionPlanRequest):
    return response_service.reduce_pollution_plan(request.goal, request.location)

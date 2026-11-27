"""Prediction period APIs and downloadable prediction reports."""
import os
import re

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response

from models.schemas import PredictionPeriodsRequest, PredictionReportRequest
from services.predict_service import (
    create_prediction_pdf,
    get_dba_periods,
    get_marriage_prediction_data,
    get_transit_periods,
)


router = APIRouter(prefix="/predict", tags=["Predictions"])
API_KEYS = {key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip()}


def auth(x_api_key: str | None = Header(default=None)) -> None:
    if not API_KEYS:
        raise HTTPException(503, "Prediction API_KEYS are not configured")
    if x_api_key not in API_KEYS:
        raise HTTPException(401, "Invalid or missing X-API-Key")


@router.post("/api/dba-periods", dependencies=[Depends(auth)])
def dba_periods(payload: PredictionPeriodsRequest):
    return get_dba_periods(payload)


@router.post("/api/transit-periods", dependencies=[Depends(auth)])
def transit_periods(payload: PredictionPeriodsRequest):
    return get_transit_periods(payload)


@router.post("/api/marriage-data", dependencies=[Depends(auth)])
def marriage_prediction_data(payload: PredictionPeriodsRequest):
    return get_marriage_prediction_data(payload)


def _prediction_response(payload: PredictionReportRequest, kind: str, bhava_number: int):
    pdf = create_prediction_pdf(payload, kind, bhava_number)
    slug = re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-") or "client"
    filename = f"{kind}-prediction-{slug}.pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/api/marriage", dependencies=[Depends(auth)])
def marriage_prediction(payload: PredictionReportRequest):
    return _prediction_response(payload, "marriage", 7)


@router.post("/api/child-birth", dependencies=[Depends(auth)])
def child_birth_prediction(payload: PredictionReportRequest):
    return _prediction_response(payload, "child-birth", 5)

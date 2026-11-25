"""Planet Lord Summary API routes."""
import os

from fastapi import APIRouter, Depends, Header, HTTPException

from models.schemas import PlanetLordSummaryRequest
from services.planet_lord_summary_service import get_planet_lord_summary


router = APIRouter(prefix="/chart", tags=["Planet Lord Summary"])
API_KEYS = {key.strip() for key in os.getenv("API_KEYS", "").split(",") if key.strip()}


def auth(x_api_key: str | None = Header(default=None)) -> None:
    if not API_KEYS:
        raise HTTPException(503, "Planet Lord Summary API_KEYS are not configured")
    if x_api_key not in API_KEYS:
        raise HTTPException(401, "Invalid or missing X-API-Key")


@router.post("/api/planet_lord_summary", dependencies=[Depends(auth)])
def planet_lord_summary(
    payload: PlanetLordSummaryRequest,
):
    return get_planet_lord_summary(payload)

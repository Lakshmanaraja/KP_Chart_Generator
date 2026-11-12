"""Time Science Character Report API (white-label)."""
#from __future__ import annotations
from fastapi import APIRouter
from fastapi import Depends, Header, HTTPException, Query
from fastapi.security import APIKeyHeader
from fastapi.responses import Response
from database.seed_loader import load_mappings, reload_mappings
from models.schemas import ReportRequest

from services.report_service import _sections, _pdf, _trait, _topics, NoTraitsFoundError
import os
import re

router = APIRouter(prefix="/report", tags=["Report"])



# 1. Define the security scheme for Swagger UI (creates the Authorize button)
# Change "X-API-Key" to whatever header name your API expects
# API_KEY_NAME = "X-API-Key"
# api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

API_KEYS = {k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()}

# Change Optional[str] to str | None
def auth(x_api_key: str | None = Header(None)):
    if API_KEYS and x_api_key not in API_KEYS:
        raise HTTPException(401, "Invalid or missing X-API-Key")


@router.get("/api/health")
def health():
    return {"status": "ok", "rules": len(load_mappings())}


@router.get("/api/topics", dependencies=[Depends(auth)])
def topics():
    return (_topics())


@router.post("/api/traits", dependencies=[Depends(auth)])
def traits(req: ReportRequest):
    return {"name": req.name, "sections": _trait(req)}


@router.post("/api/character", dependencies=[Depends(auth)])
def character_report(req: ReportRequest, format: str = Query("pdf", pattern="^(pdf|json)$")):
    try:
        pdf = _pdf(req) if format == "pdf" else None
        sections = _sections(req) if format == "json" else None
    except NoTraitsFoundError:
        raise HTTPException(422, "No matching character traits for this chart")
    if format == "json":
        return {"name": req.name, "sections": sections}
    fname = "character-report-" + re.sub(r"[^a-z0-9]+", "-", req.name.lower()).strip("-") + ".pdf"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.post("/api/reload-rules", dependencies=[Depends(auth)])
def reload_rules():
    return {"rules": len(reload_mappings())}

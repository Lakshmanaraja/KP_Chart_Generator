import os
import re
import json
from typing import List, Optional
from pydantic import BaseModel, Field
#from chart_client import get_chart
from database.seed_loader import load_mappings, reload_mappings
from services.ranker_service import build_report
from services.chart_service import compute_kp_json

from pdf.mobile_report import render_pdf
from models.schemas import ReportRequest

class NoTraitsFoundError(Exception):
    """Raised when a chart has no matching character traits."""
    pass


def _sections(req: ReportRequest):
    chart = compute_kp_json(req.date_of_birth, req.time_of_birth, req.latitude,
                          req.longitude, req.timezone, req.ayanamsa)
    #chart = json.loads(raw)
    chart["planets"] = [p for p in chart.get("planets", []) ] #if p.get("planet_name") not in OUTER
    #chart = req.chart or get_chart(req.date_of_birth, req.time_of_birth, req.latitude,req.longitude, req.timezone, req.ayanamsa)
    return build_report(chart, load_mappings(), req.topics, req.extra_tags)

def _pdf(req: ReportRequest):
    sections = _sections(req)
    if not sections:
        raise NoTraitsFoundError("No matching character traits for this chart")
    tz = req.timezone
    client = {"name": req.name, "date_of_birth": req.date_of_birth, "time_of_birth": req.time_of_birth,
              "place": req.place, "timezone": f"UTC{'+' if tz >= 0 else ''}{tz:g}"}
    return render_pdf(sections, client)

def _trait(date_of_birth, time_of_birth, latitude,
                          longitude, timezone, ayanamsa):
    return _sections(date_of_birth, time_of_birth, latitude,
                          longitude, timezone, ayanamsa)

def _topics():
    return sorted({(m.get("section") or "Others").strip() for m in load_mappings()})


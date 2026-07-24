
from fastapi import APIRouter
from models.schemas import BirthInput
from services.chart_service import compute_kp_json

router = APIRouter(prefix="/chart", tags=["Chart"])

@router.get("/api/kp_chart")
def compute_kp_json_endpoint(date_str:str, time_str:str, lat:float, lon:float, tz_offset_hours:float, ayan_mode='Lahiri'):
    result = compute_kp_json(date_str, time_str, lat, lon, tz_offset_hours, ayan_mode='Lahiri')
    return result

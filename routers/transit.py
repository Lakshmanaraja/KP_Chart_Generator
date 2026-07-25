from fastapi import APIRouter
from services.transit_service import get_planet_between_degrees
from services.transit_service import get_planet_star_transit_dates

router = APIRouter(prefix="/transit", tags=["Transit"])

@router.get("/api/planet_between_degrees")
def get_planet_between_degrees_endpoint(planet: str, start_degree: float, end_degree: float, start_date: str, end_date: str = None):
    return get_planet_between_degrees(planet, start_degree, end_degree, start_date, end_date)

@router.get("/api/planet_star_transit_dates")
def get_planet_star_transit_dates_endpoint(planet:str,star_lord:str,start_date:str,end_date:str):
    return get_planet_star_transit_dates(planet,star_lord,start_date,end_date)

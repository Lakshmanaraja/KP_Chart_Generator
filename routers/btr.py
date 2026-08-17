from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from services.btr_service import calc_answer_chart,bhava_planet_presence_for_questions,btr_correction
from services.btr_service import calc_bhava_planet_presence
from typing import List, Dict

router = APIRouter(prefix="/btr", tags=["BTR"])

@router.get("/api/btr_correction")
def btr_correction_endpoint(dateOfBirth:str,originalBirthTime:str,lat:float,lon:float,tz:float,time_delta:int,time_range:int,answer_chart:str,planet_order:str,must_not_mismatch:str,isPrimaryPL=1,isLoc=1,isConnectedPL=0,ayanamsa='Lahiri'):
    result = btr_correction(dateOfBirth,originalBirthTime,lat,lon,tz,time_delta,time_range,answer_chart,planet_order,must_not_mismatch,isPrimaryPL,isLoc,isConnectedPL,ayanamsa)
    return result

@router.get("/api/calc_bhava_planet_presence")
def calc_bhava_planet_presence_endpoint(birth_date:str,birth_time:str,lat:float,lon:float,tz:float,isPrimaryPL=1,isLoc=1,isConnectedPL=0,ayan_mode='Lahiri'):
    presence,kpjson = calc_bhava_planet_presence(birth_date,birth_time,lat,lon,tz,isPrimaryPL,isLoc,isConnectedPL,ayan_mode)
    response = {} 
    response["presence"]= presence
    response["kpjson"]= kpjson
    json_compatible = jsonable_encoder(response)
    return JSONResponse(content=json_compatible)

@router.get("/api/bhava_planet_presence_for_questions")
def bhava_planet_presence_for_questions_endpoint(dateOfBirth:str,originalBirthTime:str,lat:float,lon:float,tz:float,time_delta:int,time_range:int,bhava_start:int,bhava_end:int,isPrimaryPL=1,isLoc=1,isConnectedPL=0,ayanamsa='Lahiri'):
    presence = bhava_planet_presence_for_questions(dateOfBirth,originalBirthTime,lat,lon,tz,time_delta,time_range,bhava_start,bhava_end,isPrimaryPL,isLoc,isConnectedPL,ayanamsa)
      # Convert DataFrame to JSON-safe structure
    json_compatible = jsonable_encoder(presence)
    return JSONResponse(content=json_compatible)
    
@router.post("/api/calc_answer_chart")
def calc_answer_chart_endpoint(question_json: List[Dict]):
    final_result_dict = calc_answer_chart(question_json)
    return JSONResponse(content=final_result_dict)


import pandas as pd

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from models.schemas import FindPatternsRequest
from services.find_patterns_service import find_patterns 

router = APIRouter(prefix="/patterns", tags=["Patterns"])

@router.post("/api/find_patterns")
async def find_patterns_end_point(payload: FindPatternsRequest, bhava_number: str, bhava_col: str = "house_id"):
    # end point to receive list of client ids and find patterns in their charts.
    list_of_client_ids = payload.list_of_client_ids
    planet_cols = payload.planet_cols
    result = find_patterns(client_ids=list_of_client_ids, bhava_number=bhava_number, bhava_col=bhava_col, planet_cols=planet_cols)
    #json_compatible = jsonable_encoder(result)
    return JSONResponse(
    content=result.where(pd.notna(result), None).to_dict(orient="records")
)
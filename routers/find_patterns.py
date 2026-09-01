import pandas as pd

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from models.schemas import FindPatternsRequest
from services.find_patterns_service import find_patterns 

router = APIRouter(prefix="/patterns", tags=["Patterns"])

@router.post("/api/find_patterns")
async def find_patterns_end_point(payload: FindPatternsRequest, cusp_bh_column: str = "house_id",planet_bh_column: str = "house"):
    # end point to receive list of client ids and find patterns in their charts.
    list_of_client_ids = payload.list_of_client_ids
    cusp_cols = payload.cusp_cols
    planet_cols = payload.planet_cols
    bhava_numbers = payload.list_of_bhavas

    result = find_patterns(client_ids=list_of_client_ids, bhava_numbers=bhava_numbers, cusp_bh_column=cusp_bh_column, planet_bh_column=planet_bh_column, cusp_cols=cusp_cols, planet_cols=planet_cols)
    #json_compatible = jsonable_encoder(result)
    return JSONResponse(
    content=result.where(pd.notna(result), None).to_dict(orient="records")
)
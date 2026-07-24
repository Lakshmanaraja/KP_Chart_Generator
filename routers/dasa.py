from fastapi import APIRouter
from fastapi import HTTPException

from services.dasa_service import major_vdasha,sub_vdasha,sub_sub_vdasha,sub_sub_sub_vdasha,clear_cache
from models.schemas import BirthInput
from services.dasa_service import ParentEndpointsNotCalledError

router = APIRouter(prefix="/dasa", tags=["Dasa"])

@router.post("/api/major_vdasha")
def major_vdasha_endpoint(data: BirthInput):
    try :
        result = major_vdasha(data)
        return result
    except ParentEndpointsNotCalledError as e:
        raise HTTPException(status_code=400, detail=str(e))

    
@router.post("/api/sub_vdasha/{md}")
def sub_vdasha_endpoint(data: BirthInput, md: str):
    try :
        result = sub_vdasha(data,md)
        return result
    except ParentEndpointsNotCalledError as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.post("/api/sub_sub_vdasha/{md}/{ad}")
def sub_sub_vdasha_endpoint(data: BirthInput, md: str, ad: str):
    try :
        result = sub_sub_vdasha(data, md, ad)
        return result
    except ParentEndpointsNotCalledError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/api/sub_sub_sub_vdasha/{md}/{ad}/{pd}")
def sub_sub_sub_vdasha_endpoint(data: BirthInput, md: str, ad: str, pd: str):
    try :
        result = sub_sub_sub_vdasha(data, md, ad, pd)
        return result
    except ParentEndpointsNotCalledError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/api/cache/clear")
def clear_cache_endpoint():
    clear_cache()
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID

class BirthInput(BaseModel):
    year: int
    month: int
    day: int
    hour: int
    minutes: int
    seconds: int
    latitude: float
    longitude: float
    timezone: float

class TimeRange(BaseModel):
    minutes: int
    sign: str
    description: str

class FindPatternsRequest(BaseModel):
    list_of_client_ids: list[str]
    list_of_bhavas: list[int]
    cusp_cols: list[str] = [
        "nakshatra_lord",
        "sub_lord",
        "sub_sub_lord",
        "sub_sub_sub_lord",
    ]
    planet_cols: list[str] = [
        "name",
        "nakshatra_lord",
        "sub_lord",
        "sub_sub_lord",
        "sub_sub_sub_lord",
    ]
# class BTRSubmission(BaseModel):
#     dateOfBirth: str
#     originalBirthTime: str
#     latitude: float
#     longitude: float
#     timezone: str
#     dst: str
#     ayanamsa: str
#     timeRange: TimeRange
#     timeDelta: int
#     originalTimeMatrix: List[List[int]]
#     answerMatrix: List[List[int]]
#     planetOrder: List[str]


class ReportRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    date_of_birth: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", examples=["1990-05-21"])
    time_of_birth: str = Field(..., pattern=r"^\d{2}:\d{2}(:\d{2})?$", examples=["14:30:00"])
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timezone: float = Field(5.5, description="UTC offset in hours, e.g. 5.5 for IST")
    place: Optional[str] = None
    ayanamsa: str = "Lahiri"
    topics: Optional[List[str]] = Field(None, description="Explicit topic list; omit for default set")
    extra_tags: Optional[List[str]] = Field(None, description="Already-verified tag names to include")
    chart: Optional[dict] = Field(None, description="Pre-computed KP chart; skips the upstream call")
    version: str = Field("mobile", pattern="^(mobile|desktop)$", description="mobile (phone) or desktop (A4)")
    text_source: str = Field("report", pattern="^(report|child)$", description="report = Report text, child = Child report text")
    gender: Optional[str] = Field(None, max_length=30, description="male/female (boy/girl accepted); blank/omitted uses saved gender when an authorized client_id is supplied, otherwise neutral pronouns")
    client_id: Optional[UUID] = Field(None, description="Saved client UUID; gender lookup requires the client's authorized Supabase user Bearer token")
    include_sn: bool = Field(True, description="Match the SN column")
    include_sk: bool = Field(True, description="Match the SK column")

ReportRequest.model_rebuild()

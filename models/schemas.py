from pydantic import BaseModel, Field
from datetime import date
from typing import Any, List, Literal, Optional
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


class PlanetLordSummaryRequest(BaseModel):
    date_of_birth: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    time_of_birth: str = Field(..., pattern=r"^\d{2}:\d{2}(:\d{2})?$")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timezone: float = Field(5.5, description="UTC offset in hours")
    ayanamsa: str = "Lahiri"
    location_include: bool = False
    moon_override_enabled: bool = False
    moon_override: dict[str, str | None] | None = None
    include_original_moon: bool = False
    calculation_mode: Literal["birth", "transit"] = "birth"
    transit_planets: list[dict[str, Any]] | None = None
    bhava_cusps: list[dict[str, Any]] | None = None


class PredictionBirthDetails(BaseModel):
    date_of_birth: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    time_of_birth: str = Field(..., pattern=r"^\d{2}:\d{2}(:\d{2})?$")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timezone: float = Field(5.5, ge=-14, le=14, description="Birth timezone offset in hours")
    ayanamsa: str = "Lahiri"


class PredictionPeriodsRequest(PredictionBirthDetails):
    from_date: Optional[date] = None
    duration_years: int = Field(3, ge=1, le=120)
    bhava_number: int = Field(..., ge=1, le=12)


class PredictionItemOverride(BaseModel):
    planet: str = Field(..., min_length=1, max_length=10)
    kind: Literal["Transit", "DBA (Dasa)", "DBA (Bhukthi)", "DBA (Antara)"]
    start: date
    end: date
    selected: bool = True
    deleted: bool = False
    tick_color: Literal["#16A34A", "#D4A017"]


class PredictionReportRequest(PredictionBirthDetails):
    name: str = Field(..., min_length=1, max_length=100)
    place: Optional[str] = None
    from_date: Optional[date] = None
    duration_years: int = Field(3, ge=1, le=120)
    version: str = Field("mobile", pattern="^(mobile|desktop)$")
    gender: Optional[str] = Field(None, max_length=30)
    extra_tags: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    include_sn: bool = False
    include_sk: bool = False
    prediction_item_overrides: Optional[List[PredictionItemOverride]] = None
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
    report_type: Optional[str] = Field(None, pattern=r"^[a-z0-9_-]{1,60}$", description="Report Content report type slug, e.g. character_assessment, understanding_child; omitted = derived from text_source")
    gender: Optional[str] = Field(None, max_length=30, description="male/female (boy/girl accepted); blank/omitted uses saved gender when an authorized client_id is supplied, otherwise neutral pronouns")
    client_id: Optional[UUID] = Field(None, description="Saved client UUID; gender lookup requires the client's authorized Supabase user Bearer token")
    include_sn: bool = Field(True, description="Match the SN column")
    include_sk: bool = Field(True, description="Match the SK column")

ReportRequest.model_rebuild()

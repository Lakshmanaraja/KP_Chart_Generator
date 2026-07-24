from pydantic import BaseModel

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
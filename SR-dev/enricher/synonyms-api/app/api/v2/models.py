from pydantic import BaseModel
from typing import List

class Procedure(BaseModel):
    uri: str
    type: str
    cpv: str
    country: str
    nutscode: str
    year: int
    month: int
    lots: int
    haslots: str

class Procedure2(BaseModel):
    uri: str
    type: str
    cpv: str
    countrybuyer: str
    nutscodebuyer: str
    countrywinner: str
    countries: int
    year: int
    month: int
    lots: int
    haslots: str

class ErrorResponse(BaseModel):
    error: str
    detail: str

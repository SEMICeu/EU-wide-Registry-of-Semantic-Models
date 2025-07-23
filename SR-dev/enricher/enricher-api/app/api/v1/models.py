from pydantic import BaseModel
from typing import List

class Synonym(BaseModel):
    term: str
    source: str

class ErrorResponse(BaseModel):
    error: str
    detail: str

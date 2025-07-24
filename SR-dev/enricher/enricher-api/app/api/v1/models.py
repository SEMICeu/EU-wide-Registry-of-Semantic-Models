from pydantic import BaseModel
from typing import List

class Synonym(BaseModel):
    term: str
    source: str
    score: int

class DetectedLanguage(BaseModel):
    language: str
    score: float

class TranslationItem(BaseModel):
    term: str
    lang: str

class TranslationResponse(BaseModel):
    detectedLanguage: DetectedLanguage
    translations: List[TranslationItem]

class ErrorResponse(BaseModel):
    error: str
    detail: str

class Theme(BaseModel):
    term: str
    score: int

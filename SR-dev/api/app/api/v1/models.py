from pydantic import BaseModel

class RankingResponse(BaseModel):
    status: str
    models_processed: int
    unique_models_ranked: int

class ErrorResponse(BaseModel):
    error: str
    detail: str

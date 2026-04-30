from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SessionCreateResponse(BaseModel):
    session_id: str
    welcome_message: str
    suggested_prompts: list[str] = Field(default_factory=list)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message")
    session_id: Optional[str] = Field(
        default=None,
        description="Optional conversation/session identifier",
    )


class ChatEvent(BaseModel):
    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str
    answer: str


from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .dto import ChatRequest, ChatResponse, SessionCreateResponse
from .service import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _to_sse(event_type: str, payload: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/session", response_model=SessionCreateResponse)
async def create_session() -> SessionCreateResponse:
    payload = chat_service.create_session()
    return SessionCreateResponse(**payload)


@router.post("/stream")
async def stream_chat(req: ChatRequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        async for event in chat_service.stream_chat(req.message, req.session_id):
            yield _to_sse(event.get("type", "message"), event.get("payload", {}))

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    final_answer = ""
    sid = req.session_id or ""
    async for event in chat_service.stream_chat(req.message, req.session_id):
        payload = event.get("payload", {})
        sid = payload.get("session_id", sid)
        if event.get("type") == "error":
            raise HTTPException(status_code=400, detail=payload.get("message", "Unknown error"))
        if event.get("type") == "final":
            final_answer = payload.get("answer", "")
    return ChatResponse(session_id=sid, answer=final_answer)


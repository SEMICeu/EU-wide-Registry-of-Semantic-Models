from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict

import config
from graph_rag.prompts import FOLLOW_UP_RESOLUTION_PROMPT


@dataclass(frozen=True)
class ResolvedQuestion:
    standalone_question: str
    confidence: float
    needs_clarification: bool
    clarification_question: str
    detected_follow_up: bool


def _extract_json_object(raw_text: str) -> Dict[str, Any]:
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json\n", "", 1).strip()
    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def resolve_user_question(user_question: str, conversation_context: str) -> ResolvedQuestion:
    prompt = FOLLOW_UP_RESOLUTION_PROMPT.format(
        conversation_context=conversation_context or "<no history>",
        user_question=user_question,
    )
    response = config.fast_llm.invoke(prompt)
    raw = getattr(response, "content", response)

    try:
        parsed = _extract_json_object(str(raw))
    except Exception:
        return ResolvedQuestion(
            standalone_question=user_question,
            confidence=0.0,
            needs_clarification=False,
            clarification_question="",
            detected_follow_up=False,
        )

    standalone_question = str(parsed.get("standalone_question", "")).strip() or user_question
    confidence_raw = parsed.get("confidence", 0.0)
    try:
        confidence = max(0.0, min(1.0, float(confidence_raw)))
    except Exception:
        confidence = 0.0

    return ResolvedQuestion(
        standalone_question=standalone_question,
        confidence=confidence,
        needs_clarification=bool(parsed.get("needs_clarification", False)),
        clarification_question=str(parsed.get("clarification_question", "")).strip(),
        detected_follow_up=bool(parsed.get("detected_follow_up", False)),
    )

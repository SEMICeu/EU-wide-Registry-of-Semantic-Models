"""
Question intent routing (SPEC vs DATA vs OUT_OF_SCOPE).
"""

import json
from typing import Any

import config
from .graph_strategy_router import RoutePlan
from ..prompts import (
    SRM_CHAT_CONTEXT_PROMPT,
    SRM_SPEC_QA_PROMPT,
    SRM_UNIFIED_ROUTER_PROMPT,
)


def _with_conversation_context(base_prompt: str, conversation_context: str | None) -> str:
    context = (conversation_context or "").strip()
    if not context:
        return base_prompt
    return f"{base_prompt}\n\nConversation context:\n{context}"


def _extract_json_object(raw_text: str) -> dict[str, Any]:
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


def classify_and_plan_route(
    question: str, conversation_context: str | None = None, allow_chat: bool = True
) -> tuple[str, RoutePlan]:
    prompt = SRM_UNIFIED_ROUTER_PROMPT.format(question=question)
    prompt = _with_conversation_context(prompt, conversation_context)
    response = config.fast_llm.invoke(prompt)
    raw = getattr(response, "content", response)
    raw_text = str(raw).strip()
    try:
        parsed = _extract_json_object(raw_text)
    except Exception:
        # Non-JSON response is treated as direct assistant reply for greetings/capabilities.
        plan: RoutePlan = {
            "strategy": "OUT_OF_SCOPE",
            "needs_schema_filters": False,
            "reason": raw_text or "Welcome to the SEMIC Semantic Registry Assistant PoC.",
        }
        if allow_chat:
            return "CHAT", plan
        # CHAT fallback is forbidden for standalone questions; force data retrieval planning.
        return "DATA", {"strategy": "HYBRID", "needs_schema_filters": True, "reason": "Forced DATA for non-follow-up"}

    intent = str(parsed.get("intent", "OUT_OF_SCOPE")).upper()
    strategy = str(parsed.get("strategy", "OUT_OF_SCOPE")).upper()
    needs_schema_filters = bool(parsed.get("needs_schema_filters", True))
    reason = str(parsed.get("reason", "")).strip()

    if intent not in {"SPEC", "DATA", "CHAT", "OUT_OF_SCOPE"}:
        intent = "OUT_OF_SCOPE"
    if strategy not in {"GRAPH", "VECTOR", "HYBRID", "OUT_OF_SCOPE"}:
        strategy = "OUT_OF_SCOPE"

    if intent == "DATA" and strategy == "OUT_OF_SCOPE":
        strategy = "HYBRID"
    if intent == "CHAT" and not allow_chat:
        intent = "DATA"
        strategy = "HYBRID"
        reason = reason or "CHAT disabled for non-follow-up message."
    if intent in {"SPEC", "CHAT", "OUT_OF_SCOPE"}:
        strategy = "OUT_OF_SCOPE"

    plan: RoutePlan = {
        "strategy": strategy,  # type: ignore[typeddict-item]
        "needs_schema_filters": needs_schema_filters,
        "reason": reason or "Unified router decision",
    }
    return intent, plan


def classify_question_intent(
    question: str, conversation_context: str | None = None, allow_chat: bool = True
) -> str:
    intent, _ = classify_and_plan_route(
        question=question, conversation_context=conversation_context, allow_chat=allow_chat
    )
    return intent


def answer_from_srm_reference(
    question: str, srm_reference: str, conversation_context: str | None = None
) -> str:
    prompt = SRM_SPEC_QA_PROMPT.format(question=question, srm_reference=srm_reference)
    prompt = _with_conversation_context(prompt, conversation_context)
    response: Any = config.llm.invoke(prompt)
    content = getattr(response, "content", None)
    return content if isinstance(content, str) else str(response)


def answer_from_chat_context(question: str, conversation_context: str | None = None) -> str:
    prompt = SRM_CHAT_CONTEXT_PROMPT.format(
        question=question,
        conversation_context=(conversation_context or "<no conversation context>"),
    )
    response: Any = config.llm.invoke(prompt)
    content = getattr(response, "content", None)
    return content if isinstance(content, str) else str(response)


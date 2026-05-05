from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any, AsyncIterator, Dict, List, Tuple

from graph_rag.conversation import ResolvedQuestion, resolve_user_question
from graph_rag.router.graph_strategy_router import route_from_plan, run_with_plan
from graph_rag.router.question_router import (
    answer_from_chat_context,
    answer_from_srm_reference,
    classify_and_plan_route,
)
from graph_rag.traversal.retry.retry_loop import GraphRetryExhaustedError


def _extract_final_answer(result: Any) -> str:
    if isinstance(result, dict):
        final = result.get("result")
        if isinstance(final, str):
            return final
        if isinstance(final, dict):
            nested = final.get("result")
            if isinstance(nested, str):
                return nested
    if isinstance(result, str):
        return result
    return str(result)


def _extract_cypher_and_context(result: Dict[str, Any]) -> Tuple[str | None, Any]:
    def _extract_cypher_from_validation(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        validation = payload.get("validation")
        if not isinstance(validation, dict):
            return None
        rounds = validation.get("rounds")
        if not isinstance(rounds, list):
            return None

        # Prefer the most recent non-empty generated query from retries/validation rounds.
        for round_info in reversed(rounds):
            if not isinstance(round_info, dict):
                continue
            generated = round_info.get("generated_query")
            if isinstance(generated, str) and generated.strip():
                return generated
        return None

    cypher_query: str | None = None
    query_context: Any = None

    route_payload = result.get("result")
    if isinstance(route_payload, dict):
        cypher = route_payload.get("generated_cypher")
        if isinstance(cypher, str):
            cypher_query = cypher
        query_context = route_payload.get("context")

    if query_context is None and "context" in result:
        query_context = result.get("context")

    if cypher_query is None and isinstance(result.get("graph_result"), dict):
        graph_payload = result.get("graph_result")
        if isinstance(graph_payload, dict):
            graph_inner = graph_payload.get("result")
            if isinstance(graph_inner, dict):
                g_cypher = graph_inner.get("generated_cypher")
                if isinstance(g_cypher, str):
                    cypher_query = g_cypher
                if query_context is None:
                    query_context = graph_inner.get("context")
            if cypher_query is None:
                cypher_query = _extract_cypher_from_validation(graph_inner)
            if cypher_query is None:
                cypher_query = _extract_cypher_from_validation(graph_payload)

    if cypher_query is None:
        cypher_query = _extract_cypher_from_validation(route_payload)
    if cypher_query is None:
        cypher_query = _extract_cypher_from_validation(result)

    if query_context is None and isinstance(result.get("vector_result"), dict):
        vector_payload = result.get("vector_result")
        if isinstance(vector_payload, dict):
            query_context = vector_payload.get("context")

    return cypher_query, query_context


def _load_srm_reference() -> str:
    this_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(this_dir))
    srm_path = os.path.join(project_root, "SRM.md")
    try:
        with open(srm_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


class ChatService:
    """
    API-oriented chat orchestration that emits intermediate events.
    """

    def __init__(self, recent_turns: int = 8) -> None:
        self._recent_turns = recent_turns
        self._sessions: Dict[str, List[Tuple[str, str]]] = {}
        self._suggested_prompts = [
            "How many assets are in the semantic registry?",
            "How does Norway model a person?",
            "Summarize the main themes covered by SRM assets in plain language.",
            "List some assets with their download URL.",
        ]

    def _get_or_create_session(self, session_id: str | None) -> str:
        sid = session_id or str(uuid.uuid4())
        self._sessions.setdefault(sid, [])
        return sid

    def _welcome_message(self) -> str:
        uml_link = "https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.1/html/overview.jpg"
        return (
            "🚀 Welcome to the SEMIC Semantic Registry Assistant PoC.\n\n"
            " Ask me about the assets and their metadata currently residing in the SEMIC Semantic Registry.\n\n"
            "How I retrieve information:\n"
            "- 🧠 Graph traversal:schema-based answers\n"
            "- 🔎 Vector search: semantic matching over titles and descriptions\n"
            "- ⚡ Hybrid: combines both when needed\n\n"
            "💡 Tip: include class and relationship names from the UML for more precise answers.\n\n"
            f" UML diagram: {uml_link}"
        )

    def create_session(self, session_id: str | None = None) -> Dict[str, Any]:
        sid = self._get_or_create_session(session_id)
        return {
            "session_id": sid,
            "welcome_message": self._welcome_message(),
            "suggested_prompts": list(self._suggested_prompts),
        }

    def _build_context(self, session_id: str) -> str:
        turns = self._sessions.get(session_id, [])
        if not turns:
            return ""
        recent = turns[-self._recent_turns :]
        return "\n".join(f"{role}: {content}" for role, content in recent)

    def _add_turn(self, session_id: str, role: str, content: str) -> None:
        self._sessions.setdefault(session_id, []).append((role, content))

    async def stream_chat(
        self, message: str, session_id: str | None = None
    ) -> AsyncIterator[Dict[str, Any]]:
        sid = self._get_or_create_session(session_id)
        raw_question = message.strip()
        if not raw_question:
            yield {"type": "error", "payload": {"session_id": sid, "message": "Please enter a question."}}
            return

        self._add_turn(sid, "user", raw_question)
        conversation_context = self._build_context(sid)
        yield {"type": "status", "payload": {"session_id": sid, "stage": "received"}}

        if conversation_context:
            yield {"type": "status", "payload": {"session_id": sid, "stage": "resolving_question"}}
            resolved = await asyncio.to_thread(resolve_user_question, raw_question, conversation_context)
            question = resolved.standalone_question
        else:
            question = raw_question
            resolved = ResolvedQuestion(
                standalone_question=raw_question,
                confidence=1.0,
                needs_clarification=False,
                clarification_question="",
                detected_follow_up=False,
            )

        if resolved.needs_clarification and resolved.clarification_question:
            self._add_turn(sid, "assistant", resolved.clarification_question)
            yield {
                "type": "final",
                "payload": {"session_id": sid, "answer": resolved.clarification_question},
            }
            return

        yield {"type": "status", "payload": {"session_id": sid, "stage": "routing"}}
        intent, llm_plan = await asyncio.to_thread(
            classify_and_plan_route,
            question,
            conversation_context=conversation_context,
            allow_chat=resolved.detected_follow_up,
        )
        route = route_from_plan(llm_plan)
        yield {
            "type": "routing",
            "payload": {
                "session_id": sid,
                "intent": intent,
                "route": route,
                "plan": llm_plan,
                "resolved_question": question,
                "follow_up_detected": resolved.detected_follow_up,
                "rewrite_confidence": resolved.confidence,
            },
        }

        if intent == "CHAT":
            chat_text = await asyncio.to_thread(
                answer_from_chat_context,
                question,
                conversation_context=conversation_context,
            )
            self._add_turn(sid, "assistant", chat_text)
            yield {"type": "final", "payload": {"session_id": sid, "answer": chat_text}}
            return

        if intent == "OUT_OF_SCOPE":
            out = "I am only here for SRM questions. I cannot help you with that."
            self._add_turn(sid, "assistant", out)
            yield {"type": "final", "payload": {"session_id": sid, "answer": out}}
            return

        if intent == "SPEC":
            yield {"type": "status", "payload": {"session_id": sid, "stage": "reading_spec"}}
            srm_reference = _load_srm_reference()
            if not srm_reference:
                msg = "I could not load SRM.md. Please ensure the file exists in project root."
                yield {"type": "error", "payload": {"session_id": sid, "message": msg}}
                return
            spec_answer = await asyncio.to_thread(
                answer_from_srm_reference,
                question,
                srm_reference,
                conversation_context=conversation_context,
            )
            self._add_turn(sid, "assistant", spec_answer)
            yield {"type": "final", "payload": {"session_id": sid, "answer": spec_answer}}
            return

        stage = {
            "graph_traversal": "traversing_graph",
            "vector_search": "running_vector_search",
            "hybrid": "running_hybrid_retrieval",
        }.get(route, "running_retrieval")
        yield {"type": "status", "payload": {"session_id": sid, "stage": stage}}

        try:
            result = await asyncio.to_thread(run_with_plan, question=question, plan=llm_plan)
        except GraphRetryExhaustedError as exc:
            # Convert traversal retry failures into user-facing fallback instead of crashing the UI loop.
            no_results_only = bool(exc.errors) and all(
                str(err).strip() == "No results returned from query execution."
                for err in exc.errors
            )
            if no_results_only:
                msg = (
                    "I could not find matching graph results for that query. "
                    "Try rephrasing with a broader scope or fewer constraints."
                )
            else:
                msg = (
                    "I hit an issue while traversing the graph after multiple attempts. "
                    "Please try rephrasing your question."
                )
            self._add_turn(sid, "assistant", msg)
            yield {
                "type": "error",
                "payload": {
                    "session_id": sid,
                    "message": msg,
                    "details": str(exc),
                },
            }
            yield {"type": "final", "payload": {"session_id": sid, "answer": msg}}
            return
        except Exception as exc:
            msg = f"An internal error occurred while processing your request: {type(exc).__name__}"
            self._add_turn(sid, "assistant", msg)
            yield {
                "type": "error",
                "payload": {"session_id": sid, "message": msg, "details": str(exc)},
            }
            yield {"type": "final", "payload": {"session_id": sid, "answer": msg}}
            return

        final_answer = _extract_final_answer(result)

        if isinstance(result, dict):
            cypher_query, query_context = _extract_cypher_and_context(result)
            debug_payload: Dict[str, Any] = {"session_id": sid, "route": route}
            if cypher_query:
                debug_payload["cypher"] = cypher_query
            if query_context is not None:
                debug_payload["context_preview"] = json.loads(
                    json.dumps(query_context, default=str)
                )
            yield {"type": "debug", "payload": debug_payload}

        self._add_turn(sid, "assistant", final_answer)
        yield {"type": "final", "payload": {"session_id": sid, "answer": final_answer}}


chat_service = ChatService()


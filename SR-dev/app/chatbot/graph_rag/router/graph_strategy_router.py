import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Literal, TypedDict

import config
from ..prompts import HYBRID_FINAL_PROMPT, FALBACK_ROUTER_PLANNER_SYSTEM_PROMPT
from ..traversal.graph_traversal import run_graph_traversal_query
from ..vector_search import HybridRAGQuery

RouteMode = Literal["graph_traversal", "vector_search", "hybrid", "out_of_scope"]
Strategy = Literal["GRAPH", "VECTOR", "HYBRID", "OUT_OF_SCOPE"]


class RoutePlan(TypedDict):
    strategy: Strategy
    needs_schema_filters: bool
    reason: str


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


def plan_route(question: str, conversation_context: str | None = None) -> RoutePlan:
    context = (conversation_context or "").strip()
    context_block = f"\nConversation context:\n{context}\n" if context else "\n"
    planner_prompt = (
        f"{FALBACK_ROUTER_PLANNER_SYSTEM_PROMPT}\n\n"
        f"{context_block}\n"
        f"User question:\n{question}\n\n"
        "Plan JSON:"
    )
    response = config.fast_llm.invoke(planner_prompt)
    raw = getattr(response, "content", response)
    parsed = _extract_json_object(str(raw))

    strategy = str(parsed.get("strategy", "HYBRID")).upper()
    needs_schema_filters = bool(parsed.get("needs_schema_filters", True))
    reason = str(parsed.get("reason", ""))

    if strategy not in {"GRAPH", "VECTOR", "HYBRID", "OUT_OF_SCOPE"}:
        raise ValueError(f"Invalid planner strategy: {strategy}")

    return RoutePlan(
        strategy=strategy,  # type: ignore[arg-type]
        needs_schema_filters=needs_schema_filters,
        reason=reason,
    )


def route_from_plan(plan: RoutePlan) -> RouteMode:
    if plan["strategy"] == "GRAPH":
        return "graph_traversal"
    if plan["strategy"] == "VECTOR":
        return "vector_search"
    if plan["strategy"] == "OUT_OF_SCOPE":
        return "out_of_scope"
    return "hybrid"


def _run_vector_only(question: str, top_k: int = 10) -> Dict[str, Any]:
    rag = HybridRAGQuery()
    context = rag.get_document_context(question, top_k=top_k)
    final_answer = rag.generate_final_answer(context=context, user_query=question)
    return {"route": "vector_search", "context": context, "result": final_answer}


def run_with_route(question: str, route: RouteMode, top_k: int = 10) -> Dict[str, Any]:
    if route == "graph_traversal":
        result = run_graph_traversal_query(question)
        return {"route": route, "result": result}

    if route == "vector_search":
        return _run_vector_only(question, top_k=top_k)

    plan: RoutePlan = {
        "strategy": "HYBRID",
        "needs_schema_filters": True,
        "reason": "Forced hybrid route",
    }
    return run_with_plan(question=question, plan=plan, top_k=top_k)


def run_with_plan(question: str, plan: RoutePlan, top_k: int = 10) -> Dict[str, Any]:
    strategy = plan["strategy"]

    if strategy == "OUT_OF_SCOPE":
        return {
            "route": "out_of_scope",
            "plan": plan,
            "result": "I am only here for SRM questions. I cannot help you with that.",
        }

    if strategy == "GRAPH":
        result = run_with_route(question, "graph_traversal", top_k=top_k)
        result["plan"] = plan
        return result
    if strategy == "VECTOR":
        result = _run_vector_only(question, top_k=top_k)
        result["plan"] = plan
        return result

    # Run both retrieval strategies in parallel to reduce end-to-end latency.
    with ThreadPoolExecutor(max_workers=2) as executor:
        graph_future = executor.submit(run_with_route, question, "graph_traversal", top_k)
        vector_future = executor.submit(_run_vector_only, question, top_k)
        graph_result = graph_future.result()
        vector_result = vector_future.result()

    graph_output_text = json.dumps(graph_result, ensure_ascii=False, default=str)
    vector_output_text = json.dumps(vector_result, ensure_ascii=False, default=str)
    prompt_text = HYBRID_FINAL_PROMPT.format(
        question=question,
        graph_output=graph_output_text,
        vector_output=vector_output_text,
    )
    response = config.llm.invoke(prompt_text)
    hybrid_answer = getattr(response, "content", None)
    if not isinstance(hybrid_answer, str):
        hybrid_answer = str(response)

    return {
        "route": "hybrid",
        "plan": plan,
        "graph_result": graph_result,
        "vector_result": vector_result,
        "result": hybrid_answer,
        "context": vector_result.get("context"),
        "hybrid_prompt_debug": {
            "graph_input_chars": len(graph_output_text),
            "vector_input_chars": len(vector_output_text),
            "graph_input_preview": graph_output_text[:1200],
            "vector_input_preview": vector_output_text[:1200],
        },
    }


def route_query(question: str, conversation_context: str | None = None) -> RouteMode:
    return route_from_plan(plan_route(question, conversation_context=conversation_context))


def run_routed_query(
    question: str, top_k: int = 10, conversation_context: str | None = None
) -> Dict[str, Any]:
    plan = plan_route(question, conversation_context=conversation_context)
    return run_with_plan(question=question, plan=plan, top_k=top_k)


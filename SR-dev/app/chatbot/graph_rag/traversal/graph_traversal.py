import json
from typing import Any, Dict

from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph

import config
from ..prompts import SRM_CYPHER_GENERATION_PROMPT, SRM_GRAPH_FINAL_PROMPT
from .retry import GraphRetryExhaustedError, invoke_with_repair

_GRAPH_CYPHER_CHAIN_SINGLETON: GraphCypherQAChain | None = None


def get_srm_neo4j_graph() -> Neo4jGraph:
    return Neo4jGraph(
        url=config.NEO4J_URI,
        username=config.NEO4J_USERNAME,
        password=config.NEO4J_PASSWORD,
        # Runtime path: avoid per-request schema refresh for lower latency.
        refresh_schema=False,
    )


def create_graph_cypher_chain() -> GraphCypherQAChain:
    global _GRAPH_CYPHER_CHAIN_SINGLETON
    if _GRAPH_CYPHER_CHAIN_SINGLETON is not None:
        return _GRAPH_CYPHER_CHAIN_SINGLETON

    graph = get_srm_neo4j_graph()
    llm = config.llm
    chain = GraphCypherQAChain.from_llm(
        llm=llm,
        graph=graph,
        verbose=False,
        cypher_prompt=SRM_CYPHER_GENERATION_PROMPT,
        allow_dangerous_requests=True,
        return_direct=True,
        return_intermediate_steps=True,
    )
    _GRAPH_CYPHER_CHAIN_SINGLETON = chain
    return _GRAPH_CYPHER_CHAIN_SINGLETON


def format_final_answer_from_context(question: str, context_rows: Any) -> str:
    prompt_text = SRM_GRAPH_FINAL_PROMPT.format(question=question, context=context_rows)
    response = config.llm.invoke(prompt_text)
    content = getattr(response, "content", None)
    return content if isinstance(content, str) else str(response)


def _has_non_empty_context(context_rows: Any) -> bool:
    if context_rows is None:
        return False
    if isinstance(context_rows, str):
        return context_rows.strip() != ""
    if isinstance(context_rows, (list, tuple, set, dict)):
        return len(context_rows) > 0
    return True


def _render_context_fallback(context_rows: Any) -> str:
    if isinstance(context_rows, list):
        lines = []
        for row in context_rows[:10]:
            if isinstance(row, dict):
                pairs = [f"{k}: {v}" for k, v in row.items()]
                lines.append("- " + ", ".join(pairs))
            else:
                lines.append(f"- {row}")
        if not lines:
            return "No matching results were found in the graph for this question."
        return "I found the following matching results in the graph:\n" + "\n".join(lines)
    if isinstance(context_rows, dict):
        pairs = [f"{k}: {v}" for k, v in context_rows.items()]
        return "I found matching results in the graph: " + ", ".join(pairs)
    if isinstance(context_rows, str):
        return f"I found matching results in the graph:\n{context_rows.strip()}"
    return f"I found matching results in the graph: {context_rows}"


def run_graph_traversal_raw(question: str) -> Dict[str, Any]:
    chain = create_graph_cypher_chain()

    result, validation = invoke_with_repair(chain, question, max_attempts=3)

    generated_cypher = None
    try:
        steps = result.get("intermediate_steps") or []
        if steps and isinstance(steps[0], dict):
            generated_cypher = steps[0].get("query")
    except Exception:
        generated_cypher = None

    return {
        "question": question,
        "generated_cypher": generated_cypher,
        "context": result.get("result"),
        "intermediate_steps": result.get("intermediate_steps", []),
        "validation": validation,
    }


def run_graph_traversal_query(question: str) -> Dict[str, Any]:
    raw = run_graph_traversal_raw(question)
    context_rows = raw.get("context")
    final_answer = format_final_answer_from_context(question, context_rows)

    # Guardrail: if query returned rows, never emit a false "no results" answer.
    if _has_non_empty_context(context_rows):
        normalized = final_answer.lower()
        if "no matching results" in normalized or "no results" in normalized:
            final_answer = _render_context_fallback(context_rows)

    output = {**raw, "result": final_answer}
    return output


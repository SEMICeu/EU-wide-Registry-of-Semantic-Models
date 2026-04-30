from typing import Any, Dict, Tuple

from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain


class GraphRetryExhaustedError(RuntimeError):
    def __init__(self, message: str, attempts: int, errors: list[str], rounds: list[dict[str, Any]]):
        super().__init__(message)
        self.attempts = attempts
        self.errors = errors
        self.rounds = rounds


def _build_repair_query(
    original_question: str, error: Exception, generated_query: str | None = None
) -> str:
    error_text = str(error)
    query_text = generated_query.strip() if isinstance(generated_query, str) else "<not available>"
    return (
        f"{original_question}\n\n"
        "IMPORTANT: Keep the same intent as the original question.\n"
        "The previous generated Cypher failed and must be corrected.\n\n"
        f"Previous generated Cypher:\n{query_text}\n\n"
        f"Neo4j error:\n{error_text}\n\n"
        "Task:\n"
        "- Fix the error and reshape the query if needed.\n"
        "- Return a single corrected Cypher query only.\n"
        "- Preserve original intent and use valid Neo4j syntax."
    )


def _validate_chain_result(result: Dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(result, dict):
        return False, "Chain output is not a dictionary."

    steps = result.get("intermediate_steps") or []
    if not steps or not isinstance(steps[0], dict):
        return False, "No intermediate steps found to verify generated Cypher."

    generated_cypher = steps[0].get("query")
    if not isinstance(generated_cypher, str) or not generated_cypher.strip():
        return False, "Generated Cypher is missing or empty."

    if "result" not in result:
        return False, "Chain output has no result payload."

    return True, ""


def _is_empty_result_payload(result: Dict[str, Any]) -> bool:
    payload = result.get("result")
    if payload is None:
        return True
    if isinstance(payload, str):
        return payload.strip() == ""
    if isinstance(payload, (list, tuple, set, dict)):
        return len(payload) == 0
    return False


def invoke_with_repair(
    chain: GraphCypherQAChain, question: str, max_attempts: int = 3
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    current_query = question
    last_error: Exception | None = None
    attempt_errors: list[str] = []
    rounds: list[dict[str, Any]] = []

    for attempt in range(1, max_attempts + 1):
        attempted_query = current_query
        try:
            result = chain.invoke({"query": current_query})
            generated_query = None
            try:
                steps = result.get("intermediate_steps") or []
                if steps and isinstance(steps[0], dict):
                    q = steps[0].get("query")
                    if isinstance(q, str) and q.strip():
                        generated_query = q
            except Exception:
                generated_query = None

            # Retry on empty result sets with the same original question.
            if _is_empty_result_payload(result):
                empty_error = "No results returned from query execution."
                last_error = RuntimeError(empty_error)
                attempt_errors.append(empty_error)
                rounds.append(
                    {
                        "round": attempt,
                        "status": "FAIL",
                        "error": empty_error,
                        "original_question": question,
                        "attempted_query": attempted_query,
                        "generated_query": generated_query,
                        "retry_query_for_next_round": question,
                    }
                )
                if attempt >= max_attempts:
                    break
                current_query = question
                continue

            is_valid, validation_error = _validate_chain_result(result)
            if is_valid:
                rounds.append(
                    {
                        "round": attempt,
                        "status": "PASS",
                        "error": None,
                        "original_question": question,
                        "attempted_query": attempted_query,
                        "generated_query": generated_query,
                        "retry_query_for_next_round": None,
                    }
                )
                return result, {
                    "status": "passed",
                    "attempts": attempt,
                    "repaired": attempt > 1,
                    "last_error": str(last_error) if last_error else None,
                    "rounds": rounds,
                }

            last_error = RuntimeError(validation_error)
            attempt_errors.append(validation_error)
            retry_query = _build_repair_query(question, last_error, generated_query)
            rounds.append(
                {
                    "round": attempt,
                    "status": "FAIL",
                    "error": validation_error,
                    "original_question": question,
                    "attempted_query": attempted_query,
                    "generated_query": generated_query,
                    "retry_query_for_next_round": retry_query,
                }
            )
            if attempt >= max_attempts:
                break
            current_query = retry_query
        except Exception as exc:
            last_error = exc
            attempt_errors.append(str(exc))
            retry_query = _build_repair_query(question, exc, None)
            rounds.append(
                {
                    "round": attempt,
                    "status": "FAIL",
                    "error": str(exc),
                    "original_question": question,
                    "attempted_query": attempted_query,
                    "generated_query": None,
                    "retry_query_for_next_round": retry_query,
                }
            )
            if attempt >= max_attempts:
                break
            current_query = retry_query

    # "No results after retries" is not a runtime error; return graceful no-results state.
    if attempt_errors and all(err == "No results returned from query execution." for err in attempt_errors):
        return {
            "result": [],
            "intermediate_steps": [],
        }, {
            "status": "no_results",
            "attempts": max_attempts,
            "repaired": False,
            "last_error": "No results returned from query execution.",
            "rounds": rounds,
        }

    if last_error is not None:
        raise GraphRetryExhaustedError(
            f"Graph traversal failed after {max_attempts} attempts. Last error: {last_error}",
            attempts=max_attempts,
            errors=attempt_errors,
            rounds=rounds,
        ) from last_error
    raise RuntimeError("Traversal invocation failed without an exception")


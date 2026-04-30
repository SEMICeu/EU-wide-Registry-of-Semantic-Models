import json
import logging
from typing import List, Dict, Any, Optional

from langchain_neo4j import Neo4jGraph
from langchain_core.messages import HumanMessage, SystemMessage

import config
try:
    from .setup import params
except ImportError:
    import params  # type: ignore
from .prompts import SRM_GRAPH_FINAL_SYSTEM_PROPMPT
from .traversal.methods import BeamSearchOverGraph, BeamSearchOverGraphWithLLM

logger = logging.getLogger(__name__)
_TRAVERSAL_SINGLETON = None


class HybridRAGQuery:
    """
    Singleton class for vector similarity search on Neo4j and answer generation.
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HybridRAGQuery, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not HybridRAGQuery._initialized:
            self._setup_environment()
            self.embeddings = None
            self.graph = None
            HybridRAGQuery._initialized = True

    def _setup_environment(self) -> None:
        self._validate_neo4j_credentials()

    def _validate_neo4j_credentials(self) -> None:
        missing = []
        if not config.NEO4J_URI:
            missing.append("NEO4J_URI")
        if not config.NEO4J_USERNAME:
            missing.append("NEO4J_USERNAME")
        if not config.NEO4J_PASSWORD:
            missing.append("NEO4J_PASSWORD")
        if missing:
            raise ValueError(f"Missing in .env: {', '.join(missing)}")

    def _initialize_embedding_service(self) -> None:
        if self.embeddings is None:
            self.embeddings = config.embeddings

    def _initialize_neo4j_connection(self) -> None:
        if self.graph is None:
            self.graph = Neo4jGraph(
                url=config.NEO4J_URI,
                username=config.NEO4J_USERNAME,
                password=config.NEO4J_PASSWORD,
                refresh_schema=False,
            )

    def _ensure_services_initialized(self) -> None:
        self._initialize_embedding_service()
        self._initialize_neo4j_connection()

    def is_count_or_aggregate_intent(self, user_query: str) -> bool:
        q = user_query.lower().strip()
        count_phrases = (
            "how many",
            "how much",
            "number of",
            "count of",
            "total number",
            "how many assets",
            "how many distributions",
            "count ",
            " total ",
        )
        return any(p in q for p in count_phrases)

    def run_count_queries(self, user_query: str) -> Dict[str, Any]:
        self._ensure_services_initialized()
        out: Dict[str, Any] = {"scope": "all", "counts": {}}
        try:
            r = self.graph.query("MATCH (n:ns1__Asset) RETURN count(n) AS c")
            out["counts"]["ns1__Asset"] = r[0]["c"] if r else 0

            r = self.graph.query("MATCH (n:ns1__AssetDistribution) RETURN count(n) AS c")
            out["counts"]["ns1__AssetDistribution"] = r[0]["c"] if r else 0

            if "flanders" in user_query.lower() or "vlaanderen" in user_query.lower():
                r = self.graph.query(
                    """
                    MATCH (a:ns1__Asset)-[:ns0__creator|ns4__contactPoint]->(agent)
                    WHERE agent.ns2__name IS NOT NULL
                    AND (toLower(toString(agent.ns2__name)) CONTAINS 'vlaanderen'
                        OR toLower(toString(agent.ns2__name)) CONTAINS 'flanders')
                    RETURN count(DISTINCT a) AS c
                    """
                )
                if r and r[0]["c"] is not None:
                    out["counts"]["ns1__Asset_flanders"] = r[0]["c"]
                    out["scope"] = "flanders"
        except Exception as e:
            logger.warning("Count queries failed: %s", e)
        return out

    def _check_vector_index_exists_with_label(self, embedding_property: str, target_label: str) -> bool:
        try:
            index_name = f"embedding_{embedding_property}_{target_label.lower()}_index"
            result = self.graph.query(
                """
                SHOW INDEXES
                YIELD name, type
                WHERE name = $index_name AND type = 'VECTOR'
                RETURN count(*) as index_count
                """,
                {"index_name": index_name},
            )
            return bool(result and result[0]["index_count"] > 0)
        except Exception:
            return False

    def _search_by_index(
        self,
        query_embedding: List[float],
        embedding_property: str,
        top_k: int,
        target_label: str,
    ) -> List[Dict[str, Any]]:
        index_name = f"embedding_{embedding_property}_{target_label.lower()}_index"
        if not self._check_vector_index_exists_with_label(embedding_property, target_label):
            return []
        try:
            cypher_query = f"""
                CALL db.index.vector.queryNodes('{index_name}', $top_k, $query_embedding)
                YIELD node, score
                WHERE node:{target_label}
                RETURN
                    elementId(node) as node_id,
                    labels(node) as labels,
                    node.uri as uri,
                    coalesce(node.ns2__title, node.ns0__title) as ns2__title,
                    coalesce(node.ns2__description, node.ns0__description) as ns2__description,
                    score,
                    'embedding_{embedding_property}' as search_type
                ORDER BY score DESC
                LIMIT $top_k
            """
            return self.graph.query(
                cypher_query, {"query_embedding": query_embedding, "top_k": top_k}
            )
        except Exception:
            return []

    def _deduplicate_and_sort_results(self, results: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
        unique_results = {}
        for result in results:
            node_id = result.get("node_id")
            if not node_id:
                continue
            if node_id not in unique_results or result["score"] > unique_results[node_id]["score"]:
                unique_results[node_id] = result
        return sorted(unique_results.values(), key=lambda x: x["score"], reverse=True)[:top_k]

    def search_similar_nodes(self, user_query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        self._ensure_services_initialized()
        query_embedding = self.embeddings.embed_query(user_query)
        self.current_query_embedding = query_embedding
        similar_nodes = []
        for embedding_property, target_label in params.VECTOR_SEARCH_CONFIGURATIONS:
            similar_nodes.extend(
                self._search_by_index(
                    query_embedding=query_embedding,
                    embedding_property=embedding_property,
                    top_k=top_k,
                    target_label=target_label,
                )
            )
        return self._deduplicate_and_sort_results(similar_nodes, top_k)

    def get_document_context(self, user_query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        try:
            return self.search_similar_nodes(user_query, top_k)
        except Exception as e:
            logger.warning("Context retrieval failed: %s", e)
            return []

    def _format_context_for_llm(self, context: List[Dict[str, Any]]) -> str:
        if not context:
            return "No context nodes available."
        cleaned = []
        for node in context:
            node = dict(node)
            for k in [
                "node_id",
                "score",
                "search_type",
                "discovered_from_node_id",
                "hop_level",
                "depth",
                "total_cost",
                "edge_cost",
                "g_score",
                "h_score",
                "f_score",
                "level",
            ]:
                node.pop(k, None)
            cleaned.append(node)
        return json.dumps({"graph_nodes": cleaned}, indent=2, ensure_ascii=False, default=str)

    def _render_context_fallback(self, context: List[Dict[str, Any]], top_n: int = 8) -> str:
        if not context:
            return "No relevant vector matches were found for this question."

        lines: List[str] = []
        for node in context[:top_n]:
            uri = node.get("uri") or "<no uri>"
            labels = ", ".join(node.get("labels", [])) if isinstance(node.get("labels"), list) else ""
            title = node.get("ns2__title") or node.get("ns0__title") or node.get("rdfs__label")

            if isinstance(title, list):
                title = title[0] if title else None
            title_text = str(title) if title else ""

            if title_text:
                lines.append(f"- {title_text} ({uri})")
            elif labels:
                lines.append(f"- {uri} [{labels}]")
            else:
                lines.append(f"- {uri}")

        return "I found relevant results from vector retrieval:\n" + "\n".join(lines)

    def generate_final_answer(
        self,
        context: List[Dict[str, Any]],
        user_query: str,
        structured_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        chat = config.llm
        formatted_context = self._format_context_for_llm(context)
        system_prompt = SRM_GRAPH_FINAL_SYSTEM_PROPMPT

        if structured_data and structured_data.get("counts"):
            structured_blob = json.dumps(structured_data, indent=2)
            user_prompt = f"""Structured query results (use these as the authoritative numbers for counts/totals):
{structured_blob}

Context from the graph (for extra detail only; do not use this to infer counts):
{formatted_context}

User Query: {user_query}

Answer the user using the structured query results above for any counts or totals. Be concise and accurate.
If vector context is non-empty, reference at least one concrete retrieved URI/title in the answer."""
        else:
            user_prompt = f"""Context Information:
{formatted_context}

User Query: {user_query}

Please provide a comprehensive answer based on the context provided above.
If context includes results, use them explicitly (mention concrete URIs/titles) and do not claim no results."""

        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = chat.invoke(messages)
        answer = response.content if isinstance(response.content, str) else str(response)

        # Guardrail: if we do have context, never return a false no-results answer.
        if context and "no matching results" in answer.lower():
            return self._render_context_fallback(context)
        return answer


def _deduplicate_contexts(
    initial_docs: List[Dict[str, Any]], additional_docs: List[Dict[str, Any]], top_k: int
) -> List[Dict[str, Any]]:
    unique_docs = {}
    for doc in initial_docs:
        node_id = doc.get("node_id")
        if node_id:
            unique_docs[node_id] = doc
    for doc in additional_docs:
        node_id = doc.get("node_id")
        if node_id and node_id not in unique_docs:
            unique_docs[node_id] = doc
    result = []
    for doc in initial_docs:
        node_id = doc.get("node_id")
        if node_id in unique_docs:
            result.append(unique_docs[node_id])
            del unique_docs[node_id]
    result.extend(unique_docs.values())
    return sorted(result, key=lambda x: x.get("score", 0), reverse=True)[:top_k]


def run_hybrid_query(user_query: str) -> Dict[str, Any]:
    """
    Run vector + traversal + final-answer generation in one call.
    """
    context_retriever = HybridRAGQuery()

    if params.ACTIVATE_INITIAL_VECTOR_SEARCH:
        initial_nodes = context_retriever.get_document_context(user_query, top_k=params.TOP_K_INITIAL)
    else:
        initial_nodes = []

    global _TRAVERSAL_SINGLETON
    if _TRAVERSAL_SINGLETON is None:
        _TRAVERSAL_SINGLETON = (
            BeamSearchOverGraphWithLLM()
            if params.GRAPH_TRAVERSAL_METHOD == "beam_search_over_the_graph_pred_llm"
            else BeamSearchOverGraph()
        )
    traversal_method = _TRAVERSAL_SINGLETON
    additional_context = traversal_method.traverse_graph(initial_nodes, user_query)
    all_context = _deduplicate_contexts(initial_nodes, additional_context, params.TOP_K_TRAVERSAL)

    structured_data = (
        context_retriever.run_count_queries(user_query)
        if context_retriever.is_count_or_aggregate_intent(user_query)
        else None
    )
    final_answer = context_retriever.generate_final_answer(
        all_context, user_query, structured_data=structured_data
    )
    return {"context": all_context, "structured_data": structured_data, "result": final_answer}


__all__ = ["HybridRAGQuery", "run_hybrid_query"]


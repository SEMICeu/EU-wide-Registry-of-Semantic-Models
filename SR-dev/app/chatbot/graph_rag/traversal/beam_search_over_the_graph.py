import os
import numpy as np
from typing import List, Dict, Any, Optional, Set, Tuple
from dotenv import load_dotenv
from langchain_neo4j import Neo4jGraph
from sklearn.metrics.pairwise import cosine_similarity


class BeamSearchOverGraph:
    """
    A graph traversal class that implements Beam Search over the graph.
    This approach explores the graph in layers (like BFS), but at each layer
    only keeps the top-w most promising nodes based on cosine similarity scores.
    """

    def __init__(
        self,
        beam_width: int = 10,
        max_depth: int = 3,
        max_total_nodes: int = 100,
        remove_mentions_nodes: bool = True,
        rel_type_filter: Optional[List[str]] = None,
    ):
        self.beam_width = beam_width
        self.max_depth = max_depth
        self.max_total_nodes = max_total_nodes
        self.remove_mentions_nodes = remove_mentions_nodes
        self.rel_type_filter = rel_type_filter
        self._setup_environment()
        self._initialize_neo4j_connection()

    def _setup_environment(self) -> None:
        load_dotenv()
        required_vars = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

    def _initialize_neo4j_connection(self) -> None:
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
            refresh_schema=False,
        )

    def traverse_graph(self, relevant_docs: List[Dict[str, Any]], user_query: str) -> List[Dict[str, Any]]:
        try:
            starting_node_ids = self._extract_node_ids(relevant_docs)
            if not starting_node_ids:
                print("No starting nodes found from initial documents")
                return []

            additional_nodes = self._perform_beam_search(starting_node_ids)
            if additional_nodes:
                filtered_items = self._filter_properties(additional_nodes)
                return filtered_items
            return []
        except Exception as e:
            print(f"⚠️ Error in Beam Search traversal: {str(e)}")
            return []

    def _extract_node_ids(self, relevant_docs: List[Dict[str, Any]]) -> List[str]:
        node_ids = []
        for doc in relevant_docs:
            if "node_id" in doc:
                node_ids.append(doc["node_id"])
        return list(set(node_ids))

    def _perform_beam_search(self, starting_node_ids: List[str]) -> List[Dict[str, Any]]:
        visited: Set[str] = set()
        discovered_nodes: List[Dict[str, Any]] = []
        current_beam: List[Tuple[str, float, int, Optional[str]]] = []

        for node_id in starting_node_ids:
            current_beam.append((node_id, 1.0, 0, None))
            visited.add(node_id)

        starting_embeddings = self._get_node_embeddings_batch(starting_node_ids)

        for _ in range(self.max_depth):
            if not current_beam:
                break

            next_layer_candidates: List[Tuple[float, str, int, str, Dict[str, Any]]] = []
            for beam_node_id, beam_score, beam_depth, beam_parent in current_beam:
                if beam_depth > 0:
                    node_metadata = self._get_node_metadata(beam_node_id, beam_parent, beam_depth, beam_score)
                    if node_metadata:
                        if node_metadata.get("relationship_type") != "MENTIONS" or not self.remove_mentions_nodes:
                            discovered_nodes.append(node_metadata)

                current_embedding = starting_embeddings.get(beam_node_id)
                if current_embedding is None:
                    current_embedding = self._get_node_embedding(beam_node_id)
                if current_embedding is None:
                    continue

                neighbors = self._get_node_neighbors(beam_node_id)
                neighbor_ids = [neighbor["node_id"] for neighbor in neighbors]
                neighbor_embeddings = self._get_node_embeddings_batch(neighbor_ids)

                for neighbor in neighbors:
                    neighbor_id = neighbor["node_id"]
                    if neighbor_id in visited:
                        continue
                    if neighbor.get("relationship_type") == "MENTIONS" and self.remove_mentions_nodes and beam_depth > 0:
                        continue
                    neighbor_embedding = neighbor_embeddings.get(neighbor_id)
                    if neighbor_embedding is None:
                        continue
                    similarity_score = self._calculate_cosine_similarity(current_embedding, neighbor_embedding)
                    next_layer_candidates.append(
                        (similarity_score, neighbor_id, beam_depth + 1, beam_node_id, neighbor)
                    )

            next_layer_candidates.sort(key=lambda x: x[0], reverse=True)
            top_candidates = next_layer_candidates[: self.beam_width]
            current_beam = []
            for score, node_id, depth, parent_id, _ in top_candidates:
                if node_id not in visited:
                    visited.add(node_id)
                    current_beam.append((node_id, score, depth, parent_id))

            if len(discovered_nodes) >= self.max_total_nodes:
                break

        return discovered_nodes[: self.max_total_nodes]

    def _get_node_neighbors(self, node_id: str) -> List[Dict[str, Any]]:
        try:
            if self.rel_type_filter:
                cypher_query = """
                MATCH (central)-[r]-(neighbor)
                WHERE elementId(central) = $node_id AND type(r) IN $rel_types
                RETURN DISTINCT
                    elementId(neighbor) as node_id,
                    labels(neighbor) as labels,
                    properties(neighbor) as properties,
                    type(r) as relationship_type,
                    1.0 as score,
                    'beam_search_neighbor' as search_type
                """
                return self.graph.query(cypher_query, {"node_id": node_id, "rel_types": self.rel_type_filter})

            cypher_query = """
            MATCH (central)-[r]-(neighbor)
            WHERE elementId(central) = $node_id
            RETURN DISTINCT
                elementId(neighbor) as node_id,
                labels(neighbor) as labels,
                properties(neighbor) as properties,
                type(r) as relationship_type,
                1.0 as score,
                'beam_search_neighbor' as search_type
            """
            return self.graph.query(cypher_query, {"node_id": node_id})
        except Exception:
            return []

    def _get_node_embedding(self, node_id: str) -> Optional[np.ndarray]:
        try:
            cypher_query = """
            MATCH (n)
            WHERE elementId(n) = $node_id
            RETURN properties(n) as all_properties
            """
            result = self.graph.query(cypher_query, {"node_id": node_id})
            if not result:
                return None
            properties = result[0]["all_properties"]
            if not properties:
                return None

            embedding_properties = []
            for key, value in properties.items():
                if key.startswith("embedding_") and isinstance(value, list):
                    try:
                        embedding_array = np.array(value, dtype=np.float32)
                        if embedding_array.size > 0:
                            embedding_properties.append(embedding_array)
                    except (ValueError, TypeError):
                        continue
            if not embedding_properties:
                return None

            concatenated_embedding = np.concatenate(embedding_properties, axis=0)
            norm = np.linalg.norm(concatenated_embedding)
            if norm > 0:
                concatenated_embedding = concatenated_embedding / norm
            return concatenated_embedding
        except Exception:
            return None

    def _get_node_embeddings_batch(self, node_ids: List[str]) -> Dict[str, np.ndarray]:
        embeddings = {}
        for node_id in node_ids:
            embedding = self._get_node_embedding(node_id)
            if embedding is not None:
                embeddings[node_id] = embedding
        return embeddings

    def _calculate_cosine_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        try:
            emb1 = embedding1.reshape(1, -1)
            emb2 = embedding2.reshape(1, -1)
            similarity = cosine_similarity(emb1, emb2)[0][0]
            return max(-1.0, min(1.0, similarity))
        except Exception:
            return 0.0

    def _get_node_metadata(
        self, node_id: str, parent_id: Optional[str], depth: int, score: float
    ) -> Optional[Dict[str, Any]]:
        try:
            if parent_id:
                cypher_query = """
                MATCH (parent)-[r]-(node)
                WHERE elementId(parent) = $parent_id AND elementId(node) = $node_id
                RETURN DISTINCT
                    elementId(node) as node_id,
                    labels(node) as labels,
                    properties(node) as properties,
                    type(r) as relationship_type,
                    $score as score,
                    'beam_search_result' as search_type
                LIMIT 1
                """
                result = self.graph.query(
                    cypher_query, {"parent_id": parent_id, "node_id": node_id, "score": score}
                )
                if result and len(result) > 0:
                    metadata = result[0].copy()
                    metadata["depth"] = depth
                    metadata["discovered_from_node_id"] = parent_id
                    return metadata
            return None
        except Exception:
            return None

    def _filter_properties(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered_items = []
        for item in items:
            filtered_item = item.copy()
            if "properties" in filtered_item and filtered_item["properties"]:
                filtered_properties = {}
                for key, value in filtered_item["properties"].items():
                    if not key.startswith("embedding_"):
                        filtered_properties[key] = value
                filtered_item["properties"] = filtered_properties
            filtered_items.append(filtered_item)
        return filtered_items


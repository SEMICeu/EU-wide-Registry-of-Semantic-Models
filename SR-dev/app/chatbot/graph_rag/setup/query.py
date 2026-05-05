import json
import logging
from typing import List, Dict, Any, Optional

from langchain_neo4j import Neo4jGraph
from langchain_core.messages import HumanMessage, SystemMessage

# Local project imports (flat structure)
import config
import params
from prompts import FINAL_ANSWER_SYSTEM_PROMPT

# Graph traversal implementations
# (only the beam-search variants are currently wired; others can be added later)
from traversal.beam_search_over_the_graph import BeamSearchOverGraph
from traversal.beam_search_over_the_graph_pred_llm import BeamSearchOverGraphWithLLM

logger = logging.getLogger(__name__)

class HybridRAGQuery:
    """
    A singleton class for performing vector similarity search on Document nodes in Neo4j
    to retrieve relevant context based on user queries.
    Initialized only once when the first instance is created.
    """
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        """Ensure only one instance of HybridRAGQuery exists."""
        if cls._instance is None: 
            cls._instance = super(HybridRAGQuery, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize the context retrieval system - only runs once."""
        if not HybridRAGQuery._initialized:
            print("🔧 Initializing HybridRAGQuery singleton...")
            
            # Initialize all services immediately
            self._setup_environment()
            self._initialize_embedding_service()
            self._initialize_neo4j_connection()
            
            HybridRAGQuery._initialized = True
            print("✅ HybridRAGQuery singleton initialized successfully")
    
    def _setup_environment(self) -> None:
        """Validate required credentials (env already loaded in config)."""
        print("🔧 Setting up environment...")
        self._validate_neo4j_credentials()
        print("✅ Environment setup complete")

    def _validate_neo4j_credentials(self) -> None:
        """Validate Neo4j connection credentials from config."""
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
        """Initialize embedding service for query processing (uses embeddings from config)."""
        print("🤖 Initializing embedding service...")
        try:
            self.embeddings = config.embeddings
            print("✅ Embedding service initialized")
        except Exception as e:
            print(f"❌ Failed to initialize embedding service: {e}")
            raise
    
    def _initialize_neo4j_connection(self) -> None:
        """Initialize Neo4j graph connection using config."""
        print("🔗 Initializing Neo4j connection...")
        self.graph = Neo4jGraph(
            url=config.NEO4J_URI,
            username=config.NEO4J_USERNAME,
            password=config.NEO4J_PASSWORD,
            refresh_schema=False,
        )
        print("✅ Neo4j connection established")

    # ---------- Intent and structured (count) queries ----------
    def is_count_or_aggregate_intent(self, user_query: str) -> bool:
        """
        Detect if the user is asking for counts/aggregates (e.g. "how many", "count", "number of").
        For such questions we run Cypher COUNT queries instead of relying on top_k retrieval.
        """
        q = user_query.lower().strip()
        count_phrases = (
            "how many", "how much", "number of", "count of", "total number",
            "how many assets", "how many distributions", "count ", " total ",
        )
        return any(p in q for p in count_phrases)

    def run_count_queries(self, user_query: str) -> Dict[str, Any]:
        """
        Run Cypher COUNT queries to get real totals for Assets and AssetDistributions.
        If the query mentions Flanders/Vlaanderen, also return counts restricted to
        assets linked to Flemish agents (creator/contactPoint).
        Returns a dict suitable for the LLM (e.g. {"ns1__Asset": 204, "ns1__AssetDistribution": 412, "scope": "all"}).
        """
        out: Dict[str, Any] = {"scope": "all", "counts": {}}
        try:
            # Total counts (entire graph)
            r = self.graph.query("""
                MATCH (n:ns1__Asset) RETURN count(n) AS c
            """)
            out["counts"]["ns1__Asset"] = r[0]["c"] if r else 0
            r = self.graph.query("""
                MATCH (n:ns1__AssetDistribution) RETURN count(n) AS c
            """)
            out["counts"]["ns1__AssetDistribution"] = r[0]["c"] if r else 0

            # Optional: Flanders-scoped counts (assets with creator/contactPoint agent name containing Vlaanderen/Flanders)
            if "flanders" in user_query.lower() or "vlaanderen" in user_query.lower():
                # ns2__name can be list or scalar; toString() works for both
                r = self.graph.query("""
                    MATCH (a:ns1__Asset)-[:ns0__creator|ns4__contactPoint]->(agent)
                    WHERE agent.ns2__name IS NOT NULL
                    AND (toLower(toString(agent.ns2__name)) CONTAINS 'vlaanderen'
                         OR toLower(toString(agent.ns2__name)) CONTAINS 'flanders')
                    RETURN count(DISTINCT a) AS c
                """)
                if r and r[0]["c"] is not None:
                    out["counts"]["ns1__Asset_flanders"] = r[0]["c"]
                    out["scope"] = "flanders"
                r = self.graph.query("""
                    MATCH (a:ns1__Asset)-[:ns4__distribution]->(d:ns1__AssetDistribution)
                    MATCH (a)-[:ns0__creator|ns4__contactPoint]->(agent)
                    WHERE agent.ns2__name IS NOT NULL
                    AND (toLower(toString(agent.ns2__name)) CONTAINS 'vlaanderen'
                         OR toLower(toString(agent.ns2__name)) CONTAINS 'flanders')
                    RETURN count(DISTINCT d) AS c
                """)
                if r and r[0]["c"] is not None:
                    out["counts"]["ns1__AssetDistribution_flanders"] = r[0]["c"]
        except Exception as e:
            logger.warning("Count queries failed: %s", e)
        return out

    def list_all_vector_indexes(self) -> None:
        """List all available vector indexes in the Neo4j database."""
        print("\n📋 Available Vector Indexes:")
        print("-" * 40)
        
        try:
            # Query to get all vector indexes
            result = self.graph.query("""
                SHOW INDEXES
                YIELD name, type, labelsOrTypes, properties, state
                WHERE type = 'VECTOR'
                RETURN name, labelsOrTypes, properties, state
                ORDER BY name
            """)
            
            if not result:
                print("⚠️  No vector indexes found in the database")
                return
            
            for idx, index_info in enumerate(result, 1):
                name = index_info.get('name', 'Unknown')
                labels = index_info.get('labelsOrTypes', [])
                properties = index_info.get('properties', [])
                state = index_info.get('state', 'Unknown')
                
                print(f"{idx}. Index: {name}")
                print(f"   Labels: {labels}")
                print(f"   Properties: {properties}")
                print(f"   State: {state}")
                print()
            
            print(f"📊 Total vector indexes found: {len(result)}")
            
        except Exception as e:
            print(f"⚠️  Error listing vector indexes: {e}")
    
    def get_available_labels_for_property(self, embedding_property: str) -> List[str]:
        """Get all node labels that have the specified embedding property."""
        try:
            result = self.graph.query(f"""
                MATCH (n)
                WHERE n.embedding_{embedding_property} IS NOT NULL
                RETURN DISTINCT labels(n) as node_labels
            """)
            
            labels = []
            for item in result:
                node_labels = item.get('node_labels', [])
                labels.extend(node_labels)
            
            # Remove duplicates and return
            return list(set(labels))
            
        except Exception as e:
            print(f"⚠️  Error getting labels for property embedding_{embedding_property}: {e}")
            return []
    
    def _search_by_index(
        self,
        query_embedding: List[float],
        embedding_property: str,
        top_k: int,
        target_label: str,
    ) -> List[Dict[str, Any]]:
        """
        Search nodes using a specific embedding property and label.
        
        Args:
            query_embedding: The query vector embedding
            embedding_property: The embedding property to search against (e.g., 'text', 'hyp_queries')
            top_k: Maximum number of results to return
            target_label: The node label to search in (default: 'Document')
            
        Returns:
            List of matching nodes with similarity scores
        """
        try:
            # Construct the proper index name using both property and label
            index_name = f"embedding_{embedding_property}_{target_label.lower()}_index"
            
            # Check if vector index exists for this property and label combination
            if not self._check_vector_index_exists_with_label(embedding_property, target_label):
                print(f"⚠️  Vector index '{index_name}' does not exist, skipping")
                return []
            
            # Perform vector similarity search using Neo4j's vector index
            cypher_query = f"""
                CALL db.index.vector.queryNodes('{index_name}', $top_k, $query_embedding)
                YIELD node, score
                WHERE node:{target_label}
                RETURN 
                    elementId(node) as node_id,
                    labels(node) as labels,
                    keys(node) as properties,
                    node.uri as uri,
                    node.ns0__title as ns0__title,
                    node.ns0__description as ns0__description,
                    score,
                    'embedding_{embedding_property}' as search_type
                ORDER BY score DESC
                LIMIT $top_k
            """
            
            result = self.graph.query(cypher_query, {
                "query_embedding": query_embedding,
                "top_k": top_k
            })
            
            print(f"📊 Found {len(result)} results using {index_name}")
            return result
            
        except Exception as e:
            print(f"⚠️  Error searching by {index_name}: {e}")
            return []
    
    def _check_vector_index_exists_with_label(self, embedding_property: str, target_label: str) -> bool:
        """
        Check if a vector index exists for the given embedding property and label combination.
        
        Args:
            embedding_property: The embedding property name (without 'embedding_' prefix)
            target_label: The node label to check for
            
        Returns:
            True if index exists, False otherwise
        """
        try:
            index_name = f"embedding_{embedding_property}_{target_label.lower()}_index"
            
            # Query to check if the index exists
            result = self.graph.query("""
                SHOW INDEXES
                YIELD name, type, labelsOrTypes, properties
                WHERE name = $index_name AND type = 'VECTOR'
                RETURN count(*) as index_count
            """, {"index_name": index_name})
            
            exists = result[0]['index_count'] > 0 if result else False
            
            if not exists:
                print(f"ℹ️  Vector index '{index_name}' not found")
            
            return exists
            
        except Exception as e:
            print(f"⚠️  Error checking vector index existence: {e}")
            return False
    
    def search_similar_nodes(self, user_query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search for graph nodes similar to the user query using vector similarity.
        Uses the configured search properties and labels from params.VECTOR_SEARCH_CONFIGURATIONS.
        """
        print(f"🔍 Searching for graph nodes similar to: '{user_query}'")
        
        try:
            # Convert user query to embedding
            query_embedding = self.embeddings.embed_query(user_query)
            
            # Store the query embedding for potential use in graph traversal
            self.current_query_embedding = query_embedding
            
            # Search using all configured embedding properties and labels
            similar_nodes = []
            
            for embedding_property, target_label in params.VECTOR_SEARCH_CONFIGURATIONS:
                print(f"🔍 Searching using embedding_{embedding_property} on {target_label} nodes...")
                
                search_results = self._search_by_index(
                    query_embedding=query_embedding,
                    embedding_property=embedding_property,
                    top_k=top_k,
                    target_label=target_label,
                )
                
                if search_results:
                    similar_nodes.extend(search_results)
                    print(f"   ✅ Found {len(search_results)} results from embedding_{embedding_property}")
                else:
                    print(f"   ⚠️  No results from embedding_{embedding_property} on {target_label}")
            
            # Remove duplicates and sort by similarity score
            unique_nodes = self._deduplicate_and_sort_results(similar_nodes, top_k)
            
            print(f"✅ Found {len(unique_nodes)} similar node(s) total")
            return unique_nodes
            
        except Exception as e:
            print(f"⚠️  Error searching for similar documents: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _deduplicate_and_sort_results(
        self, 
        results: List[Dict[str, Any]], 
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate documents and sort by similarity score.
        
        Args:
            results: List of search results from different embedding properties
            top_k: Maximum number of results to return
            
        Returns:
            Deduplicated and sorted list of document results
        """
        # Use node_id to deduplicate, keeping the result with highest score
        unique_results = {}
        
        for result in results:
            node_id = result.get('node_id')
            if not node_id:
                continue
            
            # Keep the result with the highest similarity score
            if node_id not in unique_results or result['score'] > unique_results[node_id]['score']:
                unique_results[node_id] = result
        
        # Sort by similarity score (highest first) and limit results
        sorted_results = sorted(
            unique_results.values(), 
            key=lambda x: x['score'], 
            reverse=True
        )[:top_k]
        
        return sorted_results
    
    def get_document_context(self, user_query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Main method to get relevant graph context for a user query.
        This is the primary interface for the class.
        """
        try:
            similar_nodes = self.search_similar_nodes(user_query, top_k)
            
            if similar_nodes:
                print(f"📝 Retrieved {len(similar_nodes)} relevant node(s)")
                self._display_results_summary(similar_nodes)
            else:
                print("⚠️  No relevant nodes found")
            
            return similar_nodes
            
        except Exception as e:
            print(f"❌ Context retrieval failed: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _display_results_summary(self, results: List[Dict[str, Any]]) -> None:
        """Display a summary of the search results."""
        if not results:
            return
        
        print(f"\n📊 Search Results Summary:")
        print("-" * 30)
        
        for i, result in enumerate(results[:5], 1):  # Show top 5 results
            score = result.get('score', 0)
            search_type = result.get('search_type', 'unknown')
            labels = result.get('labels', [])
            uri = result.get('uri', '')
            title = result.get('ns0__title', '')

            print(f"{i}. Labels: {labels}")
            if uri:
                print(f"   URI: {uri}")
            if title:
                preview_title = title[:150] + "..." if len(title) > 150 else title
                print(f"   Title: {preview_title}")
            print(f"   Similarity: {score:.4f} (via {search_type})")
            print()

    def generate_final_answer(
        self,
        context: List[Dict[str, Any]],
        user_query: str,
        structured_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a final answer from context and optional structured data (e.g. count results).
        
        Args:
            context: Relevant graph nodes from vector/traversal
            user_query: The user's question
            structured_data: Optional dict from run_count_queries(); if present, the model must use these as authoritative numbers for count/aggregate answers.
        """
        print(f"🤖 Generating final answer based on {len(context)} context documents" + (" and structured query results" if structured_data else "") + "...")
        
        try:
            chat = config.llm
            formatted_context = self._format_context_for_llm(context)
            system_prompt = FINAL_ANSWER_SYSTEM_PROMPT

            if structured_data and structured_data.get("counts"):
                structured_blob = json.dumps(structured_data, indent=2)
                user_prompt = f"""Structured query results (use these as the authoritative numbers for counts/totals):
{structured_blob}

Context from the graph (for extra detail only; do not use this to infer counts):
{formatted_context}

User Query: {user_query}

Answer the user using the structured query results above for any counts or totals. Be concise and accurate."""
            else:
                user_prompt = f"""Context Information:
{formatted_context}

User Query: {user_query}

Please provide a comprehensive answer based on the context provided above."""

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = chat.invoke(messages)
            print("✅ Final answer generated successfully")
            return response.content
        except Exception as e:
            print(f"⚠️  Error generating final answer: {e}")
            import traceback
            traceback.print_exc()
            return "I'm sorry, but I couldn't generate a response to your query due to a technical error."
    
    def _format_context_for_llm(self, context: List[Dict[str, Any]]) -> str:
        """
        Format graph context for LLM consumption as JSON string.
        """

        if not context:
            return "No context nodes available."

        cleaned = []
        for node in context:
            node = dict(node)  # shallow copy
            # Remove internal metadata not useful to the LLM
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

        formatted = {"graph_nodes": cleaned}
        # default=str handles Neo4j types (DateTime, etc.) and other non-JSON-serializable values
        return json.dumps(formatted, indent=2, ensure_ascii=False, default=str)


def _deduplicate_contexts(initial_docs: List[Dict[str, Any]], additional_docs: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    """
    Deduplicate documents from initial and additional contexts based on node_id.
    
    Args:
        initial_docs: Documents from initial vector search
        additional_docs: Documents from graph traversal
        top_k: Maximum number of results to return
        
    Returns:
        Combined list with duplicates removed, preserving initial docs when duplicates exist
    """
    # Use node_id as the key for deduplication
    unique_docs = {}
    
    # First add initial documents (they get priority)
    for doc in initial_docs:
        node_id = doc.get('node_id')
        if node_id:
            unique_docs[node_id] = doc
    
    # Then add additional documents (only if not already present)
    for doc in additional_docs:
        node_id = doc.get('node_id')
        if node_id and node_id not in unique_docs:
            unique_docs[node_id] = doc
    
    # Convert back to list, maintaining order (initial docs first, then additional)
    result = []
    
    # Add initial docs in original order
    for doc in initial_docs:
        node_id = doc.get('node_id')
        if node_id in unique_docs:
            result.append(unique_docs[node_id])
            del unique_docs[node_id]  # Remove to avoid adding again
    
    # Add remaining additional docs
    result.extend(unique_docs.values())
    
    # Sort by similarity score (highest first) and limit results
    sorted_results = sorted(
        result, 
        key=lambda x: x['score'], 
        reverse=True
    )[:top_k]
    
    return sorted_results


def main():
    """
    Example usage of the HybridRAGQuery over the SRM RDF graph.

    Retrieval strategy:
    - List/describe questions ("Which assets...", "List all...") → vector search + graph traversal
      gives a relevant subgraph; the LLM answers from that context. Top_k limits how many nodes
      are shown, so the answer is about the retrieved sample only.
    - Count/aggregate questions ("How many assets...", "number of") → we detect intent and run
      Cypher COUNT queries to get real totals, then pass those numbers to the LLM so the answer
      uses authoritative counts instead of "how many nodes we retrieved".
    """
    print("🚀 Testing HybridRAGQuery over SRM RDF graph")
    print("=" * 50)
    
    # First call - will initialize the singleton and all services
    print("Creating HybridRAGQuery instance:")
    context_retriever = HybridRAGQuery()
    # List all available vector indexes before the first query
    #context_retriever.list_all_vector_indexes()

    # Example SRM / Flanders questions (you can swap these as needed)
    query_1 = "Which standards in the registry describe enrollment or inschrijving credentials?"
    query_2 = "For each Asset, list its title, description, and status."
    query_3 = "Which Assets are available in Dutch language, and what do they describe?"
    query_11 = "Which Assets are available in English language, and what do they describe?"
    query_4 = "how manny assets and are assetdisribution does flanders have?"
    query_5 = "List all Assets with their creators and publishers."
    query_6 = "Which Assets share the same theme or classification?"
    query_7 = "Summarize the Flanders enrollment credential Asset and its key properties."
    query_8 = "Which Assets have implementations or are reused by portals or repositories?"
    query_9 = "List all Agents and their roles as creators or contact points for Assets."
    query_10 = "Describe how languages, statuses, and distributions are modeled for Assets in this graph."
    query = query_4  # default query for this run   


    print("\n" + "🔄 PHASE 1: VECTOR SEARCH" + "\n" + "=" * 50)
    if params.ACTIVATE_INITIAL_VECTOR_SEARCH:
        print("🔍 Performing initial vector search...")
        initial_nodes = context_retriever.get_document_context(query, top_k=params.TOP_K_INITIAL)
    else:
        print("⏭️  Skipping initial vector search (ACTIVATE_INITIAL_VECTOR_SEARCH = False)")
        initial_nodes = []
    
    print("\n" + "🔄 PHASE 2: GRAPH TRAVERSAL ANALYSIS" + "\n" + "=" * 50)

    
    try:
        # Initialize graph traversal method based on configuration
        if params.GRAPH_TRAVERSAL_METHOD == "khop_limited_bfs":
            print("🔧 Initializing k-hop limited BFS traversal...")
            traversal_method = KhopLimitedBFS()
        elif params.GRAPH_TRAVERSAL_METHOD == "khop_limited_bfs_pred_llm":
            print("🔧 Initializing Predicate Constrained BFS traversal...")
            traversal_method = KhopLimitedBFSWithLLM()
        elif params.GRAPH_TRAVERSAL_METHOD == "depth_limited_dfs":
            print("🔧 Initializing Depth Limited DFS traversal...")
            traversal_method = DepthLimitedDFS()
        elif params.GRAPH_TRAVERSAL_METHOD == "depth_limited_dfs_pred_llm":
            print("🔧 Initializing Predicate Constrained DFS traversal...")
            traversal_method = DepthLimitedDFSWithLLM()
        elif params.GRAPH_TRAVERSAL_METHOD == "uniform_cost_search_ucs":
            print("🔧 Initializing Uniform Cost Search UCS traversal...")
            traversal_method = UniformCostSearchUCS()
        elif params.GRAPH_TRAVERSAL_METHOD == "uniform_cost_search_ucs_pred_llm":
            print("🔧 Initializing Uniform Cost Search UCS with Predicate LLM traversal...")
            traversal_method = UniformCostSearchUCSWithLLM()
        elif params.GRAPH_TRAVERSAL_METHOD == "astar_search_heuristic":
            print("🔧 Initializing A* Search with Heuristic traversal...")
            query_embedding = getattr(context_retriever, 'current_query_embedding', None)
            traversal_method = AStarSearchHeuristic(query_embedding=query_embedding)
        elif params.GRAPH_TRAVERSAL_METHOD == "astar_search_heuristic_pred_llm":
            print("🔧 Initializing A* Search with Heuristic Predicate LLM traversal...")
            query_embedding = getattr(context_retriever, 'current_query_embedding', None)
            traversal_method = AStarSearchHeuristicWithLLM(query_embedding=query_embedding)
        elif params.GRAPH_TRAVERSAL_METHOD == "beam_search_over_the_graph":
            print("🔧 Initializing Beam Search Over Graph traversal...")
            traversal_method = BeamSearchOverGraph()
        elif params.GRAPH_TRAVERSAL_METHOD == "beam_search_over_the_graph_pred_llm":
            print("🔧 Initializing Beam Search Over Graph with Predicate LLM traversal...")
            traversal_method = BeamSearchOverGraphWithLLM()
        else:
            print("🔧 Initializing ContextToCypher...")
            traversal_method = ContextToCypher()
        
        # Get additional context through graph traversal
        additional_context = traversal_method.traverse_graph(initial_nodes, query)
        #print('additional_context', json.dumps(additional_context, indent=2, default=str))

        # Combine initial and additional context with deduplication and apply TOP_K limit
        all_context = _deduplicate_contexts(initial_nodes, additional_context, params.TOP_K_TRAVERSAL)
       # print('all_context', json.dumps(all_context, indent=2, default=str))
        
        print(f"\n📊 FINAL CONTEXT SUMMARY:")
        print(f"Initial documents: {len(initial_nodes)}")
        print(f"Additional documents from graph traversal: {len(additional_context)}")
        print(f"Total context documents (after deduplication and TOP_K limit): {len(all_context)}")
        
    except Exception as e:
        print(f"⚠️  Error during graph traversal: {e}")
        print("Continuing with initial context only...")
        all_context = initial_nodes[:params.TOP_K_TRAVERSAL]  # Apply TOP_K limit even for initial context only
    
    print("\n" + "🔄 PHASE 3: ANSWER GENERATION" + "\n" + "=" * 50)

    # For count/aggregate questions, run Cypher count queries so the answer uses real totals, not top_k sample
    structured_data = None
    if context_retriever.is_count_or_aggregate_intent(query):
        print("📊 Count/aggregate intent detected: running Cypher count queries for authoritative numbers...")
        structured_data = context_retriever.run_count_queries(query)
        print("   Count results:", structured_data)

    # Generate final answer (with optional structured count data so the model reports real totals)
    if all_context or structured_data:
        final_answer = context_retriever.generate_final_answer(
            all_context, query, structured_data=structured_data
        )
        print("\n" + "🎯 FINAL ANSWER" + "\n" + "=" * 50)
        print(final_answer)
    else:
        print("⚠️  No context available to generate an answer.")
        print("Please check your vector search configuration and graph traversal setup.")
    
    print("\n" + "=" * 50)
    print("🏁 Query processing completed!")


if __name__ == "__main__":
    main()

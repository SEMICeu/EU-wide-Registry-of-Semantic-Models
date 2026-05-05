# main.py

import os
import glob
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional, Tuple
from getpass import getpass
from dotenv import load_dotenv

from langchain_openai import OpenAIEmbeddings
from langchain_neo4j import Neo4jGraph

# Ensure project root is importable when running this file directly:
# `python .\graph_rag\setup\ingestion.py`
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Windows terminals may default to cp1252 and crash on emoji prints.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

try:
    from . import params
except ImportError:
    import params  # type: ignore
import config


# When True, skip text → graph extraction and operate directly
# on the RDF graph already loaded into Neo4j (from flanders.ttl).
USE_RDF_GRAPH_ONLY = True


class KnowledgeGraphIngestion:
    """
    A comprehensive class for ingesting documents into a Neo4j knowledge graph
    with optional vector embeddings and indexes.
    """
    
    def __init__(self):
        """Initialize the ingestion system with all services."""
        # Core services
        self.graph: Optional[Neo4jGraph] = None
        self.embeddings: Optional[OpenAIEmbeddings] = None
        
        # Track newly ingested data for this session
        self.current_session_nodes: List[str] = []
        self.current_session_relationships: List[str] = []
    
    def _initialize_embedding_services(self) -> None:
        """Initialize embedding services (uses embeddings from config)."""
        # Use embeddings from config (PWC/Azure endpoint)
        self.embeddings = config.embeddings
    
    def _ensure_services_initialized(self) -> None:
        """Ensure embedding services are properly initialized."""
        if self.embeddings is None:
            print("🔧 Initializing embedding services...")
            self._initialize_embedding_services()
    
    def setup_environment(self) -> None:
        """Load environment variables and validate required credentials."""
        print("🔧 Setting up environment...")
        # Keep container-provided env vars (e.g. NEO4J_URI=bolt://neo4j:7687)
        # and only fill missing values from .env.
        load_dotenv(override=False)
        
        # PWC API Key (used for LLM and embeddings via config)
        if not os.getenv("PWC_API_KEY"):
            if sys.stdin and sys.stdin.isatty():
                os.environ["PWC_API_KEY"] = getpass("Enter your PWC API key: ")
            else:
                raise RuntimeError(
                    "PWC_API_KEY is not set and interactive prompt is unavailable. "
                    "Set PWC_API_KEY via environment or .env before startup."
                )
        
        # Neo4j Credentials validation
        self._validate_neo4j_credentials()
        print("✅ Environment setup complete")
    
    def _validate_neo4j_credentials(self) -> None:
        """Validate Neo4j connection credentials."""
        required_vars = ["NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    def initialize_neo4j_connection(self) -> None:
        """Initialize Neo4j graph connection."""
        print("🔗 Initializing Neo4j connection...")
        
        self.graph = Neo4jGraph(
            url=os.getenv("NEO4J_URI"),
            username=os.getenv("NEO4J_USERNAME"),
            password=os.getenv("NEO4J_PASSWORD"),
            refresh_schema=False,
        )
        
        # Check Neo4j version for compatibility
        self._check_neo4j_version()
        
        print("✅ Neo4j connection established")
    
    def _ensure_n10s_constraint_and_config(self) -> None:
        """
        Ensure required neosemantics (n10s) constraint and graph config exist.

        This mirrors the setup in main.py so this script can fully own
        the "load TTL + prepare graph" workflow.
        """
        print("🔧 Ensuring n10s constraint and graph configuration...")

        # Required uniqueness constraint for n10s imports
        constraint_cypher = """
        CREATE CONSTRAINT n10s_unique_uri
        IF NOT EXISTS
        FOR (r:Resource)
        REQUIRE r.uri IS UNIQUE
        """
        self.graph.query(constraint_cypher)

        # Graph config (idempotent; will error if already initialized)
        config = {
            "handleVocabUris": "SHORTEN",
            "handleMultival": "ARRAY",
            "keepLangTag": True,
            "handleRDFTypes": "LABELS",
        }

        try:
            self.graph.query(
                "CALL n10s.graphconfig.init($config)",
                {"config": config},
            )
        except Exception:
            # Most likely already initialized; safe to ignore
            pass

        print("✅ n10s constraint and graph configuration ready")

    def _import_ttl_with_neosemantics(self, ttl_file_name: str = "data_SRM.ttl") -> None:
        """
        Import a TTL file into Neo4j using neosemantics (n10s) from
        graph_rag/setup/data.
        """
        local_ttl_path = os.path.join(_THIS_DIR, "data", ttl_file_name)
        if not os.path.exists(local_ttl_path):
            raise FileNotFoundError(f"TTL file not found: {local_ttl_path}")

        print(f"📥 Importing TTL via n10s from local file: {local_ttl_path}")
        with open(local_ttl_path, "r", encoding="utf-8") as f:
            ttl_content = f.read()

        result = self.graph.query(
            """
            CALL n10s.rdf.import.inline(
              $rdf,
              $format,
              { handleVocabUris: "SHORTEN",
                handleMultival: "ARRAY",
                keepLangTag: true,
                handleRDFTypes: "LABELS" }
            )
            """,
            {"rdf": ttl_content, "format": "Turtle"},
        )

        if result:
            summary = result[0]
            print("📈 n10s import summary:", summary)
        else:
            print("⚠️ n10s import returned no summary rows")

    def _prepare_ttl_files_for_neo4j_import(self, ttl_file_names: List[str]) -> List[str]:
        """
        Validate TTL files under graph_rag/setup/data and return importable names.
        """
        data_dir = os.path.join(_THIS_DIR, "data")
        prepared: List[str] = []
        missing: List[str] = []

        for ttl_name in ttl_file_names:
            root_data_path = os.path.join(data_dir, ttl_name)
            if os.path.exists(root_data_path):
                prepared.append(ttl_name)
            else:
                missing.append(ttl_name)

        if missing:
            print(f"⚠️ Missing TTL file(s) in graph_rag/setup/data: {', '.join(missing)}")

        return prepared
    
    def _check_neo4j_version(self) -> None:
        """Check Neo4j version and log compatibility information."""
        try:
            version_result = self.graph.query("CALL dbms.components() YIELD name, versions, edition WHERE name = 'Neo4j Kernel' RETURN versions[0] as version")
            if version_result:
                version = version_result[0]['version']
                print(f"ℹ️  Neo4j version: {version}")
                
                # Parse version to determine vector index syntax
                major_version = int(version.split('.')[0])
                if major_version >= 5:
                    print("ℹ️  Using Neo4j 5+ vector index syntax")
                    # Test if relationship vector indexes are supported
                    self._test_relationship_vector_support()
                else:
                    print("ℹ️  Using legacy Neo4j vector index syntax")
                    print("⚠️  Relationship vector indexes may not be supported in this version")
            else:
                print("ℹ️  Could not determine Neo4j version")
        except Exception as e:
            print(f"ℹ️  Could not check Neo4j version: {e}")
    
    def _test_relationship_vector_support(self) -> None:
        """Test if relationship vector indexes are supported in this Neo4j instance."""
        try:
            # Try to create a test relationship vector index with configurable parameters
            test_result = self.graph.query(f"""
                CREATE VECTOR INDEX test_rel_vector_index
                IF NOT EXISTS
                FOR ()-[r:TEST_REL]-() ON (r.test_embedding)
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {params.vector_embedding_dimensions},
                        `vector.similarity_function`: '{params.vector_similarity_function}'
                    }}
                }}
            """)
            
            # If successful, drop the test index
            self.graph.query("DROP INDEX test_rel_vector_index IF EXISTS")
            print("✅ Relationship vector indexes are supported")
            
        except Exception as e:
            print(f"⚠️  Relationship vector indexes may not be supported: {e}")
            print("ℹ️  This could be due to Neo4j version, edition, or configuration")
    
    def create_vector_embeddings(self) -> None:
        """Create vector embeddings for graph properties if enabled."""
        if not params.add_vector_index:
            print("ℹ️  Vector embeddings disabled in configuration")
            return
        
        print("🔍 Creating vector embeddings...")
        
        try:
            # Ensure all services are initialized
            self._ensure_services_initialized()
            
            # Process nodes and relationships in parallel
            self._parallel_process_embeddings()
            
            # Create vector indexes in parallel
            self._parallel_create_vector_indexes()
            
            # Verify embeddings were created
            self._verify_embeddings()
            
            print("✅ Vector embeddings creation complete")
            
        except Exception as e:
            print(f"⚠️  Error creating vector embeddings: {e}")
            import traceback
            traceback.print_exc()
    
    def _parallel_process_embeddings(self) -> None:
        """Process node and relationship embeddings in parallel."""
        
        def process_node_embeddings():
            """Process embeddings for node properties."""
            print("📋 Processing node embeddings...")
            
            nodes_data = self._get_nodes_data()
            if not nodes_data:
                print("⚠️  No nodes found for embedding")
                return []
            
            properties_to_embed = self._collect_node_properties_to_embed(nodes_data)
            
            if properties_to_embed:
                self._parallel_create_embeddings_batch(properties_to_embed, "node")
                print(f"✅ Created embeddings for {len(properties_to_embed)} node properties")
                return properties_to_embed
            else:
                print("⚠️  No suitable node properties found for embedding")
                return []
        
        def process_relationship_embeddings():
            """Process embeddings for relationship properties."""
            print("📋 Processing relationship embeddings...")
            
            relationships_data = self._get_relationships_data()
            if not relationships_data:
                print("⚠️  No relationships found for embedding")
                return []
            
            properties_to_embed = self._collect_relationship_properties_to_embed(relationships_data)
            
            if properties_to_embed:
                self._parallel_create_embeddings_batch(properties_to_embed, "relationship")
                print(f"✅ Created embeddings for {len(properties_to_embed)} relationship properties")
                return properties_to_embed
            else:
                print("⚠️  No suitable relationship properties found for embedding")
                return []
        
        # Process nodes and relationships in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            node_future = executor.submit(process_node_embeddings)
            rel_future = executor.submit(process_relationship_embeddings)
            
            # Wait for both to complete
            node_properties = node_future.result()
            rel_properties = rel_future.result()
    
    def _parallel_create_vector_indexes(self) -> None:
        """Create vector indexes in parallel."""
        print("🔍 Creating vector indexes...")
        
        properties_to_index = self._get_properties_to_index()
        
        if not properties_to_index:
            print("⚠️  No properties specified for indexing")
            return
        
        print(f"Creating indexes for properties: {sorted(list(properties_to_index))}")
        
        def create_property_indexes_parallel(prop: str) -> Tuple[str, int]:
            """Create vector indexes for a specific property in parallel."""
            return prop, self._create_property_indexes(prop)
        
        # Create indexes for all properties in parallel
        max_workers = min(4, len(properties_to_index))
        total_created = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_prop = {
                executor.submit(create_property_indexes_parallel, prop): prop
                for prop in properties_to_index
            }
            
            for future in as_completed(future_to_prop):
                prop, created = future.result()
                if created:
                    total_created += 1
        
        print(f"✅ Successfully created vector indexes for {total_created} properties")
    
    def _get_nodes_data(self) -> List[Dict[str, Any]]:
        """Retrieve nodes data from Neo4j for current session only."""
        if not self.current_session_nodes:
            print("ℹ️  No current session nodes to process")
            return []
        
        print(f"📋 Getting data for {len(self.current_session_nodes)} current session nodes")
        return self.graph.query("""
            MATCH (n) 
            WHERE elementId(n) IN $node_ids
            RETURN labels(n) as node_labels, keys(n) as properties, elementId(n) as node_id
        """, {"node_ids": self.current_session_nodes})
    
    def _get_relationships_data(self) -> List[Dict[str, Any]]:
        """Retrieve relationships data from Neo4j for current session only."""
        if not self.current_session_relationships:
            print("⚠️  No current session relationships found - falling back to all relationships")
            print("🔍 Getting all relationships from database...")
            
            # Fallback: get all non-MENTIONS relationships
            result = self.graph.query("""
                MATCH ()-[r]->() 
                RETURN type(r) as rel_type, keys(r) as properties, elementId(r) as rel_id
                LIMIT 1000
            """)
            
            return result
        
        print(f"📋 Getting data for {len(self.current_session_relationships)} current session relationships (excluding MENTIONS)")
        result = self.graph.query("""
            MATCH ()-[r]->() 
            WHERE elementId(r) IN $rel_ids AND type(r) <> 'MENTIONS'
            RETURN type(r) as rel_type, keys(r) as properties, elementId(r) as rel_id
        """, {"rel_ids": self.current_session_relationships})
        
        return result
    
    def _collect_node_properties_to_embed(self, nodes_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Collect node properties that should be embedded."""
        properties_to_embed = []
        
        for node_info in nodes_data:
            if not self._should_process_node(node_info):
                continue
            
            node_data = self._get_node_data(node_info['node_id'])
            if not node_data:
                continue
            
            properties_to_embed.extend(
                self._extract_node_property_embeddings(node_info, node_data)
            )
        
        return properties_to_embed
    
    def _collect_relationship_properties_to_embed(self, relationships_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Collect relationship properties that should be embedded."""
        properties_to_embed = []
        
        for rel_info in relationships_data:
            if not self._should_process_relationship(rel_info):
                continue
            
            # Get relationship data from Neo4j
            rel_data = self._get_relationship_data(rel_info['rel_id'])
            if not rel_data:
                continue
            
            # Extract properties for embedding
            extracted_props = self._extract_relationship_property_embeddings(rel_info, rel_data)
            if extracted_props:
                properties_to_embed.extend(extracted_props)
        
        return properties_to_embed
    
    def _should_process_node(self, node_info: Dict[str, Any]) -> bool:
        """Check if node should be processed based on filters."""
        if not params.filter_node_labels_to_index:
            return True
        
        # Check for "ALL" parameter
        if "ALL" in params.filter_node_labels_to_index:
            return True
        
        node_labels = node_info.get('node_labels', [])
        return any(label in params.filter_node_labels_to_index for label in node_labels)
    
    def _should_process_relationship(self, rel_info: Dict[str, Any]) -> bool:
        """Check if relationship should be processed based on filters."""
        rel_type = rel_info.get('rel_type', '')
        
        if not params.filter_rels_labels_to_index:
            return True
        
        # Check for "ALL" parameter
        if "ALL" in params.filter_rels_labels_to_index:
            return True
        
        result = rel_type in params.filter_rels_labels_to_index
        return result
    
    def _get_node_data(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node data by ID."""
        result = self.graph.query("""
            MATCH (n) 
            WHERE elementId(n) = $node_id 
            RETURN n
        """, {"node_id": node_id})
        
        return result[0]['n'] if result else None
    
    def _get_relationship_data(self, rel_id: str) -> Optional[Dict[str, Any]]:
        """Get relationship data by ID."""
        result = self.graph.query("""
            MATCH ()-[r]->() 
            WHERE elementId(r) = $rel_id 
            RETURN r, properties(r) as all_props
        """, {"rel_id": rel_id})
        
        return result[0] if result else None
    
    def _extract_node_property_embeddings(self, node_info: Dict[str, Any], node_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract embeddings for node properties."""
        properties_to_embed = []
        node_labels = node_info.get('node_labels', [])
        properties = node_info.get('properties', [])
        
        for prop in properties:
            if not self._should_embed_node_property(prop):
                continue
            
            if prop in node_data and node_data[prop] is not None:
                value = str(node_data[prop])
                if self._is_valid_embedding_value(value, prop):
                    context_text = f"Node type: {', '.join(node_labels) if node_labels else 'Unknown'} | Property {prop}: {value}"
                    
                    properties_to_embed.append({
                        'node_id': node_info['node_id'],
                        'property_name': prop,
                        'text': context_text,
                        'embedding_name': f'embedding_{prop}',
                        'type': 'node'
                    })
        
        return properties_to_embed
    
    def _extract_relationship_property_embeddings(self, rel_info: Dict[str, Any], rel_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract relationship properties that should be embedded."""
        properties_to_embed = []
        rel_type = rel_info.get('rel_type', 'Unknown')
        properties = rel_info.get('properties', [])
        all_props = rel_data.get('all_props', {})
        
        for prop in properties:
            if not self._should_embed_relationship_property(prop):
                continue
            
            if prop not in all_props:
                continue
                
            if all_props[prop] is None:
                continue
            
            value = str(all_props[prop])
            
            if self._is_valid_embedding_value(value, prop):
                context_text = f"Relationship type: {rel_type} | Property {prop}: {value}"
                
                properties_to_embed.append({
                    'rel_id': rel_info['rel_id'],
                    'property_name': prop,
                    'text': context_text,
                    'embedding_name': f'embedding_{prop}',
                    'type': 'relationship'
                })
        
        return properties_to_embed
    
    def _should_embed_node_property(self, prop: str) -> bool:
        """Check if node property should be embedded."""
        if not params.filter_node_properties_to_index:
            return True
        
        # Check for "ALL" parameter
        if "ALL" in params.filter_node_properties_to_index:
            return True
        
        return prop in params.filter_node_properties_to_index
    
    def _should_embed_relationship_property(self, prop: str) -> bool:
        """Check if relationship property should be embedded."""
        if not params.filter_rels_properties_to_index:
            return True
        
        # Check for "ALL" parameter
        if "ALL" in params.filter_rels_properties_to_index:
            return True
        
        result = prop in params.filter_rels_properties_to_index
        return result
    
    def _should_embed_document_property(self, prop: str) -> bool:
        """Check if document property should be embedded based on node property filters."""
        if not params.filter_node_properties_to_index:
            return True
        
        # Check for "ALL" parameter
        if "ALL" in params.filter_node_properties_to_index:
            return True
        
        return prop in params.filter_node_properties_to_index
    
    def _is_valid_embedding_value(self, value: str, prop: str) -> bool:
        """Check if value is suitable for embedding."""
        return (len(value) < params.max_embedding_text_length and 
                not value.startswith(params.embedding_exclusion_prefix) and 
                not prop.startswith('embedding'))
    
    def _create_embeddings_batch(self, properties_to_embed: List[Dict[str, Any]], embed_type: str) -> None:
        """Create embeddings in batches with parallel processing."""
        if not properties_to_embed:
            return
            
        # Use the parallel version for better performance
        self._parallel_create_embeddings_batch(properties_to_embed, embed_type)
    
    def _parallel_create_embeddings_batch(self, properties_to_embed: List[Dict[str, Any]], embed_type: str) -> None:
        """Create embeddings in parallel batches."""
        if not properties_to_embed:
            return
        
        def create_embedding_batch(batch_info: Tuple[int, List[Dict]]) -> Tuple[int, List[List[float]]]:
            """Create embeddings for a single batch."""
            batch_idx, batch = batch_info
            texts = [item['text'] for item in batch]
            embeddings = self.embeddings.embed_documents(texts)
            return batch_idx, embeddings
        
        # Split into batches
        batch_size = params.embedding_batch_size
        batches = [
            properties_to_embed[i:i+batch_size] 
            for i in range(0, len(properties_to_embed), batch_size)
        ]
        
        total_batches = len(batches)
        print(f"🔍 Processing {total_batches} embedding batches in parallel...")
        
        # Process batches in parallel
        max_workers = min(4, total_batches, os.cpu_count() or 2)  # Limit to avoid API rate limits
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all batch tasks
            batch_tasks = [(i, batch) for i, batch in enumerate(batches)]
            future_to_batch = {
                executor.submit(create_embedding_batch, batch_info): batch_info
                for batch_info in batch_tasks
            }
            
            # Collect results maintaining order
            batch_results = [None] * total_batches
            completed = 0
            
            for future in as_completed(future_to_batch):
                try:
                    batch_idx, embeddings = future.result()
                    batch_results[batch_idx] = embeddings
                    completed += 1
                    print(f"{embed_type.title()} properties batch {completed}/{total_batches} - Embedded {len(embeddings)} properties")
                    
                except Exception as batch_error:
                    batch_info = future_to_batch[future]
                    print(f"⚠️  Error processing {embed_type} properties batch {batch_info[0] + 1}: {batch_error}")
                    batch_results[batch_info[0]] = []
        
        # Store embeddings in order
        for batch_idx, (batch, embeddings) in enumerate(zip(batches, batch_results)):
            if embeddings:
                for item, embedding in zip(batch, embeddings):
                    self._store_embedding(item, embedding, embed_type)
    
    def _store_embedding(self, item: Dict[str, Any], embedding: List[float], embed_type: str) -> None:
        """Store embedding in Neo4j."""
        if embed_type == 'node' or embed_type == 'document_node':
            self.graph.query(f"""
                MATCH (n) 
                WHERE elementId(n) = $node_id 
                SET n.{item['embedding_name']} = $embedding
            """, {
                "node_id": item['node_id'], 
                "embedding": embedding
            })
        else:  # relationship
            self.graph.query(f"""
                MATCH ()-[r]->() 
                WHERE elementId(r) = $rel_id 
                SET r.{item['embedding_name']} = $embedding
            """, {
                "rel_id": item['rel_id'], 
                "embedding": embedding
            })
    
    def _get_properties_to_index(self) -> set:
        """Get set of properties that should be indexed."""
        properties_to_index = set()
        
        if params.filter_node_properties_to_index:
            properties_to_index.update(params.filter_node_properties_to_index)
        
        if params.filter_rels_properties_to_index:
            properties_to_index.update(params.filter_rels_properties_to_index)
        
        return properties_to_index
    
    def _create_property_indexes(self, prop: str) -> bool:
        """Create vector indexes for a specific property on current session nodes and relationships only."""
        if not self.current_session_nodes and not self.current_session_relationships:
            print(f"ℹ️  No current session data to index for property {prop}")
            return False
        
        success_count = 0
        
        try:
            # Get unique node labels that have this embedding property in current session
            if self.current_session_nodes:
                node_labels_result = self.graph.query(f"""
                    MATCH (n) 
                    WHERE elementId(n) IN $node_ids AND n.embedding_{prop} IS NOT NULL 
                    RETURN DISTINCT labels(n) as node_labels
                """, {"node_ids": self.current_session_nodes})
                
                # Create indexes for each node label that has this property
                for label_info in node_labels_result:
                    node_labels = label_info['node_labels']
                    for label in node_labels:
                        try:
                            index_name = f"embedding_{prop}_{label.lower()}_index"
                            self.graph.query(f"""
                                CREATE VECTOR INDEX {index_name}
                                IF NOT EXISTS
                                FOR (n:{label}) ON (n.embedding_{prop})
                                OPTIONS {{
                                    indexConfig: {{
                                        `vector.dimensions`: {params.vector_embedding_dimensions},
                                        `vector.similarity_function`: '{params.vector_similarity_function}'
                                    }}
                                }}
                            """)
                            print(f"✅ Created node vector index for {label}.embedding_{prop}")
                            success_count += 1
                            
                        except Exception as node_error:
                            print(f"⚠️  Could not create node index for {label}.embedding_{prop}: {node_error}")
            
            # Get unique relationship types that have this embedding property in current session
            if self.current_session_relationships:
                rel_types_result = self.graph.query(f"""
                    MATCH ()-[r]->() 
                    WHERE elementId(r) IN $rel_ids AND r.embedding_{prop} IS NOT NULL 
                    RETURN DISTINCT type(r) as rel_type
                """, {"rel_ids": self.current_session_relationships})
                
                # Create indexes for each relationship type that has this property
                for rel_info in rel_types_result:
                    rel_type = rel_info['rel_type']
                    try:
                        index_name = f"embedding_{prop}_{rel_type.lower()}_rel_index"
                        
                        # Use configurable vector parameters for relationship indexes
                        self.graph.query(f"""
                            CREATE VECTOR INDEX {index_name}
                            IF NOT EXISTS
                            FOR ()-[r:{rel_type}]-() ON (r.embedding_{prop})
                            OPTIONS {{
                                indexConfig: {{
                                    `vector.dimensions`: {params.vector_embedding_dimensions},
                                    `vector.similarity_function`: '{params.vector_similarity_function}'
                                }}
                            }}
                        """)
                        
                        print(f"✅ Created relationship vector index for {rel_type}.embedding_{prop}")
                        success_count += 1
                        
                    except Exception as rel_error:
                        print(f"⚠️  Could not create relationship index for {rel_type}.embedding_{prop}: {rel_error}")
                        
                        # Let's also check what Neo4j version we're dealing with
                        print(f"ℹ️  This might be due to Neo4j version compatibility.")
                        print(f"ℹ️  Relationship vector indexes require Neo4j 5.0+ with specific configurations.")
            
            return success_count > 0
            
        except Exception as e:
            print(f"⚠️  Error creating indexes for embedding_{prop}: {e}")
            return False
    
    def _verify_embeddings(self) -> None:
        """Verify that embeddings were successfully created for current session only."""
        print("\n📊 Verifying embeddings for current session...")
        
        if not self.current_session_nodes and not self.current_session_relationships:
            print("ℹ️  No current session data to verify")
            return
        
        try:
            # Check node embeddings for current session
            properties_to_check = self._get_properties_to_index()
            
            for prop in sorted(properties_to_check):
                node_count = 0
                rel_count = 0
                
                # Count current session nodes with this embedding
                if self.current_session_nodes:
                    node_count_result = self.graph.query(f"""
                        MATCH (n) 
                        WHERE elementId(n) IN $node_ids AND n.embedding_{prop} IS NOT NULL 
                        RETURN count(n) as count
                    """, {"node_ids": self.current_session_nodes})
                    
                    node_count = node_count_result[0]['count'] if node_count_result else 0
                
                # Count current session relationships with this embedding
                if self.current_session_relationships:
                    rel_count_result = self.graph.query(f"""
                        MATCH ()-[r]->() 
                        WHERE elementId(r) IN $rel_ids AND r.embedding_{prop} IS NOT NULL 
                        RETURN count(r) as count
                    """, {"rel_ids": self.current_session_relationships})
                    
                    rel_count = rel_count_result[0]['count'] if rel_count_result else 0
                
                if node_count > 0 or rel_count > 0:
                    print(f"✅ {prop}: {node_count} nodes, {rel_count} relationships")
                else:
                    print(f"⚠️  {prop}: No embeddings found in current session")
            
            # Overall summary for current session
            total_node_embeddings = 0
            total_rel_embeddings = 0
            
            for prop in properties_to_check:
                if self.current_session_nodes:
                    node_result = self.graph.query(f"""
                        MATCH (n) 
                        WHERE elementId(n) IN $node_ids AND n.embedding_{prop} IS NOT NULL 
                        RETURN count(n) as count
                    """, {"node_ids": self.current_session_nodes})
                    total_node_embeddings += node_result[0]['count'] if node_result else 0
                
                if self.current_session_relationships:
                    rel_result = self.graph.query(f"""
                        MATCH ()-[r]->() 
                        WHERE elementId(r) IN $rel_ids AND r.embedding_{prop} IS NOT NULL 
                        RETURN count(r) as count
                    """, {"rel_ids": self.current_session_relationships})
                    total_rel_embeddings += rel_result[0]['count'] if rel_result else 0
            
            print(f"\n🎉 Total embeddings created for current session: {total_node_embeddings + total_rel_embeddings}")
            print(f"   - Node embeddings: {total_node_embeddings}")
            print(f"   - Relationship embeddings: {total_rel_embeddings}")
            
        except Exception as e:
            print(f"⚠️  Error verifying embeddings: {e}")
    
    def add_multivectors_to_document_nodes(self) -> None:
        """Add custom properties to Document nodes from current session only."""
        if not hasattr(params, 'document_multi_vector_properties') or not params.document_multi_vector_properties:
            print("ℹ️  No document node properties to add")
            return
        
        if not self.current_session_sources:
            print("ℹ️  No current session sources to process")
            return
        
        print("🔧 Adding custom properties to Document nodes from current session...")
        
        try:
            # Get Document nodes from current session sources only
            sources_list = list(self.current_session_sources)
            document_nodes = self.graph.query("""
                MATCH (d:Document) 
                WHERE any(source IN $sources WHERE d.source CONTAINS source OR d.source = source)
                RETURN elementId(d) as node_id, d.text as text, d.source as source
            """, {"sources": sources_list})
            
            if not document_nodes:
                print("⚠️  No Document nodes found in current session")
                return
            
            print(f"📄 Found {len(document_nodes)} Document nodes from current session to process")
            
            # Parallel processing of document properties
            added_properties, properties_to_embed = self._parallel_process_document_properties(document_nodes)
            
            print(f"✅ Successfully processed multi-vector properties for {len(document_nodes)} Document nodes")
            
            # Create vector embeddings for the new properties
            if params.add_vector_index and properties_to_embed:
                print("🔍 Creating vector embeddings for new document properties...")
                
                # Show which properties will get embeddings
                properties_with_embeddings = {item['property_name'] for item in properties_to_embed}
                print(f"ℹ️  Creating embeddings for properties: {sorted(properties_with_embeddings)}")
                
                # Ensure embedding services are initialized
                self._ensure_services_initialized()
                
                # Create embeddings in parallel batches
                self._parallel_create_embeddings_batch(properties_to_embed, "document_node")
                
                # Create vector indexes for the new properties
                self._parallel_create_document_property_indexes(added_properties)
                
                # Verify the embeddings were created
                self._verify_document_property_embeddings(added_properties)
                
                print("✅ Vector embeddings for document properties created successfully")
            else:
                if not params.add_vector_index:
                    print("ℹ️  Vector embeddings disabled in configuration")
                elif not properties_to_embed:
                    print("ℹ️  No valid properties found for embedding")
                else:
                    print("ℹ️  No properties to embed")
            
        except Exception as e:
            print(f"⚠️  Error adding properties to Document nodes: {e}")
            import traceback
            traceback.print_exc()
    
    def _parallel_process_document_properties(self, document_nodes: List[Dict]) -> Tuple[set, List[Dict]]:
        """Process document properties in parallel using ThreadPoolExecutor."""
        
        def process_single_property(doc_node: Dict, prop_config: Dict) -> Dict:
            """Process a single document-property combination."""
            node_id = doc_node['node_id']
            document_text = doc_node['text']
            source = doc_node.get('source', 'unknown')
            property_name = prop_config.get('property_name')
            prompt = prop_config.get('prompt')
            
            if not property_name or not prompt:
                return {'error': f"Invalid property config: {prop_config}"}
            
            try:
                # Create the full prompt with document text
                full_prompt = f"{prompt}\n\nDocument text:\n{document_text}"
                
                # Call LLM to generate the property value
                response = self.llm.invoke(full_prompt)
                property_value = response.content.strip()
                
                return {
                    'node_id': node_id,
                    'property_name': property_name,
                    'property_value': property_value,
                    'document_text': document_text,
                    'source': source,
                    'success': True
                }
                
            except Exception as e:
                return {
                    'error': f"Error processing {property_name} for {source}: {e}",
                    'node_id': node_id,
                    'property_name': property_name,
                    'success': False
                }
        
        # Create all combinations of documents and properties
        tasks = []
        for doc_node in document_nodes:
            for prop_config in params.document_multi_vector_properties:
                tasks.append((doc_node, prop_config))
        
        print(f"🚀 Processing {len(tasks)} document-property combinations in parallel...")
        
        # Process in parallel with optimal number of workers
        max_workers = min(8, len(tasks), os.cpu_count() or 4)
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(process_single_property, doc_node, prop_config): (doc_node, prop_config)
                for doc_node, prop_config in tasks
            }
            
            # Collect results as they complete
            completed = 0
            for future in as_completed(future_to_task):
                result = future.result()
                results.append(result)
                completed += 1
                
                if completed % 10 == 0 or completed == len(tasks):
                    print(f"📝 Completed {completed}/{len(tasks)} property generations")
        
        # Process results and update Neo4j in batches
        return self._batch_update_document_properties(results)
    
    def _batch_update_document_properties(self, results: List[Dict]) -> Tuple[set, List[Dict]]:
        """Update document properties in Neo4j using batch operations."""
        added_properties = set()
        properties_to_embed = []
        successful_updates = []
        
        # Separate successful and failed results
        for result in results:
            if result.get('success'):
                successful_updates.append(result)
            else:
                if 'error' in result:
                    print(f"⚠️  {result['error']}")
        
        if not successful_updates:
            print("⚠️  No successful property generations to update")
            return added_properties, properties_to_embed
        
        # Group updates by property name for batch processing
        property_groups = {}
        for result in successful_updates:
            prop_name = result['property_name']
            if prop_name not in property_groups:
                property_groups[prop_name] = []
            property_groups[prop_name].append(result)
        
        # Batch update each property type
        for property_name, group in property_groups.items():
            print(f"📝 Batch updating {len(group)} nodes with property '{property_name}'")
            
            try:
                # Prepare batch update query
                batch_params = []
                for result in group:
                    batch_params.append({
                        'node_id': result['node_id'],
                        'property_value': result['property_value']
                    })
                
                # Execute batch update
                self.graph.query(f"""
                    UNWIND $batch_params as param
                    MATCH (d) 
                    WHERE elementId(d) = param.node_id 
                    SET d.{property_name} = param.property_value
                """, {'batch_params': batch_params})
                
                added_properties.add(property_name)
                
                # Prepare for embedding creation
                for result in group:
                    if self._is_valid_embedding_value(result['property_value'], property_name):
                        context_text = f"Node type: Document | Property {property_name}: {result['property_value']}"
                        
                        properties_to_embed.append({
                            'node_id': result['node_id'],
                            'property_name': property_name,
                            'text': context_text,
                            'embedding_name': f'embedding_{property_name}',
                            'type': 'node'
                        })
                
                print(f"✅ Successfully updated {len(group)} nodes with property '{property_name}'")
                
            except Exception as e:
                print(f"⚠️  Error batch updating property '{property_name}': {e}")
        
        return added_properties, properties_to_embed
    
    def _parallel_create_document_property_indexes(self, added_properties: set) -> None:
        """Create vector indexes for document properties in parallel."""
        if not added_properties:
            print("ℹ️  No document properties to index")
            return
        
        print("🔍 Creating vector indexes for new document properties...")
        print(f"Creating indexes for document properties: {sorted(added_properties)}")
        
        def create_single_index(prop: str) -> Tuple[str, bool, str]:
            """Create a single vector index."""
            try:
                index_name = f"embedding_{prop}_document_index"
                self.graph.query(f"""
                    CREATE VECTOR INDEX {index_name}
                    IF NOT EXISTS
                    FOR (n:Document) ON (n.embedding_{prop})
                    OPTIONS {{
                        indexConfig: {{
                            `vector.dimensions`: {params.vector_embedding_dimensions},
                            `vector.similarity_function`: '{params.vector_similarity_function}'
                        }}
                    }}
                """)
                return prop, True, f"Created vector index for Document.embedding_{prop}"
                
            except Exception as e:
                return prop, False, f"Could not create vector index for Document.embedding_{prop}: {e}"
        
        # Create indexes in parallel
        max_workers = min(4, len(added_properties))
        created_indexes = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_prop = {
                executor.submit(create_single_index, prop): prop
                for prop in added_properties
            }
            
            for future in as_completed(future_to_prop):
                prop, success, message = future.result()
                if success:
                    print(f"✅ {message}")
                    created_indexes += 1
                else:
                    print(f"⚠️  {message}")
        
        print(f"✅ Successfully created {created_indexes} vector indexes for document properties")
    
    def _verify_document_property_embeddings(self, added_properties: set) -> None:
        """Verify that embeddings were successfully created for document properties in current session only."""
        print("\n📊 Verifying document property embeddings for current session...")
        
        if not added_properties:
            print("ℹ️  No document properties to verify")
            return
        
        if not self.current_session_sources:
            print("ℹ️  No current session sources to verify")
            return
        
        try:
            total_embeddings = 0
            sources_list = list(self.current_session_sources)
            
            for prop in sorted(added_properties):
                # Count Document nodes from current session with this embedding
                count_result = self.graph.query(f"""
                    MATCH (d:Document) 
                    WHERE any(source IN $sources WHERE d.source CONTAINS source OR d.source = source)
                    AND d.embedding_{prop} IS NOT NULL 
                    RETURN count(d) as count
                """, {"sources": sources_list})
                
                count = count_result[0]['count'] if count_result else 0
                total_embeddings += count
                
                if count > 0:
                    print(f"✅ embedding_{prop}: {count} Document nodes from current session")
                else:
                    print(f"⚠️  embedding_{prop}: No embeddings found in current session Document nodes")
            
            print(f"\n🎉 Total document property embeddings created for current session: {total_embeddings}")
            
        except Exception as e:
            print(f"⚠️  Error verifying document property embeddings: {e}")
    
    def _reset_session_tracking(self) -> None:
        """Reset session tracking for a new ingestion run."""
        self.current_session_nodes.clear()
        self.current_session_relationships.clear()
        print("🔄 Reset session tracking for new ingestion run")

    def _seed_session_from_existing_rdf_graph(self) -> None:
        """
        Seed current_session_nodes and current_session_relationships
        from the RDF graph already loaded into Neo4j (via n10s).

        This is used when we are not ingesting from text documents,
        but instead operating directly on the existing graph.
        """
        print("🔍 Seeding session from existing RDF graph in Neo4j...")

        # Optionally filter to specific labels / relationship types via params
        try:
            # Nodes: either all, or filtered via params.filter_node_labels_to_index
            if params.filter_node_labels_to_index and "ALL" not in params.filter_node_labels_to_index:
                node_query = """
                    MATCH (n)
                    WHERE any(l IN labels(n) WHERE l IN $labels)
                    RETURN elementId(n) AS node_id
                """
                node_params = {"labels": params.filter_node_labels_to_index}
            else:
                node_query = "MATCH (n) RETURN elementId(n) AS node_id"
                node_params = {}

            nodes_result = self.graph.query(node_query, node_params)
            self.current_session_nodes = [row["node_id"] for row in nodes_result]

            # Relationships: either all, or filtered via params.filter_rels_labels_to_index
            if params.filter_rels_labels_to_index and "ALL" not in params.filter_rels_labels_to_index:
                rel_query = """
                    MATCH ()-[r]->()
                    WHERE type(r) IN $types
                    RETURN elementId(r) AS rel_id
                """
                rel_params = {"types": params.filter_rels_labels_to_index}
            else:
                rel_query = "MATCH ()-[r]->() RETURN elementId(r) AS rel_id"
                rel_params = {}

            rels_result = self.graph.query(rel_query, rel_params)
            self.current_session_relationships = [row["rel_id"] for row in rels_result]

            print(f"✅ Seeded session from RDF graph: {len(self.current_session_nodes)} nodes, {len(self.current_session_relationships)} relationships")
        except Exception as e:
            print(f"⚠️  Error seeding session from RDF graph: {e}")
            self.current_session_nodes = []
            self.current_session_relationships = []
    
    def run_ingestion(self) -> None:
        """Execute the ingestion or embedding process for the current use case."""
        print("🚀 Starting Knowledge Graph Ingestion / Embedding Process")
        print("=" * 50)
        
        try:
            # Reset session tracking for this run
            self._reset_session_tracking()
            
            # Setup phase
            self.setup_environment()
            self.initialize_neo4j_connection()

            if USE_RDF_GRAPH_ONLY:
                # For the TTL-based use case:
                # - Load /data/data_SRM.ttl (core SRM + common vocabs) via n10s
                # - Then load /data/enriched_SRM.ttl with additional annotations
                # - Then work directly on that graph to create embeddings/indexes
                requested_ttl_files_env = os.getenv("NEO4J_TTL_FILES", "").strip()
                requested_ttl_files = (
                    [name.strip() for name in requested_ttl_files_env.split(",") if name.strip()]
                    if requested_ttl_files_env
                    else ["data_SRM.ttl", "enriched_SRM.ttl"]
                )
                ttl_files = self._prepare_ttl_files_for_neo4j_import(requested_ttl_files)
                if not ttl_files:
                    raise FileNotFoundError(
                        "No TTL files were available for Neo4j import. "
                        "Set NEO4J_TTL_FILES or place files under ./data."
                    )

                print(f"ℹ️ Loading RDF graph from TTL via n10s: {', '.join(ttl_files)}")
                self._ensure_n10s_constraint_and_config()
                for ttl_file_name in ttl_files:
                    self._import_ttl_with_neosemantics(ttl_file_name=ttl_file_name)
                self._ensure_services_initialized()
                self._seed_session_from_existing_rdf_graph()
                self.create_vector_embeddings()
                print("=" * 50)
                print("🎉 RDF Graph Embedding Process Completed Successfully!")
                print(f"📊 Processed {len(self.current_session_nodes)} nodes and {len(self.current_session_relationships)} relationships from existing graph")
            else:
                # Original text → graph ingestion pipeline
                self.setup_llm_and_transformer()
                
                # Data processing phase
                self.load_documents()
                graph_docs = self.extract_graph_documents()
                
                # Ingestion phase
                self.ingest_to_neo4j(graph_docs)

                # Vector embeddings phase (optional) - only for current session
                self.create_vector_embeddings()
                
                # Add custom properties to Document nodes - only for current session
                self.add_multivectors_to_document_nodes()
                
                print("=" * 50)
                print("🎉 Knowledge Graph Ingestion Process Completed Successfully!")
                print(f"📊 Processed {len(self.current_session_sources)} source files")
                print(f"📊 Created embeddings for {len(self.current_session_nodes)} nodes and {len(self.current_session_relationships)} relationships")
            
        except Exception as e:
            print(f"❌ Ingestion process failed: {e}")
            import traceback
            traceback.print_exc()
            raise


def main():
    """Main function to run the ingestion process."""
    ingestion = KnowledgeGraphIngestion()
    ingestion.run_ingestion()


if __name__ == "__main__":
    main()

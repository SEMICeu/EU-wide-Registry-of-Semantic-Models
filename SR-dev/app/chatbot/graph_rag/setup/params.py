

# Add the import for prompts at the top of the file

# ==================== QUERY CONFIGURATION ====================
# Tuples of (embedding_property, target_label) for vector similarity search
# Each tuple defines which embedding property to search on which node label
# Tailored to the SRM RDF graph imported via n10s
VECTOR_SEARCH_CONFIGURATIONS = [
    ("ns2__description", "ns4__Asset"),             # main semantic field on Assets (current SRM graph)
    ("ns2__title",       "ns4__Asset"),             # Asset titles
    ("ns2__title",       "ns4__AssetDistribution"), # Distribution titles
    ("ns2__name",        "ns0__Agent"),             # Agent / Kind names
    ("rdfs__label",      "rdfs__Class"),            # schema/class labels
]

TOP_K_INITIAL = 4  # More results so Asset + Distribution nodes both appear; was 2
TOP_K_TRAVERSAL = 100 # Maximum number of results to retrieve per graph traversal
ACTIVATE_INITIAL_VECTOR_SEARCH = True # Whether to activate the initial vector search

# ==================== GRAPH TRAVERSAL CONFIGURATION ====================
# Graph traversal method selection
# Options: "context_to_cypher", "kop_limited_bfs", "kop_limited_bfs_pred_llm", "depth_limited_dfs", "depth_limited_dfs_pred_llm", "uniform_cost_search_ucs", "uniform_cost_search_ucs_pred_llm", "astar_search_heuristic", "astar_search_heuristic_pred_llm", "beam_search_over_the_graph", "beam_search_over_the_graph_pred_llm"
GRAPH_TRAVERSAL_METHOD = "beam_search_over_the_graph_pred_llm"


# ==================== INGESTION CONFIGURATION ====================
# Configuration parameters for knowledge graph extraction

# DOCUMENT PROCESSING CONFIGURATION 

# Directory path containing documents to be processed
# Supports glob patterns (e.g., "docs/*", "data/**/*.txt")
documents_source_path = "docs/*"

# SEMANTIC CHUNKING CONFIGURATION

# Method for determining breakpoints in semantic chunking
# Options: "percentile", "standard_deviation", "interquartile"
semantic_chunker_breakpoint_type = "percentile"

# Threshold value for semantic chunking breakpoints
# For percentile: value between 0-100 (e.g., 95.0 = top 5% discontinuities)
# Higher values = fewer, larger chunks; Lower values = more, smaller chunks
semantic_chunker_breakpoint_threshold = 95.0

# Minimum size (in characters) for any semantic chunk
# Prevents creation of very small chunks that lack context
semantic_chunker_min_chunk_size = 2000

# VECTOR EMBEDDING CONFIGURATION

# Dimensionality of vector embeddings (must match embedding model)
# OpenAI text-embedding-ada-002: 1536 dimensions
# OpenAI text-embedding-3-small: 1536 dimensions  
# OpenAI text-embedding-3-large: 3072 dimensions
vector_embedding_dimensions = 1536

# Similarity function used for vector comparisons in Neo4j indexes
# Options: 'cosine', 'euclidean'
# 'cosine' is recommended for most text embeddings
vector_similarity_function = 'cosine'

# Maximum character length for text values to be embedded
# Prevents embedding of very long texts that may cause API errors
max_embedding_text_length = 10000

# Prefix to exclude from embedding (e.g., base64 data URLs)
# Values starting with this prefix will not be embedded
embedding_exclusion_prefix = 'data:'

# Batch size for processing embeddings to avoid API rate limits
# Smaller values = more API calls but less likely to hit rate limits
embedding_batch_size = 10



# ==================== DATABASE QUERY CONFIGURATION ====================

# Maximum number of nodes/relationships to fetch in single queries
# Prevents memory issues with very large graphs
database_query_limit = 1000


# .................. Vector index configuration ..................
# Enable vector indexes for our RDF-based graph
add_vector_index = True

# Focus on the RDF node types present in the imported TTL
filter_node_labels_to_index = [
    "ns4__Asset",
    "ns4__AssetDistribution",
    "skos__Concept",
    "ns3__Kind",
    "ns0__Agent",
    "rdfs__Class",       # schema/class labels for vector search over rdfs__label
]

# Text-like properties to embed on those nodes
filter_node_properties_to_index = [
    "ns2__title",        # Asset / Distribution titles
    "ns2__description",  # Asset descriptions
    "ns2__name",         # Agent / Kind names
    "rdfs__label",       # Class / resource labels (schema-level)
    "skos_altLabel",     # Alternative labels
]

# We do not currently embed relationship properties in the RDF graph
filter_rels_labels_to_index = []
filter_rels_properties_to_index = []

# Disable LLM-generated multi-vector document properties for this use case
document_multi_vector_properties = []


# ------------------ Graph schema extraction configuration ------------------

# Whether to add a base entity label to all nodes in Neo4j
# When True, each node gets an additional '__Entity__' label alongside its specific type (Person, Country, etc.)
# This creates optimized indexes that significantly improve query performance and import speed across all entity types
# The base label enables faster cross-entity searches and graph traversals without any performance overhead
baseEntityLabel = True

# Whether to include source document information with extracted entities
include_source = True


# Import libraries
import os
import yaml
import requests
import warnings
from rdflib import Graph, URIRef
from SPARQLWrapper import SPARQLWrapper, JSON
from urllib.parse import urlparse
import time
from collections import Counter
from rdflib.namespace import XSD
import logging
import sys

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Set configuration variables
SPARQL_QUERY_ENDPOINT = config['sparql']['sparql_query_endpoint']
SPARQL_UPDATE_ENDPOINT = config['sparql']['sparql_update_endpoint']  # Virtuoso uses the same endpoint for updates
GRAPH_URI = config['sparql']['graph_uri']
BYPASS_SSL = config['sparql']['bypass_ssl']
LOVRANK_UPDATE_QUERY = config['lovrank_update_query']

LOVRANK_PROPERTY = "http://example.org/LOVRank"
DCT_REQUIRES = "http://purl.org/dc/terms/requires"
DCT_STANDARD = "http://purl.org/dc/terms/Standard"

# Setup logging to file and console
LOG_FILE = "semantic_registry_analysis.log"

def setup_logging():
    """Setup logging to both file and console."""
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    
    # File handler (overwrites file each run)
    file_handler = logging.FileHandler(LOG_FILE, mode='w')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(console_handler)
    
    return logger

# Initialize logging
logger = setup_logging()

def log_print(message):
    """Print and log a message."""
    logger.info(message)

# Suppress SSL warnings if bypassing verification
if BYPASS_SSL:
    requests.packages.urllib3.disable_warnings()

def download_and_parse(url):
    """Download RDF data from a URL and parse it into an rdflib Graph."""
    try:
        if BYPASS_SSL:
            warnings.warn(f"Bypassing SSL verification, use for testing only.")
            response = requests.get(url, verify=False)
        else:
            response = requests.get(url)

        if response.status_code == 200:
            graph = Graph()
            graph.parse(data=response.text, format="turtle")
            log_print(f"Parsed RDF from: {url}")
            return graph
        else:
            log_print(f"Failed to download {url}: Status code {response.status_code}")
            return None
    except requests.exceptions.SSLError as ssl_err:
        log_print(f"SSL error downloading {url}: {str(ssl_err)}")
        return None
    except requests.exceptions.RequestException as e:
        log_print(f"Error downloading {url}: {str(e)}")
        return None
    except Exception as e:
        log_print(f"Error parsing RDF from {url}: {str(e)}")
        return None

def get_download_urls():
    """Get download URLs from SPARQL endpoint."""
    sparql = SPARQLWrapper(SPARQL_QUERY_ENDPOINT)
    sparql.setQuery(config['sparql_query'])
    sparql.setReturnFormat(JSON)
    
    try:
        results = sparql.query().convert()
        # Return tuples of (dct:Standard URI, download URL)
        return [(result['s']['value'], result['download']['value']) 
                for result in results['results']['bindings']]
    except Exception as e:
        log_print(f"Error querying SPARQL endpoint: {str(e)}")
        return []

def normalize_uri(uri):
    """Remove trailing / or # from URI for comparison purposes."""
    uri_str = str(uri).rstrip('/#')
    return uri_str

def get_dct_standard_mappings(download_urls, ontology_namespaces):
    """
    Create dct:Standard mappings by matching dct:Standard URIs to actual namespaces
    found in the RDF data, handling trailing / and # variations.
    """
    mappings = {}
    
    # Create a set of all actual namespaces found in RDF data
    all_actual_namespaces = set()
    for standard_uri, ns_set in ontology_namespaces.items():
        all_actual_namespaces.update(ns_set)
    
    for standard_uri, download_url in download_urls:
        # Get the namespaces actually used in this ontology's RDF
        actual_namespaces = ontology_namespaces.get(standard_uri, set())
        
        log_print(f"DEBUG: Processing {standard_uri}")
        log_print(f"DEBUG: Available namespaces: {sorted(actual_namespaces)}")
        
        # Try to find the best matching namespace for this dct:Standard URI
        best_match = None
        
        # First, try exact match
        if standard_uri in actual_namespaces:
            best_match = standard_uri
            log_print(f"DEBUG: Exact match found: {standard_uri}")
        else:
            # Look for actual namespaces that match the dct:Standard URI 
            # when we remove trailing / or # from the actual namespace
            best_match = None
            for actual_ns in actual_namespaces:
                # Remove trailing / or # from the actual namespace and compare
                normalized_actual = normalize_uri(actual_ns)
                if normalized_actual == standard_uri:
                    # Found a match! Use the full actual namespace (with trailing char)
                    best_match = actual_ns
                    log_print(f"DEBUG: Found match by removing trailing char: {standard_uri} -> {actual_ns}")
                    break
        
        if best_match:
            mappings[standard_uri] = best_match
            log_print(f"dct:Standard {standard_uri} -> matched namespace: {best_match}")
        else:
            # If no match found, maybe this ontology doesn't define its own namespace
            # but only uses external ones. Map to None or the standard_uri itself.
            mappings[standard_uri] = None
            log_print(f"dct:Standard {standard_uri} -> no matching namespace found in RDF data")
    
    return mappings

def extract_namespace(uri):
    """
    Extract the namespace from a URI, handling different formats and edge cases.
    
    Args:
        uri: The URI to parse
        
    Returns:
        str: The namespace portion of the URI
    """
    try:
        uri_str = str(uri)
        
        # Handle fragments (e.g., http://example.org/ns#term -> http://example.org/ns#)
        if '#' in uri_str:
            return uri_str.rsplit('#', 1)[0] + '#'
            
        # Handle standard path-based URIs (e.g., http://example.org/ns/term -> http://example.org/ns/)
        parsed = urlparse(uri_str)
        path = parsed.path
        
        if path and path != '/':
            # Split on the last meaningful slash
            base = path.rsplit('/', 1)[0] + '/'
            return f"{parsed.scheme}://{parsed.netloc}{base}"
            
        # Fallback to scheme and authority with trailing slash
        return f"{parsed.scheme}://{parsed.netloc}/"
        
    except Exception as e:
        log_print(f"Error parsing URI {uri}: {str(e)}")
        return str(uri)  # Fallback to the full URI

def get_unique_namespaces(graph):
    """Return a set of unique namespaces actually used in the graph's triples."""
    namespaces = set()
    
    # Extract namespaces from all URIs in the triples
    for s, p, o in graph:
        for term in (s, p, o):
            if isinstance(term, URIRef):
                ns = extract_namespace(str(term))
                namespaces.add(ns)
                    
    return namespaces

def write_lovrank_to_endpoint(ontology_uri, lovrank_value, update_query_template):
    """Write the LOVRank value as a property to the dct:Standard resource in the SPARQL endpoint."""
    update_query = update_query_template.format(
        ontology_uri=ontology_uri,
        lovrank_value=lovrank_value
    )
    headers = {"Content-Type": "application/sparql-update"}
    try:
        response = requests.post(
            SPARQL_UPDATE_ENDPOINT,
            data=update_query.encode('utf-8'),
            headers=headers,
            verify=not BYPASS_SSL
        )
        if response.status_code in (200, 204):
            log_print(f"LOVRank {lovrank_value} written to {ontology_uri}")
        else:
            log_print(f"Failed to write LOVRank for {ontology_uri}: {response.status_code} {response.text}")
    except Exception as e:
        log_print(f"Failed to write LOVRank for {ontology_uri}: {e}")

def write_requires_to_endpoint(subject_uri, object_uri, update_query_template):
    """Write a dct:requires relationship between two ontologies to the SPARQL endpoint."""
    update_query = update_query_template.format(
        subject_uri=subject_uri,
        object_uri=object_uri
    )
    headers = {"Content-Type": "application/sparql-update"}
    try:
        response = requests.post(
            SPARQL_UPDATE_ENDPOINT,
            data=update_query.encode('utf-8'),
            headers=headers,
            verify=not BYPASS_SSL
        )
        """if response.status_code in (200, 204):
            log_print(f"{subject_uri} dct:requires {object_uri} written.")
        else:
            log_print(f"Failed to write dct:requires for {subject_uri} -> {object_uri}: {response.status_code} {response.text}")
        """
    except Exception as e:
        log_print(f"Failed to write dct:requires for {subject_uri} -> {object_uri}: {e}")

def print_namespace_analysis(standard_uri, filename, namespaces):
    """Print the namespace analysis for a dct:Standard ontology."""
    log_print(f"\nUnique namespaces in dct:Standard {standard_uri} (filename: {filename}):")
    for ns in sorted(namespaces):
        log_print(f"  {ns}")
    log_print(f"Unique namespace count: {len(namespaces)}")

def main():
    start_time = time.time()
    log_print("=== Semantic Registry Metrics Analysis ===\n")
    
    # Get download URLs from SPARQL endpoint
    log_print("Fetching download URLs from SPARQL endpoint...")
    download_urls = get_download_urls()
    log_print(f"Found {len(download_urls)} dct:Standard ontologies to analyze\n")

    # Store per-ontology data
    ontology_namespaces = {}  # standard_uri -> set of namespaces used in the RDF
    ontology_main_ns = {}     # standard_uri -> main namespace from dct:Standard URI

    # Process each dct:Standard ontology first to collect all namespace data
    log_print("Processing ontologies and collecting namespace data...")
    for standard_uri, download_url in download_urls:
        filename = os.path.basename(urlparse(download_url).path)
        graph = download_and_parse(download_url)
        if graph:
            unique_ns = get_unique_namespaces(graph)
            ontology_namespaces[standard_uri] = unique_ns
            print_namespace_analysis(standard_uri, filename, unique_ns)

    # Now create dct:Standard mappings based on actual namespace data
    log_print("\nCreating dct:Standard namespace mappings based on actual RDF data...")
    dct_standard_mappings = get_dct_standard_mappings(download_urls, ontology_namespaces)
    log_print(f"Created {len(dct_standard_mappings)} dct:Standard mappings\n")

    # Update ontology_main_ns with the correct mappings
    for standard_uri in ontology_namespaces.keys():
        ontology_main_ns[standard_uri] = dct_standard_mappings.get(standard_uri)

    total_ontologies = len(ontology_namespaces)
    if total_ontologies == 0:
        log_print("No ontologies found or processed. Exiting.")
        return

    # Build a reverse index: namespace -> set of ontologies that use it
    ns_to_ontologies = {}
    for onto, ns_set in ontology_namespaces.items():
        for ns in ns_set:
            ns_to_ontologies.setdefault(ns, set()).add(onto)

    # Build a mapping from main namespace to dct:Standard URI
    ns_to_ontology_uri = {ns: uri for uri, ns in ontology_main_ns.items() if ns}

    requires_update_query = config['requires_update_query']

    # Calculate backlinks and LOVRank for each ontology
    log_print("\n=== LOVRank Metrics Table ===")
    log_print(f"{'dct:Standard URI':60} {'Backlinks':>10} {'LOVRank':>10}")
    log_print("-" * 85)
    
    for standard_uri, main_ns in ontology_main_ns.items():
        if not main_ns:
            backlinks = 0
            log_print(f"DEBUG: {standard_uri} has no matching namespace")
        else:
            # Get all ontologies that use this namespace
            using_ontologies = ns_to_ontologies.get(main_ns, set())
            # Exclude self-references
            backlinks = len(using_ontologies - {standard_uri})
            if backlinks > 0:
                log_print(f"DEBUG: {standard_uri} (ns: {main_ns}) is used by {backlinks} other ontologies")
        
        lovrank = backlinks / total_ontologies if total_ontologies > 0 else 0
        log_print(f"{standard_uri:60} {backlinks:10} {lovrank:10.3f}")
        write_lovrank_to_endpoint(standard_uri, f"{lovrank:.6f}", LOVRANK_UPDATE_QUERY)
    
    log_print("-" * 85)
    log_print(f"Total ontologies: {total_ontologies}")

    # For each ontology, check which other ontologies' namespaces it uses
    dependency_count = 0
    for standard_uri, used_namespaces in ontology_namespaces.items():
        for ns in used_namespaces:
            # If this namespace is the main namespace of another ontology (not itself)
            if ns in ns_to_ontology_uri and ns_to_ontology_uri[ns] != standard_uri:
                target_ontology = ns_to_ontology_uri[ns]
                # Write dct:requires triple
                write_requires_to_endpoint(standard_uri, target_ontology, requires_update_query)
                dependency_count += 1
    
    log_print(f"\nTotal dependencies established: {dependency_count}")
    elapsed = time.time() - start_time
    log_print(f"\nScript execution time: {elapsed:.2f} seconds")
    log_print(f"Log saved to: {LOG_FILE}")

if __name__ == "__main__":
    main()
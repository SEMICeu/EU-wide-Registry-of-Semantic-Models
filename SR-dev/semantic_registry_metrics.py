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

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Set configuration variables
SPARQL_QUERY_ENDPOINT = config['sparql']['sparql_query_endpoint']
SPARQL_UPDATE_ENDPOINT = config['sparql']['sparql_update_endpoint']
BYPASS_SSL = config['sparql']['bypass_ssl']
LOVRANK_UPDATE_QUERY = config['lovrank_update_query']

LOVRANK_PROPERTY = "http://example.org/LOVRank"  # Replace with your actual property URI
DCT_REQUIRES = "http://purl.org/dc/terms/requires"

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
            print(f"Parsed RDF from: {url}")
            return graph
        else:
            print(f"Failed to download {url}: Status code {response.status_code}")
            return None
    except requests.exceptions.SSLError as ssl_err:
        print(f"SSL error downloading {url}: {str(ssl_err)}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {str(e)}")
        return None
    except Exception as e:
        print(f"Error parsing RDF from {url}: {str(e)}")
        return None

def get_download_urls():
    """Get download URLs from SPARQL endpoint."""
    sparql = SPARQLWrapper(SPARQL_QUERY_ENDPOINT)
    sparql.setQuery(config['sparql_query'])
    sparql.setReturnFormat(JSON)
    
    try:
        results = sparql.query().convert()
        return [(result['s']['value'], result['download']['value']) 
                for result in results['results']['bindings']]
    except Exception as e:
        print(f"Error querying SPARQL endpoint: {str(e)}")
        return []

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
        print(f"Error parsing URI {uri}: {str(e)}")
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

def guess_main_namespace(graph):
    """Guess the main namespace of an ontology by finding the most common namespace in subjects."""
    ns_counter = Counter()
    for s, p, o in graph:
        if isinstance(s, URIRef):
            ns = extract_namespace(s)
            ns_counter[ns] += 1
    if ns_counter:
        return ns_counter.most_common(1)[0][0]
    return None

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
            print(f"LOVRank {lovrank_value} written to {ontology_uri}")
        else:
            print(f"Failed to write LOVRank for {ontology_uri}: {response.status_code} {response.text}")
    except Exception as e:
        print(f"Failed to write LOVRank for {ontology_uri}: {e}")

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
            print(f"{subject_uri} dct:requires {object_uri} written.")
        else:
            print(f"Failed to write dct:requires for {subject_uri} -> {object_uri}: {response.status_code} {response.text}")
        """
    except Exception as e:
        print(f"Failed to write dct:requires for {subject_uri} -> {object_uri}: {e}")

def print_namespace_analysis(model_uri, filename, namespaces):
    """Print the namespace analysis for a model."""
    print(f"\nUnique namespaces in Model {model_uri} (filename: {filename}):")
    for ns in sorted(namespaces):
        print(f"  {ns}")
    print(f"Unique namespace count: {len(namespaces)}")

def main():
    start_time = time.time()
    print("=== Semantic Registry Metrics Analysis ===\n")
    
    # Get download URLs from SPARQL endpoint
    print("Fetching download URLs from SPARQL endpoint...")
    download_urls = get_download_urls()
    print(f"Found {len(download_urls)} models to analyze\n")

    # Store per-ontology data
    ontology_namespaces = {}  # model_uri -> set of namespaces used
    ontology_main_ns = {}     # model_uri -> guessed main namespace

    # Process each model
    for model_uri, download_url in download_urls:
        filename = os.path.basename(urlparse(download_url).path)
        graph = download_and_parse(download_url)
        if graph:
            unique_ns = get_unique_namespaces(graph)
            main_ns = guess_main_namespace(graph)
            ontology_namespaces[model_uri] = unique_ns
            ontology_main_ns[model_uri] = main_ns
            print_namespace_analysis(model_uri, filename, unique_ns)

    total_ontologies = len(ontology_namespaces)
    if total_ontologies == 0:
        print("No ontologies found or processed. Exiting.")
        return

    # Build a reverse index: namespace -> set of ontologies that use it
    ns_to_ontologies = {}
    for onto, ns_set in ontology_namespaces.items():
        for ns in ns_set:
            ns_to_ontologies.setdefault(ns, set()).add(onto)

    # Build a mapping from main namespace to ontology URI
    ns_to_ontology_uri = {ns: uri for uri, ns in ontology_main_ns.items() if ns}

    requires_update_query = config['requires_update_query']

    # Calculate backlinks and LOVRank for each ontology
    print("\n=== LOVRank Metrics Table ===")
    print(f"{'Ontology':60} {'Backlinks':>10} {'LOVRank':>10}")
    print("-" * 85)
    for ontology_uri, main_ns in ontology_main_ns.items():
        if not main_ns:
            backlinks = 0
        else:
            list_backlinks = ns_to_ontologies.get(main_ns, set())
            backlinks = len(list_backlinks - {ontology_uri})
        lovrank = backlinks / total_ontologies if total_ontologies > 0 else 0
        print(f"{ontology_uri:60} {backlinks:10} {lovrank:10.3f}")
        write_lovrank_to_endpoint(ontology_uri, f"{lovrank:.6f}", LOVRANK_UPDATE_QUERY)
    print("-" * 85)
    print(f"Total ontologies: {total_ontologies}")

    # For each ontology, check which other ontologies' namespaces it uses
    dependency_count = 0
    for ontology_uri, used_namespaces in ontology_namespaces.items():
        for ns in used_namespaces:
            # If this namespace is the main namespace of another ontology (not itself)
            if ns in ns_to_ontology_uri and ns_to_ontology_uri[ns] != ontology_uri:
                target_ontology = ns_to_ontology_uri[ns]
                # Write dct:requires triple
                write_requires_to_endpoint(ontology_uri, target_ontology, requires_update_query)
                dependency_count += 1
    
    print(f"\nTotal dependencies established: {dependency_count}")
    elapsed = time.time() - start_time
    print(f"\nScript execution time: {elapsed:.2f} seconds")

if __name__ == "__main__":
    main()
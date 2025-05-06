#!/usr/bin/env python3

# Import libraries
import os
import yaml
import requests
import warnings
from rdflib import Graph, URIRef
from SPARQLWrapper import SPARQLWrapper, JSON
from urllib.parse import urlparse
from rdflib.term import URIRef
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
USE_PREFIXCC = config.get('prefixcc', {}).get('enabled', False)  # Optional prefix.cc lookup

LOVRANK_PROPERTY = "http://example.org/LOVRank"  # Replace with your actual property URI

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

# Suppress SSL warnings if bypassing verification
if BYPASS_SSL:
    requests.packages.urllib3.disable_warnings()

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

def parse_uri_namespace(uri):
    """Parse a URI to extract its namespace, handling edge cases."""
    try:
        parsed = urlparse(str(uri))
        path = parsed.path
        # Prefer fragment if present (e.g., http://example.org/ns#term)
        if parsed.fragment:
            return f"{parsed.scheme}://{parsed.netloc}{path}#"
        # Otherwise, split on the last meaningful slash
        if path and path != '/':
            base = path.rsplit('/', 1)[0] + '/'
            return f"{parsed.scheme}://{parsed.netloc}{base}"
        # Fallback to scheme and authority
        return f"{parsed.scheme}://{parsed.netloc}/"
    except Exception as e:
        print(f"Error parsing URI {uri}: {str(e)}")
        return str(uri)  # Fallback to the full URI

def lookup_prefixcc(uri):
    """Query prefix.cc to get the prefix for a namespace URI (optional)."""
    if not USE_PREFIXCC:
        return None
    try:
        response = requests.get(f"http://prefix.cc/reverse?uri={uri}&format=json")
        if response.status_code == 200:
            data = response.json()
            return data.get('prefix')
    except Exception as e:
        print(f"Error querying prefix.cc for {uri}: {str(e)}")
    return None

def extract_namespace(uri):
    """Extract the namespace from a URI string."""
    uri = str(uri)
    if '#' in uri:
        return uri.rsplit('#', 1)[0] + '#'
    else:
        return uri.rsplit('/', 1)[0] + '/'

def get_unique_namespaces(graph):
    """Return a set of unique namespaces actually used in the graph's triples."""
    namespaces = set()
    for s, p, o in graph:
        for term in (s, p, o):
            if isinstance(term, URIRef):
                ns = extract_namespace(term)
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

def analyze_namespaces(graph, model_uri, filename):
    """Analyze and print unique namespaces for a given graph."""
    unique_ns = get_unique_namespaces(graph)
    print(f"\nUnique namespaces in Model {model_uri} (filename: {filename}):")
    for ns in sorted(unique_ns):
        print(f"  {ns}")
    print(f"Unique namespace count: {len(unique_ns)}")
    return unique_ns

def analyze_model_namespaces(download_urls):
    """Analyze namespaces for each model and aggregate unique namespaces across all models."""
    all_unique_ns = set()

    for model_uri, download_url in download_urls:
        filename = os.path.basename(urlparse(download_url).path)
        graph = download_and_parse(download_url)
        if not graph:
            continue

        # Extract declared namespaces from the graph
        model_ns = set()
        declared_ns = {str(uri) for _, uri in graph.namespaces()}
        model_ns.update(declared_ns)

        # Extract namespaces from URIs in triples (for undeclared namespaces)
        for s, p, o in graph:
            for term in (s, p, o):
                if isinstance(term, URIRef):
                    uri = str(term)
                    # Check if URI belongs to a declared namespace
                    ns = next((ns for ns in declared_ns if uri.startswith(ns)), None)
                    if not ns:
                        ns = parse_uri_namespace(uri)
                    model_ns.add(ns)

        # Optionally map namespaces to prefixes using prefix.cc
        ns_with_prefix = []
        for ns in sorted(model_ns):
            prefix = lookup_prefixcc(ns) if USE_PREFIXCC else None
            ns_with_prefix.append((ns, prefix))

        # Print namespaces for the current model
        print(f"\nUnique namespaces in Model {model_uri} (filename: {filename}):")
        for ns, prefix in ns_with_prefix:
            if prefix:
                print(f"  {ns} (prefix: {prefix})")
            else:
                print(f"  {ns}")
        print(f"Unique namespace count: {len(model_ns)}")

        # Aggregate namespaces across all models
        all_unique_ns.update(model_ns)

    return all_unique_ns

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

    total_ontologies = len(ontology_namespaces)

    # Build a reverse index: namespace -> set of ontologies that use it
    ns_to_ontologies = {}
    for onto, ns_set in ontology_namespaces.items():
        for ns in ns_set:
            ns_to_ontologies.setdefault(ns, set()).add(onto)

    # Calculate backlinks and LOVRank for each ontology
    print("\n=== LOVRank Metrics Table ===")
    print(f"{'Ontology':60} {'Backlinks':>10} {'LOVRank':>10}")
    print("-" * 85)
    for ontology_uri, main_ns in ontology_main_ns.items():
        if not main_ns:
            backlinks = 0
        else:
            backlinks = len(ns_to_ontologies.get(main_ns, set()) - {ontology_uri})
        lovrank = backlinks / total_ontologies if total_ontologies > 0 else 0
        print(f"{ontology_uri:60} {backlinks:10} {lovrank:10.3f}")
        write_lovrank_to_endpoint(ontology_uri, f"{lovrank:.6f}", LOVRANK_UPDATE_QUERY)
    print("-" * 85)
    print(f"Total ontologies: {total_ontologies}")

    elapsed = time.time() - start_time
    print(f"\nScript execution time: {elapsed:.2f} seconds")

if __name__ == "__main__":
    main()
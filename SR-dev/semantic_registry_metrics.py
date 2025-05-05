#!/usr/bin/env python3

# Import libraries
import os
import yaml
import requests
import warnings
from rdflib import Graph, Namespace
from SPARQLWrapper import SPARQLWrapper, JSON
from urllib.parse import urlparse
from rdflib.term import URIRef

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# Set configuration variables
SPARQL_ENDPOINT = config['sparql']['endpoint']
GRAPH_URI = config['sparql']['graph_uri']
BYPASS_SSL = config['sparql']['bypass_ssl']
SPARQL_QUERY = config['sparql_query']

def download_and_parse(url):
    """Download RDF data from a URL and parse it into an rdflib Graph."""
    try:
        # Bypass SSL verification if configured (not recommended for production)
        if BYPASS_SSL:
            warnings.warn(f"Bypassing SSL verification for {url}. This is insecure and should be used only for testing.")
            response = requests.get(url, verify=False)
        else:
            response = requests.get(url)

        if response.status_code == 200:
            # Parse RDF data into a Graph (assuming Turtle format)
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
    sparql = SPARQLWrapper(SPARQL_ENDPOINT)
    sparql.setQuery(SPARQL_QUERY)
    sparql.setReturnFormat(JSON)
    
    try:
        results = sparql.query().convert()
        return [(result['s']['value'], result['download']['value']) 
                for result in results['results']['bindings']]
    except Exception as e:
        print(f"Error querying SPARQL endpoint: {str(e)}")
        return []

def extract_namespace(uri):
    """Extract the namespace from a URI string."""
    uri = str(uri)
    if '#' in uri:
        return uri.rsplit('#', 1)[0] + '#'
    else:
        return uri.rsplit('/', 1)[0] + '/'

def get_unique_namespaces(graph):
    """Return a set of unique namespaces used in the graph."""
    namespaces = set()
    for s, p, o in graph:
        for term in (s, p, o):
            if isinstance(term, URIRef):
                ns = extract_namespace(term)
                namespaces.add(ns)
    return namespaces

def analyze_namespaces(graph, model_uri, filename):
    """Analyze and print unique namespaces for a given graph."""
    unique_ns = get_unique_namespaces(graph)
    print(f"\nUnique namespaces in Model {model_uri} (filename: {filename}):")
    for ns in sorted(unique_ns):
        print(f"  {ns}")
    print(f"Unique namespace count: {len(unique_ns)}")
    return unique_ns

def main():
    print("=== Semantic Registry Metrics Analysis ===\n")
    
    # Get download URLs from SPARQL endpoint
    print("Fetching download URLs from SPARQL endpoint...")
    download_urls = get_download_urls()
    print(f"Found {len(download_urls)} models to analyze\n")

    # Store all unique namespaces across all models
    all_unique_ns = set()

    # Process each model
    for model_uri, download_url in download_urls:
        filename = os.path.basename(urlparse(download_url).path)
        graph = download_and_parse(download_url)
        if graph:
            unique_ns = analyze_namespaces(graph, model_uri, filename)
            all_unique_ns.update(unique_ns)

    # Print summary of unique namespaces across all models
    print("\n=== Unique Namespaces Across All Models ===")
    for ns in sorted(all_unique_ns):
        print(f"  {ns}")
    print(f"Total unique namespaces: {len(all_unique_ns)}")

if __name__ == "__main__":
    main() 
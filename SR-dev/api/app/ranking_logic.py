from fastapi.concurrency import run_in_threadpool
import logging
import httpx
from rdflib import Graph, URIRef
from SPARQLWrapper import SPARQLWrapper, JSON
from urllib.parse import urlparse
from collections import Counter

logger = logging.getLogger(__name__)

def extract_namespace(uri: str) -> str:
    """Extracts the namespace from a URI."""
    try:
        if '#' in uri:
            return uri.rsplit('#', 1)[0] + '#'
        parsed = urlparse(uri)
        path = parsed.path
        if path and path != '/':
            base = path.rsplit('/', 1)[0] + '/'
            return f"{parsed.scheme}://{parsed.netloc}{base}"
        return f"{parsed.scheme}://{parsed.netloc}/"
    except Exception as e:
        logger.error(f"Error parsing URI {uri}: {e}")
        return uri

def get_unique_namespaces(graph: Graph) -> set:
    """Returns a set of unique namespaces from all URIs in a graph's triples."""
    return {extract_namespace(str(term)) for s, p, o in graph for term in (s, p, o) if isinstance(term, URIRef)}

async def download_and_parse(url: str, bypass_ssl: bool) -> Graph | None:
    """Downloads and parses RDF data from a URL into an rdflib Graph."""
    try:
        async with httpx.AsyncClient(verify=not bypass_ssl, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code == 200:
                graph = Graph()
                graph.parse(data=response.text, format="turtle")
                logger.info(f"Successfully parsed RDF from: {url}")
                return graph
            else:
                logger.warning(f"Failed to download {url}: Status {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Error downloading or parsing {url}: {e}")
        return None

async def get_download_urls(sparql_endpoint: str, query: str) -> list:
    """Gets a list of (resource_uri, download_url) tuples from a SPARQL endpoint."""
    sparql = SPARQLWrapper(sparql_endpoint)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    try:
        results = await run_in_threadpool(sparql.queryAndConvert)
        return [(r['s']['value'], r['download']['value']) for r in results['results']['bindings']]
    except Exception as e:
        logger.error(f"SPARQL query failed: {e}")
        return []

def get_dct_standard_mappings(download_urls: list, ontology_namespaces: dict) -> dict:
    """Maps dct:Standard URIs to their actual namespaces found in the RDF data."""
    mappings = {}
    for standard_uri, download_url in download_urls:
        actual_namespaces = ontology_namespaces.get(standard_uri, set())
        best_match = None
        if standard_uri in actual_namespaces:
            best_match = standard_uri
        else:
            for actual_ns in actual_namespaces:
                if str(actual_ns).rstrip('/#') == standard_uri:
                    best_match = actual_ns
                    break
        mappings[standard_uri] = best_match
    return mappings

async def write_to_sparql_endpoint(endpoint: str, query: str, bypass_ssl: bool):
    """Executes a SPARQL update query."""
    headers = {"Content-Type": "application/sparql-update"}
    try:
        async with httpx.AsyncClient(verify=not bypass_ssl) as client:
            response = await client.post(endpoint, data=query.encode('utf-8'), headers=headers)
            if response.status_code not in (200, 204):
                logger.error(f"SPARQL update failed with status {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Failed to write to SPARQL endpoint: {e}")

async def run_ranking_process(sparql_query_endpoint: str, sparql_update_endpoint: str, bypass_ssl: bool, queries: dict):
    """The main logic for the ranking process."""
    logger.info("Starting semantic model ranking process...")
    download_urls = await get_download_urls(sparql_query_endpoint, queries['sparql_query'])
    if not download_urls:
        logger.info("No models found to process.")
        return

    ontology_graphs = {}
    ontology_namespaces = {}
    for standard_uri, url in download_urls:
        graph = await download_and_parse(url, bypass_ssl)
        if graph:
            ontology_graphs[standard_uri] = graph
            ontology_namespaces[standard_uri] = get_unique_namespaces(graph)

    mappings = get_dct_standard_mappings(download_urls, ontology_namespaces)
    ns_to_uri_map = {ns: uri for uri, ns in mappings.items() if ns}

    all_dependencies = []
    logger.info("Analyzing dependencies and writing `dct:requires` triples...")
    for subject_uri, graph in ontology_graphs.items():
        subject_ns = mappings.get(subject_uri)
        if not subject_ns:
            continue
        
        used_namespaces = get_unique_namespaces(graph)
        for ns in used_namespaces:
            if ns != subject_ns and ns in ns_to_uri_map:
                object_uri = ns_to_uri_map[ns]
                if subject_uri != object_uri:
                    all_dependencies.append(object_uri)
                    update_query = queries['requires_update_query'].format(subject_uri=subject_uri, object_uri=object_uri)
                    await write_to_sparql_endpoint(sparql_update_endpoint, update_query, bypass_ssl)

    logger.info("Calculating and writing LOVRank scores...")
    lovrank_scores = Counter(all_dependencies)
    for ontology_uri, score in lovrank_scores.items():
        update_query = queries['lovrank_update_query'].format(ontology_uri=ontology_uri, lovrank_value=score)
        await write_to_sparql_endpoint(sparql_update_endpoint, update_query, bypass_ssl)

    logger.info("Ranking process finished.")
    return {
        "status": "completed",
        "models_processed": len(download_urls),
        "unique_models_ranked": len(lovrank_scores)
    }

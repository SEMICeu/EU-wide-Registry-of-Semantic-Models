import os
import yaml
import httpx
import asyncio
import logging
from rdflib import Graph, URIRef
from urllib.parse import urlparse
from collections import Counter
from rdflib.namespace import XSD
from datetime import datetime
from typing import Dict, Set, Optional, List, Tuple

from .api.v1.models import (
    AnalysisResult, OntologyMetric
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

class AsyncSemanticRegistryAnalyzer:
    _RDF_ACCEPT_HEADER = (
        "text/turtle, application/x-turtle;q=1.0, application/n-triples;q=0.9, "
        "application/ld+json;q=0.8, application/rdf+xml;q=0.7, text/plain;q=0.5, */*;q=0.1"
    )

    def __init__(self, config_override: Optional[Dict] = None):
        self.config = self.load_config(config_override)
        self.sparql_query_endpoint = self.config['sparql']['sparql_query_endpoint']
        self.sparql_update_endpoint = self.config['sparql']['sparql_update_endpoint']
        self.graph_uri = self.config['sparql']['graph_uri']
        self.bypass_ssl = self.config['sparql']['bypass_ssl']
        self.lovrank_update_query = self.config['lovrank_update_query']
        self.requires_update_query = self.config['requires_update_query']
        self.sparql_query = self.config['sparql_query']
        self.log_file = "semantic_registry_analysis.log"
        # Lightweight file logger for per-standard success/failure diagnostics.
        self.logger = logging.getLogger("semantic_registry_analyzer")
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file, encoding="utf-8")
            formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    @staticmethod
    def load_config(config_override: Optional[Dict] = None):
        with open(CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        if config_override:
            # Shallow update for now
            config.update(config_override)
        return config

    async def get_download_urls(self) -> List:
        async with httpx.AsyncClient(verify=not self.bypass_ssl) as client:
            data = {
                'query': self.sparql_query,
                'format': 'application/sparql-results+json'
            }
            resp = await client.post(self.sparql_query_endpoint, data=data)
            resp.raise_for_status()
            results = resp.json()
            return [
                (
                    result['s']['value'],
                    result['download']['value'],
                    result.get('preferredNamespaceUri', {}).get('value')
                )
                for result in results['results']['bindings']
            ]

    async def download_and_parse(
        self,
        url: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> Tuple[Optional[Graph], Optional[str]]:
        """Download a URL and parse it as RDF, with HTML handling.

        If an external client is provided we reuse it; otherwise a short-lived
        client is created just for this call.
        """
        owns_client = client is None
        failure_reason: Optional[str] = None
        if owns_client:
            client = httpx.AsyncClient(
                verify=not self.bypass_ssl,
                timeout=30,
                follow_redirects=True,
            )

        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                failure_reason = f"http_status_{resp.status_code}"
                return None, failure_reason

            # Some URLs are HTML landing pages; retry with RDF/Turtle Accept to
            # content-negotiate the Turtle representation when available.
            if self._response_looks_like_html(resp):
                resp2 = await client.get(
                    url,
                    headers={"Accept": self._RDF_ACCEPT_HEADER},
                )
                if resp2.status_code == 200:
                    resp = resp2
                else:
                    failure_reason = f"http_status_after_html_retry_{resp2.status_code}"
                    return None, failure_reason

            # After retry, if it still looks like HTML, don't try to parse it as RDF.
            if self._response_looks_like_html(resp):
                failure_reason = "html_after_retry_no_rdf"
                return None, failure_reason

            graph = Graph()
            fmt = self._rdflib_format_from_response(resp, url)
            if fmt:
                try:
                    graph.parse(data=resp.text, format=fmt)
                    return graph, None
                except Exception:
                    failure_reason = f"parse_error_format_{fmt}"

            # Unknown/misleading content-type or failed specific format: try a few
            # common RDF serializations as a fallback.
            for candidate in ("turtle", "nt", "json-ld", "xml"):
                try:
                    graph.parse(data=resp.text, format=candidate)
                    return graph, None
                except Exception:
                    continue
            if failure_reason is None:
                failure_reason = "parse_error_all_formats"
        except Exception as exc:
            failure_reason = f"exception_{type(exc).__name__}"
        finally:
            if owns_client and client is not None:
                await client.aclose()
        return None, failure_reason

    @staticmethod
    def _response_looks_like_html(resp: httpx.Response) -> bool:
        ct = (resp.headers.get("content-type") or "").lower()
        if "text/html" in ct or "application/xhtml+xml" in ct:
            return True
        # Some servers mislabel HTML (or omit content-type). Heuristic on body prefix.
        prefix = (resp.text[:512] if resp.text else "").lstrip().lower()
        return prefix.startswith("<!doctype html") or prefix.startswith("<html")

    @staticmethod
    def _rdflib_format_from_response(resp: httpx.Response, url: str) -> Optional[str]:
        ct = (resp.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if ct in ("text/turtle", "application/x-turtle"):
            return "turtle"
        if ct == "application/n-triples":
            return "nt"
        if ct == "application/ld+json":
            return "json-ld"
        if ct in ("application/rdf+xml", "application/xml", "text/xml"):
            return "xml"

        lower_url = (url or "").lower()
        if lower_url.endswith((".ttl", ".turtle")):
            return "turtle"
        if lower_url.endswith(".nt"):
            return "nt"
        if lower_url.endswith(".jsonld"):
            return "json-ld"
        if lower_url.endswith((".rdf", ".xml")):
            return "xml"
        return None

    @staticmethod
    def extract_namespace(uri):
        uri_str = str(uri)
        if '#' in uri_str:
            return uri_str.rsplit('#', 1)[0] + '#'
        parsed = urlparse(uri_str)
        path = parsed.path
        if path and path != '/':
            base = path.rsplit('/', 1)[0] + '/'
            return f"{parsed.scheme}://{parsed.netloc}{base}"
        return f"{parsed.scheme}://{parsed.netloc}/"

    @staticmethod
    def normalize_uri(uri):
        return str(uri).rstrip('/#')

    @staticmethod
    def get_unique_namespaces(graph: Graph) -> Set[str]:
        namespaces = set()
        for s, p, o in graph:
            for term in (s, p, o):
                if isinstance(term, URIRef):
                    ns = AsyncSemanticRegistryAnalyzer.extract_namespace(term)
                    namespaces.add(ns)
        return namespaces

    def get_dct_standard_mappings(self, download_urls, ontology_namespaces):
        mappings = {}
        for standard_uri, download_url in download_urls:
            actual_namespaces = ontology_namespaces.get(standard_uri, set())
            best_match = None
            if standard_uri in actual_namespaces:
                best_match = standard_uri
            else:
                for actual_ns in actual_namespaces:
                    normalized_actual = self.normalize_uri(actual_ns)
                    if normalized_actual == standard_uri:
                        best_match = actual_ns
                        break
            mappings[standard_uri] = best_match if best_match else None
        return mappings

    async def write_lovrank_to_endpoint(
        self,
        ontology_uri,
        lovrank_value,
        client: Optional[httpx.AsyncClient] = None,
    ):
        update_query = self.lovrank_update_query.format(
            ontology_uri=ontology_uri,
            lovrank_value=lovrank_value,
        )
        headers = {"Content-Type": "application/sparql-update"}
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(verify=not self.bypass_ssl)
        try:
            await client.post(
                self.sparql_update_endpoint,
                data=update_query.encode('utf-8'),
                headers=headers,
            )
        finally:
            if owns_client and client is not None:
                await client.aclose()

    async def write_requires_to_endpoint(
        self,
        subject_uri,
        object_uri,
        client: Optional[httpx.AsyncClient] = None,
    ):
        update_query = self.requires_update_query.format(
            subject_uri=subject_uri,
            object_uri=object_uri,
        )
        headers = {"Content-Type": "application/sparql-update"}
        owns_client = client is None
        if owns_client:
            client = httpx.AsyncClient(verify=not self.bypass_ssl)
        try:
            await client.post(
                self.sparql_update_endpoint,
                data=update_query.encode('utf-8'),
                headers=headers,
            )
        finally:
            if owns_client and client is not None:
                await client.aclose()

    async def run_analysis(self, analysis_id: str) -> AnalysisResult:
        start_time = datetime.now()
        download_urls = await self.get_download_urls()
        ontology_namespaces = {}
        ontology_main_ns = {}
        # Map preferredNamespaceUri to its associated fake URIs and download URLs
        pref_ns_map = {}
        download_map = {}
        for fake_uri, download_url, preferred_ns in download_urls:
            if preferred_ns:
                pref_ns_map.setdefault(preferred_ns, set()).add(fake_uri)
                download_map[fake_uri] = download_url

        # Download and parse all ontologies. Reuse a single HTTP client to avoid
        # exhausting file descriptors when many downloads are in flight.
        ontology_namespaces = {}
        async with httpx.AsyncClient(
            verify=not self.bypass_ssl,
            timeout=30,
            follow_redirects=True,
        ) as client:
            download_results = await asyncio.gather(*[
                self.download_and_parse(download_map[fake_uri], client=client)
                for fake_uri in download_map
            ])

        # Log which standards were successfully downloaded/parsed and which were not,
        # together with a simple reason code.
        for fake_uri, (graph, reason) in zip(download_map, download_results):
            url = download_map[fake_uri]
            if graph:
                ontology_namespaces[fake_uri] = self.get_unique_namespaces(graph)
                self.logger.info(
                    "ontology_parsed_successfully standard_uri=%s download_url=%s",
                    fake_uri,
                    url,
                )
            else:
                self.logger.warning(
                    "ontology_parse_skipped standard_uri=%s download_url=%s reason=%s",
                    fake_uri,
                    url,
                    reason or "unknown",
                )

        # Build backlinks per preferred_namespace
        pref_ns_to_ontologies = {}
        for fake_uri, used_namespaces in ontology_namespaces.items():
            for ns in used_namespaces:
                pref_ns_to_ontologies.setdefault(ns, set()).add(fake_uri)

        ontology_metrics = []
        lovrank_tasks = []
        total_ontologies = sum(len(fake_uris) for fake_uris in pref_ns_map.values())

        async with httpx.AsyncClient(verify=not self.bypass_ssl) as update_client:
            for pref_ns, fake_uris in pref_ns_map.items():
                referencing_uris = pref_ns_to_ontologies.get(pref_ns, set())
                backlinks = len(referencing_uris - pref_ns_map.get(pref_ns, set()))
                lovrank = backlinks / total_ontologies if total_ontologies else 0
                for fake_uri in fake_uris:
                    ontology_metrics.append(OntologyMetric(
                        standard_uri=fake_uri,
                        backlinks=backlinks,
                        lovrank=lovrank,
                        preferred_namespace_uri=pref_ns
                    ))
                    lovrank_tasks.append(
                        self.write_lovrank_to_endpoint(fake_uri, f"{lovrank:.6f}"),  # client reused below
                    )
            # Attach the shared client to all lovrank tasks
            lovrank_tasks = [
                self.write_lovrank_to_endpoint(m.standard_uri, f"{m.lovrank:.6f}", client=update_client)
                for m in ontology_metrics
            ]

            await asyncio.gather(*lovrank_tasks)
            # Write dct:requires based on preferredNamespaceUri
            requires_tasks = []
            dependency_count = 0
            for source_fake_uri, used_namespaces in ontology_namespaces.items():
                source_pref_ns = None
                for pref_ns, fake_uris in pref_ns_map.items():
                    if source_fake_uri in fake_uris:
                        source_pref_ns = pref_ns
                        break
                for ns in used_namespaces:
                    if ns in pref_ns_map and ns != source_pref_ns:
                        for target_fake_uri in pref_ns_map[ns]:
                            requires_tasks.append(
                                self.write_requires_to_endpoint(
                                    source_fake_uri,
                                    target_fake_uri,
                                    client=update_client,
                                )
                            )
                            dependency_count += 1
            await asyncio.gather(*requires_tasks)
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        return AnalysisResult(
            analysis_id=analysis_id,
            total_ontologies=total_ontologies,
            dependencies_established=dependency_count,
            execution_time=execution_time,
            ontology_metrics=ontology_metrics,
            log_file=self.log_file,
            started_at=start_time,
            completed_at=end_time
        )

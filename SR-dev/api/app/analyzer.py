import os
import yaml
import httpx
import asyncio
from rdflib import Graph, URIRef
from urllib.parse import urlparse
from collections import Counter
from rdflib.namespace import XSD
from datetime import datetime
from typing import Dict, Set, Optional, List

from .api.v1.models import (
    AnalysisResult, OntologyMetric
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

class AsyncSemanticRegistryAnalyzer:
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
                (result['s']['value'], result['download']['value'])
                for result in results['results']['bindings']
            ]

    async def download_and_parse(self, url: str) -> Optional[Graph]:
        try:
            async with httpx.AsyncClient(verify=not self.bypass_ssl, timeout=30) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    graph = Graph()
                    graph.parse(data=resp.text, format="turtle")
                    return graph
        except Exception:
            pass
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

    async def write_lovrank_to_endpoint(self, ontology_uri, lovrank_value):
        update_query = self.lovrank_update_query.format(
            ontology_uri=ontology_uri,
            lovrank_value=lovrank_value
        )
        headers = {"Content-Type": "application/sparql-update"}
        async with httpx.AsyncClient(verify=not self.bypass_ssl) as client:
            await client.post(
                self.sparql_update_endpoint,
                data=update_query.encode('utf-8'),
                headers=headers
            )

    async def write_requires_to_endpoint(self, subject_uri, object_uri):
        update_query = self.requires_update_query.format(
            subject_uri=subject_uri,
            object_uri=object_uri
        )
        headers = {"Content-Type": "application/sparql-update"}
        async with httpx.AsyncClient(verify=not self.bypass_ssl) as client:
            await client.post(
                self.sparql_update_endpoint,
                data=update_query.encode('utf-8'),
                headers=headers
            )

    async def run_analysis(self, analysis_id: str) -> AnalysisResult:
        start_time = datetime.now()
        download_urls = await self.get_download_urls()
        ontology_namespaces = {}
        ontology_main_ns = {}
        # Download and parse all ontologies
        tasks = [self.download_and_parse(url) for _, url in download_urls]
        graphs = await asyncio.gather(*tasks)
        for (standard_uri, _), graph in zip(download_urls, graphs):
            if graph:
                unique_ns = self.get_unique_namespaces(graph)
                ontology_namespaces[standard_uri] = unique_ns
        dct_standard_mappings = self.get_dct_standard_mappings(download_urls, ontology_namespaces)
        for standard_uri in ontology_namespaces.keys():
            ontology_main_ns[standard_uri] = dct_standard_mappings.get(standard_uri)
        total_ontologies = len(ontology_namespaces)
        ns_to_ontologies = {}
        for onto, ns_set in ontology_namespaces.items():
            for ns in ns_set:
                ns_to_ontologies.setdefault(ns, set()).add(onto)
        ns_to_ontology_uri = {ns: uri for uri, ns in ontology_main_ns.items() if ns}
        # Calculate backlinks and LOVRank
        ontology_metrics = []
        lovrank_tasks = []
        for standard_uri, main_ns in ontology_main_ns.items():
            if not main_ns:
                backlinks = 0
            else:
                using_ontologies = ns_to_ontologies.get(main_ns, set())
                backlinks = len(using_ontologies - {standard_uri})
            lovrank = backlinks / total_ontologies if total_ontologies > 0 else 0
            ontology_metrics.append(OntologyMetric(
                standard_uri=standard_uri,
                backlinks=backlinks,
                lovrank=lovrank,
                main_namespace=main_ns
            ))
            lovrank_tasks.append(self.write_lovrank_to_endpoint(standard_uri, f"{lovrank:.6f}"))
        await asyncio.gather(*lovrank_tasks)
        # Write dct:requires dependencies
        dependency_count = 0
        requires_tasks = []
        for standard_uri, used_namespaces in ontology_namespaces.items():
            for ns in used_namespaces:
                if ns in ns_to_ontology_uri and ns_to_ontology_uri[ns] != standard_uri:
                    target_ontology = ns_to_ontology_uri[ns]
                    requires_tasks.append(self.write_requires_to_endpoint(standard_uri, target_ontology))
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

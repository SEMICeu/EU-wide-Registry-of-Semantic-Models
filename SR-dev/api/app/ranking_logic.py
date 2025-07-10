# main.py - FastAPI Application
import asyncio
import os
import yaml
import aiohttp
import aiofiles
import warnings
from rdflib import Graph, URIRef
from SPARQLWrapper import SPARQLWrapper, JSON
from urllib.parse import urlparse
import time
from collections import Counter
from rdflib.namespace import XSD
import logging
import sys
from typing import List, Dict, Set, Tuple, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid

# Pydantic models for API responses
class AnalysisResult(BaseModel):
    analysis_id: str
    total_ontologies: int
    dependencies_established: int
    execution_time: float
    ontology_metrics: List[Dict]
    log_file: str

class AnalysisStatus(BaseModel):
    analysis_id: str
    status: str  # "running", "completed", "failed"
    progress: Optional[str] = None
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None

# FastAPI app
app = FastAPI(title="Semantic Registry Analysis API")

# In-memory storage for analysis results (in production, use a database)
analysis_results: Dict[str, AnalysisStatus] = {}

# Configuration and constants
LOVRANK_PROPERTY = "http://example.org/LOVRank"
DCT_REQUIRES = "http://purl.org/dc/terms/requires"
DCT_STANDARD = "http://purl.org/dc/terms/Standard"

# Thread pool for CPU-bound operations
executor = ThreadPoolExecutor(max_workers=4)

class AsyncSemanticRegistryAnalyzer:
    def __init__(self, config_path: str = None):
        if config_path is None:
            # This will resolve to the parent directory of the current file (api/app/ -> api/)
            config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
        self.config = self._load_config(config_path)
        self.SPARQL_QUERY_ENDPOINT = self.config['sparql']['sparql_query_endpoint']
        self.SPARQL_UPDATE_ENDPOINT = self.config['sparql']['sparql_update_endpoint']
        self.BYPASS_SSL = self.config['sparql']['bypass_ssl']
        self.LOVRANK_UPDATE_QUERY = self.config['lovrank_update_query']
        self.requires_update_query = self.config['requires_update_query']
        
        # Setup SSL warnings
        if self.BYPASS_SSL:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail=f"Config file {config_path} not found")
    
    async def setup_logging(self, analysis_id: str) -> logging.Logger:
        """Setup logging to both file and console."""
        LOG_FILE = f"semantic_registry_analysis_{analysis_id}.log"
        
        # Create logger
        logger = logging.getLogger(f"analysis_{analysis_id}")
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
        
        return logger, LOG_FILE
    
    async def download_and_parse(self, session: aiohttp.ClientSession, url: str, logger: logging.Logger) -> Optional[Graph]:
        """Download RDF data from a URL and parse it into an rdflib Graph."""
        try:
            ssl_context = False if self.BYPASS_SSL else None
            if self.BYPASS_SSL:
                logger.warning(f"Bypassing SSL verification, use for testing only.")
            
            async with session.get(url, ssl=ssl_context) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Parse RDF in thread pool (CPU-bound operation)
                    graph = await asyncio.get_event_loop().run_in_executor(
                        executor, self._parse_rdf, content, url, logger
                    )
                    return graph
                else:
                    logger.info(f"Failed to download {url}: Status code {response.status}")
                    return None
        except aiohttp.ClientSSLError as ssl_err:
            logger.info(f"SSL error downloading {url}: {str(ssl_err)}")
            return None
        except aiohttp.ClientError as e:
            logger.info(f"Error downloading {url}: {str(e)}")
            return None
        except Exception as e:
            logger.info(f"Error parsing RDF from {url}: {str(e)}")
            return None
    
    def _parse_rdf(self, content: str, url: str, logger: logging.Logger) -> Graph:
        """Parse RDF content (runs in thread pool)."""
        graph = Graph()
        graph.parse(data=content, format="turtle")
        logger.info(f"Parsed RDF from: {url}")
        return graph
    
    async def get_download_urls(self, logger: logging.Logger) -> List[Tuple[str, str]]:
        """Get download URLs from SPARQL endpoint."""
        # SPARQL operations are synchronous, run in thread pool
        return await asyncio.get_event_loop().run_in_executor(
            executor, self._get_download_urls_sync, logger
        )
    
    def _get_download_urls_sync(self, logger: logging.Logger) -> List[Tuple[str, str]]:
        """Synchronous SPARQL query (runs in thread pool)."""
        sparql = SPARQLWrapper(self.SPARQL_QUERY_ENDPOINT)
        sparql.setQuery(self.config['sparql_query'])
        sparql.setReturnFormat(JSON)
        
        try:
            results = sparql.query().convert()
            return [(result['s']['value'], result['download']['value']) 
                    for result in results['results']['bindings']]
        except Exception as e:
            logger.info(f"Error querying SPARQL endpoint: {str(e)}")
            return []
    
    def normalize_uri(self, uri: str) -> str:
        """Remove trailing / or # from URI for comparison purposes."""
        return str(uri).rstrip('/#')
    
    def get_dct_standard_mappings(self, download_urls: List[Tuple[str, str]], 
                                 ontology_namespaces: Dict[str, Set[str]], 
                                 logger: logging.Logger) -> Dict[str, Optional[str]]:
        """Create dct:Standard mappings by matching dct:Standard URIs to actual namespaces."""
        mappings = {}
        
        for standard_uri, download_url in download_urls:
            actual_namespaces = ontology_namespaces.get(standard_uri, set())
            
            logger.info(f"DEBUG: Processing {standard_uri}")
            logger.info(f"DEBUG: Available namespaces: {sorted(actual_namespaces)}")
            
            best_match = None
            
            # First, try exact match
            if standard_uri in actual_namespaces:
                best_match = standard_uri
                logger.info(f"DEBUG: Exact match found: {standard_uri}")
            else:
                # Look for actual namespaces that match the dct:Standard URI
                for actual_ns in actual_namespaces:
                    normalized_actual = self.normalize_uri(actual_ns)
                    if normalized_actual == standard_uri:
                        best_match = actual_ns
                        logger.info(f"DEBUG: Found match by removing trailing char: {standard_uri} -> {actual_ns}")
                        break
            
            if best_match:
                mappings[standard_uri] = best_match
                logger.info(f"dct:Standard {standard_uri} -> matched namespace: {best_match}")
            else:
                mappings[standard_uri] = None
                logger.info(f"dct:Standard {standard_uri} -> no matching namespace found in RDF data")
        
        return mappings
    
    def extract_namespace(self, uri: str) -> str:
        """Extract the namespace from a URI."""
        try:
            uri_str = str(uri)
            
            if '#' in uri_str:
                return uri_str.rsplit('#', 1)[0] + '#'
                
            parsed = urlparse(uri_str)
            path = parsed.path
            
            if path and path != '/':
                base = path.rsplit('/', 1)[0] + '/'
                return f"{parsed.scheme}://{parsed.netloc}{base}"
                
            return f"{parsed.scheme}://{parsed.netloc}/"
            
        except Exception as e:
            return str(uri)
    
    def get_unique_namespaces(self, graph: Graph) -> Set[str]:
        """Return a set of unique namespaces actually used in the graph's triples."""
        namespaces = set()
        
        for s, p, o in graph:
            for term in (s, p, o):
                if isinstance(term, URIRef):
                    ns = self.extract_namespace(str(term))
                    namespaces.add(ns)
                    
        return namespaces
    
    async def write_lovrank_to_endpoint(self, session: aiohttp.ClientSession, 
                                      ontology_uri: str, lovrank_value: str, 
                                      logger: logging.Logger) -> None:
        """Write the LOVRank value to the SPARQL endpoint."""
        update_query = self.LOVRANK_UPDATE_QUERY.format(
            ontology_uri=ontology_uri,
            lovrank_value=lovrank_value
        )
        headers = {"Content-Type": "application/sparql-update"}
        
        try:
            ssl_context = False if self.BYPASS_SSL else None
            async with session.post(
                self.SPARQL_UPDATE_ENDPOINT,
                data=update_query.encode('utf-8'),
                headers=headers,
                ssl=ssl_context
            ) as response:
                if response.status in (200, 204):
                    logger.info(f"LOVRank {lovrank_value} written to {ontology_uri}")
                else:
                    response_text = await response.text()
                    logger.info(f"Failed to write LOVRank for {ontology_uri}: {response.status} {response_text}")
        except Exception as e:
            logger.info(f"Failed to write LOVRank for {ontology_uri}: {e}")
    
    async def write_requires_to_endpoint(self, session: aiohttp.ClientSession, 
                                       subject_uri: str, object_uri: str, 
                                       logger: logging.Logger) -> None:
        """Write a dct:requires relationship to the SPARQL endpoint."""
        update_query = self.requires_update_query.format(
            subject_uri=subject_uri,
            object_uri=object_uri
        )
        headers = {"Content-Type": "application/sparql-update"}
        
        try:
            ssl_context = False if self.BYPASS_SSL else None
            async with session.post(
                self.SPARQL_UPDATE_ENDPOINT,
                data=update_query.encode('utf-8'),
                headers=headers,
                ssl=ssl_context
            ) as response:
                pass  # Silent as in original code
        except Exception as e:
            logger.info(f"Failed to write dct:requires for {subject_uri} -> {object_uri}: {e}")
    
    def print_namespace_analysis(self, standard_uri: str, filename: str, 
                               namespaces: Set[str], logger: logging.Logger) -> None:
        """Print the namespace analysis for a dct:Standard ontology."""
        logger.info(f"\nUnique namespaces in dct:Standard {standard_uri} (filename: {filename}):")
        for ns in sorted(namespaces):
            logger.info(f"  {ns}")
        logger.info(f"Unique namespace count: {len(namespaces)}")
    
    async def run_analysis(self, analysis_id: str) -> AnalysisResult:
        """Run the complete analysis asynchronously."""
        start_time = time.time()
        logger, log_file = await self.setup_logging(analysis_id)
        
        try:
            # Update status
            analysis_results[analysis_id].status = "running"
            analysis_results[analysis_id].progress = "Initializing analysis..."
            
            logger.info("=== Semantic Registry Metrics Analysis ===\n")
            
            # Get download URLs
            analysis_results[analysis_id].progress = "Fetching download URLs..."
            logger.info("Fetching download URLs from SPARQL endpoint...")
            download_urls = await self.get_download_urls(logger)
            logger.info(f"Found {len(download_urls)} dct:Standard ontologies to analyze\n")
            
            # Create HTTP session for all requests
            connector = aiohttp.TCPConnector(ssl=not self.BYPASS_SSL)
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                # Process ontologies
                analysis_results[analysis_id].progress = "Processing ontologies..."
                logger.info("Processing ontologies and collecting namespace data...")
                
                ontology_namespaces = {}
                ontology_main_ns = {}
                
                # Download and parse all ontologies concurrently
                tasks = []
                for standard_uri, download_url in download_urls:
                    task = self.download_and_parse(session, download_url, logger)
                    tasks.append((standard_uri, download_url, task))
                
                # Process results as they complete
                for standard_uri, download_url, task in tasks:
                    graph = await task
                    if graph:
                        filename = os.path.basename(urlparse(download_url).path)
                        unique_ns = self.get_unique_namespaces(graph)
                        ontology_namespaces[standard_uri] = unique_ns
                        self.print_namespace_analysis(standard_uri, filename, unique_ns, logger)
                
                # Create mappings
                analysis_results[analysis_id].progress = "Creating namespace mappings..."
                logger.info("\nCreating dct:Standard namespace mappings based on actual RDF data...")
                dct_standard_mappings = self.get_dct_standard_mappings(download_urls, ontology_namespaces, logger)
                logger.info(f"Created {len(dct_standard_mappings)} dct:Standard mappings\n")
                
                # Update ontology_main_ns
                for standard_uri in ontology_namespaces.keys():
                    ontology_main_ns[standard_uri] = dct_standard_mappings.get(standard_uri)
                
                total_ontologies = len(ontology_namespaces)
                if total_ontologies == 0:
                    logger.info("No ontologies found or processed.")
                    raise HTTPException(status_code=404, detail="No ontologies found or processed")
                
                # Build indices
                ns_to_ontologies = {}
                for onto, ns_set in ontology_namespaces.items():
                    for ns in ns_set:
                        ns_to_ontologies.setdefault(ns, set()).add(onto)
                
                ns_to_ontology_uri = {ns: uri for uri, ns in ontology_main_ns.items() if ns}
                
                # Calculate LOVRank
                analysis_results[analysis_id].progress = "Calculating LOVRank metrics..."
                logger.info("\n=== LOVRank Metrics Table ===")
                logger.info(f"{'dct:Standard URI':60} {'Backlinks':>10} {'LOVRank':>10}")
                logger.info("-" * 85)
                
                ontology_metrics = []
                lovrank_tasks = []
                
                for standard_uri, main_ns in ontology_main_ns.items():
                    if not main_ns:
                        backlinks = 0
                        logger.info(f"DEBUG: {standard_uri} has no matching namespace")
                    else:
                        using_ontologies = ns_to_ontologies.get(main_ns, set())
                        backlinks = len(using_ontologies - {standard_uri})
                        if backlinks > 0:
                            logger.info(f"DEBUG: {standard_uri} (ns: {main_ns}) is used by {backlinks} other ontologies")
                    
                    lovrank = backlinks / total_ontologies if total_ontologies > 0 else 0
                    logger.info(f"{standard_uri:60} {backlinks:10} {lovrank:10.3f}")
                    
                    # Store metrics
                    ontology_metrics.append({
                        "standard_uri": standard_uri,
                        "backlinks": backlinks,
                        "lovrank": round(lovrank, 6)
                    })
                    
                    # Queue LOVRank update
                    task = self.write_lovrank_to_endpoint(session, standard_uri, f"{lovrank:.6f}", logger)
                    lovrank_tasks.append(task)
                
                # Wait for all LOVRank updates
                await asyncio.gather(*lovrank_tasks)
                
                logger.info("-" * 85)
                logger.info(f"Total ontologies: {total_ontologies}")
                
                # Process dependencies
                analysis_results[analysis_id].progress = "Processing dependencies..."
                dependency_count = 0
                dependency_tasks = []
                
                for standard_uri, used_namespaces in ontology_namespaces.items():
                    for ns in used_namespaces:
                        if ns in ns_to_ontology_uri and ns_to_ontology_uri[ns] != standard_uri:
                            target_ontology = ns_to_ontology_uri[ns]
                            task = self.write_requires_to_endpoint(session, standard_uri, target_ontology, logger)
                            dependency_tasks.append(task)
                            dependency_count += 1
                
                # Wait for all dependency updates
                await asyncio.gather(*dependency_tasks)
                
                logger.info(f"\nTotal dependencies established: {dependency_count}")
                elapsed = time.time() - start_time
                logger.info(f"\nScript execution time: {elapsed:.2f} seconds")
                logger.info(f"Log saved to: {log_file}")
                
                # Create result
                result = AnalysisResult(
                    analysis_id=analysis_id,
                    total_ontologies=total_ontologies,
                    dependencies_established=dependency_count,
                    execution_time=elapsed,
                    ontology_metrics=ontology_metrics,
                    log_file=log_file
                )
                
                return result
                
        except Exception as e:
            logger.error(f"Analysis failed: {str(e)}")
            raise e

# Global analyzer instance
analyzer = AsyncSemanticRegistryAnalyzer()

@app.post("/analyze", response_model=dict)
async def start_analysis(background_tasks: BackgroundTasks):
    """Start a new semantic registry analysis."""
    analysis_id = str(uuid.uuid4())
    
    # Initialize analysis status
    analysis_results[analysis_id] = AnalysisStatus(
        analysis_id=analysis_id,
        status="starting",
        progress="Initializing..."
    )
    
    # Start background task
    background_tasks.add_task(run_analysis_task, analysis_id)
    
    return {"analysis_id": analysis_id, "message": "Analysis started"}

async def run_analysis_task(analysis_id: str):
    """Background task to run the analysis."""
    try:
        result = await analyzer.run_analysis(analysis_id)
        analysis_results[analysis_id].status = "completed"
        analysis_results[analysis_id].result = result
        analysis_results[analysis_id].progress = "Analysis completed successfully"
    except Exception as e:
        analysis_results[analysis_id].status = "failed"
        analysis_results[analysis_id].error = str(e)
        analysis_results[analysis_id].progress = f"Analysis failed: {str(e)}"

@app.get("/analysis/{analysis_id}", response_model=AnalysisStatus)
async def get_analysis_status(analysis_id: str):
    """Get the status of an analysis."""
    if analysis_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    return analysis_results[analysis_id]

@app.get("/analysis/{analysis_id}/result", response_model=AnalysisResult)
async def get_analysis_result(analysis_id: str):
    """Get the result of a completed analysis."""
    if analysis_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    status = analysis_results[analysis_id]
    if status.status != "completed":
        raise HTTPException(status_code=400, detail=f"Analysis is {status.status}")
    
    return status.result

@app.get("/analyses", response_model=List[dict])
async def list_analyses():
    """List all analyses."""
    return [
        {
            "analysis_id": analysis_id,
            "status": status.status,
            "progress": status.progress
        }
        for analysis_id, status in analysis_results.items()
    ]

@app.delete("/analysis/{analysis_id}")
async def delete_analysis(analysis_id: str):
    """Delete an analysis."""
    if analysis_id not in analysis_results:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    del analysis_results[analysis_id]
    return {"message": "Analysis deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
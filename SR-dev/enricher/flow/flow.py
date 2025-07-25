from prefect import flow, task

@task
def fetch_data(source_endpoint):
    # Call external API
    return {"some": "data"}

@task
def enrich_graph(graph_uri, data):
    # Run SPARQL UPDATE using RDFLib, SPARQLWrapper, etc.
    pass

@flow
def enrichment_flow(graph_uri: str, source_endpoint: str):
    data = fetch_data(source_endpoint)
    enrich_graph(graph_uri, data)
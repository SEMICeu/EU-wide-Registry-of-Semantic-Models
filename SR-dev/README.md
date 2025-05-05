# Semantic Registry Metrics

This directory contains scripts and configuration for analyzing semantic registry metrics.

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Configure the settings:
The `config.yaml` file contains all the configuration settings for the SPARQL endpoint and queries. You can modify these settings as needed:

- `sparql.endpoint`: The SPARQL endpoint URL
- `sparql.graph_uri`: The graph URI to query
- `sparql.bypass_ssl`: Whether to bypass SSL verification (use with caution)
- `sparql_query`: The SPARQL query to execute

## Files

- `semantic-registry-metrics.ipynb`: Jupyter notebook for interactive analysis
- `semantic_registry_metrics.py`: Python script version of the notebook
- `config.yaml`: Configuration settings
- `requirements.txt`: Python package dependencies

## Usage

You can either:

1. Run the Jupyter notebook:
```bash
jupyter notebook semantic-registry-metrics.ipynb
```

2. Or run the Python script:
```bash
python semantic_registry_metrics.py
```

Both will use the settings from `config.yaml` for configuration. 
from fastapi import APIRouter, Query
from SPARQLWrapper import SPARQLWrapper, JSON
import yaml
import os
from typing import Optional
from datetime import datetime
from enum import Enum

import sys
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.schemas.country import Country
from app.schemas.nutscode import NUTSCode
from app.schemas.proceduretype import Proceduretype
from app.schemas.haslots import Haslots

v1_router = APIRouter(prefix="/v1")

@v1_router.get("/indicator1", 
            summary="Get a list of procedures for indicator1",    
            description="This endpoint returns a list of procedures for indicator1, filtered if needed, retrieved from Cellar",
            response_description="The response includes the direct sparql result from Cellar in a json object")
async def sparql_query(
    limit: int = Query(10, ge=1, le=100),
    year: Optional[int] = Query(
        default=None,
        ge=2020,  # greater than or equal to 2020
        le=datetime.now().year   # less than or equal to current year
        ),
    month: Optional[int] = Query(
        default=None,
        ge=1,  # greater than or equal to 1
        le=12   # less than or equal to current year
        ),   
    country: Optional[Country] = Query(None),
    nutscode: Optional[NUTSCode] = Query(None),
    proceduretype: Optional[Proceduretype] = Query(None),
    cpvcode: Optional[str] = Query(default=None, pattern=r"^\d{2}$"),
    lots: Optional[int] = Query(default=None,ge=1,le=1000),
    haslots: Optional[Haslots] = Query(None)
    ):

    # Get the directory where endpoints.py is located (api/)
    base_dir = os.path.dirname(__file__)
    # Construct the path to the YAML file (go up one level, then into config/)
    yaml_path = os.path.join(base_dir, "../..", "core", "config.yaml")
    # Normalize the path to avoid issues like ../
    yaml_path = os.path.normpath(yaml_path)
    
    # Load YAML configuration
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)

    endpoint = config["endpoint"]
    query_template = config["query1"]
    query_filter_limit = config["query1-filter-limit"]
    query_filter_year = config["query1-filter-year"]
    query_filter_month = config["query1-filter-month"]
    query_filter_country = config["query1-filter-country"]
    query_filter_nutscode = config["query1-filter-nutscode"]
    query_filter_proceduretype = config["query1-filter-proceduretype"]
    query_filter_cpvcode = config["query1-filter-cpvcode"]
    query_filter_lots = config["query1-filter-lots"]
    query_filter_haslots = config["query1-filter-haslots"]
    query_close_where = config["query1-close-where"]

    # prepare query
    query = query_template
    if year is not None:
        query = query + query_filter_year.replace("{year}", str(year))
    if month is not None:
        query = query + query_filter_month.replace("{month}", str(month))
    if country is not None and country.value is not None:
        query = query + query_filter_country.replace("{country}", str(country.value))
    if nutscode is not None and nutscode.value is not None:
        query = query + query_filter_nutscode.replace("{nutsCode}", str(nutscode.value))
    if proceduretype is not None and proceduretype.value is not None:
        query = query + query_filter_proceduretype.replace("{procedureType}", str(proceduretype.value))
    if cpvcode is not None:
        query = query + query_filter_cpvcode.replace("{cpvCode}", str(cpvcode))
    if lots is not None:
        query = query + query_filter_lots.replace("{lots}", str(lots))
    if haslots is not None and haslots.value is not None:
        query = query + query_filter_haslots.replace("{haslots}", str(haslots.value))
    query = query + query_close_where
    query = query + query_filter_limit.replace("{limit}", str(limit))
    print(query)
    # Set up endpoint
    sparql = SPARQLWrapper(endpoint)

    # Set up query
    sparql.setQuery(query)

    # Set return format
    sparql.setReturnFormat(JSON)

    # Execute the query
    results = sparql.query().convert()

    # Process and print results
    # for result in results["results"]["bindings"]:
    #    print(result["label"]["value"])
    return {"message": results}

@v1_router.get("/indicator2",
            summary="Get a list of procedures for indicator2",
            description="This endpoint returns a list of procedures for indicator2, filtered if needed, retrieved from Cellar",
            response_description="The response includes the direct sparql result from Cellar in a json object")
async def sparql_query(
    limit: int = Query(10, ge=1, le=100),
    year: Optional[int] = Query(
        default=None,
        ge=2020,  # greater than or equal to 2020
        le=datetime.now().year   # less than or equal to current year
        ),
    month: Optional[int] = Query(
        default=None,
        ge=1,  # greater than or equal to 1
        le=12   # less than or equal to current year
        ),   
    country: Optional[Country] = Query(None),
    nutscode: Optional[NUTSCode] = Query(None),
    proceduretype: Optional[Proceduretype] = Query(None),
    cpvcode: Optional[str] = Query(default=None, pattern=r"^\d{2}$"),
    lots: Optional[int] = Query(default=None,ge=1,le=1000),
    haslots: Optional[Haslots] = Query(None)
    ):

    # Get the directory where endpoints.py is located (api/)
    base_dir = os.path.dirname(__file__)
    # Construct the path to the YAML file (go up one level, then into config/)
    yaml_path = os.path.join(base_dir, "../..", "core", "config.yaml")
    # Normalize the path to avoid issues like ../
    yaml_path = os.path.normpath(yaml_path)
    
    # Load YAML configuration
    with open(yaml_path, "r") as f:
        config = yaml.safe_load(f)

    endpoint = config["endpoint"]
    query_template = config["query1"]
    query_filter_limit = config["query1-filter-limit"]
    query_filter_year = config["query1-filter-year"]
    query_filter_month = config["query1-filter-month"]
    query_filter_country = config["query1-filter-country"]
    query_filter_nutscode = config["query1-filter-nutscode"]
    query_filter_proceduretype = config["query1-filter-proceduretype"]
    query_filter_cpvcode = config["query1-filter-cpvcode"]
    query_filter_lots = config["query1-filter-lots"]
    query_filter_haslots = config["query1-filter-haslots"]
    query_close_where = config["query1-close-where"]

    # prepare query
    query = query_template
    if year is not None:
        query = query + query_filter_year.replace("{year}", str(year))
    if month is not None:
        query = query + query_filter_month.replace("{month}", str(month))
    if country is not None and country.value is not None:
        query = query + query_filter_country.replace("{country}", str(country.value))
    if nutscode is not None and nutscode.value is not None:
        query = query + query_filter_nutscode.replace("{nutsCode}", str(nutscode.value))
    if proceduretype is not None and proceduretype.value is not None:
        query = query + query_filter_proceduretype.replace("{procedureType}", str(proceduretype.value))
    if cpvcode is not None:
        query = query + query_filter_cpvcode.replace("{cpvCode}", str(cpvcode))
    if lots is not None:
        query = query + query_filter_lots.replace("{lots}", str(lots))
    if haslots is not None and haslots.value is not None:
        query = query + query_filter_haslots.replace("{haslots}", str(haslots.value))
    query = query + query_close_where
    query = query + query_filter_limit.replace("{limit}", str(limit))
    print(query)
    # Set up endpoint
    sparql = SPARQLWrapper(endpoint)

    # Set up query
    sparql.setQuery(query)

    # Set return format
    sparql.setReturnFormat(JSON)

    # Execute the query
    results = sparql.query().convert()

    # Process and print results
    # for result in results["results"]["bindings"]:
    #    print(result["label"]["value"])
    return {"message": results}
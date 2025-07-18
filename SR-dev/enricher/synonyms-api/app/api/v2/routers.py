from fastapi import APIRouter, Query, HTTPException, Request
import os
from typing import Optional
from datetime import datetime
from typing import List, Annotated
import logging

import sys
# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.schemas.country import Country
from app.schemas.nutscode import NUTSCode
from app.schemas.proceduretype import Proceduretype
from app.schemas.haslots import Haslots
from app.api.v2.models import ErrorResponse, Procedure, Procedure2

logger = logging.getLogger(__name__)

v2_router = APIRouter(prefix="/v2")

@v2_router.get("/indicator1",
    response_model=List[Procedure],
    responses={
        200: {"description": "Successful response", "model": List[Procedure]},
        400: {"description": "Bad Request", "model": ErrorResponse},
        500: {"description": "Internal Server Error", "model": ErrorResponse},
    },
    summary="Get a list of procedures for indicator1",  
    description="This endpoint returns a list of procedures for indicator1, filtered if needed, retrieved from Cellar. V2 provides a different response.",
    response_description="The response is a JSON object including list of procedures ")
async def sparql_query(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    year: Annotated[int , Query(default=..., ge=2020, le=datetime.now().year )] = None,
    month: Annotated[int , Query(default=..., ge=1, le=12)] = None,  
    country: Optional[Country] = Query(None),
    nutscode: Optional[NUTSCode] = Query(None),
    type: Optional[Proceduretype] = Query(None),
    cpv: Optional[str] = Query(default=None, pattern=r"^\d{2}$"),
    lots: Annotated[int , Query(default=..., ge=1, le=1000)] = None,
    haslots: Optional[Haslots] = Query(None)
    ):

    try:
        config = request.app.state.config

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
        filters = []
        if year is not None: filters.append(query_filter_year.replace("{year}", str(year)))
        if month is not None: filters.append(query_filter_month.replace("{month}", str(month)))
        if country is not None and country.value is not None: filters.append(query_filter_country.replace("{country}", str(country.value)))
        if nutscode is not None and nutscode.value is not None: filters.append(query_filter_nutscode.replace("{nutsCode}", str(nutscode.value)))
        if type is not None and type.value is not None: filters.append(query_filter_proceduretype.replace("{procedureType}", str(type.value)))
        if cpv is not None: filters.append(query_filter_cpvcode.replace("{cpvCode}", str(cpv)))
        if lots is not None: filters.append(query_filter_lots.replace("{lots}", str(lots)))
        if haslots is not None and haslots.value is not None: filters.append(query_filter_haslots.replace("{haslots}", str(haslots.value)))
       
        query = query_template + ''.join(filters) + query_close_where + query_filter_limit.replace("{limit}", str(limit))
        logger.info(query)
        
        sparql = request.app.state.sparql
        # Set up query
        sparql.setQuery(query)
        # Execute the query
        results = sparql.query().convert()

        # Process and print results
        procedures = []
        for result in results["results"]["bindings"]:
            procedure = Procedure(
                uri=result['procedure']['value'],
                type=result['procedureType']['value'],
                cpv=result['cpvcode2']['value'],
                country=result['country']['value'],
                nutscode=result['nutsCode']['value'],
                year=result['year']['value'],
                month=result['month']['value'],
                lots=result['lots']['value'],
                haslots=result['hasLots']['value'],
            )
            procedures.append(procedure)
        return procedures
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(detail=str(e), error="INVALID_INPUT").model_dump()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(detail=str(e), error="INTERNAL_ERROR").model_dump()
        )

@v2_router.get("/indicator2", 
    response_model=List[Procedure2],
    responses={
        200: {"description": "Successful response", "model": List[Procedure2]},
        400: {"description": "Bad Request", "model": ErrorResponse},
        500: {"description": "Internal Server Error", "model": ErrorResponse},
    },
    summary="Get a list of procedures for indicator2",  
    description="This endpoint returns a list of procedures for indicator2, filtered if needed, retrieved from Cellar. V2 provides a different response.",
    response_description="The response is a JSON object including list of procedures ")
async def sparql_query(
    request: Request,
    limit: int = Query(100, ge=1, le=500),
    type: Optional[Proceduretype] = Query(None),
    cpv: Optional[str] = Query(default=None, pattern=r"^\d{2}$"),
    countrybuyer: Optional[Country] = Query(None),
    nutscodebuyer: Optional[NUTSCode] = Query(None),
    countrywinner: Optional[Country] = Query(None),
    countries: Annotated[int , Query(default=..., ge=1, le=100)] = None, 
    year: Annotated[int , Query(default=..., ge=2020, le=datetime.now().year )] = None,
    month: Annotated[int , Query(default=..., ge=1, le=12)] = None,  
    lots: Annotated[int , Query(default=..., ge=1, le=1000)] = None,
    haslots: Optional[Haslots] = Query(None)
    ):

    try:
        config = request.app.state.config

        endpoint = config["endpoint"]
        query_template = config["query2"]
        query_filter_limit = config["query2-filter-limit"]
        query_filter_proceduretype = config["query2-filter-proceduretype"]
        query_filter_cpvcode = config["query2-filter-cpvcode"]
        query_filter_country_buyer = config["query2-filter-country-buyer"]
        query_filter_nutscode_buyer = config["query2-filter-nutscode-buyer"]
        query_filter_country_winner = config["query2-filter-country-winner"]
        query_filter_countries = config["query2-filter-countries"]
        query_filter_year = config["query2-filter-year"]
        query_filter_month = config["query2-filter-month"]
        query_filter_lots = config["query2-filter-lots"]
        query_filter_haslots = config["query2-filter-haslots"]
        query_close_where = config["query2-close-where"]

        # prepare query
        filters = []
        if type is not None and type.value is not None: filters.append(query_filter_proceduretype.replace("{procedureType}", str(type.value)))
        if cpv is not None: filters.append(query_filter_cpvcode.replace("{cpvCode}", str(cpv)))
        if countrybuyer is not None and countrybuyer.value is not None: filters.append(query_filter_country_buyer.replace("{countryBuyer}", str(countrybuyer.value)))
        if nutscodebuyer is not None and nutscodebuyer.value is not None: filters.append(query_filter_nutscode_buyer.replace("{nutsCodeBuyer}", str(nutscodebuyer.value)))
        if countrywinner is not None and countrywinner.value is not None: filters.append(query_filter_country_winner.replace("{countryWinner}", str(countrywinner.value)))
        if countries is not None: filters.append(query_filter_countries.replace("{countries}", str(countries)))
        if year is not None: filters.append(query_filter_year.replace("{year}", str(year)))
        if month is not None: filters.append(query_filter_month.replace("{month}", str(month)))
        if lots is not None: filters.append(query_filter_lots.replace("{lots}", str(lots)))
        if haslots is not None and haslots.value is not None: filters.append(query_filter_haslots.replace("{haslots}", str(haslots.value)))
        
        query = query_template + ''.join(filters) + query_close_where + query_filter_limit.replace("{limit}", str(limit))
        logger.info(query)

        # Set up endpoint
        sparql = request.app.state.sparql
        # Set up query
        sparql.setQuery(query)
        # Execute the query
        results = sparql.query().convert()

        # Process and print results
        procedures = []
        for result in results["results"]["bindings"]:
            procedure = Procedure2(
                uri=result['procedure']['value'],
                type=result['procedureType']['value'],
                cpv=result['cpvcode2']['value'],
                countrybuyer=result['countryBuyer']['value'],
                nutscodebuyer=result['nutsCodeBuyer']['value'],
                countrywinner=result['countryWinner']['value'],
                countries=result['countries']['value'],
                year=result['year']['value'],
                month=result['month']['value'],
                lots=result['lots']['value'],
                haslots=result['hasLots']['value'],
            )
            procedures.append(procedure)
        return procedures
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(detail=str(e), error="INVALID_INPUT").model_dump()
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(detail=str(e), error="INTERNAL_ERROR").model_dump()
        )
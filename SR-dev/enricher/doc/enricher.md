# Enricher

## Objective

The objective is to be able to find the standards in the registry.

The scope of the enricher is to enrich the data for the registry by:
- adding automatically a classification (dcat:theme) for a dct:Standard
- find synonyms (skos:altLabel) for the name of the classes being part of a dct:Standard
- translate the description (dct:description) of a dct:Standard in multiple languages

For more information of the model, see the [SRM](https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.0/)

## Setup

The environment is completely based on Python 3 that should be setup.

Steps:
1) Pull the code and open the project with VSCode
2) From the terminal type:
   cd .\SR-dev\enricher\enricher-api\
3) create and activate the environment space:
   
  - ```python -m venv .venv```
   
  - ```& .venv/Scripts/Activate```                                                                 
5) setup the requirements:

   ```pip install -r .\requirements.txt```
   
6) run the prefect server to monitor the execution:
   
   ```prefect server start```
   
   the prefect dashboard should be accessible on http://127.0.0.1:4200
8) from the dashboard configure prefect to enable concurrency on task with tag "enrich" set to 5 slots, see screenshot [prefect concurrency](prefect_concurrency.jpg)
9)  

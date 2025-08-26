# Enricher

## Objective

The objective is to be able to find the standards in the registry.

The scope of the enricher is to enrich the data for the registry by:
- adding automatically a classification (dcat:theme) for a dct:Standard, so they can be easily found out via the classification filter
- find synonyms (skos:altLabel) for the name of the classes being part of a dct:Standard, so via synonyms classes and thefore standard can be found.
- translate the description (dct:description) of a dct:Standard in multiple languages, so end user can search in their own languages.

For more information of the model, see the [SRM](https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.0/)

## Architecture

The enricher is mainly based on 2 open source software:
- [FastAPI](https://fastapi.tiangolo.com/) to trigger the Enricher and to execute 3 main API: classify, synonyms and translate.
- [Prefect](https://www.prefect.io/) to create a flow of 3 respective tasks (classify, synonyms and translate), that fetch the data needed from Virtuoso, calls the respective API and store the new data in Virtuoso.

See the [architecture](enricher_architecture.png) for better understanding.

## Setup

The environment is completely based on Python 3 that should be setup in the system (the version 3.11 was used for development).

Steps:
1) Pull the code and open the project with VSCode
2) From the terminal type:
   cd .\SR-dev\enricher\enricher-api\
3) create and activate the environment space:
   
  - ```python -m venv .venv```
   
  - ```& .venv/Scripts/Activate```                                                                 
4) setup the requirements:

   ```pip install -r .\requirements.txt```

5) make sure that database files are in place. The Enricher uses SQLite, via SQL Alchemy, in 2 different files:
   - enrichment_jobs.db : to store the job id executions over time, that could be used to track the execution status of the enrichment and link withe Prefect job id. The file should be present in [/enricher-api/app/v1/db/](https://github.com/SEMICeu/EU-wide-Registry-of-Semantic-Models/tree/main/SR-dev/enricher/enricher-api/app/api/v1/db) folder. Inside that folder there is create_db.py that could be executed to create the file with the command
     ```python create_db.py```
     
   - synonyms_cache.db : to store the synonyms instead of query data sources. The file should be present in [/enricher-api/app/v1/routers/synonyms](https://github.com/SEMICeu/EU-wide-Registry-of-Semantic-Models/tree/main/SR-dev/enricher/enricher-api/app/api/v1/routers/synonyms). Inside that folder there is create_db.py that could be executed to create the file with the command
  
     ```python create_db.py```

6) There are multiple configuration files:
   - [config_log.yaml](https://github.com/SEMICeu/EU-wide-Registry-of-Semantic-Models/blob/main/SR-dev/enricher/enricher-api/app/config_log.yaml) : to configure the logging of the application
   - [config_prefect.yaml](https://github.com/SEMICeu/EU-wide-Registry-of-Semantic-Models/blob/main/SR-dev/enricher/enricher-api/app/config_prefect.yaml) : to configure the behaviour of the prefect flow and tasks
   - [config_api_classify.yaml](https://github.com/SEMICeu/EU-wide-Registry-of-Semantic-Models/blob/main/SR-dev/enricher/enricher-api/app/config_api_classify.yaml) : to configure the behaviour of the api classify
   - [config_api_synonyms.yaml](https://github.com/SEMICeu/EU-wide-Registry-of-Semantic-Models/blob/main/SR-dev/enricher/enricher-api/app/config_api_synonyms.yaml) : to configure the behaviour of the api synonyms

7) Make sure you can access the Hugging face models page https://huggingface.co/models, that is used by the Enricher, via the [list_models](https://github.com/SEMICeu/EU-wide-Registry-of-Semantic-Models/blob/main/SR-dev/enricher/enricher-api/app/api/v1/mlmodels.py#L198), to download first the list of machine learning models for translation.
   The page is sometimes blocked by the company proxy and you can get the log message:
   
   {"time": "2025-08-22 22:53:47", "level": "INFO", "name": "app.api.v1.mlmodels", "message": "Fetching models from Hugging Face Hub..."}
   {"time": "2025-08-22 22:53:47", "level": "ERROR", "name": "app", "message": "Failed to preload translation pairs: Expecting value: line 1 column 1 (char 0)"}

## Execution
 
1) run the prefect server to monitor the execution:
   
   ```prefect server start```
   
   the Prefect dashboard should be accessible on http://127.0.0.1:4200
2) from the Prefect dashboard configure concurrency on task with tag "enrich" set to 5 slots, see screenshot [prefect concurrency](prefect_concurrency.jpg)
3) in VSCode, open a new terminal and launch:

    ```uvicorn app.main:app --workers 5 --log-config app/config_log.yaml```

 The idea is that the FastAPI will provide 5 parallel workers and Prefect will allocate max 5 slots of concurrency at the same time. The application will write to the app.log file.
 
 The FastAPI documentation will be available on http://127.0.0.1:8000/docs#

4) Execute the POST operation on /enricher-api/v1/job passing the parameters. The prefect flow will be triggered and it can be monitored see for example the [prefect classify task](prefect_classify_task.jpg)

### Executing classify task
The classify task is divided in 3 steps:

 1) fetch the English description of the Standard to classify from the graph in the sparql endpoint, see query
 2) classify the descriptions accordingly to the Publications Office data themes, calling the classify API
 3) add the data themes to the graph 

### Executing synonyms task
The classify task is divided in 3 steps:

 1) fetch:
   - the English description of the Standard and
   - the English labels of classes belonging to the Standard
   
   from the graph in the sparql endpoint, see query
 2) find the best synonyms for a label, if it exists, calling the synonyms API
 3) add (update) the synonyms back to the graph, see query 

#### Synonyms API

The synoynms API has 3 data sources to find synonyms: nltk (wordnet), altervista API and datamuse API.
The end user can pass the below parameters:
 - a term, the text to be searched for synonyms
 - the data sources in which to search
 - a context, a sentence to be used to give a context and reorder the results in decreasing order probability
 - the maximum number of results

The synonyms task provides then:
 - a label as term
 - the English description of the Standard as context
 - the maximum value 1 to be returned

To evaluate against the context, the synonyms API uses the sentence transformers model "all-MiniLM-L6-v2".

The synonyms found for a term are stored in a cache so the synonyms api uses the cache to retrieve the synonyms first without call the API.
The end user can get or delete the cache and look at the cache statistics from the respective API endpoints.

### Executing translate task
The classify task is divided in 5 steps:

 1) delete the translations from the graph in the sparql endpoint, see query
 2) find descriptions to translate, by looking at the language list finding those missing, see query
 3) make batches of a certain size, defined in the [config_prefect.yaml](https://github.com/SEMICeu/EU-wide-Registry-of-Semantic-Models/blob/main/SR-dev/enricher/enricher-api/app/config_prefect.yaml) : to configure the behaviour of the prefect flow and tasks
 4) translate batch, calling the translate API
 5) add translations to the graph, see query

## Debug

1) Check executions of the tasks on the Prefect dashboard
2) Monitor the app.log file, it could be also monitored/analysed with streamlit with the command:

   ```streamlit run log_dashboard.py```

Notes:
1) if you stop the execution from the VSCode terminal, while it is executing the Prefect tasks, make sure that there aren't active tasks in the concurrency with the command:

   ```prefect concurrency-limit inspect enrich```
   
   if you see active tasks better reset via the command:

   ```prefect concurrency-limit reset enrich```

2) Sometimes in the app.log you see warnings on concurrency of sqlite, these are internal warnings of Prefect that you can ignore.



















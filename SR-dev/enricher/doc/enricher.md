# Enricher

## Objective

The objective is to be able to find the standards in the registry.

The scope of the enricher is to enrich the data for the registry by:
- adding automatically a classification (dcat:theme) for a dct:Standard
- find synonyms (skos:altLabel) for the name of the classes being part of a dct:Standard
- translate the description (dct:description) of a dct:Standard in multiple languages

For more information of the model, see the [SRM](https://semiceu.github.io/uri.semic.eu-generated/SRM/releases/1.0.0/)

## Architecture

The enricher is based on:
- FastAPI to trigger its own execution and to trigger 3 main API: synonyms, classify and translate.
- Prefect to create a flow of 3 respective tasks (synonyms, classify and translate), that fetch the data from Virtuoso, calls the respective API and store the new data in Virtuoso

See the [architecture](enricher_architecture.png) for better understanding.

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

## Execution
0) Make sure you can access the Hugging face models page https://huggingface.co/models, that is used by the application to download first the list of machine learning models for translation 
1) run the prefect server to monitor the execution:
   
   ```prefect server start```
   
   the Prefect dashboard should be accessible on http://127.0.0.1:4200
2) from the Prefect dashboard configure concurrency on task with tag "enrich" set to 5 slots, see screenshot [prefect concurrency](prefect_concurrency.jpg)
3) in VSCode, open a new terminal and launch:

    ```uvicorn app.main:app --workers 5 --log-config log_config.yaml```

 The idea is that the FastAPI will provide 5 parallel workers and Prefect will allocate max 5 slots of concurrency at the same time. The application will write to the app.log file.
 
 The FastAPI documentation will be available on http://127.0.0.1:8000/docs#

4) Execute the POST operation on /enricher-api/v1/job passing the default parameters

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
  







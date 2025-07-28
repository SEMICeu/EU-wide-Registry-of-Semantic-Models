sequenceDiagram
    participant C as Client
    participant A as FastAPI
    participant DB as Database
    participant P as Prefect Flow
    participant API1 as Classify API
    participant API2 as Translate API
    participant API3 as Synonyms API
    participant V as Virtuoso SPARQL

    C->>A: POST /job (graph_uri, source_endpoint)
    A->>DB: Insert job (status=pending)
    DB-->>A: Job ID
    A-->>C: 201 Created (job_id)

    A->>P: Start enrichment_flow(job_id)

    P->>DB: Update job (status=running, flow_run_id, flow_url)
    DB-->>P: OK

    C->>A: GET /job/{job_id}
    A->>DB: Query job status
    DB-->>A: status=running
    A-->>C: status=running

    par Parallel Tasks
        rect rgb(204, 255, 204)
            P->>V: fetch - SPARQL SELECT
            V-->>P: Data
            P->>API1: Call Classify API
            API1-->>P: Classified data
            P->>V: enrich - SPARQL UPDATE with classified data
            V-->>P: OK
        end

        rect rgb(153, 153, 255)
            P->>V: SPARQL SELECT
            V-->>P: Data
            P->>API2: Call Translate API
            API2-->>P: Translated data
            P->>V: enrich - SPARQL UPDATE with translations
            V-->>P: OK
        end

        rect rgb(255, 204, 255)
            P->>V: fetch - SPARQL SELECT
            V-->>P: Data
            P->>API3: Call Synonyms API
            API3-->>P: Synonyms data
            P->>V: enrich - SPARQL UPDATE with synonyms
            V-->>P: OK
        end
    end

    P->>DB: Update job (status=completed, flow_run_id, flow_url)
    DB-->>P: OK

    C->>A: GET /job/{job_id}
    A->>DB: Query job status
    DB-->>A: status=completed, flow_run_id, flow_url
    A-->>C: status=completed + flow metadata

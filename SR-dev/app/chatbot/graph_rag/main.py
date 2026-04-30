from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase

import config
from graph_rag.api.router import router as chat_router

app = FastAPI(
    title="SR-GraphRAG API",
    version="1.0.0",
    description="Backend API for SRM GraphRAG chat with streaming events.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str | int]:
    try:
        with GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD),
        ) as driver:
            with driver.session(database="neo4j") as session:
                row = session.run("MATCH (n) RETURN count(n) AS total_nodes").single()
                total_nodes = int(row["total_nodes"]) if row and row["total_nodes"] is not None else 0
        if total_nodes <= 0:
            raise HTTPException(status_code=503, detail="Neo4j connected but no ingested data found.")
        return {"status": "ready", "neo4j": "connected", "total_nodes": total_nodes}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Neo4j not ready: {type(exc).__name__}: {exc}")


app.include_router(chat_router)



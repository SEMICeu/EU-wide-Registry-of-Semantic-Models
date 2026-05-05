from __future__ import annotations

import os
import time

from neo4j import GraphDatabase

from graph_rag.setup.setup import main as run_ingestion


def _wait_for_neo4j(max_attempts: int = 60, sleep_seconds: int = 2) -> None:
    uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")

    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            with GraphDatabase.driver(uri, auth=(username, password)) as driver:
                with driver.session(database="neo4j") as session:
                    session.run("RETURN 1 AS ok").single()
            print(f"[bootstrap] Neo4j is reachable (attempt {attempt}).")
            return
        except Exception as exc:
            last_error = exc
            print(f"[bootstrap] Waiting for Neo4j (attempt {attempt}/{max_attempts}): {exc}")
            time.sleep(sleep_seconds)
    raise RuntimeError(f"Neo4j not reachable after {max_attempts} attempts: {last_error}")


def _assert_ingested() -> None:
    uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    username = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    with GraphDatabase.driver(uri, auth=(username, password)) as driver:
        with driver.session(database="neo4j") as session:
            row = session.run("MATCH (n) RETURN count(n) AS total_nodes").single()
            total_nodes = int(row["total_nodes"]) if row and row["total_nodes"] is not None else 0
    if total_nodes <= 0:
        raise RuntimeError("Ingestion check failed: Neo4j has zero nodes after ingestion.")
    print(f"[bootstrap] Ingestion check passed: total_nodes={total_nodes}.")


def main() -> None:
    _wait_for_neo4j()
    print("[bootstrap] Starting ingestion pipeline...")
    run_ingestion()
    _assert_ingested()
    print("[bootstrap] Backend bootstrap completed.")


if __name__ == "__main__":
    main()


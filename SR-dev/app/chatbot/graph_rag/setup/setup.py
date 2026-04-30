"""
Neo4j setup entrypoint for SRM TTL ingestion.

Runs the setup ingestion pipeline that:
- ensures n10s constraint/config
- imports data_SRM.ttl
- imports enriched_SRM.ttl
- continues with configured embedding/indexing steps
"""

try:
    from .ingestion import KnowledgeGraphIngestion
except ImportError:
    from ingestion import KnowledgeGraphIngestion  # type: ignore


def main() -> None:
    ingestion = KnowledgeGraphIngestion()
    ingestion.run_ingestion()


if __name__ == "__main__":
    main()


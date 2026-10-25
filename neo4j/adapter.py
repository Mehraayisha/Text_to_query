"""
Neo4j Graph Database Adapter.
Handles connecting to Neo4j, extracting graph schema (nodes, properties, relationships),
and building the Unified Semantic Layer.
"""

import os
from typing import Optional

try:
    from .base_adapter import BaseAdapter
    from .models import DatabaseMetadata
    from .schema_extract import extract_neo4j_schema
    from .normalizer import normalize_neo4j_schema
except ImportError:
    from base_adapter import BaseAdapter
    from models import DatabaseMetadata
    from schema_extract import extract_neo4j_schema
    from normalizer import normalize_neo4j_schema

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Neo4jGraphAdapter(BaseAdapter):
    """Graph Adapter for Neo4j Database."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None
    ):
        uri = uri or os.getenv("NEO4J_URI", "neo4j+s://demo.neo4jlabs.com")
        user = user or os.getenv("NEO4J_USER", "northwind")
        password = password or os.getenv("NEO4J_PASSWORD", "northwind")
        database = database or os.getenv("NEO4J_DATABASE", "northwind")

        super().__init__(
            database_id=f"neo4j_{database}",
            database_name=f"Neo4j ({database})",
            dialect="neo4j_cypher"
        )
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database

    def extract_schema(self) -> DatabaseMetadata:
        """Extracts schema from Neo4j and normalizes into DatabaseMetadata."""
        raw_schema = extract_neo4j_schema(self.uri, self.user, self.password, database=self.database)
        return normalize_neo4j_schema(
            raw_schema=raw_schema,
            database_id=self.database_id,
            database_name=self.database_name,
            dialect=self.dialect
        )


# Alias
Neo4jAdapter = Neo4jGraphAdapter

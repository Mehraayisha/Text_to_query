"""
Database Adapters Package
Defines the BaseAdapter interface and concrete implementations for Graph (Neo4j), SQL (BigQuery/Postgres), etc.
"""

from .base_adapter import BaseAdapter
from .neo4j_adapter import Neo4jGraphAdapter
from .sql_adapter import BigQuerySQLAdapter

__all__ = ["BaseAdapter", "Neo4jGraphAdapter", "BigQuerySQLAdapter"]

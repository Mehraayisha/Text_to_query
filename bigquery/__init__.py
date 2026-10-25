"""
BigQuery Adapter & Semantic Layer Package.
Self-contained package providing the BigQuery adapter, schema extractor, normalizer,
semantic layer models, and Text2SQL terminal application.
"""

from .adapter import BigQuerySQLAdapter, BigQueryAdapter
from .schema_extract import extract_bigquery_schema
from .normalizer import normalize_bigquery_schema, normalize_sql_schema
from .base_adapter import BaseAdapter
from .models import (
    DatabaseMetadata,
    EntitySchema,
    AttributeSchema,
    RelationshipSchema,
    DatabaseType,
    EntityType,
    Cardinality,
)
from .text2sql import start_terminal_app

__all__ = [
    "BigQuerySQLAdapter",
    "BigQueryAdapter",
    "extract_bigquery_schema",
    "normalize_bigquery_schema",
    "normalize_sql_schema",
    "BaseAdapter",
    "DatabaseMetadata",
    "EntitySchema",
    "AttributeSchema",
    "RelationshipSchema",
    "DatabaseType",
    "EntityType",
    "Cardinality",
    "start_terminal_app",
]

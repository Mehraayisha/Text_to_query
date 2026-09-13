"""
Unified Semantic Layer Package
Normalizes database metadata across heterogeneous data sources into a single standard schema format.
"""

from .models import (
    DatabaseMetadata,
    EntitySchema,
    AttributeSchema,
    RelationshipSchema,
    DatabaseType,
    EntityType,
    Cardinality,
)
from .normalizer import normalize_sql_schema, normalize_neo4j_schema

__all__ = [
    "DatabaseMetadata",
    "EntitySchema",
    "AttributeSchema",
    "RelationshipSchema",
    "DatabaseType",
    "EntityType",
    "Cardinality",
    "normalize_sql_schema",
    "normalize_neo4j_schema",
]

"""
MongoDB Module for Unified Semantic Layer and Natural Language Querying.
Matches the architecture of bigquery/ and neo4j/ modules.
"""

import sys

from .models import (
    DatabaseMetadata,
    EntitySchema,
    AttributeSchema,
    RelationshipSchema,
    DatabaseType,
    EntityType,
    Cardinality,
    GenericDataType,
    map_raw_type_to_generic,
)
from .base_adapter import BaseAdapter
from .adapter import MongoDBDocumentAdapter, MongoDBAdapter
from .normalizer import normalize_mongodb_schema
from .schema_discovery import SchemaDiscoverer
from .config import Config
from .agent import MongoDBAgent

# Register backwards-compatible alias for any code importing 'mongodb_agent'
sys.modules["mongodb_agent"] = sys.modules[__name__]

__all__ = [
    "DatabaseMetadata",
    "EntitySchema",
    "AttributeSchema",
    "RelationshipSchema",
    "DatabaseType",
    "EntityType",
    "Cardinality",
    "GenericDataType",
    "map_raw_type_to_generic",
    "BaseAdapter",
    "MongoDBDocumentAdapter",
    "MongoDBAdapter",
    "normalize_mongodb_schema",
    "SchemaDiscoverer",
    "Config",
    "MongoDBAgent",
]


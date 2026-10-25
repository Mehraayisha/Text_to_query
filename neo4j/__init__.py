"""
Neo4j Adapter & Semantic Layer Package.
Self-contained package providing the Neo4j adapter, schema extractor, normalizer,
semantic layer models, and Text2Cypher terminal application.
"""

import sys
import os
import importlib.util
import importlib.machinery

# Dynamically locate and merge official site-packages neo4j driver
_cur_dir = os.path.dirname(os.path.abspath(__file__))
_search_paths = [p for p in sys.path if os.path.abspath(p) not in (_cur_dir, os.path.dirname(_cur_dir), "")]
_spec = importlib.machinery.PathFinder.find_spec('neo4j', _search_paths)
if _spec and _spec.submodule_search_locations:
    for _loc in _spec.submodule_search_locations:
        if _loc not in __path__:
            __path__.append(_loc)
    _real = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_real)
    for _k, _v in _real.__dict__.items():
        if not _k.startswith("__"):
            globals()[_k] = _v

from .adapter import Neo4jGraphAdapter, Neo4jAdapter
from .schema_extract import extract_neo4j_schema
from .normalizer import normalize_neo4j_schema
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
from .text2cypher import start_terminal_app

__all__ = [
    "Neo4jGraphAdapter",
    "Neo4jAdapter",
    "extract_neo4j_schema",
    "normalize_neo4j_schema",
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

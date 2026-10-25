"""
MongoDB Document Database Adapter.
Exposes MongoDBDocumentAdapter and related models for the Unified Semantic Layer.
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from mongodb_agent.adapter import MongoDBDocumentAdapter, MongoDBAdapter
from mongodb_agent.models import DatabaseMetadata
from mongodb_agent.base_adapter import BaseAdapter
from mongodb_agent.normalizer import normalize_mongodb_schema

__all__ = [
    "MongoDBDocumentAdapter",
    "MongoDBAdapter",
    "DatabaseMetadata",
    "BaseAdapter",
    "normalize_mongodb_schema",
]


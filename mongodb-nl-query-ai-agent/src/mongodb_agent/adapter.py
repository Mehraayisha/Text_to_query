"""
MongoDB Document Database Adapter inside mongodb_agent.
Handles connecting to MongoDB, extracting Document schema (collections, fields, types, relationships)
via SchemaDiscoverer, and building the Unified Semantic Layer.
Conforms to SEMANTIC_LAYER_SPEC.md.
"""

import os
from typing import Optional
from mongodb_agent.base_adapter import BaseAdapter
from mongodb_agent.models import DatabaseMetadata
from mongodb_agent.normalizer import normalize_mongodb_schema
from mongodb_agent.schema_discovery import SchemaDiscoverer

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class MongoDBDocumentAdapter(BaseAdapter):
    """Document Adapter for MongoDB Database."""

    def __init__(
        self,
        uri: Optional[str] = None,
        database: Optional[str] = None,
        sample_size: int = 50,
    ):
        uri = uri or os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        database = database or os.getenv("MONGODB_DATABASE", "sample_mflix")

        super().__init__(
            database_id=f"mongodb_{database}",
            database_name=f"MongoDB ({database})",
            dialect="mongodb",
        )
        self.uri = uri
        self.database = database
        self.sample_size = sample_size

    def extract_schema(self) -> DatabaseMetadata:
        """
        Extracts MongoDB metadata using SchemaDiscoverer
        and normalizes it into Unified DatabaseMetadata.
        """
        discoverer = SchemaDiscoverer(
            uri=self.uri,
            database_name=self.database,
            sample_size=self.sample_size,
        )

        collections_analysis, relationships_data, _ = discoverer.discover()

        return normalize_mongodb_schema(
            collections_analysis=collections_analysis,
            relationships_data=relationships_data,
            database_id=self.database_id,
            database_name=self.database_name,
            dialect=self.dialect,
        )

    def export_semantic_layer(self, output_path: str, indent: int = 2) -> DatabaseMetadata:
        """Extracts schema and saves the Unified Semantic Layer to a JSON file."""
        out_dir = os.path.dirname(os.path.abspath(output_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        return super().export_semantic_layer(output_path=output_path, indent=indent)


# Alias
MongoDBAdapter = MongoDBDocumentAdapter


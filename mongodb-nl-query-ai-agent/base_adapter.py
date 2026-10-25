"""
Abstract Base Adapter Interface for MongoDB Document Database.
"""

from abc import ABC, abstractmethod
try:
    from .models import DatabaseMetadata
except ImportError:
    from models import DatabaseMetadata


class BaseAdapter(ABC):
    """Abstract Base Class for database adapters."""

    def __init__(self, database_id: str, database_name: str, dialect: str):
        self.database_id = database_id
        self.database_name = database_name
        self.dialect = dialect

    @abstractmethod
    def extract_schema(self) -> DatabaseMetadata:
        """Extracts raw schema metadata from the connected database source into DatabaseMetadata."""
        pass

    def export_semantic_layer(self, output_path: str, indent: int = 2) -> DatabaseMetadata:
        """Extracts schema and saves the Unified Semantic Layer to a JSON file."""
        metadata = self.extract_schema()
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(metadata.to_json(indent=indent))
        return metadata


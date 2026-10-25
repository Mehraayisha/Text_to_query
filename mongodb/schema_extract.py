"""
MongoDB Raw Schema and Document Structure Extractor.
Uses SchemaDiscoverer to connect to MongoDB, sample documents, infer nested structures,
and detect cross-collection relationships.
"""

from typing import Dict, Any, List, Tuple, Optional
from mongodb.schema_discovery import SchemaDiscoverer


def extract_mongodb_schema(
    uri: Optional[str] = None,
    database: Optional[str] = None,
    sample_size: int = 50,
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """
    Connects to MongoDB, analyzes collections & nested documents, and detects relationships.

    Returns:
        Tuple of (collections_analysis, relationships_data, raw_model_dict)
    """
    discoverer = SchemaDiscoverer(
        uri=uri,
        database_name=database,
        sample_size=sample_size,
    )
    return discoverer.discover()


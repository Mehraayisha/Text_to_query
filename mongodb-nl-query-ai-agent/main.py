"""
MongoDB Unified Semantic Layer Extraction Runner.
Connects to MongoDB via MongoDBDocumentAdapter, extracts schema via SchemaDiscoverer,
and exports the Unified Semantic Layer JSON (and optionally YAML).
"""

import os
import sys

# Ensure local folder and src are in path for standalone execution
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from adapter import MongoDBDocumentAdapter


def run_extraction(output_filename: str = None):
    print("==================================================")
    print("EXTRACTING MONGODB UNIFIED SEMANTIC LAYER")
    print("==================================================")

    adapter = MongoDBDocumentAdapter()
    db_name = adapter.database
    filename = output_filename or f"unified_semantic_layer_mongodb_{db_name}.json"
    output_path = os.path.join(current_dir, filename)

    metadata = adapter.export_semantic_layer(output_path)

    print(f"[OK] Database ID: {metadata.database_id}")
    print(f"[OK] Database Type: {metadata.database_type} ({metadata.dialect})")
    print(f"[OK] Extracted {len(metadata.entities)} Collections and {len(metadata.relationships)} Relationships.")
    print(f"[OK] Saved Unified Semantic Layer to '{output_path}'\n")

    return metadata


if __name__ == "__main__":
    run_extraction()


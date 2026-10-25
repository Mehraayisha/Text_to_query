"""
Neo4j Unified Semantic Layer Extraction Runner.
Connects to Neo4j via Neo4jGraphAdapter, extracts schema, and exports the Unified Semantic Layer.
"""

import os
import sys

# Ensure local folder is in path for standalone execution
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from adapter import Neo4jGraphAdapter


def run_extraction():
    print("==================================================")
    print("EXTRACTING NEO4J UNIFIED SEMANTIC LAYER")
    print("==================================================")

    adapter = Neo4jGraphAdapter()
    output_path = os.path.join(current_dir, "unified_semantic_layer_neo4j_northwind.json")

    metadata = adapter.export_semantic_layer(output_path)

    print(f"[OK] Database ID: {metadata.database_id}")
    print(f"[OK] Database Type: {metadata.database_type} ({metadata.dialect})")
    print(f"[OK] Extracted {len(metadata.entities)} Node Labels and {len(metadata.relationships)} Graph Relationships.")
    print(f"[OK] Saved Unified Semantic Layer to '{output_path}'\n")

    return metadata


if __name__ == "__main__":
    run_extraction()

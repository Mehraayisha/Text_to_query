"""
BigQuery Unified Semantic Layer Extraction Runner.
Connects to BigQuery via BigQuerySQLAdapter, extracts schema, and exports the Unified Semantic Layer.
"""

import os
import sys

# Ensure local folder is in path for standalone execution
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from adapter import BigQuerySQLAdapter


def run_extraction():
    print("==================================================")
    print("EXTRACTING BIGQUERY UNIFIED SEMANTIC LAYER")
    print("==================================================")

    adapter = BigQuerySQLAdapter()
    output_path = os.path.join(current_dir, "unified_semantic_layer_bq_thelook.json")

    metadata = adapter.export_semantic_layer(output_path)

    print(f"[OK] Database ID: {metadata.database_id}")
    print(f"[OK] Database Type: {metadata.database_type} ({metadata.dialect})")
    print(f"[OK] Extracted {len(metadata.entities)} Tables and {len(metadata.relationships)} Foreign Key Relationships.")
    print(f"[OK] Saved Unified Semantic Layer to '{output_path}'\n")

    return metadata


if __name__ == "__main__":
    run_extraction()

"""
Semantic Layer & Adapter Schema Extraction Test Script.
Tests connecting to database sources via Adapters and generating Unified Semantic Layer JSON artifacts.
"""

from adapters import Neo4jGraphAdapter, BigQuerySQLAdapter
from semantic_layer import DatabaseMetadata


def test_neo4j_semantic_layer():
    print("==================================================")
    print("1. EXTRACTING NEO4J UNIFIED SEMANTIC LAYER")
    print("==================================================")

    adapter = Neo4jGraphAdapter()
    output_path = "unified_semantic_layer_neo4j_northwind.json"

    # Extract schema & export Unified Semantic Layer
    metadata: DatabaseMetadata = adapter.export_semantic_layer(output_path)

    print(f"[OK] Database ID: {metadata.database_id}")
    print(f"[OK] Database Type: {metadata.database_type} ({metadata.dialect})")
    print(f"[OK] Extracted {len(metadata.entities)} Node Labels and {len(metadata.relationships)} Graph Relationships.")
    print(f"[OK] Saved Unified Semantic Layer to '{output_path}'\n")


def test_bigquery_semantic_layer():
    print("==================================================")
    print("2. EXTRACTING BIGQUERY UNIFIED SEMANTIC LAYER")
    print("==================================================")

    adapter = BigQuerySQLAdapter()
    output_path = "unified_semantic_layer_bq_thelook.json"

    # Extract schema & export Unified Semantic Layer
    metadata: DatabaseMetadata = adapter.export_semantic_layer(output_path)

    print(f"[OK] Database ID: {metadata.database_id}")
    print(f"[OK] Database Type: {metadata.database_type} ({metadata.dialect})")
    print(f"[OK] Extracted {len(metadata.entities)} Tables and {len(metadata.relationships)} Foreign Key Relationships.")
    print(f"[OK] Saved Unified Semantic Layer to '{output_path}'\n")


if __name__ == "__main__":
    print("Starting Unified Semantic Layer Extraction via Adapters...\n")
    test_neo4j_semantic_layer()
    test_bigquery_semantic_layer()
    print("ALL UNIFIED SEMANTIC LAYER EXTRACTIONS COMPLETED SUCCESSFULLY!")

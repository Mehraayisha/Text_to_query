"""
Semantic Layer & Adapter Schema Extraction Test Script.
Runs extraction for Neo4j and BigQuery from their self-contained folders.
"""

from neo4j.adapter import Neo4jGraphAdapter
from bigquery.adapter import BigQuerySQLAdapter


def test_neo4j_semantic_layer():
    print("==================================================")
    print("1. EXTRACTING NEO4J UNIFIED SEMANTIC LAYER")
    print("==================================================")
    adapter = Neo4jGraphAdapter()
    metadata = adapter.export_semantic_layer("neo4j/unified_semantic_layer_neo4j_northwind.json")
    print(f"[OK] Database ID: {metadata.database_id}")
    print(f"[OK] Database Type: {metadata.database_type} ({metadata.dialect})")
    print(f"[OK] Extracted {len(metadata.entities)} Node Labels and {len(metadata.relationships)} Graph Relationships.")
    print("[OK] Saved Unified Semantic Layer to 'neo4j/unified_semantic_layer_neo4j_northwind.json'\n")


def test_bigquery_semantic_layer():
    print("==================================================")
    print("2. EXTRACTING BIGQUERY UNIFIED SEMANTIC LAYER")
    print("==================================================")
    adapter = BigQuerySQLAdapter()
    metadata = adapter.export_semantic_layer("bigquery/unified_semantic_layer_bq_thelook.json")
    print(f"[OK] Database ID: {metadata.database_id}")
    print(f"[OK] Database Type: {metadata.database_type} ({metadata.dialect})")
    print(f"[OK] Extracted {len(metadata.entities)} Tables and {len(metadata.relationships)} Foreign Key Relationships.")
    print("[OK] Saved Unified Semantic Layer to 'bigquery/unified_semantic_layer_bq_thelook.json'\n")


if __name__ == "__main__":
    print("Starting Unified Semantic Layer Extraction...\n")
    test_neo4j_semantic_layer()
    test_bigquery_semantic_layer()
    print("ALL UNIFIED SEMANTIC LAYER EXTRACTIONS COMPLETED SUCCESSFULLY!")

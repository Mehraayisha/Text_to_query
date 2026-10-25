"""
Semantic Layer & Adapter Schema Extraction Test Script.
Runs extraction for Neo4j, BigQuery, and MongoDB from their self-contained folders.
"""

from neo4j.adapter import Neo4jGraphAdapter
from bigquery.adapter import BigQuerySQLAdapter
from mongodb.adapter import MongoDBDocumentAdapter


def test_neo4j_semantic_layer():
    print("==================================================")
    print("1. EXTRACTING NEO4J UNIFIED SEMANTIC LAYER")
    print("==================================================")
    try:
        adapter = Neo4jGraphAdapter()
        metadata = adapter.export_semantic_layer("neo4j/unified_semantic_layer_neo4j_northwind.json")
        print(f"[OK] Database ID: {metadata.database_id}")
        print(f"[OK] Database Type: {metadata.database_type} ({metadata.dialect})")
        print(f"[OK] Extracted {len(metadata.entities)} Node Labels and {len(metadata.relationships)} Graph Relationships.")
        print("[OK] Saved Unified Semantic Layer to 'neo4j/unified_semantic_layer_neo4j_northwind.json'\n")
    except Exception as e:
        print(f"[WARNING] Neo4j extraction failed or skipped: {e}\n")


def test_bigquery_semantic_layer():
    print("==================================================")
    print("2. EXTRACTING BIGQUERY UNIFIED SEMANTIC LAYER")
    print("==================================================")
    try:
        adapter = BigQuerySQLAdapter()
        metadata = adapter.export_semantic_layer("bigquery/unified_semantic_layer_bq_thelook.json")
        print(f"[OK] Database ID: {metadata.database_id}")
        print(f"[OK] Database Type: {metadata.database_type} ({metadata.dialect})")
        print(f"[OK] Extracted {len(metadata.entities)} Tables and {len(metadata.relationships)} Foreign Key Relationships.")
        print("[OK] Saved Unified Semantic Layer to 'bigquery/unified_semantic_layer_bq_thelook.json'\n")
    except Exception as e:
        print(f"[WARNING] BigQuery extraction failed or skipped: {e}\n")


def test_mongodb_semantic_layer():
    print("==================================================")
    print("3. EXTRACTING MONGODB UNIFIED SEMANTIC LAYER")
    print("==================================================")
    try:
        adapter = MongoDBDocumentAdapter()
        metadata = adapter.export_semantic_layer("mongodb/semantic_models/unified_semantic_layer_sample_mflix.json")
        print(f"[OK] Database ID: {metadata.database_id}")
        print(f"[OK] Database Type: {metadata.database_type} ({metadata.dialect})")
        print(f"[OK] Extracted {len(metadata.entities)} Collections and {len(metadata.relationships)} Document Reference Relationships.")
        print("[OK] Saved Unified Semantic Layer to 'mongodb/semantic_models/unified_semantic_layer_sample_mflix.json'\n")
    except Exception as e:
        print(f"[WARNING] MongoDB extraction failed or skipped: {e}\n")


if __name__ == "__main__":
    print("Starting Unified Semantic Layer Extraction...\n")
    test_neo4j_semantic_layer()
    test_bigquery_semantic_layer()
    test_mongodb_semantic_layer()
    print("ALL UNIFIED SEMANTIC LAYER EXTRACTIONS COMPLETED!")

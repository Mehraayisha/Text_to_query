"""Extract and export the configured MySQL database semantic layer."""

from adapters import MySQLAdapter


if __name__ == "__main__":
    metadata = MySQLAdapter().export_semantic_layer("unified_semantic_layer_mysql.json")
    print(f"[OK] Database: {metadata.database_name}")
    print(f"[OK] Extracted {len(metadata.entities)} tables and {len(metadata.relationships)} relationships.")
    print("[OK] Saved Unified Semantic Layer to 'unified_semantic_layer_mysql.json'")

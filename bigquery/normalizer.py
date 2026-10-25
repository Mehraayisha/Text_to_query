"""
BigQuery SQL Schema Normalizer for the Unified Semantic Layer.
Converts raw BigQuery schema into the standardized DatabaseMetadata model.
"""

from typing import Dict, Any, List
try:
    from .models import (
        DatabaseMetadata,
        EntitySchema,
        AttributeSchema,
        RelationshipSchema,
        DatabaseType,
        EntityType,
        Cardinality,
        map_raw_type_to_generic,
    )
except ImportError:
    from models import (
        DatabaseMetadata,
        EntitySchema,
        AttributeSchema,
        RelationshipSchema,
        DatabaseType,
        EntityType,
        Cardinality,
        map_raw_type_to_generic,
    )


def normalize_bigquery_schema(
    raw_schema: Dict[str, Any],
    database_id: str = "bq_thelook_ecommerce",
    database_name: str = "BigQuery (bigquery-public-data.thelook_ecommerce)",
    dialect: str = "bigquery"
) -> DatabaseMetadata:
    """Converts raw BigQuery JSON schema extract into unified DatabaseMetadata."""
    entities: Dict[str, EntitySchema] = {}
    relationships: List[RelationshipSchema] = []

    for table_key, table_info in raw_schema.items():
        table_name = table_info.get("table_name", table_key)
        columns = table_info.get("columns", [])
        
        attributes: List[AttributeSchema] = []
        primary_keys: List[str] = []

        for col in columns:
            col_name = col.get("column_name", "")
            raw_type = col.get("data_type", "STRING")
            desc = col.get("description", "")
            is_pk = col.get("is_primary_key", col_name.lower() == "id")
            is_fk = col.get("is_foreign_key", col_name.lower().endswith("_id") and col_name.lower() != "id")

            if is_pk:
                primary_keys.append(col_name)

            attr = AttributeSchema(
                name=col_name,
                data_type=raw_type,
                generic_type=map_raw_type_to_generic(raw_type),
                is_primary_key=is_pk,
                is_foreign_key=is_fk,
                description=desc,
                sample_values=[]
            )
            attributes.append(attr)

            # Auto-infer relationship from foreign key naming convention (e.g. order_id -> orders.id)
            if is_fk:
                ref_target = col_name.lower()[:-3] + "s"  # simple plural heuristic e.g. user_id -> users
                if ref_target in raw_schema or col_name.lower()[:-3] in raw_schema:
                    target_table = ref_target if ref_target in raw_schema else col_name.lower()[:-3]
                    rel = RelationshipSchema(
                        name=f"FK_{table_name}_{target_table}",
                        source_entity=table_name,
                        source_attribute=col_name,
                        target_entity=target_table,
                        target_attribute="id",
                        cardinality=Cardinality.MANY_TO_ONE.value,
                        description=f"{table_name}.{col_name} references {target_table}.id"
                    )
                    relationships.append(rel)

        entity = EntitySchema(
            name=table_name,
            entity_type=EntityType.TABLE.value,
            description=f"Table {table_name}",
            attributes=attributes,
            primary_keys=primary_keys
        )
        entities[table_name] = entity

    return DatabaseMetadata(
        database_id=database_id,
        database_name=database_name,
        database_type=DatabaseType.SQL.value,
        dialect=dialect,
        entities=entities,
        relationships=relationships
    )


# Alias
normalize_sql_schema = normalize_bigquery_schema

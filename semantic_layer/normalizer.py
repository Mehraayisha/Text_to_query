"""
Schema Normalizers for the Unified Semantic Layer.
Converts raw JSON schema outputs from SQL, Neo4j, MongoDB, etc. into DatabaseMetadata objects.
"""

from typing import Dict, Any, List
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


def normalize_sql_schema(
    raw_schema: Dict[str, Any],
    database_id: str = "sql_database",
    database_name: str = "SQL Database",
    dialect: str = "postgres"
) -> DatabaseMetadata:
    """Converts raw SQL JSON schema extract into unified DatabaseMetadata."""
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


def normalize_neo4j_schema(
    raw_schema: Dict[str, Any],
    database_id: str = "neo4j_northwind",
    database_name: str = "Neo4j Northwind Graph",
    dialect: str = "neo4j_cypher"
) -> DatabaseMetadata:
    """Converts raw Neo4j JSON schema extract into unified DatabaseMetadata."""
    entities: Dict[str, EntitySchema] = {}
    relationships: List[RelationshipSchema] = []

    nodes_data = raw_schema.get("nodes", {})
    rels_data = raw_schema.get("relationships", [])

    for node_label, node_info in nodes_data.items():
        props = node_info.get("properties", [])
        attributes: List[AttributeSchema] = []
        primary_keys: List[str] = []

        for prop in props:
            p_name = prop.get("property_name", "")
            raw_type = prop.get("data_type", "String")
            is_pk = p_name.lower().endswith("id")

            if is_pk and not primary_keys:
                primary_keys.append(p_name)

            attr = AttributeSchema(
                name=p_name,
                data_type=raw_type,
                generic_type=map_raw_type_to_generic(raw_type),
                is_primary_key=is_pk,
                is_foreign_key=False,
                description="",
                sample_values=[]
            )
            attributes.append(attr)

        entity = EntitySchema(
            name=node_label,
            entity_type=EntityType.NODE_LABEL.value,
            description=f"Graph Node Label: {node_label}",
            attributes=attributes,
            primary_keys=primary_keys
        )
        entities[node_label] = entity

    if isinstance(rels_data, dict):
        for rel_type, rel_info in rels_data.items():
            connections = rel_info.get("connections", [])
            for conn in connections:
                source_node = conn.get("source", "")
                target_node = conn.get("target", "")
                rel = RelationshipSchema(
                    name=rel_type,
                    source_entity=source_node,
                    source_attribute="",
                    target_entity=target_node,
                    target_attribute="",
                    cardinality=Cardinality.MANY_TO_ONE.value,
                    description=f"Graph Edge: (:{source_node})-[:{rel_type}]->(:{target_node})"
                )
                relationships.append(rel)
    elif isinstance(rels_data, list):
        for rel_item in rels_data:
            source_node = rel_item.get("source_node", rel_item.get("source", ""))
            rel_type = rel_item.get("relationship_type", rel_item.get("type", ""))
            target_node = rel_item.get("target_node", rel_item.get("target", ""))

            rel = RelationshipSchema(
                name=rel_type,
                source_entity=source_node,
                source_attribute="",
                target_entity=target_node,
                target_attribute="",
                cardinality=Cardinality.MANY_TO_ONE.value,
                description=f"Graph Edge: (:{source_node})-[:{rel_type}]->(:{target_node})"
            )
            relationships.append(rel)

    return DatabaseMetadata(
        database_id=database_id,
        database_name=database_name,
        database_type=DatabaseType.GRAPH.value,
        dialect=dialect,
        entities=entities,
        relationships=relationships
    )

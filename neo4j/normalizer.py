"""
Neo4j Graph Schema Normalizer for the Unified Semantic Layer.
Converts raw Neo4j node/edge schema into the standardized DatabaseMetadata model.
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
            raw_props = rel_info.get("properties", [])
            rel_attributes = [
                AttributeSchema(
                    name=p.get("property_name", ""),
                    data_type=p.get("data_type", "String"),
                    generic_type=map_raw_type_to_generic(p.get("data_type", "String")),
                )
                for p in raw_props
            ]
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
                    description=f"Graph Edge: (:{source_node})-[:{rel_type}]->(:{target_node})",
                    properties=rel_attributes
                )
                relationships.append(rel)
    elif isinstance(rels_data, list):
        for rel_item in rels_data:
            source_node = rel_item.get("source_node", rel_item.get("source", ""))
            rel_type = rel_item.get("relationship_type", rel_item.get("type", ""))
            target_node = rel_item.get("target_node", rel_item.get("target", ""))
            raw_props = rel_item.get("properties", [])
            rel_attributes = [
                AttributeSchema(
                    name=p.get("property_name", ""),
                    data_type=p.get("data_type", "String"),
                    generic_type=map_raw_type_to_generic(p.get("data_type", "String")),
                )
                for p in raw_props
            ]

            rel = RelationshipSchema(
                name=rel_type,
                source_entity=source_node,
                source_attribute="",
                target_entity=target_node,
                target_attribute="",
                cardinality=Cardinality.MANY_TO_ONE.value,
                description=f"Graph Edge: (:{source_node})-[:{rel_type}]->(:{target_node})",
                properties=rel_attributes
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

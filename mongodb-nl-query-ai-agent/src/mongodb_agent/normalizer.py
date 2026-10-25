"""
MongoDB Document Schema Normalizer for the Unified Semantic Layer inside mongodb_agent.
Converts MongoDB collections analysis and detected relationships into the standardized DatabaseMetadata model.
Conforms to SEMANTIC_LAYER_SPEC.md.
"""

from typing import Dict, Any, List
from mongodb_agent.models import (
    DatabaseMetadata,
    EntitySchema,
    AttributeSchema,
    RelationshipSchema,
    DatabaseType,
    EntityType,
    Cardinality,
    map_raw_type_to_generic,
)


def normalize_mongodb_schema(
    collections_analysis: Dict[str, Dict[str, Any]],
    relationships_data: List[Dict[str, Any]],
    database_id: str = "mongodb_database",
    database_name: str = "MongoDB Database",
    dialect: str = "mongodb",
) -> DatabaseMetadata:
    """
    Normalizes MongoDB schema analysis and relationships into Unified DatabaseMetadata.

    Args:
        collections_analysis: Dict of collection name to collection analysis dict (fields, descriptions, etc.)
        relationships_data: List of detected relationships (from, to, description, etc.)
        database_id: Unique database identifier
        database_name: Human readable database name
        dialect: Query dialect identifier ('mongodb')

    Returns:
        DatabaseMetadata instance conforming to SEMANTIC_LAYER_SPEC.md.
    """
    entities: Dict[str, EntitySchema] = {}
    relationships: List[RelationshipSchema] = []

    # Map of foreign key source paths for fast lookup: "collection.field"
    fk_sources = set()
    for rel in relationships_data:
        from_path = rel.get("from", "")
        if from_path:
            fk_sources.add(from_path)

    for coll_name, coll_info in collections_analysis.items():
        attributes: List[AttributeSchema] = []
        primary_keys: List[str] = ["_id"]

        fields_dict = coll_info.get("fields", {})
        for field_name, field_info in fields_dict.items():
            raw_type = field_info.get("data_type", "string")
            is_pk = (field_name == "_id")
            full_field_path = f"{coll_name}.{field_name}"
            is_fk = full_field_path in fk_sources

            # Extract sample values safely
            raw_samples = field_info.get("sample_values", [])
            sample_values = list(raw_samples) if isinstance(raw_samples, (list, tuple, set)) else [raw_samples]

            attr = AttributeSchema(
                name=field_name,
                data_type=str(raw_type),
                generic_type=map_raw_type_to_generic(raw_type),
                is_primary_key=is_pk,
                is_foreign_key=is_fk,
                description=field_info.get("description", f"{field_name} attribute in {coll_name}"),
                sample_values=sample_values[:5],
            )
            attributes.append(attr)

        entity = EntitySchema(
            name=coll_name,
            entity_type=EntityType.COLLECTION.value,
            description=coll_info.get("description", f"MongoDB Collection: {coll_name}"),
            attributes=attributes,
            primary_keys=primary_keys,
        )
        entities[coll_name] = entity

    # Normalize relationships
    for rel in relationships_data:
        from_str = rel.get("from", "")
        to_str = rel.get("to", "")

        if "." in from_str and "." in to_str:
            src_coll, src_attr = from_str.split(".", 1)
            target_coll, target_attr = to_str.split(".", 1)
        else:
            src_coll = rel.get("source_entity", "")
            src_attr = rel.get("source_attribute", "")
            target_coll = rel.get("target_entity", "")
            target_attr = rel.get("target_attribute", "")

        rel_name = rel.get("name") or f"REF_{src_coll}_{target_coll}"
        cardinality = rel.get("cardinality", Cardinality.MANY_TO_ONE.value)
        desc = rel.get("description") or f"Reference: {src_coll}.{src_attr} references {target_coll}.{target_attr}"

        relationships.append(
            RelationshipSchema(
                name=rel_name,
                source_entity=src_coll,
                source_attribute=src_attr,
                target_entity=target_coll,
                target_attribute=target_attr,
                cardinality=cardinality,
                description=desc,
            )
        )

    return DatabaseMetadata(
        database_id=database_id,
        database_name=database_name,
        database_type=DatabaseType.DOCUMENT.value,
        dialect=dialect,
        entities=entities,
        relationships=relationships,
    )


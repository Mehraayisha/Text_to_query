"""MySQL schema normalizer using the repository's shared semantic models."""

from typing import Any, Dict, List

from bigquery.models import (
    AttributeSchema,
    Cardinality,
    DatabaseMetadata,
    DatabaseType,
    EntitySchema,
    EntityType,
    RelationshipSchema,
    map_raw_type_to_generic,
)


def normalize_mysql_schema(
    raw_schema: Dict[str, Any],
    database_id: str,
    database_name: str,
    dialect: str = "mysql",
) -> DatabaseMetadata:
    entities: Dict[str, EntitySchema] = {}
    relationships: List[RelationshipSchema] = []

    for table_key, table_info in raw_schema.items():
        table_name = table_info.get("table_name", table_key)
        attributes: List[AttributeSchema] = []
        primary_keys: List[str] = []

        for column in table_info.get("columns", []):
            name = column.get("column_name", "")
            data_type = column.get("data_type", "STRING")
            is_primary_key = bool(column.get("is_primary_key", False))
            if is_primary_key:
                primary_keys.append(name)

            attributes.append(
                AttributeSchema(
                    name=name,
                    data_type=data_type,
                    generic_type=map_raw_type_to_generic(data_type),
                    is_primary_key=is_primary_key,
                    is_foreign_key=bool(column.get("is_foreign_key", False)),
                    description=column.get("description", ""),
                    sample_values=[],
                )
            )

            target_table = column.get("referenced_table")
            target_column = column.get("referenced_column")
            if target_table and target_column:
                relationships.append(
                    RelationshipSchema(
                        name=f"FK_{table_name}_{target_table}_{name}",
                        source_entity=table_name,
                        source_attribute=name,
                        target_entity=target_table,
                        target_attribute=target_column,
                        cardinality=Cardinality.MANY_TO_ONE.value,
                        description=(
                            f"{table_name}.{name} references "
                            f"{target_table}.{target_column}"
                        ),
                    )
                )

        entities[table_name] = EntitySchema(
            name=table_name,
            entity_type=EntityType.TABLE.value,
            description=f"Table {table_name}",
            attributes=attributes,
            primary_keys=primary_keys,
        )

    return DatabaseMetadata(
        database_id=database_id,
        database_name=database_name,
        database_type=DatabaseType.SQL.value,
        dialect=dialect,
        entities=entities,
        relationships=relationships,
    )

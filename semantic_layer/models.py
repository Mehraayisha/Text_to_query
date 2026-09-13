"""
Core Pydantic / Dataclass Models for the Unified Semantic Layer.
Standardizes metadata representations across SQL, Graph, Document, Vector, Time-Series, Key-Value, Object, and API sources.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Dict, Optional, Any
import json


class DatabaseType(str, Enum):
    SQL = "sql"
    GRAPH = "graph"
    DOCUMENT = "document"
    VECTOR = "vector"
    TIMESERIES = "timeseries"
    KEY_VALUE = "key_value"
    OBJECT = "object"
    API = "api"


class EntityType(str, Enum):
    TABLE = "table"
    NODE_LABEL = "node_label"
    COLLECTION = "collection"
    VECTOR_PAYLOAD = "vector_payload"
    TIMESERIES_MEASUREMENT = "timeseries_measurement"
    BUCKET = "bucket"
    DATASET = "dataset"


class Cardinality(str, Enum):
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"
    UNKNOWN = "UNKNOWN"


class GenericDataType(str, Enum):
    STRING = "STRING"
    NUMBER = "NUMBER"
    BOOLEAN = "BOOLEAN"
    DATETIME = "DATETIME"
    GEOMETRY = "GEOMETRY"
    ARRAY = "ARRAY"
    OBJECT = "OBJECT"
    UNKNOWN = "UNKNOWN"


def map_raw_type_to_generic(raw_type: str) -> str:
    """Maps raw source database data types to unified generic types."""
    t = str(raw_type).upper()
    if any(k in t for k in ["INT", "FLOAT", "DOUBLE", "LONG", "NUMBER", "DECIMAL", "NUMERIC"]):
        return GenericDataType.NUMBER.value
    if any(k in t for k in ["CHAR", "TEXT", "STRING", "VARCHAR"]):
        return GenericDataType.STRING.value
    if "BOOL" in t:
        return GenericDataType.BOOLEAN.value
    if any(k in t for k in ["DATE", "TIME", "TIMESTAMP"]):
        return GenericDataType.DATETIME.value
    if any(k in t for k in ["ARRAY", "LIST"]):
        return GenericDataType.ARRAY.value
    if any(k in t for k in ["GEOG", "GEOM", "POINT", "POLYGON"]):
        return GenericDataType.GEOMETRY.value
    if any(k in t for k in ["MAP", "STRUCT", "JSON", "OBJECT", "DICT"]):
        return GenericDataType.OBJECT.value
    return GenericDataType.STRING.value


@dataclass
class AttributeSchema:
    name: str
    data_type: str
    generic_type: str = GenericDataType.STRING.value
    is_primary_key: bool = False
    is_foreign_key: bool = False
    description: str = ""
    sample_values: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AttributeSchema":
        return cls(
            name=d.get("name", ""),
            data_type=d.get("data_type", "STRING"),
            generic_type=d.get("generic_type", map_raw_type_to_generic(d.get("data_type", "STRING"))),
            is_primary_key=d.get("is_primary_key", False),
            is_foreign_key=d.get("is_foreign_key", False),
            description=d.get("description", ""),
            sample_values=d.get("sample_values", []),
        )


@dataclass
class EntitySchema:
    name: str
    entity_type: str = EntityType.TABLE.value
    description: str = ""
    attributes: List[AttributeSchema] = field(default_factory=list)
    primary_keys: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "attributes": [attr.to_dict() for attr in self.attributes],
            "primary_keys": self.primary_keys,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EntitySchema":
        return cls(
            name=d.get("name", ""),
            entity_type=d.get("entity_type", EntityType.TABLE.value),
            description=d.get("description", ""),
            attributes=[AttributeSchema.from_dict(a) for a in d.get("attributes", [])],
            primary_keys=d.get("primary_keys", []),
        )


@dataclass
class RelationshipSchema:
    name: str
    source_entity: str
    source_attribute: str
    target_entity: str
    target_attribute: str
    cardinality: str = Cardinality.MANY_TO_ONE.value
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RelationshipSchema":
        return cls(
            name=d.get("name", ""),
            source_entity=d.get("source_entity", ""),
            source_attribute=d.get("source_attribute", ""),
            target_entity=d.get("target_entity", ""),
            target_attribute=d.get("target_attribute", ""),
            cardinality=d.get("cardinality", Cardinality.MANY_TO_ONE.value),
            description=d.get("description", ""),
        )


@dataclass
class DatabaseMetadata:
    database_id: str
    database_name: str
    database_type: str  # from DatabaseType enum value
    dialect: str
    entities: Dict[str, EntitySchema] = field(default_factory=dict)
    relationships: List[RelationshipSchema] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "database_id": self.database_id,
            "database_name": self.database_name,
            "database_type": self.database_type,
            "dialect": self.dialect,
            "entities": {name: entity.to_dict() for name, entity in self.entities.items()},
            "relationships": [rel.to_dict() for rel in self.relationships],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DatabaseMetadata":
        entities = {
            name: EntitySchema.from_dict(e_data)
            for name, e_data in d.get("entities", {}).items()
        }
        relationships = [
            RelationshipSchema.from_dict(r_data)
            for r_data in d.get("relationships", [])
        ]
        return cls(
            database_id=d.get("database_id", ""),
            database_name=d.get("database_name", ""),
            database_type=d.get("database_type", DatabaseType.SQL.value),
            dialect=d.get("dialect", "sql"),
            entities=entities,
            relationships=relationships,
        )

    @classmethod
    def from_json(cls, json_str: str) -> "DatabaseMetadata":
        return cls.from_dict(json.loads(json_str))

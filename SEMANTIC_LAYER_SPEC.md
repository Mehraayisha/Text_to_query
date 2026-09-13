# Unified Semantic Layer Specification

This document defines the standardized JSON schema and conventions for the **Unified Semantic Layer** across all database paradigms supported by the natural language query platform.

Whether connecting an **SQL** database (PostgreSQL, BigQuery, MySQL), a **Graph** database (Neo4j), a **Document** store (MongoDB), a **Vector** index (Qdrant), or a **Time-Series** store (InfluxDB), the metadata must normalize into this standard structure.

---

## 1. Top-Level Schema

```json
{
  "database_id": "string",
  "database_name": "string",
  "database_type": "string",
  "dialect": "string",
  "entities": {
    "<entity_name>": { ... }
  },
  "relationships": [
    { ... }
  ]
}
```

### Top-Level Fields

| Field | Type | Description | Examples |
|---|---|---|---|
| `database_id` | `string` | Unique internal machine-readable ID for the data source. | `"bq_thelook_ecommerce"`, `"neo4j_northwind"`, `"mongo_analytics"`, `"postgres_prod"` |
| `database_name` | `string` | Human-readable name including project/schema/dataset scope. | `"BigQuery (bigquery-public-data.thelook_ecommerce)"`, `"Neo4j (northwind)"`, `"PostgreSQL (ecommerce_public)"` |
| `database_type` | `string` | High-level database category (enum value). | `"sql"`, `"graph"`, `"document"`, `"vector"`, `"timeseries"`, `"key_value"`, `"object"`, `"api"` |
| `dialect` | `string` | Query dialect or engine identifier for query generation. | `"bigquery"`, `"postgres"`, `"mysql"`, `"snowflake"`, `"neo4j_cypher"`, `"mongodb"`, `"qdrant_rest"`, `"influxql"`, `"dynamodb_partiql"` |
| `entities` | `object` | Map of entity names to their entity definitions (`EntitySchema`). | `{ "users": { ... }, "orders": { ... } }` |
| `relationships` | `array` | List of semantic links/relationships between entities (`RelationshipSchema`). | `[ { "name": "FK_order_items_orders", ... } ]` |

---

## 2. Entity Schema (`entities.<entity_name>`)

Each entry in `entities` represents a logical table, node label, collection, bucket, or measurement.

```json
{
  "name": "users",
  "entity_type": "table",
  "description": "Table users",
  "attributes": [
    {
      "name": "id",
      "data_type": "INT64",
      "generic_type": "NUMBER",
      "is_primary_key": true,
      "is_foreign_key": false,
      "description": "Unique identifier for user",
      "sample_values": []
    }
  ],
  "primary_keys": [
    "id"
  ]
}
```

### Entity Fields

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Exact entity name in the database (e.g. table name, node label, collection name). |
| `entity_type` | `string` | The structural kind of entity. Must be one of: <br>• `"table"` (SQL)<br>• `"node_label"` (Graph/Neo4j)<br>• `"collection"` (Document/MongoDB)<br>• `"vector_payload"` (Vector/Qdrant)<br>• `"timeseries_measurement"` (Time-Series/InfluxDB)<br>• `"bucket"` (Object storage/S3)<br>• `"dataset"` (API / HF datasets) |
| `description` | `string` | Business context or documentation for the entity. |
| `attributes` | `array` | List of attributes/columns/properties within this entity. |
| `primary_keys` | `array[string]` | List of attribute names that uniquely identify records or nodes in this entity. |

---

## 3. Attribute Schema (`attributes[]`)

Each item in `attributes` represents a column, document field, or graph node property.

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Column, property, or field name (e.g. `order_id`, `productName`, `unitPrice`). |
| `data_type` | `string` | Native database data type (e.g. `INT64`, `TIMESTAMP`, `VARCHAR(255)`, `Double`, `String`, `ObjectId`, `BOOLEAN`). |
| `generic_type` | `string` | Unified cross-database type. One of: <br>• `"STRING"`<br>• `"NUMBER"`<br>• `"BOOLEAN"`<br>• `"DATETIME"`<br>• `"GEOMETRY"`<br>• `"ARRAY"`<br>• `"OBJECT"`<br>• `"UNKNOWN"` |
| `is_primary_key` | `boolean` | `true` if this attribute is (or acts as) a primary key / unique identifier. |
| `is_foreign_key` | `boolean` | `true` if this attribute references another entity's primary key (SQL/Document). |
| `description` | `string` | Semantic meaning, units of measure, or comments for this field. |
| `sample_values` | `array` | Optional preview values to guide LLM prompt generation (e.g. `["Shipped", "Cancelled"]`). |

---

## 4. Relationship Schema (`relationships[]`)

Represents joins, graph edges, or parent-child references.

```json
{
  "name": "FK_order_items_orders",
  "source_entity": "order_items",
  "source_attribute": "order_id",
  "target_entity": "orders",
  "target_attribute": "id",
  "cardinality": "MANY_TO_ONE",
  "description": "order_items.order_id references orders.id"
}
```

### Relationship Fields

| Field | Type | Description |
|---|---|---|
| `name` | `string` | Identifier for the link. In SQL: `FK_<source>_<target>`. In Graph: edge type name e.g. `PART_OF`, `PURCHASED`. |
| `source_entity` | `string` | Originating entity name (e.g. `order_items`, `Product`). |
| `source_attribute` | `string` | Foreign key attribute in source entity. (*Leave as empty string `""` for Graph relationships where nodes connect directly via edges*). |
| `target_entity` | `string` | Destination entity name (e.g. `orders`, `Category`). |
| `target_attribute` | `string` | Referenced primary key attribute in target entity. (*Leave as empty string `""` for Graph relationships*). |
| `cardinality` | `string` | Multiplicity of the link. Must be one of: <br>• `"ONE_TO_ONE"`<br>• `"ONE_TO_MANY"`<br>• `"MANY_TO_ONE"`<br>• `"MANY_TO_MANY"`<br>• `"UNKNOWN"` |
| `description` | `string` | Clear human-readable relationship description for LLMs (e.g. `"Graph Edge: (:Product)-[:PART_OF]->(:Category)"` or `"orders.user_id references users.id"`). |

---

## 5. Comparison: SQL vs. Graph vs. Document

| Feature | Relational SQL (BigQuery / Postgres) | Graph (Neo4j) | Document (MongoDB) |
|---|---|---|---|
| **`database_type`** | `"sql"` | `"graph"` | `"document"` |
| **`dialect`** | `"bigquery"` / `"postgres"` / `"mysql"` | `"neo4j_cypher"` | `"mongodb"` |
| **`entity_type`** | `"table"` | `"node_label"` | `"collection"` |
| **`primary_keys`** | Table primary key (e.g. `["id"]`) | Node key or ID prop (e.g. `["productID"]`) | `["_id"]` |
| **`source_attribute`** | Foreign key column (e.g. `"user_id"`) | `""` (direct edge) | Referenced field (e.g. `"customer_id"`) |
| **`target_attribute`** | Referenced PK (e.g. `"id"`) | `""` (direct edge) | Target PK (e.g. `"_id"`) |
| **Relationship Name** | `"FK_orders_users"` | `"PURCHASED"` | `"REF_orders_customers"` |

---

## 6. How to Validate in Python

You can validate any generated semantic layer JSON file using the built-in models:

```python
from semantic_layer import DatabaseMetadata

# Load and validate
with open("your_semantic_layer.json", "r", encoding="utf-8") as f:
    json_data = f.read()

# Automatically parses and validates against dataclass schemas
metadata = DatabaseMetadata.from_json(json_data)

print(f"Loaded database: {metadata.database_name} ({metadata.database_type})")
print(f"Entities: {len(metadata.entities)}, Relationships: {len(metadata.relationships)}")
```

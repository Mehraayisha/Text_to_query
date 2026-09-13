# Text_to_query: Unified LLM-Based Natural Language Query Platform for Heterogeneous Databases

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Database Support](https://img.shields.io/badge/databases-SQL%20%7C%20Graph%20%7C%20Document-orange.svg)](#supported-database-adapters)

> A unified, paradigm-agnostic platform enabling users to query heterogeneous databases (Relational, Graph, Document, Vector, etc.) using natural language by leveraging a **Unified Semantic Layer** and intelligent, context-optimized metadata retrieval.

---

## 📌 Problem Statement & Motivation

Modern organizations store data across a disparate array of database technologies—ranging from relational warehouses (BigQuery, PostgreSQL) and graph databases (Neo4j) to document stores (MongoDB) and vector stores (Qdrant).

* **Steep Learning Curve:** Each data source requires specialized query languages (SQL dialects, Cypher, MQL, API calls).
* **LLM Context Window Overload:** Supplying an entire database schema directly to an LLM wastes significant token budgets, increases latency, and leads to hallucinations.
* **Lack of Standardization:** Different database engines represent relationships, schemas, and data types with distinct paradigms.

**Text_to_query** solves this by:
1. Automatically extracting and normalizing database metadata into a standardized **Unified Semantic Layer**.
2. Selectively retrieving only the metadata relevant to the user's natural language question, drastically reducing token usage and improving translation accuracy.
3. Routing query generation through dedicated **Database Adapters**.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    User([User Natural Language Query]) --> Retrieval[Selective Metadata Retrieval]
    Retrieval --> Semantic[Unified Semantic Layer]
    Semantic --> LLM[LLM Query Generator]
    LLM --> Router{Adapter Query Router}
    
    Router -->|SQL Dialect| SQLAdapter[SQL Adapter\n(BigQuery, PostgreSQL, etc.)]
    Router -->|Cypher| GraphAdapter[Graph Adapter\n(Neo4j)]
    Router -->|MQL| DocAdapter[Document Adapter\n(MongoDB)]
    Router -->|API / Similarity| OtherAdapter[Vector / TimeSeries Adapters]
    
    SQLAdapter --> DB1[(Relational DB / Warehouse)]
    GraphAdapter --> DB2[(Graph DB)]
    DocAdapter --> DB3[(Document Store)]
    OtherAdapter --> DB4[(Vector / Time-Series DB)]
    
    DB1 --> ResultAgg[Result Formatter]
    DB2 --> ResultAgg
    DB3 --> ResultAgg
    DB4 --> ResultAgg
    ResultAgg --> FinalOutput([User-Friendly Response])
```

---

## 🧩 Supported Database Adapters

| Adapter Type | Engine / Source | Query Language | Current Status |
|---|---|---|---|
| **SQL Adapter** | Google Cloud BigQuery | BigQuery SQL | ✅ Supported |
| **SQL Adapter** | PostgreSQL, MySQL, SQL Server | Standard SQL | 🔄 Extensible via BaseAdapter |
| **Graph Adapter** | Neo4j | Cypher | ✅ Supported |
| **Document Adapter** | MongoDB | MQL / Aggregation Pipelines | 📋 Planned |
| **Vector Adapter** | Qdrant | Vector Similarity Search | 📋 Planned |
| **Time-Series Adapter** | InfluxDB | InfluxQL / Flux | 📋 Planned |

---

## 📂 Project Structure

```plaintext
Text_to_query/
├── .env.example                               # Template for database credentials
├── .gitignore                                 # Git ignore configuration (ignores secrets & caches)
├── requirements.txt                           # Python package dependencies
├── project_context.md                         # Detailed project domain, motivation, and architecture
├── SEMANTIC_LAYER_SPEC.md                     # Formal Unified Semantic Layer JSON schema specification
├── unified_semantic_layer_template.json       # Minimal starter template for semantic layer definition
│
├── adapters/                                  # Database adapter layer
│   ├── __init__.py                            # Package exports
│   ├── base_adapter.py                        # Abstract base adapter class
│   ├── sql_adapter.py                         # BigQuery and relational SQL adapter
│   └── neo4j_adapter.py                       # Neo4j graph database adapter
│
├── semantic_layer/                            # Semantic schema models & normalizers
│   ├── __init__.py                            # Package exports
│   ├── models.py                              # Dataclass models (Entity, Attribute, Relationship, DatabaseMetadata)
│   └── normalizer.py                          # Schema normalizers converting raw schemas to semantic JSON
│
├── bq_schema_extract.py                       # Direct BigQuery INFORMATION_SCHEMA extractor
├── neo4j_schema_extract.py                    # Direct Neo4j APOC / cypher schema extractor
├── main.py                                    # Execution & test entry point for adapters & semantic layer
│
├── unified_semantic_layer_bq_thelook.json     # Sample extracted semantic layer: BigQuery (thelook_ecommerce)
└── unified_semantic_layer_neo4j_northwind.json# Sample extracted semantic layer: Neo4j (Northwind graph)
```

---

## 🧠 The Unified Semantic Layer

The platform normalizes any data source into a unified JSON format defined in [`SEMANTIC_LAYER_SPEC.md`](SEMANTIC_LAYER_SPEC.md).

### Key Components:
- **`database_id` & `database_type`:** Identifies the target engine (`sql`, `graph`, `document`, etc.) and dialect.
- **`entities`:** Represents collections, tables, node labels, or buckets with standard attributes and generic types (`STRING`, `NUMBER`, `DATETIME`, `BOOLEAN`, etc.).
- **`relationships`:** Standardizes foreign keys, graph edges/relationships, and document references into a unified model (`source_entity`, `target_entity`, `type`).

```json
{
  "database_id": "bq_thelook_ecommerce",
  "database_type": "sql",
  "dialect": "bigquery",
  "entities": {
    "orders": {
      "name": "orders",
      "entity_type": "table",
      "attributes": [
        {
          "name": "order_id",
          "data_type": "INT64",
          "generic_type": "NUMBER",
          "is_primary_key": true
        }
      ]
    }
  },
  "relationships": [
    {
      "name": "FK_orders_users",
      "source_entity": "orders",
      "target_entity": "users",
      "relationship_type": "MANY_TO_ONE",
      "join_keys": [
        { "source_attribute": "user_id", "target_attribute": "id" }
      ]
    }
  ]
}
```

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/Mehraayisha/Text_to_query.git
cd Text_to_query
```

### 2. Set Up a Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the example `.env` template:
```bash
cp .env.example .env
```

Edit `.env` to supply credentials for your data sources:

```ini
# Neo4j Graph Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password_here

# Google Cloud BigQuery
GOOGLE_APPLICATION_CREDENTIALS=jsonkeybq.json
BIGQUERY_PROJECT_ID=your-gcp-project-id
BIGQUERY_DATASET=your_dataset
```

> ⚠️ **Security Notice:** Never commit `.env` or Google Cloud credential keys (`jsonkeybq.json`) to version control. Both are protected in `.gitignore`.

---

## 🧪 Running Schema Extraction & Tests

To test the adapters and extract the unified semantic layer from configured databases:

```bash
python main.py
```

This will:
1. Connect to **Neo4j**, inspect node labels, properties, and relationship types, and output `unified_semantic_layer_neo4j_northwind.json`.
2. Connect to **Google BigQuery**, query `INFORMATION_SCHEMA` for tables, columns, and foreign keys, and output `unified_semantic_layer_bq_thelook.json`.

---

## 🔮 Roadmap

- [x] Base adapter architecture & abstract interface
- [x] Unified Semantic Layer JSON schema specification & Dataclass models
- [x] Google BigQuery SQL adapter & schema normalizer
- [x] Neo4j Graph adapter & schema normalizer
- [ ] Selective Metadata Retrieval module (RAG / semantic search over semantic layer)
- [ ] LLM Prompt Engine & Multi-dialectic query generation
- [ ] MongoDB document adapter implementation
- [ ] Qdrant vector adapter implementation
- [ ] Interactive Web UI / Chat interface

---

## 📄 License

Distributed under the MIT License.

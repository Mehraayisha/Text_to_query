# Text_to_query: Unified LLM-Based Natural Language Query Platform for Heterogeneous Databases

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Database Support](https://img.shields.io/badge/databases-SQL%20%7C%20Graph%20%7C%20Document-orange.svg)](#-supported-database-adapters)
[![LLM Support](https://img.shields.io/badge/LLM-Ollama%20%2F%20Llama%203.1-purple.svg)](https://ollama.ai)

> A unified, paradigm-agnostic platform enabling users to query heterogeneous databases (Relational Warehouses, Graph Databases, Document Stores, Vector Databases) using natural language by leveraging a **Unified Semantic Layer** and intelligent, context-optimized LLM query generation.

---

## 📌 Problem Statement & Motivation

Modern enterprise data architectures span across disparate database engines—from analytical cloud data warehouses (Google Cloud BigQuery, Snowflake, PostgreSQL) and graph stores (Neo4j) to document stores (MongoDB) and vector databases (Qdrant).

* **Steep Learning Curve:** Each data store demands specialized query syntax (SQL dialects, Cypher, MQL, vector similarity filters).
* **LLM Context Window Overload:** Dumping raw schemas into an LLM wastes token budgets, slows response times, and increases hallucinations.
* **Lack of Paradigm Standardization:** Different database engines model entities, relationships, attributes, and data types with conflicting conventions.

**Text_to_query** solves this by:
1. **Unified Semantic Layer:** Standardizing relational tables, graph nodes/edges, and document collections into a common schema representation.
2. **Selective Context Injection:** Feeding the LLM only the necessary entities, relationships, and domain-specific business rules.
3. **Interactive Text-to-Query Engines:** Translating natural language directly into target dialects (BigQuery Standard SQL, Neo4j Cypher) using local LLMs (Ollama / Llama 3.1) and executing them live with tabular visualization.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    User([User Natural Language Query]) --> PreProcess[Query Intent & Schema Resolution]
    PreProcess --> Semantic[Unified Semantic Layer Context\n(Entities, Relationships, Rules)]
    Semantic --> PromptEngine[Few-Shot Prompt Engine]
    PromptEngine --> LLM[Local Ollama LLM\ne.g., llama3.1]
    
    LLM --> Router{Dialect Router}
    
    Router -->|BigQuery SQL| BQRunner[BigQuery Text2SQL Engine]
    Router -->|Cypher| Neo4jRunner[Neo4j Text2Cypher Engine]
    Router -->|MQL| DocRunner[Document Engine / Planned]
    
    BQRunner --> BigQuery[(Google Cloud BigQuery)]
    Neo4jRunner --> Neo4jDB[(Neo4j Graph Database)]
    
    BigQuery --> TabularResults[Tabular Formatter & Metrics]
    Neo4jDB --> TabularResults
    
    TabularResults --> Output([Interactive Terminal UI])
```

---

## 🧩 Supported Database Adapters & Dialects

| Adapter / Engine | Target Database | Generated Dialect | Schema Extractor | Interactive Text-to-Query |
|---|---|---|---|---|
| **BigQuery Adapter** | Google Cloud BigQuery | BigQuery Standard SQL | ✅ Supported (`INFORMATION_SCHEMA`) | ✅ Supported (`text2sql.py`) |
| **Neo4j Adapter** | Neo4j Graph Database | Neo4j Cypher | ✅ Supported (APOC & Graph Meta) | ✅ Supported (`text2cypher.py`) |
| **SQL Adapter** | PostgreSQL, MySQL, Snowflake | Standard ANSI SQL | 🔄 Extensible via `BaseAdapter` | 📋 In Progress |
| **Document Adapter** | MongoDB, Amazon DynamoDB | MQL / Aggregations | 📋 Planned | 📋 Planned |
| **Vector Adapter** | Qdrant | Vector Similarity Search | 📋 Planned | 📋 Planned |

---

## 📂 Project Structure

The project is organized into self-contained dialect modules for clean isolation, testability, and extensibility:

```plaintext
Text_to_query/
├── .env.example                               # Environment template for DB credentials & LLM endpoints
├── .gitignore                                 # Git ignore patterns (protects secrets, keys, and caches)
├── requirements.txt                           # Core Python dependencies
├── project_context.md                         # Architecture rationale, domain background, and adapter design
├── SEMANTIC_LAYER_SPEC.md                     # Formal Unified Semantic Layer JSON schema specification
├── unified_semantic_layer_template.json       # Clean starter template for semantic layer definitions
├── main.py                                    # Orchestrator to run schema extractions across all engines
│
├── bigquery/                                  # Google Cloud BigQuery Module
│   ├── adapter.py                             # BigQuery adapter implementing BaseDatabaseAdapter
│   ├── base_adapter.py                        # Common adapter abstract interface
│   ├── models.py                              # Semantic layer dataclasses (Entity, Attribute, Relationship)
│   ├── normalizer.py                          # Normalizes INFORMATION_SCHEMA into Unified Semantic Layer
│   ├── schema_extract.py                      # Raw BigQuery schema & foreign key extractor
│   ├── text2sql.py                            # Interactive Text-to-SQL CLI with live query execution
│   ├── unified_semantic_layer_bq_thelook.json # Extracted semantic layer for 'thelook_ecommerce'
│   └── main.py                                # Standalone BigQuery schema extraction runner
│
└── neo4j/                                     # Neo4j Graph Database Module
    ├── adapter.py                             # Neo4j adapter implementing BaseDatabaseAdapter
    ├── base_adapter.py                        # Common adapter abstract interface
    ├── models.py                              # Semantic layer dataclasses
    ├── normalizer.py                          # Normalizes graph metadata into Unified Semantic Layer
    ├── schema_extract.py                      # Neo4j APOC / Cypher schema extractor
    ├── text2cypher.py                         # Interactive Text-to-Cypher CLI with live query execution
    ├── unified_semantic_layer_neo4j_northwind.json # Extracted semantic layer for 'Northwind' graph
    └── main.py                                # Standalone Neo4j schema extraction runner
```

---

## 🧠 The Unified Semantic Layer

Every data source is normalized into a unified, paradigm-agnostic JSON format (detailed in [`SEMANTIC_LAYER_SPEC.md`](SEMANTIC_LAYER_SPEC.md)).

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

## ⚡ Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/Mehraayisha/Text_to_query.git
cd Text_to_query
```

### 2. Set Up Python Virtual Environment
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

### 4. Configure Local Ollama LLM
Both `text2sql.py` and `text2cypher.py` utilize local LLMs via [Ollama](https://ollama.ai) for privacy, zero cost, and low latency:
```bash
# Download and run Ollama, then pull the recommended model
ollama pull llama3.1
ollama serve
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Configure your credentials in `.env`:
```ini
# Local Ollama Configuration
OLLAMA_ENDPOINT=http://localhost:11434/api/generate
OLLAMA_MODEL=llama3.1

# Neo4j Graph Database
NEO4J_URI=neo4j+s://demo.neo4jlabs.com
NEO4J_USER=northwind
NEO4J_PASSWORD=northwind
NEO4J_DATABASE=northwind

# Google Cloud BigQuery
GOOGLE_APPLICATION_CREDENTIALS=jsonkeybq.json
BIGQUERY_BILLING_PROJECT=your-gcp-project-id
BIGQUERY_TARGET_PROJECT=bigquery-public-data
BIGQUERY_DATASET=thelook_ecommerce
```

> 🔒 **Security Notice:** Never commit `.env` or service account keys (`jsonkeybq.json`). Both are excluded via `.gitignore`.

---

## 💬 Interactive Text-to-Query Applications

### 🔹 BigQuery Text-to-SQL (`bigquery/text2sql.py`)
Translates natural language questions to BigQuery Standard SQL, applies business domain rules (such as revenue exclusions and margin calculations), executes on Google Cloud BigQuery, and displays the formatted results.

```bash
# Run the BigQuery interactive CLI
python bigquery/text2sql.py
```

**Example Queries:**
* `"What are the top 5 product categories by revenue in 2023?"`
* `"List the 10 customers with the highest total spend who joined after 2021."`
* `"What is the monthly gross profit for completed orders in the last 6 months?"`

### 🔹 Neo4j Text-to-Cypher (`neo4j/text2cypher.py`)
Translates natural language into Cypher queries utilizing relationship directions, node labels, and property keys defined in the semantic layer, executes on Neo4j, and renders tabular graph query output.

```bash
# Run the Neo4j interactive CLI
python neo4j/text2cypher.py
```

**Example Queries:**
* `"Which products belong to the 'Beverages' category?"`
* `"Show the top 5 customers who have placed the most orders."`
* `"Find all suppliers located in the USA and list their products."`

### 🔹 MySQL Text-to-SQL (`chat_mysql.py`)
Extract the configured MySQL schema, translate natural-language questions into
read-only MySQL SQL using Gemini Flash, execute the query, and summarize the results.

Configure the `MYSQL_*` and `GEMINI_*` values in `.env`, then run:

```bash
python chat_mysql.py
```

Only one `SELECT` or `WITH` statement is accepted, and results are limited to 100 rows.
The MySQL adapter uses the shared semantic models from `bigquery/models.py` so its
metadata remains compatible with the repository's unified semantic-layer format.

---

## 🔄 Schema Extraction & Semantic Layer Generation

Extract and normalize live database schemas into the Unified Semantic Layer:

### Extract All Databases
```bash
python main.py
```

### Extract Individually
```bash
# BigQuery only
python bigquery/main.py

# Neo4j only
python neo4j/main.py

# MySQL only
python run_mysql.py
```

The generated files represent the standardized source of truth consumed by the prompt
engine and query generators. MySQL output is written to
`unified_semantic_layer_mysql.json`.

---

## 🔮 Roadmap

- [x] Base database adapter abstraction & interface
- [x] Unified Semantic Layer JSON specification & Dataclass models
- [x] Google Cloud BigQuery schema extractor & normalizer
- [x] Neo4j Graph database schema extractor & normalizer
- [x] MySQL schema extractor & adapter
- [x] MySQL natural-language read-only query client with Gemini Flash
- [x] Interactive BigQuery Text-to-SQL engine with Ollama (Llama 3.1) & live execution
- [x] Interactive Neo4j Text-to-Cypher engine with Ollama (Llama 3.1) & live execution
- [ ] Selective Metadata Retrieval module (RAG / vector embeddings over semantic layers)
- [ ] Multi-database unified query router (single input bar routing to correct adapter)
- [ ] MongoDB document adapter & text-to-MQL engine
- [ ] Amazon DynamoDB / NoSQL adapter
- [ ] Qdrant vector adapter implementation
- [ ] Web UI / Dashboard (Streamlit / React)

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.

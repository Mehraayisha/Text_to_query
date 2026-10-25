# Multi-Database Natural Language to Query Engine (Text2Cypher & Text2SQL)

An enterprise-grade, privacy-first system that translates natural language business questions into precise, executable database queries for both Graph (**Neo4j Cypher**) and Relational/Data Warehouse (**Google Cloud BigQuery Standard SQL**) databases using a locally hosted Large Language Model (**Meta Llama 3.1** via **Ollama**).

---

## 1. System Overview

Querying modern databases usually requires specialized syntax expertise:
- **Graph databases** require declarative pattern-matching queries like Cypher (`MATCH (u:User)-[:PURCHASED]->(p:Product)...`).
- **Data Warehouses** require complex SQL dialects with explicit column data types, window functions, and multi-table joins (`SELECT ... FROM `dataset.orders` JOIN ...`).

This project solves this problem by providing a natural language interface where business users and developers can ask plain English questions (e.g., *"Which 5 product brands generated the highest gross profit?"*) and receive accurate query results rendered in clean terminal tables—**without sending database schemas, credentials, or proprietary data to external cloud LLM providers**.

### Key Highlights
- **100% Free & Local Inference**: Powered by local `llama3.1` running via Ollama (`http://localhost:11434`) at zero API cost.
- **Strict Data Privacy**: No proprietary schemas, queries, or database records leave your local machine or network.
- **Zero Hallucination Architecture**: Driven by a pre-computed **Unified Semantic Layer** that injects exact schemas, column types, join paths, and business formulas into every generation step.
- **Interactive Terminal REPLs**: Dedicated, resilient command-line applications for both Neo4j and BigQuery.

---

## 2. System Architecture & End-to-End Execution Flow

The system operates on an automated, closed-loop pipeline for both databases:

```
┌────────────────────────────────────────────────────────┐
│                   User Question                        │
│   "Find top 5 customers by total spending in 2023"     │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                The Semantic Layer                      │
│  - Exact Column Types (INT64, FLOAT64, STRING, etc.)   │
│  - Directional Triplets & Explicit Foreign Key Paths   │
│  - Domain Business Rules & Calculations (Gross Margin) │
│  - Hardcoded Few-Shot Query Examples                   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│           Local LLM Inference (llama3.1)               │
│      Ollama HTTP API (temp=0.0, deterministic)         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│            Query Parser & Sanitizer                    │
│   - Strips Markdown (```sql, ```cypher)                │
│   - Removes Conversational Preamble                    │
│   - Fixes Literal Escaped Characters (\n, \t)          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             Database Execution & Guardrails            │
│   - Neo4j Bolt Driver (Cypher)                         │
│   - Google Cloud BigQuery API Client (Standard SQL)    │
│   - Graceful Exception Catching (No REPL Crashes)      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│                 Terminal ASCII Table                   │
│        Interactive, formatted tabular output           │
└────────────────────────────────────────────────────────┘
```

### Detailed Step-by-Step Flow:
1. **User Terminal Input**: The user inputs a business question in the interactive terminal REPL (`Text2SQL > ` or `Text2Cypher > `).
2. **Semantic Context Injection**: The application loads the local `unified_semantic_layer_*.json` file and constructs a high-density system prompt containing the exact schema, types, relationships, business rules, and few-shot examples.
3. **Local LLM Inference**: The prompt is dispatched via HTTP POST to the local Ollama instance running `llama3.1` at `temperature: 0.0`.
4. **Query Parsing & Sanitization**: The response is stripped of conversational chit-chat, markdown code wrappers, and escaped characters, yielding pure SQL or Cypher.
5. **Database Execution**: The query is executed against the live database using official drivers (`neo4j` Python driver or `google-cloud-bigquery`).
6. **Result Rendering**: Query execution times and record counts are displayed, followed by an automatically formatted ASCII table.

---

## 3. Project Directory Structure

The project is structured into modular, self-contained packages for each supported database dialect:

```
mainpro/
├── ARCHITECTURE.md                  # Comprehensive system documentation
├── requirements.txt                 # Project dependencies
├── .env                             # Environment configuration (credentials, endpoints)
├── jsonkeybq.json                   # Google Cloud BigQuery service account credentials
├── main.py                          # Unified semantic layer extraction runner
│
├── neo4j/                           # Neo4j Graph Package
│   ├── __init__.py                  # Dynamic module loader & driver resolver
│   ├── models.py                    # Graph schema dataclasses (Triplets, Nodes, Rels)
│   ├── base_adapter.py              # Base graph adapter interface
│   ├── adapter.py                   # Live Neo4j connection & metadata extractor
│   ├── schema_extract.py            # Extracts nodes, properties, and relationship types
│   ├── normalizer.py                # Formats graph schema into Unified JSON format
│   ├── text2cypher.py               # Interactive Text-to-Cypher Terminal REPL
│   └── unified_semantic_layer_neo4j_northwind.json  # Pre-computed graph semantic layer
│
└── bigquery/                        # BigQuery SQL Package
    ├── __init__.py                  # Package initializer
    ├── models.py                    # SQL schema dataclasses (Tables, Columns, FKs)
    ├── base_adapter.py              # Base relational adapter interface
    ├── adapter.py                   # Live BigQuery connection & INFORMATION_SCHEMA extractor
    ├── schema_extract.py            # Extracts table metadata and column types
    ├── normalizer.py                # Formats SQL schema into Unified JSON format
    ├── text2sql.py                  # Interactive Text-to-SQL Terminal REPL
    └── unified_semantic_layer_bq_thelook.json       # Pre-computed BigQuery semantic layer
```

---

## 4. The Semantic Layer ("The Secret Sauce")

Standard Large Language Models frequently fail when generating database queries because:
1. **Hallucinated Columns**: They guess common column names (e.g., assuming `orders.id` exists when the actual column is `orders.order_id`).
2. **Reversed or Invented Relationships**: They guess graph directions (e.g., `(Category)-[:SUPPLIES]->(Supplier)`) or join tables on non-existent keys.
3. **Data Type Mismatches**: They attempt numeric math (`SUM(freight)`) on string columns, causing fatal runtime database errors.
4. **Ambiguous Business Metrics**: They don't know what your organization means by *"Gross Profit"* or *"Completed Orders"*.

The **Semantic Layer** is the core bridge that eliminates these failure modes before the prompt reaches the LLM.

### What the Semantic Layer Injects:
* **Explicit Data Types**: Maps every attribute to its exact database type (`INT64`, `FLOAT64`, `STRING`, `TIMESTAMP`, `BOOL`).
* **Strict Directional Triplets (Graph)**: Injects exact relationship paths:
  ```text
  (:Supplier)-[:SUPPLIES]->(:Product)-[:PART_OF]->(:Category)
  (:Customer)-[:PURCHASED]->(:Order)-[:ORDERS]->(:Product)
  ```
* **Exact Foreign Key Join Paths (SQL)**: Mandates exact join predicates:
  ```sql
  order_items.order_id = orders.order_id
  order_items.user_id = users.id
  order_items.product_id = products.id
  order_items.inventory_item_id = inventory_items.id
  ```
* **Business Metric Formulas**: Defines canonical business calculations directly in the prompt:
  * *Total Revenue*: `SUM(order_items.sale_price)` where `status NOT IN ('Cancelled', 'Returned')`.
  * *Gross Profit*: `SUM(order_items.sale_price - inventory_items.cost)`.
  * *Completed Orders*: `orders.status = 'Complete'`.
* **In-Context Few-Shot Examples**: Hardcoded pairs of natural language questions and exact, vetted queries that guide syntax, casing, and grouping patterns.

---

## 5. The Local LLM Engine (`llama3.1` via Ollama)

Both query pipelines connect to a local instance of **Meta Llama 3.1 (8B)** running on [Ollama](https://ollama.ai/):

* **Endpoint**: `http://localhost:11434/api/generate`
* **Model**: `llama3.1`
* **Temperature**: `0.0` (Zero randomness for fully deterministic, reproducible query generation)
* **Top-P**: `0.9`

### Why `llama3.1` over proprietary Cloud LLMs?
1. **Data Security & Privacy**: Sensitive database table structures, enterprise business rules, and customer inquiries never leave the local environment.
2. **Zero Operational Costs**: Eliminates token fees, rate limits, and external API downtime.
3. **Strong Multi-Paradigm Reasoning**: Llama 3.1 demonstrates outstanding capability in understanding both declarative graph traversal (Cypher) and complex SQL joins and aggregations.

---

## 6. Defensive Guardrails & Error Handling

To ensure reliability during continuous terminal sessions, both applications implement strict defensive guardrails:

### 1. Aggressive Prompt Constraints
The system prompts enforce non-negotiable generation rules:
* `"CRITICAL: NEVER guess, assume, or invent column names like id. You must ONLY use the exact column names explicitly listed in the schema."`
* `"When joining tables, you must EXACTLY COPY AND PASTE the provided foreign key JOIN conditions."`
* `"Strict Directional Triplets: You must strictly adhere to the provided relationship directions. Never invent new paths or reverse direction."`

### 2. Robust Query Sanitization
Raw output from generative models often contains conversational filler or markdown markers. The extractors (`extract_sql` and `extract_cypher`) perform:
* Extraction of code within explicit markdown blocks (```` ```sql ````, ```` ```cypher ````, ```` ``` ````).
* Stripping of literal escaped characters (`\n`, `\t`) generated by local LLMs.
* Removal of preambles (e.g., *"Here is the query you requested:"*) and post-query explanations.
* Truncation at trailing comment markers or semicolons.

### 3. Graceful Runtime Exception Handling
Database errors (syntax errors, invalid types, authentication issues) are trapped within `try...except` blocks in the REPL loop. Instead of terminating the program, the system:
* Prints a clear diagnostic error message with troubleshooting suggestions.
* Returns immediately to the interactive prompt (`Text2SQL > `) so the user can rephrase or refine their request.

---

## 7. How to Run the Applications

### Prerequisites
1. Ensure Ollama is running locally with the `llama3.1` model installed:
   ```bash
   ollama run llama3.1
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running Text-to-Cypher (Neo4j)
Launch the interactive Neo4j terminal assistant:
```bash
python neo4j/text2cypher.py
```
*Example input:*
```text
Text2Cypher > Which suppliers provide dairy products?
Text2Cypher > What are the top 5 most expensive products?
```

### Running Text-to-SQL (BigQuery)
Launch the interactive BigQuery terminal assistant:
```bash
python bigquery/text2sql.py
```
*Example input:*
```text
Text2SQL > What are the top 5 product categories by total sales revenue?
Text2SQL > Which 5 product brands generated the highest gross profit?
```

### Re-Extracting Semantic Layers
To refresh the database schemas from live instances into the semantic layer JSON files:
```bash
python main.py
```

# Project Context: A Unified LLM-Based Natural Language Query Platform for Heterogeneous Databases

## 1. Domain & Problem Statement
The project operates in the domain of Large Language Models (LLMs), Natural Language Query Processing, Heterogeneous Database Systems (both relational and non-relational), and Semantic Schema Mapping. 

**The Problem:** Organizations currently store data across multiple diverse databases. Each database requires knowledge of specific query languages (like SQL, MongoDB Query Language, or Cypher) and complex schemas.
**The Need:** A unified platform that enables users to query these disparate database technologies using plain English, entirely bypassing the need to write database-specific queries.

## 2. Project Objectives & Motivation
* **Unified Interface:** Develop a unified natural language query platform supporting both relational and non-relational databases.
* **Semantic Schema Mapping:** Automatically extract metadata and build a unified semantic representation (Semantic Layer) across connected databases.
* **Optimized LLM Usage:** Dynamically retrieve only the metadata relevant to the specific query. This addresses a major research gap by avoiding supplying the complete schema to the LLM, thereby drastically reducing LLM context size and token consumption while improving text-to-query accuracy.

## 3. Proposed System Architecture Flow
The platform processes requests through a sequential pipeline:
1. **Natural Language Query** (Input from user)
2. **Relevant Metadata Retrieval** (Fetching only what is necessary)
3. **Semantic Layer** (Understanding entities and relationships)
4. **LLM Query Generation** (Translating into SQL, MQL, Cypher, etc.)
5. **Selected Database** (Routing to the correct source)
6. **Query Execution**
7. **User-Friendly Result** (Output back to user)

## 4. Database Adapter Architecture
**Architecture Idea:** Instead of implementing a completely separate natural-language pipeline for every source, the system uses a common query-planning layer. This layer routes the request to the appropriate adapter based on the data source. Each adapter translates the interpreted user intent into the specific retrieval operation required by that source.

### Adapters and Their Retrieval Mechanisms
* **SQL Adapter:** Generates and executes SQL or database-specific SQL dialects.
  * *Sources:* PostgreSQL, MySQL, SQL Server, Azure SQL, Google Cloud BigQuery, Snowflake, Amazon Redshift, ClickHouse, Databricks, Trino, Amazon Athena.
* **Document Adapter:** Generates MongoDB Query Language queries or aggregation pipelines.
  * *Sources:* MongoDB.
* **Graph Adapter:** Generates Cypher queries for graph traversal and relationship-based retrieval.
  * *Sources:* Neo4j.
* **Vector Adapter:** Converts natural-language intent into embeddings and performs vector similarity search with filtering.
  * *Sources:* Qdrant.
* **Time-Series Adapter:** Generates time-series queries (such as InfluxQL/SQL) and retrieves time-based measurements.
  * *Sources:* InfluxDB.
* **Object/File Adapter:** Locates and retrieves files/objects and processes structured or unstructured file contents.
  * *Sources:* Amazon S3, Google Cloud Storage (GCS), Azure Blob Storage, MinIO, Cloudflare R2.
* **API / Dataset Adapter:** Interacts with external APIs or dataset sources and retrieves the relevant records/data.
  * *Sources:* HTTP (Web/API), Hugging Face (Dataset Source).
* **Key-Value / Document Adapter:** Uses PartiQL or DynamoDB APIs for key-value/document retrieval.
  * *Sources:* Amazon DynamoDB.

## 5. Expected Outcomes
* A single natural language interface for querying 23 different heterogeneous databases and data sources.
* Eliminates the requirement for end-users to learn and write database-specific query languages.
* Improved query generation driven by deep semantic understanding of database entities and relationships.
* Significantly reduced LLM token consumption due to the selective, relevant metadata retrieval approach.
* User-assisted validation and refinement of semantic schema mappings.

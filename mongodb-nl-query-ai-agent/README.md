# 🍃 MongoDB Natural Language Query AI Agent

A lightweight, powerful AI agent that converts **Natural Language questions into MongoDB Aggregation Pipelines**, executes them safely, and returns both structured data and conversational summaries.

Designed as an independent, modular NLP-to-Database component for multi-database querying systems.

---

## ✨ Features

- **Natural Language to Aggregation Pipeline:** Converts English queries into optimized MongoDB queries (`$match`, `$group`, `$sort`, `$limit`, `$unwind`).
- **Automatic Schema Discovery:** Connects to any MongoDB database, samples documents, detects nested objects & arrays, infers relationships, and generates YAML semantic models automatically.
- **Direct & Cloud Ready:** Seamless direct connection with MongoDB Atlas or local MongoDB instances via PyMongo.
- **Multi-LLM Compatible:** Built-in support for OpenRouter, OpenAI, and Azure OpenAI, including an HTTP client fallback that works with zero extra setup.
- **REST API & Swagger UI:** Ready-to-use FastAPI endpoints for microservice integration.

---

## 📁 Project Structure

```text
mongodb-nl-query-ai-agent/
├── src/
│   └── mongodb_agent/
│       ├── agent.py               # Main MongoDBAgent interface
│       ├── api.py                 # FastAPI REST API & endpoints
│       ├── schema_discovery.py    # Automatic schema inference & YAML generator
│       ├── graph.py               # LangGraph workflow orchestration
│       ├── config.py              # Environment configuration loader
│       ├── nodes/                 # Selector, Query Executor, Refiner, Output Parser
│       ├── prompts/               # System & prompt engineering templates
│       ├── semantic_models/       # YAML schema loader & optimizer
│       └── services/              # Direct MongoClient & LLM connectors
├── semantic_models/               # Generated YAML semantic models
│   ├── sample_mflix.yaml          # Auto-discovered database schema
│   └── example_collection.yaml
├── examples/
│   ├── test_connection.py         # MongoDB connection & query verification
│   └── basic_query.py             # Python query example
├── scripts/
│   ├── discover_schema.py         # Schema discovery runner
│   └── start_server.sh            # Server launcher script
├── tests/                         # Pytest test suite
├── server.py                      # FastAPI server runner
├── .env                           # Credentials & config (git-ignored)
├── .env.example                   # Environment configuration template
└── pyproject.toml
```

---

## 🚀 Quick Start

### 1. Configure Environment (`.env`)
Create or edit `.env`:

```ini
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openrouter_or_openai_api_key
OPENAI_MODEL=openrouter/free
OPENAI_BASE_URL=https://openrouter.ai/api/v1

MONGODB_CONNECTION_TYPE=direct
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=sample_mflix

VECTOR_DB=local
SEMANTIC_MODEL_PATH=./semantic_models
```

### 2. Run Schema Discovery
Automatically analyze your collections and build the schema model:

```powershell
python scripts/discover_schema.py
```
*Saves the discovered model to `./semantic_models/<database>.yaml`.*

### 3. Verify Connection
```powershell
python examples/test_connection.py
```

### 4. Start the API Server
```powershell
python server.py
```
- **API URL:** `http://127.0.0.1:8000`
- **Interactive Swagger Docs:** `http://127.0.0.1:8000/docs`

---

## 🔌 API Endpoints

### Query Database
**`POST /api/mongodb`**
```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/api/mongodb' \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "Show me top 5 highest-rated sci-fi movies"
  }'
```

**Response:**
```json
{
  "question": "Show me top 5 highest-rated sci-fi movies",
  "yaml_file_name": "sample_mflix.yaml",
  "mongodb_query": "db.movies.aggregate([{\"$match\": {\"genres\": {\"$regex\": \"sci-fi\", \"$options\": \"i\"}}}, {\"$sort\": {\"imdb.rating\": -1}}, {\"$limit\": 5}])",
  "query_result": [...],
  "natural_language_response": "1. Inception (Year: 2010, IMDb: 8.8, Genres: Action, Sci-Fi)...",
  "execution_time_ms": 1420.5,
  "status": "success",
  "timestamp": "2026-10-25T15:30:00.000000"
}
```

### Trigger Schema Discovery
**`POST /api/discover-schema`**
```bash
curl -X 'POST' 'http://127.0.0.1:8000/api/discover-schema'
```

---

## 🐍 Using as a Python Library

```python
from mongodb_agent import MongoDBAgent, Config

config = Config.from_env()
agent = MongoDBAgent(config)

response = agent.query("Show me 5 action movies released after 2012")

print("Generated Query:", response["aggregation_pipeline"])
print("Summary:", response["query_result"])
print("Raw Documents:", response["raw_mongo_result"])
```

---

## 🧪 Testing

Run the test suite:
```powershell
python -m pytest tests
```

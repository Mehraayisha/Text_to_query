# ⚡ Quick Start Guide

Get up and running with the MongoDB Natural Language Query AI Agent in 3 minutes.

---

## 1. Setup Environment
Ensure your `.env` contains your MongoDB Atlas URI and OpenRouter/OpenAI API key:

```ini
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-or-v1-...
OPENAI_MODEL=openrouter/free
OPENAI_BASE_URL=https://openrouter.ai/api/v1

MONGODB_CONNECTION_TYPE=direct
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE=sample_mflix
```

---

## 2. Generate Schema Automatically
If you haven't generated the schema for your database yet:

```powershell
python scripts/discover_schema.py
```
This generates `semantic_models/<database_name>.yaml`.

---

## 3. Test Connection
```powershell
python examples/test_connection.py
```

---

## 4. Launch Server
```powershell
python server.py
```
Open **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)** in your browser to interactively test queries.

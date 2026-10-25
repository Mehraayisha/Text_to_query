#!/usr/bin/env python3
"""
Text_to_query Platform Server - Unified FastAPI Server & Swagger UI
Serves natural language query processing and schema discovery across connected databases.
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure root directory is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(root_dir, ".env"))
    load_dotenv(os.path.join(root_dir, "mongodb", ".env"))
except ImportError:
    pass

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
log_dir = os.path.join(root_dir, "logs")
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(log_dir, "platform_server.log"), mode="a", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("text_to_query.server")

# Initialize FastAPI app
app = FastAPI(
    title="Text_to_query: Unified NL-to-Database Platform",
    description="Unified Natural Language Query Engine for Heterogeneous Databases (Relational, Graph, Document)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_bson(obj):
    """Convert BSON types (ObjectId, datetime) to JSON-serializable primitives."""
    from bson import ObjectId
    from datetime import datetime as dt, date
    if isinstance(obj, list):
        return [serialize_bson(x) for x in obj]
    elif isinstance(obj, dict):
        return {str(k): serialize_bson(v) for k, v in obj.items()}
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, (dt, date)):
        return obj.isoformat()
    return obj


# ============================================================
# Request / Response Schemas
# ============================================================

class MongoDBQueryRequest(BaseModel):
    question: str = Field(..., description="Natural language question about the MongoDB data", example="Show me top 5 movies with rating greater than 8")
    model_file_name: Optional[str] = Field(default=None, description="Semantic model JSON filename (defaults to <database>.json)")
    include_debug: bool = Field(default=False, description="Include intermediate execution steps and matched rules")


class MongoDBQueryResponse(BaseModel):
    question: str
    model_file_name: Optional[str] = Field(default=None, description="Semantic model file used")
    mongodb_query: Optional[str] = Field(default="N/A", description="Generated MongoDB aggregation pipeline")
    query_result: List[Dict[str, Any]] = Field(default_factory=list, description="Query execution results")
    natural_language_response: str = Field(description="Natural language explanation of results")
    execution_time_ms: float
    status: str = Field(description="success or error")
    timestamp: str
    debug_info: Optional[Dict[str, Any]] = None


class DiscoverSchemaRequest(BaseModel):
    database: Optional[str] = Field(default=None, description="MongoDB database name to discover")
    output_filename: Optional[str] = Field(default=None, description="Output JSON filename (defaults to <database>.json)")
    sample_size: int = Field(default=50, description="Documents to sample per collection")
    export_unified_json: bool = Field(default=True, description="Also export Unified Semantic Layer JSON conforming to SEMANTIC_LAYER_SPEC.md")


class DiscoverSchemaResponse(BaseModel):
    status: str
    database: str
    output_path: str
    message: str


# ============================================================
# MongoDB Agent Initialization
# ============================================================

mongodb_agent_instance = None
mongodb_agent_available = False
init_error_message = ""

def get_mongodb_agent():
    global mongodb_agent_instance, mongodb_agent_available, init_error_message
    if mongodb_agent_instance is not None:
        return mongodb_agent_instance
    try:
        from mongodb.config import Config
        from mongodb.agent import MongoDBAgent
        config = Config.from_env()
        mongodb_agent_instance = MongoDBAgent(config)
        mongodb_agent_available = True
        init_error_message = ""
        logger.info("MongoDB Agent initialized successfully!")
        return mongodb_agent_instance
    except Exception as e:
        init_error_message = str(e)
        logger.warning(f"MongoDB Agent initialization pending/failed: {e}")
        return None

# Try initial connection at startup
get_mongodb_agent()


# ============================================================
# API Endpoints
# ============================================================

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">🔍</text></svg>'
    return Response(content=svg, media_type="image/svg+xml")


@app.get("/")
async def root():
    return {
        "service": "Text_to_query Unified Platform API",
        "version": "1.0.0",
        "status": "running",
        "supported_engines": {
            "mongodb": {
                "dialect": "mongodb",
                "available": mongodb_agent_available,
                "endpoints": ["POST /api/mongodb", "POST /api/discover-schema"]
            },
            "bigquery": {
                "dialect": "bigquery_sql",
                "cli": "python bigquery/text2sql.py"
            },
            "neo4j": {
                "dialect": "neo4j_cypher",
                "cli": "python neo4j/text2cypher.py"
            }
        },
        "docs": "http://127.0.0.1:8000/docs"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mongodb_agent_available": mongodb_agent_available,
    }


@app.post("/api/mongodb", response_model=MongoDBQueryResponse)
async def query_mongodb(request: MongoDBQueryRequest):
    """
    Executes a natural language question against MongoDB:
    1. Loads the database semantic model
    2. Translates English to MongoDB Aggregation Pipeline ($match, $group, etc.)
    3. Executes query live on MongoDB
    4. Returns structured documents and natural language summary
    """
    start_time = datetime.now()

    agent = get_mongodb_agent()
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail=f"MongoDB Agent could not be initialized: {init_error_message or 'Check database credentials & connection'}"
        )

    try:
        model_file = request.model_file_name or f"{agent.config.mongodb_database or 'sample_mflix'}.json"
        logger.info(f"Executing MongoDB query: '{request.question}' using model '{model_file}'")

        result = agent.query(
            question=request.question,
            yaml_file_name=model_file
        )

        end_time = datetime.now()
        exec_time = round((end_time - start_time).total_seconds() * 1000, 2)

        mql = str(result.get("aggregation_pipeline") or result.get("sql_query") or "N/A")
        raw_data = result.get("raw_mongo_result")
        query_result = serialize_bson(raw_data if isinstance(raw_data, list) else ([raw_data] if raw_data else []))

        natural_lang = result.get("query_result") or result.get("natural_language_response") or "Query executed successfully."

        debug_info = None
        if request.include_debug:
            debug_info = {
                "collection_name": result.get("collection_name", ""),
                "matched_rules": result.get("matched_rules", []),
                "verified_queries_used": result.get("verified_queries_used", []),
                "error": result.get("error", "")
            }

        return MongoDBQueryResponse(
            question=request.question,
            model_file_name=model_file,
            mongodb_query=mql,
            query_result=query_result,
            natural_language_response=natural_lang,
            execution_time_ms=exec_time,
            status="success" if not result.get("error") else "error",
            timestamp=datetime.now().isoformat(),
            debug_info=debug_info,
        )

    except Exception as e:
        logger.error(f"Error executing MongoDB query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/discover-schema", response_model=DiscoverSchemaResponse)
async def discover_schema_endpoint(request: Optional[DiscoverSchemaRequest] = None):
    """
    Auto-discovers MongoDB schema from live collections, infers nested types and relationships,
    and exports both the agent semantic model and the Unified Semantic Layer JSON.
    """
    try:
        from mongodb.schema_discovery import SchemaDiscoverer
        from mongodb.adapter import MongoDBDocumentAdapter

        req_db = request.database if request else None
        req_out = request.output_filename if request else None
        req_sample = request.sample_size if request else 50
        req_json = request.export_unified_json if request else True

        discoverer = SchemaDiscoverer(
            database_name=req_db,
            sample_size=req_sample,
        )
        saved_path = discoverer.discover_and_save(output_filename=req_out)

        json_msg = ""
        if req_json:
            try:
                adapter = MongoDBDocumentAdapter(
                    uri=discoverer.uri,
                    database=discoverer.database_name,
                    sample_size=req_sample,
                )
                base_name = os.path.splitext(os.path.basename(saved_path))[0]
                json_path = os.path.join(discoverer.output_dir, f"unified_semantic_layer_{base_name}.json")
                adapter.export_semantic_layer(json_path)
                json_msg = f" and Unified Semantic Layer JSON to {json_path}"
            except Exception as json_err:
                logger.warning(f"Could not export unified JSON: {json_err}")

        return DiscoverSchemaResponse(
            status="success",
            database=discoverer.database_name,
            output_path=saved_path,
            message=f"Schema successfully discovered and saved to {saved_path}{json_msg}",
        )
    except Exception as e:
        logger.error(f"Error during schema discovery: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    host = os.getenv("SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("SERVER_PORT", "8000"))
    reload = os.getenv("DEV_MODE", "true").lower() == "true"

    print("=" * 70)
    print("🚀 Text_to_query: Unified NL-to-Database Platform Server")
    print(f"📡 API Running at:  http://{host}:{port}")
    print(f"📚 Interactive Swagger Docs: http://{host}:{port}/docs")
    print("=" * 70)

    uvicorn.run("server:app", host=host, port=port, reload=reload)

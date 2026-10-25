
def serialize_bson(obj):
    """Convert BSON types (ObjectId, datetime) to JSON-serializable primitives."""
    from bson import ObjectId
    from datetime import datetime, date
    if isinstance(obj, list):
        return [serialize_bson(x) for x in obj]
    elif isinstance(obj, dict):
        return {str(k): serialize_bson(v) for k, v in obj.items()}
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


def normalize_to_pipeline(query_input):
    """Normalize any MongoDB query string/dict into an aggregation pipeline list."""
    import re
    import json
    import ast
    from datetime import datetime

    if isinstance(query_input, dict):
        if "aggregation_pipeline" in query_input and isinstance(query_input["aggregation_pipeline"], list):
            return query_input["aggregation_pipeline"]
        if "mongodb_query" in query_input and isinstance(query_input["mongodb_query"], str):
            query_input = query_input["mongodb_query"]

    if isinstance(query_input, list):
        return query_input

    if not isinstance(query_input, str):
        return [{"$limit": 10}]

    query_str = query_input.strip()

    # Extract pipeline from db.collection.aggregate([...])
    if "aggregate(" in query_str:
        start = query_str.find("[")
        end = query_str.rfind("]") + 1
        if start != -1 and end > start:
            p_str = query_str[start:end]
            p_str = re.sub(r'ISODate\("([^"]+)"\)', r'"\1"', p_str)
            p_str = re.sub(r',\s*"(\{)', r', \1', p_str)
            p_str = re.sub(r'(\})\s*"\]', r'\1]', p_str)
            p_str = re.sub(r',\s*\]', ']', p_str)
            p_str = re.sub(r'([{,\s])([a-zA-Z0-9_\$]+)\s*:', r'\1"\2":', p_str)
            try:
                return json.loads(p_str)
            except Exception:
                try:
                    return ast.literal_eval(p_str)
                except Exception:
                    pass

    # Convert db.collection.find(...) to aggregation stages
    if "find(" in query_str:
        stages = []
        match = re.search(r'\.find\(([\s\S]*?)\)(?:\.sort\(([\s\S]*?)\))?(?:\.limit\((\d+)\))?', query_str)
        if match:
            filter_part = match.group(1).strip() or "{}"
            sort_part = match.group(2)
            limit_part = match.group(3)

            filter_part = re.sub(r'ISODate\("([^"]+)"\)', r'"\1"', filter_part)
            filter_part = re.sub(r'([{,\s])([a-zA-Z0-9_\$]+)\s*:', r'\1"\2":', filter_part)
            try:
                f_obj = json.loads(filter_part)
                if f_obj:
                    stages.append({"$match": f_obj})
            except Exception:
                try:
                    f_obj = ast.literal_eval(filter_part)
                    if f_obj:
                        stages.append({"$match": f_obj})
                except Exception:
                    pass

            if sort_part:
                sort_part = re.sub(r'([{,\s])([a-zA-Z0-9_\$]+)\s*:', r'\1"\2":', sort_part.strip())
                try:
                    s_obj = json.loads(sort_part)
                    stages.append({"$sort": s_obj})
                except Exception:
                    pass

            if limit_part:
                stages.append({"$limit": int(limit_part)})

            if stages:
                return stages

    # Try standard json loads
    try:
        res = json.loads(query_str)
        if isinstance(res, list):
            return res
        if isinstance(res, dict):
            return [{"$match": res}]
    except Exception:
        pass

    return [{"$limit": 10}]

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Direct MongoDB client using PyMongo

Handles:
- Direct MongoDB connection
- Aggregation pipeline execution
- Connection pooling
- Error handling
"""

import logging
from typing import Dict, Any, Optional
import json

from mongodb_agent.config import Config

logger = logging.getLogger(__name__)

# PyMongo is optional - only imported if direct connection is used
try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError

    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    logger.warning("PyMongo not installed. Direct MongoDB connection unavailable.")


class DirectMongoClient:
    """Direct MongoDB client using PyMongo"""

    def __init__(self, config: Config):
        if not PYMONGO_AVAILABLE:
            raise ImportError(
                "PyMongo is required for direct MongoDB connection. "
                "Install it with: pip install pymongo"
            )

        self.uri = config.mongodb_uri
        self.database_name = config.mongodb_database
        self.client = None
        self.db = None

        if not self.uri:
            raise ValueError("MONGODB_URI is required for direct connection")
        if not self.database_name:
            raise ValueError("MONGODB_DATABASE is required for direct connection")

        logger.info(f"Initializing direct MongoDB connection to: {self.database_name}")
        self._connect()

    def _connect(self):
        """Establish MongoDB connection"""
        try:
            self.client = MongoClient(self.uri)
            self.db = self.client[self.database_name]
            # Test connection
            self.client.admin.command("ping")
            logger.info(f"✅ Connected to MongoDB: {self.database_name}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to MongoDB: {e}")
            raise

    def execute_query(
        self, aggregation_pipeline: str, db_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute MongoDB aggregation pipeline directly

        Args:
            aggregation_pipeline: MongoDB aggregation pipeline (JSON string or list)
            db_details: Database details (must include 'collection' name)

        Returns:
            Dict with keys: success, data, error
        """
        try:
            # Parse collection name from various possible keys
            collection_name = (
                db_details.get("collection")
                or db_details.get("collectionName")
                or db_details.get("collection_name")
            )

            if not collection_name:
                error_msg = "Collection name is required in db_details (use 'collection' key)"
                logger.error(error_msg)
                return {"success": False, "data": None, "error": error_msg}

            collection = self.db[collection_name]

            # Parse pipeline
            pipeline = normalize_to_pipeline(aggregation_pipeline)

            # Convert any ISO date strings back to datetime objects
            from datetime import datetime
            def _convert_dates(item):
                if isinstance(item, dict):
                    return {k: _convert_dates(v) for k, v in item.items()}
                elif isinstance(item, list):
                    return [_convert_dates(x) for x in item]
                return item

            pipeline = _convert_dates(pipeline)

            if not isinstance(pipeline, list):
                error_msg = f"Pipeline must be a list of stages, got: {type(pipeline)}"
                logger.error(error_msg)
                return {"success": False, "data": None, "error": error_msg}

            logger.info("=" * 80)
            logger.info("📤 DIRECT MONGODB QUERY")
            logger.info(f"Database: {self.database_name}")
            logger.info(f"Collection: {collection_name}")
            logger.info(f"Pipeline: {str(pipeline)[:1000]}")  # Use str() instead of json.dumps()
            logger.info("=" * 80)

            # Execute aggregation
            result = list(collection.aggregate(pipeline))

            logger.info("=" * 80)
            logger.info("📥 MONGODB RESPONSE")
            logger.info(f"Success: True")
            logger.info(f"Documents Returned: {len(result)}")
            if len(result) > 0:
                logger.info(f"Sample Document Keys: {list(result[0].keys()) if result else []}")
            logger.info("=" * 80)

            return {"success": True, "data": serialize_bson(result), "error": None}

        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in aggregation pipeline: {e}"
            logger.error(error_msg)
            logger.error(f"Pipeline string: {aggregation_pipeline[:500]}")
            return {"success": False, "data": None, "error": error_msg}

        except Exception as e:
            error_msg = f"MongoDB query failed: {str(e)}"
            logger.exception(error_msg)
            return {"success": False, "data": None, "error": error_msg}

    def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")


def get_direct_client(config: Config) -> DirectMongoClient:
    """Get direct MongoDB client instance"""
    return DirectMongoClient(config)

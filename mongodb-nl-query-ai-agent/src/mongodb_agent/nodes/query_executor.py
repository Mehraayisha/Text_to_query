# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Query Executor Node - Execute MongoDB Query

This node:
1. Takes MongoDB aggregation pipeline from state
2. Calls MongoDB client (MCP or Direct) to execute query
3. Returns query results or error
4. Cleans up large state fields to reduce memory
"""

import logging
from typing import Dict, Any

# Global instances (set by build_graph)
mongodb_client = None
config = None

logger = logging.getLogger(__name__)


def query_executor(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute MongoDB query via configured client (MCP or Direct)

    Args:
        state: Current agent state with sql_query (MongoDB pipeline)

    Returns:
        Updated state with query_result or error
    """
    logger.info("⚡ Query Executor: Executing MongoDB query")

    try:
        # 1. Get query and db details
        query = state.get("sql_query")
        if not query:
            raise ValueError("No MongoDB query generated")

        db_details = state.get("db_details", {}).copy()

        # Extract collection name for direct MongoDB connection
        collection_name = state.get("collection_name")
        if collection_name and "collection" not in db_details:
            db_details["collection"] = collection_name

        query_str = query if isinstance(query, str) else str(query)
        logger.info(f"Executing query: {query_str[:100]}...")
        logger.info(
            f"Database: {db_details.get('dbName', db_details.get('database', db_details.get('collection')))}"
        )

        # 2. Execute via MongoDB client (MCP or Direct)
        response = mongodb_client.execute_query(aggregation_pipeline=query, db_details=db_details)

        # 3. Process response
        if response.get("success"):
            logger.info("✅ Query executed successfully")

            # Get actual MongoDB results data
            mongo_data = response.get("data", [])

            # Keep results as list/dict for API to consume
            # Generate natural language summary
            if isinstance(mongo_data, list):
                result_summary = f"Query returned {len(mongo_data)} document(s)"
            else:
                result_summary = "Query executed successfully"

            # Clean up large fields to reduce state size
            return {
                "sql_query": str(query),
                "query_result": result_summary,  # Natural language summary
                "raw_mongo_result": mongo_data,  # Actual data
                "error": "",
                "exception_class": "",
                "messages": state.get("messages", []),
                # Clear unnecessary fields
                "schema": "",
                "verified_queries": "",
                "custom_instructions": "",
                "fk_str": "",
                "content_yaml": "",
                "metrics": "",
                "raw_extracted_schema_dict": {},
            }
        else:
            error_msg = response.get("error", "Unknown error")
            logger.error(f"❌ Query execution failed: {error_msg}")

            return {
                "sql_query": str(query),
                "query_result": None,
                "error": error_msg,
                "exception_class": "MCPExecutionError",
                "messages": state.get("messages", []),
                # Clear unnecessary fields even in error case
                "schema": "",
                "verified_queries": "",
                "custom_instructions": "",
                "fk_str": "",
                "content_yaml": "",
                "metrics": "",
                "raw_extracted_schema_dict": {},
            }

    except Exception as e:
        logger.exception(f"❌ Query executor error: {e}")
        return {
            "error": f"Execution error: {str(e)}",
            "exception_class": type(e).__name__,
            "query_result": None,
        }

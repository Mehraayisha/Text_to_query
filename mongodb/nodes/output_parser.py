# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Output Parser Node - Direct Database Result Formatter

Formats query results directly from MongoDB without invoking a secondary LLM.
Returns data as-is for fast, deterministic, and token-free output display.
"""

import logging
import json
from typing import Dict, Any

# Global instances (maintained for graph builder compatibility)
llm = None
config = None

logger = logging.getLogger(__name__)


def output_parser(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format query result directly as-is without calling LLM.

    Args:
        state: Current agent state with raw_mongo_result and query_result

    Returns:
        Updated state with formatted query_result and preserved raw_mongo_result
    """
    logger.info("📝 Output Parser: Formatting database results as-is (no secondary LLM call)")

    try:
        raw_mongo_result = state.get("raw_mongo_result")
        query_result = state.get("query_result")

        # Determine data to display
        data = raw_mongo_result if raw_mongo_result is not None else query_result

        if data is None:
            formatted_response = "(No documents returned)"
        elif isinstance(data, list):
            if len(data) == 0:
                formatted_response = "(No documents found matching the query)"
            else:
                formatted_response = json.dumps(data, indent=2, default=str)
        elif isinstance(data, dict):
            formatted_response = json.dumps(data, indent=2, default=str)
        else:
            formatted_response = str(data)

        logger.info(f"Direct formatted result: {len(formatted_response)} chars")

        return {
            "query_result": formatted_response,
            "raw_mongo_result": raw_mongo_result,
        }

    except Exception as e:
        logger.exception(f"❌ Output parser error: {e}")
        return {
            "query_result": str(state.get("raw_mongo_result") or state.get("query_result") or f"Error: {e}")
        }

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Query Refiner Node - Fix MongoDB Query Errors

This node:
1. Takes the failed query and error message
2. Calls LLM to fix the query
3. Returns corrected MongoDB pipeline
4. Increments iteration counter
"""

import logging
from typing import Dict, Any

from langchain_core.messages import AIMessage

# Global instances (set by build_graph)
llm = None
config = None

logger = logging.getLogger(__name__)


def query_refiner(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Refine MongoDB query based on error

    Args:
        state: Current agent state with error and failed sql_query

    Returns:
        Updated state with corrected sql_query
    """
    logger.info("🔧 Query Refiner: Fixing MongoDB query")

    try:
        # 1. Get context
        failed_query = state.get("sql_query", "")
        error = state.get("error", "")
        exception_class = state.get("exception_class", "")
        user_question = state["messages"][0].content if state.get("messages") else ""

        logger.info(f"Failed query: {failed_query[:100]}...")
        logger.info(f"Error: {error}")

        # 2. Build refiner prompt
        from mongodb_agent.prompts import build_refiner_prompt

        # Get schema context from state
        schema_context = state.get("schema_context", "")
        fk_relationships = state.get("fk_relationships", "")

        prompt = build_refiner_prompt(
            query=user_question,
            desc_str=schema_context,
            fk_str=fk_relationships,
            sql=failed_query,
            error=error,
            exception_class=exception_class,
        )

        # 3. Call LLM to fix query
        logger.info("🤖 Calling LLM to fix query")
        full_response = ""
        for chunk in llm.stream(prompt):
            full_response += chunk.content

        logger.info(f"✅ LLM response: {len(full_response)} chars")

        # 4. Parse corrected query
        from mongodb_agent.utils.parsers import parse_mongodb_query_from_string

        corrected_query = parse_mongodb_query_from_string(full_response)

        # 5. Return updated state
        return {
            "sql_query": corrected_query,
            "iterations": state.get("iterations", 0) + 1,
            "messages": [AIMessage(content=full_response)],
        }

    except Exception as e:
        logger.exception(f"❌ Query refiner error: {e}")
        return {"error": f"Refiner error: {str(e)}", "iterations": state.get("iterations", 0) + 1}

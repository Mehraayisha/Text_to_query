# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Output Parser Node - Convert JSON to Natural Language

This node:
1. Takes query results (JSON/dict)
2. Calls LLM to generate user-friendly natural language response
3. Returns formatted answer
"""

import logging
import json
from typing import Dict, Any

# Global instances (set by build_graph)
llm = None
config = None

logger = logging.getLogger(__name__)


def output_parser(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse query result into natural language

    Args:
        state: Current agent state with query_result

    Returns:
        Updated state with formatted query_result (natural language)
    """
    logger.info("📝 Output Parser: Converting results to natural language")

    try:
        # 1. Get query result - check both raw_mongo_result and query_result
        raw_mongo_result = state.get("raw_mongo_result")
        query_result_summary = state.get("query_result", "No data available")
        user_query = state["messages"][0].content if state.get("messages") else ""

        # Use raw MongoDB data for formatting if available, otherwise use summary
        query_result = raw_mongo_result if raw_mongo_result is not None else query_result_summary

        logger.info(f"Parsing result: {str(query_result)[:100]}...")

        # 2. Convert query_result to JSON format for better LLM parsing
        if isinstance(query_result, (list, dict)):
            # Convert Python data structure to JSON with proper double quotes
            query_result_formatted = json.dumps(query_result, indent=2, default=str)
        else:
            query_result_formatted = str(query_result)

        # 3. Build output parser prompt
        from mongodb_agent.prompts import build_output_parser_prompt

        prompt = build_output_parser_prompt(
            user_query=user_query, query_result=query_result_formatted
        )

        # 4. Call LLM to format response
        logger.info("🤖 Calling LLM to format response")
        logger.info(f"📤 LLM REQUEST PROMPT ({len(prompt)} chars):\n{prompt}")
        logger.info("=" * 80)
        full_response = ""
        for chunk in llm.stream(prompt):
            full_response += chunk.content

        logger.info(f"✅ Natural language response: {len(full_response)} chars")
        logger.info(f"📝 NATURAL LANGUAGE RESPONSE:\n{full_response}")

        # Fallback if LLM generated a generic apology/refusal but data is present
        refusal_phrases = ["unable to assist", "i cannot assist", "apologies, i", "as an ai"]
        if (any(phrase in full_response.lower() for phrase in refusal_phrases) or not full_response.strip()) and isinstance(raw_mongo_result, list) and len(raw_mongo_result) > 0:
            logger.info("Output parser: LLM produced refusal or empty output. Using direct data summarizer.")
            lines = [f"Found {len(raw_mongo_result)} results:"]
            for i, doc in enumerate(raw_mongo_result[:10], 1):
                title = doc.get("title") or doc.get("name") or doc.get("_id")
                meta = []
                if "year" in doc:
                    meta.append(f"Year: {doc['year']}")
                if "imdb" in doc and isinstance(doc["imdb"], dict) and "rating" in doc["imdb"]:
                    meta.append(f"IMDb: {doc['imdb']['rating']}")
                if "genres" in doc:
                    g = doc["genres"]
                    meta.append(f"Genres: {', '.join(g) if isinstance(g, list) else g}")
                meta_str = f" ({', '.join(meta)})" if meta else ""
                lines.append(f"{i}. {title}{meta_str}")
            full_response = "\n".join(lines)

        # 5. Return formatted response
        # Keep both the raw MongoDB data and the natural language response
        return {
            "query_result": full_response,  # Natural language response
            "raw_mongo_result": state.get("raw_mongo_result"),  # Preserve raw data
        }

    except Exception as e:
        logger.exception(f"❌ Output parser error: {e}")
        return {"query_result": f"Error formatting response: {str(e)}"}

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Router Node - Conditional Routing Logic

This node decides the next step based on:
- Query execution success/failure
- Error types (fatal vs recoverable)
- Iteration count (max retries)
"""

import logging
from typing import Dict, Any, Literal

logger = logging.getLogger(__name__)


def route_to_decide(state: Dict[str, Any]) -> Literal["success", "error", "fatal_error"]:
    """
    Route to next node based on execution result

    Routing logic:
    - No error → "success" → Go to output_parser
    - No query generated → "fatal_error" → END
    - MCP connectivity error → "fatal_error" → END
    - Query syntax error + iterations < 1 → "error" → Go to query_refiner
    - iterations >= 1 → "fatal_error" → END (max retries)

    Args:
        state: Current agent state

    Returns:
        Route decision: "success", "error", or "fatal_error"
    """
    error = state.get("error", "")
    iterations = state.get("iterations", 0)

    logger.info(f"🔀 Router: error='{error[:50] if error else 'none'}', iterations={iterations}")

    # Check for no query generated
    if "No SQL found" in error or "No MongoDB query found" in error:
        logger.error("No MongoDB query was generated, terminating")
        return "fatal_error"

    # No error - success path
    if error == "":
        logger.info("✅ Route: success → output_parser")
        return "success"

    # Check for MCP connectivity errors (fatal)
    mcp_connectivity_errors = [
        "No valid content in MCP result",
        "Failed to connect to",
        "Connection error",
        "HTTP 401",
        "HTTP 403",
        "HTTP 500",
        "Timeout",
        "Authentication failed",
    ]

    if any(mcp_error in error for mcp_error in mcp_connectivity_errors):
        logger.error(f"MCP connectivity error detected: {error}. Treating as fatal")
        return "fatal_error"

    # Check iteration count (max 1 retry)
    if iterations >= 1 or "fatal_error" in error.lower():
        logger.error(f"Max retries reached (iterations={iterations}), terminating")
        return "fatal_error"

    # Recoverable error - try to refine
    logger.info("⚠️ Route: error → query_refiner (retry)")
    return "error"

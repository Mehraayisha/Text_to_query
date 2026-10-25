# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
MCP (Model Context Protocol) client for MongoDB

Handles:
- MongoDB query execution via MCP protocol
- OAuth2 authentication with token caching
- Connection pooling
"""

import logging
import requests
from typing import Dict, Any, Optional

from mongodb_agent.config import Config
from mongodb_agent.utils.token_cache import TokenCache

logger = logging.getLogger(__name__)


class MCPClient:
    """MongoDB MCP protocol client"""

    def __init__(self, config: Config):
        self.endpoint = config.mongodb_mcp_endpoint
        self.token_cache = None

        if config.enable_token_cache and config.mongodb_oauth_token_url:
            logger.info(f"Initializing token cache (TTL: {config.token_cache_ttl}s)")
            self.token_cache = TokenCache(
                token_url=config.mongodb_oauth_token_url,
                client_id=config.mongodb_client_id,
                client_secret=config.mongodb_client_secret,
                ttl_seconds=config.token_cache_ttl,
            )

        logger.info(f"MCP client initialized: {self.endpoint}")

    def execute_query(
        self, aggregation_pipeline: str, db_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute MongoDB aggregation pipeline via MCP

        Args:
            aggregation_pipeline: MongoDB aggregation pipeline (string)
            db_details: Database connection details (dbName, userName, etc.)

        Returns:
            Dict with keys: success, data, error
        """
        try:
            # Get authentication token
            headers = {"Content-Type": "application/json"}
            if self.token_cache:
                token = self.token_cache.get_token()
                headers["Authorization"] = f"Bearer {token}"

            # Prepare MCP request
            # Extract parameters with proper fallback handling (check for truthy values)
            db_name = (
                db_details.get("dbName")
                or db_details.get("db_name")
                or db_details.get("database")
                or ""
            )
            user_name = (
                db_details.get("userName")
                or db_details.get("schema_name")
                or db_details.get("schema")
                or ""
            )
            app_name = (
                db_details.get("applicationName")
                or db_details.get("app_name")
                or "MongoDB-Agent-REST-API"
            )

            payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": "execute_query",
                    "dbName": db_name,
                    "userName": user_name,
                    "applicationName": app_name,
                    "arguments": {"query": aggregation_pipeline, "parameters": {}},
                },
            }

            logger.info(f"Executing MCP query: {aggregation_pipeline[:100]}...")

            # Log MCP Request
            logger.info("=" * 80)
            logger.info("📤 MCP REQUEST")
            logger.info(f"Endpoint: {self.endpoint}")
            logger.info(f"Database: {payload['params']['dbName']}")
            logger.info(f"Schema: {payload['params']['userName']}")
            logger.info(f"Application: {payload['params']['applicationName']}")
            logger.info(f"Query: {aggregation_pipeline}")
            logger.info("")
            logger.info("Complete MCP Payload:")
            import json

            logger.info(json.dumps(payload, indent=2))
            logger.info("=" * 80)

            # Execute request
            response = requests.post(self.endpoint, json=payload, headers=headers, timeout=30)

            # Log MCP Response
            logger.info("=" * 80)
            logger.info("📥 MCP RESPONSE")
            logger.info(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                logger.info(f"Success: True")
                logger.info(f"Result Keys: {list(result.keys())}")
                if "result" in result:
                    result_data = result.get("result", [])
                    if isinstance(result_data, list):
                        logger.info(f"Documents Returned: {len(result_data)}")
                        if len(result_data) > 0:
                            logger.info(
                                f"Sample Document Keys: {list(result_data[0].keys()) if result_data else []}"
                            )
                    else:
                        logger.info(f"Result Type: {type(result_data)}")

                # Log complete response for debugging
                logger.info("")
                logger.info("Complete MCP Response:")
                logger.info(json.dumps(result, indent=2, default=str)[:2000])  # First 2000 chars
                logger.info("=" * 80)
                return {"success": True, "data": result.get("result", result), "error": None}
            else:
                error_msg = f"MCP request failed: HTTP {response.status_code}"
                logger.error(f"Error: {error_msg}")
                logger.error(f"Response: {response.text[:500]}")
                logger.info("=" * 80)
                return {"success": False, "data": None, "error": error_msg}

        except Exception as e:
            logger.exception(f"MCP client error: {e}")
            return {"success": False, "data": None, "error": str(e)}


def get_mcp_client(config: Config) -> MCPClient:
    """Get MCP client instance"""
    return MCPClient(config)

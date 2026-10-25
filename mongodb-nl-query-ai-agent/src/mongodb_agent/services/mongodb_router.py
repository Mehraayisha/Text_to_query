# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
MongoDB Router - Routes queries to MCP or Direct client

Provides a unified interface for MongoDB queries regardless of connection type.
Automatically selects the appropriate client based on configuration.
"""

import logging
from typing import Dict, Any

from mongodb_agent.config import Config

logger = logging.getLogger(__name__)


class MongoDBRouter:
    """Routes MongoDB queries to appropriate client (MCP or Direct)"""

    def __init__(self, config: Config):
        self.config = config
        self.connection_type = config.mongodb_connection_type
        self.client = None

        logger.info(f"🔧 Initializing MongoDB Router: {self.connection_type.upper()} mode")

        if self.connection_type == "direct":
            from mongodb_agent.services.direct_client import get_direct_client

            self.client = get_direct_client(config)
            logger.info("✅ Using Direct MongoDB connection (PyMongo)")
        else:
            from mongodb_agent.services.mcp_client import get_mcp_client

            self.client = get_mcp_client(config)
            logger.info("✅ Using MCP protocol connection")

    def execute_query(
        self, aggregation_pipeline: str, db_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute MongoDB query via configured client

        Args:
            aggregation_pipeline: MongoDB aggregation pipeline (string or list)
            db_details: Database/collection connection details
                For MCP: dbName, userName, applicationName
                For Direct: collection (collection name)

        Returns:
            Dict with keys:
                - success (bool): Query execution status
                - data (list): Query results (if successful)
                - error (str): Error message (if failed)
        """
        if not self.client:
            return {"success": False, "data": None, "error": "MongoDB client not initialized"}

        return self.client.execute_query(aggregation_pipeline, db_details)

    def close(self):
        """Close MongoDB connection if applicable"""
        if self.client and hasattr(self.client, "close"):
            self.client.close()
            logger.info("MongoDB connection closed")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False


def get_mongodb_client(config: Config) -> MongoDBRouter:
    """
    Get MongoDB client (MCP or Direct based on config)

    Args:
        config: MongoDB Agent configuration

    Returns:
        MongoDBRouter instance configured for MCP or Direct connection

    Example:
        >>> config = Config.from_env()
        >>> client = get_mongodb_client(config)
        >>> result = client.execute_query(
        ...     "[{'$match': {'status': 'active'}}]",
        ...     {"collection": "users"}
        ... )
    """
    return MongoDBRouter(config)

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
MongoDB Router - Routes queries directly to PyMongo Direct Client
"""

import logging
from typing import Dict, Any

from mongodb.config import Config
from mongodb.services.direct_client import get_direct_client

logger = logging.getLogger(__name__)


class MongoDBRouter:
    """Direct PyMongo Client Router"""

    def __init__(self, config: Config):
        self.config = config
        logger.info("🔧 Initializing MongoDB Router: DIRECT mode (PyMongo)")
        self.client = get_direct_client(config)
        logger.info("✅ Using Direct MongoDB connection (PyMongo)")

    def execute_query(
        self, aggregation_pipeline: str, db_details: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute MongoDB query via configured client
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
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def get_mongodb_client(config: Config) -> MongoDBRouter:
    """Get direct MongoDB client instance"""
    return MongoDBRouter(config)

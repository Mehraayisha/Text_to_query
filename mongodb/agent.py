# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
MongoDB Agent - Main entry point

Provides the MongoDBAgent class for natural language to MongoDB query conversion.

Example:
    from mongodb import MongoDBAgent, Config

    config = Config.from_env()
    agent = MongoDBAgent(config)

    result = agent.query(
        question="How many orders were shipped last month?",
        yaml_file_name="OrdersCollection",
        db_details={"database": "ESM", "schema": "Orders"}
    )

    print(result["query_result"])
"""

import logging
from typing import Optional, Dict, Any

from mongodb.config import Config
from mongodb.graph import build_graph
from mongodb.state import InputSchema, ResponseSchema


class MongoDBAgent:
    """
    MongoDB Agent for natural language query processing

    Converts natural language questions into MongoDB aggregation pipelines
    using semantic models and LLM reasoning.
    """

    def __init__(self, config: Config):
        """
        Initialize MongoDB Agent

        Args:
            config: Configuration object
        """
        self.config = config
        self.config.validate()

        # Set up logging
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format="%(asctime)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

        # Build the LangGraph
        self.logger.info(f"Building MongoDB agent with {config.llm_provider} LLM")
        self.compiled_graph = build_graph(config)
        self.logger.info("MongoDB agent initialized successfully")

    def query(
        self, question: str, yaml_file_name: Optional[str] = None, db_details: Optional[Dict[str, Any]] = None
    ) -> ResponseSchema:
        """
        Execute a natural language query

        Args:
            question: Natural language question
            yaml_file_name: Semantic model file name (e.g., "OrdersCollection.yaml")
            db_details: Database connection details (database, schema, etc.)

        Returns:
            ResponseSchema with query_result, sql_query, error, etc.

        Example:
            result = agent.query(
                question="Show me top 5 orders from last week",
                yaml_file_name="OrdersCollection.yaml",
                db_details={"database": "ESM", "schema": "Orders"}
            )
        """
        if db_details is None:
            db_details = {}

        if not yaml_file_name:
            yaml_file_name = f"{self.config.mongodb_database or 'sample_mflix'}.json"

        # Prepare input
        input_data: InputSchema = {
            "question": question,
            "yaml_file_name": yaml_file_name,
            "db_details": db_details,
        }

        self.logger.info(f"Processing query: {question[:100]}...")

        try:
            # Execute the graph
            result = self.compiled_graph.invoke(input_data)

            # Extract response
            response: ResponseSchema = {
                "query_result": result.get("query_result", ""),
                "raw_mongo_result": result.get("raw_mongo_result"),  # Include raw data
                "sql_query": result.get("sql_query"),
                "aggregation_pipeline": result.get("aggregation_pipeline"),
                "collection_name": result.get("collection_name"),
                "error": result.get("error"),
            }

            if response["error"]:
                self.logger.error(f"Query failed: {response['error']}")
            else:
                self.logger.info("Query executed successfully")

            return response

        except Exception as e:
            self.logger.exception(f"Unexpected error: {e}")
            return {
                "query_result": "",
                "error": f"Unexpected error: {str(e)}",
                "sql_query": None,
                "aggregation_pipeline": None,
                "collection_name": None,
            }

    def get_semantic_model(self, model_name: str) -> str:
        """
        Retrieve a semantic model YAML

        Args:
            model_name: Name of the semantic model

        Returns:
            YAML content as string
        """
        # This will be implemented to load from vector DB or local files
        from mongodb.semantic_models.loader import load_semantic_model

        return load_semantic_model(model_name, self.config)

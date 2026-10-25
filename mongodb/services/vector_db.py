# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Vector database abstraction

Supports:
- Weaviate
- Local YAML files
- Chroma (future)
- Pinecone (future)
"""

import logging
from typing import Optional, List, Dict, Any

from mongodb.config import Config

logger = logging.getLogger(__name__)


class VectorClient:
    """Abstract vector database client"""

    def search_semantic_model(self, file_name: str) -> Optional[Dict[str, Any]]:
        """
        Search for semantic model by file name

        Returns:
            Dict with keys: text, db_name, schema_name, app_name, db_type
        """
        raise NotImplementedError


class WeaviateClient(VectorClient):
    """Weaviate vector database client"""

    def __init__(self, config: Config):
        import weaviate
        from weaviate.classes.init import Auth

        logger.info(f"Connecting to Weaviate: {config.weaviate_url}")

        if config.weaviate_api_key:
            self.client = weaviate.connect_to_custom(
                http_host=config.weaviate_url.replace("http://", "").replace("https://", ""),
                http_port=443 if "https" in config.weaviate_url else 80,
                http_secure="https" in config.weaviate_url,
                auth_credentials=Auth.api_key(config.weaviate_api_key),
            )
        else:
            self.client = weaviate.connect_to_local(
                host=config.weaviate_url.replace("http://", "").split(":")[0],
                port=(
                    int(config.weaviate_url.split(":")[-1]) if ":" in config.weaviate_url else 8080
                ),
            )

        logger.info("Weaviate connected successfully")

    def search_semantic_model(self, file_name: str) -> Optional[Dict[str, Any]]:
        """Search SemanticLayerCollection for semantic model"""
        from weaviate.classes.query import Filter

        collection = self.client.collections.get("SemanticLayerCollection")
        filter_condition = Filter.by_property("source").equal(file_name)

        response = collection.query.fetch_objects(
            filters=filter_condition,
            return_properties=["text", "db_name", "schema_name", "app_name", "db_type"],
        )

        if response.objects and len(response.objects) > 0:
            item = response.objects[0]
            return {
                "text": item.properties.get("text"),
                "db_name": item.properties.get("db_name"),
                "schema_name": item.properties.get("schema_name"),
                "app_name": item.properties.get("app_name"),
                "db_type": item.properties.get("db_type"),
            }

        return None


class LocalFileClient(VectorClient):
    """Local YAML file client (no vector DB)"""

    def __init__(self, config: Config):
        import os

        self.semantic_model_path = config.semantic_model_path
        logger.info(f"Using local semantic models from: {self.semantic_model_path}")

        if not os.path.exists(self.semantic_model_path):
            logger.warning(f"Semantic model path does not exist: {self.semantic_model_path}")

    def search_semantic_model(self, file_name: str) -> Optional[Dict[str, Any]]:
        """Load semantic model from local file"""
        import os
        import yaml

        # Try multiple file paths (supporting both .json and .yaml)
        module_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_name = file_name.replace(".yaml", "").replace(".yml", "").replace(".json", "")

        possible_paths = [
            os.path.join(self.semantic_model_path, file_name),
            os.path.join(self.semantic_model_path, f"{base_name}.json"),
            os.path.join(self.semantic_model_path, f"{base_name}.yaml"),
            os.path.join(module_dir, "semantic_models", file_name),
            os.path.join(module_dir, "semantic_models", f"{base_name}.json"),
            os.path.join(module_dir, "semantic_models", f"{base_name}.yaml"),
            os.path.join("semantic_models", file_name),
            os.path.join("semantic_models", f"{base_name}.json"),
        ]

        for file_path in possible_paths:
            if os.path.exists(file_path):
                logger.info(f"Loading semantic model from: {file_path}")
                try:
                    import json
                    with open(file_path, "r", encoding="utf-8") as f:
                        if file_path.endswith(".json"):
                            yaml_content = json.load(f)
                        else:
                            yaml_content = yaml.safe_load(f)
                except Exception:
                    with open(file_path, "r", encoding="utf-8") as f:
                        yaml_content = yaml.safe_load(f)

                # Extract metadata
                db_name = None
                schema_name = None
                db_type = "mongodb"

                if "collection_info" in yaml_content:
                    db_name = yaml_content["collection_info"].get("database")
                    schema_name = yaml_content["collection_info"].get("schema_name")

                return {
                    "text": yaml.dump(yaml_content),
                    "db_name": db_name,
                    "schema_name": schema_name,
                    "app_name": "GenAI-Agent",
                    "db_type": db_type,
                }

        logger.error(f"Semantic model not found: {file_name}")
        return None


def get_vector_client(config: Config) -> VectorClient:
    """
    Get vector database client

    Args:
        config: Configuration object

    Returns:
        VectorClient instance
    """
    if config.vector_db == "weaviate":
        return WeaviateClient(config)
    elif config.vector_db == "local":
        return LocalFileClient(config)
    else:
        raise ValueError(f"Unsupported vector DB: {config.vector_db}")

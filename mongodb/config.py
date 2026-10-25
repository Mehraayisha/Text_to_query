# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Configuration management for MongoDB Agent

Provides a flexible Config class that supports:
- Multiple LLM providers (Azure OpenAI, OpenAI, Anthropic)
- Multiple vector databases (Weaviate, local files, Chroma)
- MongoDB connection via MCP protocol
- OAuth2 token caching
- Environment-based configuration
"""

import os
from typing import Literal, Optional
from dataclasses import dataclass, field


@dataclass
class Config:
    """MongoDB Agent Configuration"""

    # LLM Provider Configuration
    llm_provider: Literal["azure", "openai", "anthropic", "local"] = "azure"
    azure_endpoint: Optional[str] = None
    azure_api_key: Optional[str] = None
    azure_deployment_name: str = "gpt-4o-mini"
    azure_api_version: str = "2024-02-15-preview"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: Optional[str] = None

    # Vector Database Configuration
    vector_db: Literal["weaviate", "local", "chroma", "pinecone"] = "local"
    weaviate_url: Optional[str] = None
    weaviate_api_key: Optional[str] = None

    # MongoDB Connection Configuration
    mongodb_connection_type: Literal["mcp", "direct"] = "mcp"

    # MongoDB MCP Configuration
    mongodb_mcp_endpoint: str = "http://localhost:3000/mongodb/query"
    mongodb_oauth_token_url: Optional[str] = None
    mongodb_client_id: Optional[str] = None
    mongodb_client_secret: Optional[str] = None

    # Direct MongoDB Configuration
    mongodb_uri: Optional[str] = None
    mongodb_database: Optional[str] = None

    # Semantic Model Configuration
    semantic_model_source: Literal["weaviate", "local_files", "s3", "git"] = "local_files"
    semantic_model_path: str = "./semantic_models"

    # Optimization Settings
    enable_token_cache: bool = True
    token_cache_ttl: int = 3000  # 50 minutes
    max_schema_fields: int = 30
    max_retry_attempts: int = 1

    # Feature Flags
    skip_conjur_auth: bool = True
    force_local_v2_files: bool = False

    # Logging
    log_level: str = "INFO"

    @classmethod
    def from_env(cls, env: str = "dev") -> "Config":
        """Load configuration from environment variables"""
        try:
            from dotenv import load_dotenv
            # Look for .env in current package root, current working dir, and parent dir
            pkg_root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
            if os.path.exists(pkg_root_env):
                load_dotenv(pkg_root_env)
            load_dotenv()
        except ImportError:
            pass
        return cls(
            llm_provider=os.getenv("LLM_PROVIDER", "azure"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini"),
            azure_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            openai_base_url=os.getenv("OPENAI_BASE_URL"),
            vector_db=os.getenv("VECTOR_DB", "local"),
            weaviate_url=os.getenv("WEAVIATE_URL"),
            weaviate_api_key=os.getenv("WEAVIATE_API_KEY"),
            mongodb_connection_type=os.getenv("MONGODB_CONNECTION_TYPE", "mcp"),
            mongodb_mcp_endpoint=os.getenv(
                "MONGODB_MCP_ENDPOINT", "http://localhost:3000/mongodb/query"
            ),
            mongodb_oauth_token_url=os.getenv("MONGODB_OAUTH_TOKEN_URL"),
            mongodb_client_id=os.getenv("MONGODB_CLIENT_ID"),
            mongodb_client_secret=os.getenv("MONGODB_CLIENT_SECRET"),
            mongodb_uri=os.getenv("MONGODB_URI"),
            mongodb_database=os.getenv("MONGODB_DATABASE"),
            semantic_model_source=os.getenv("SEMANTIC_MODEL_SOURCE", "local_files"),
            semantic_model_path=os.getenv("SEMANTIC_MODEL_PATH", "mongodb/semantic_models" if os.path.exists("mongodb/semantic_models") else "./semantic_models"),
            enable_token_cache=os.getenv("ENABLE_TOKEN_CACHE", "true").lower() == "true",
            token_cache_ttl=int(os.getenv("TOKEN_CACHE_TTL", "3000")),
            max_schema_fields=int(os.getenv("MAX_SCHEMA_FIELDS", "30")),
            skip_conjur_auth=os.getenv("SKIP_CONJUR_AUTH", "true").lower() == "true",
            force_local_v2_files=os.getenv("FORCE_LOCAL_V2_FILES", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    @classmethod
    def from_legacy_env(cls, env: str) -> "Config":
        """
        Convert legacy mongodb_structure_agent environment to new Config
        Maintains backward compatibility with existing deployments
        """
        return cls.from_env(env)

    def validate(self) -> None:
        """Validate configuration"""
        if self.llm_provider == "azure":
            if not self.azure_endpoint or not self.azure_api_key:
                raise ValueError(
                    "Azure OpenAI requires AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY"
                )

        if self.llm_provider == "openai":
            if not self.openai_api_key:
                raise ValueError("OpenAI requires OPENAI_API_KEY")

        if self.vector_db == "weaviate" and not self.weaviate_url:
            raise ValueError("Weaviate requires WEAVIATE_URL")

        if self.mongodb_connection_type == "direct":
            if not self.mongodb_uri:
                raise ValueError("Direct MongoDB connection requires MONGODB_URI")
            if not self.mongodb_database:
                raise ValueError("Direct MongoDB connection requires MONGODB_DATABASE")

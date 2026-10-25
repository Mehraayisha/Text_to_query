# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
MongoDB LangGraph Agent - Natural Language to MongoDB Query

A reusable package for converting natural language queries to MongoDB aggregation
pipelines using LangGraph, semantic models, and LLM agents.

Public API:
- MongoDBAgent: Main agent class
- Config: Configuration management
- build_graph: StateGraph builder (for advanced usage)
- SchemaDiscoverer: Automatic schema inference & YAML generation
- MongoDBDocumentAdapter: Unified Semantic Layer adapter
"""

from mongodb_agent.agent import MongoDBAgent
from mongodb_agent.config import Config
from mongodb_agent.graph import build_graph
from mongodb_agent.state import AgentState, InputSchema, ResponseSchema
from mongodb_agent.schema_discovery import SchemaDiscoverer
try:
    from mongodb_agent.adapter import MongoDBDocumentAdapter, MongoDBAdapter
except ImportError:
    pass

__version__ = "0.1.0"
__all__ = [
    "MongoDBAgent",
    "Config",
    "build_graph",
    "AgentState",
    "InputSchema",
    "ResponseSchema",
    "SchemaDiscoverer",
    "MongoDBDocumentAdapter",
    "MongoDBAdapter",
]

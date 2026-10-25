# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
State definitions for MongoDB Agent

Defines the TypedDict schemas for:
- AgentState: Internal state passed between nodes
- InputSchema: User input to the agent
- ResponseSchema: Agent output
"""

from typing import Optional, TypedDict
from typing_extensions import Annotated
from langchain_core.messages import AIMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Internal state for MongoDB Agent graph"""

    file_name: str
    messages: Annotated[list[AIMessage], add_messages]
    iterations: int
    raw_extracted_schema_dict: Optional[dict]
    schema: str
    verified_queries: str
    custom_instructions: str
    fk_str: str
    content_yaml: str
    metrics: str
    yaml_content: str
    db_details: dict
    sql_query: Optional[str]  # MongoDB aggregation pipeline (string)
    aggregation_pipeline: Optional[list]  # Parsed pipeline
    collection_name: Optional[str]
    database_name: Optional[str]
    query_result: Optional[str]
    raw_mongo_result: Optional[list]  # Actual MongoDB results data
    error: Optional[str]
    exception_class: Optional[str]


class InputSchema(TypedDict):
    """User input schema"""

    question: str
    yaml_file_name: str
    db_details: dict


class ResponseSchema(TypedDict, total=False):
    """Agent response schema"""

    query_result: str
    raw_mongo_result: Optional[list]  # Actual MongoDB results data
    error: Optional[str]
    sql_query: Optional[str]  # MongoDB pipeline
    aggregation_pipeline: Optional[list]
    collection_name: Optional[str]

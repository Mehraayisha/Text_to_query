# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Graph builder for MongoDB Agent

Constructs the LangGraph StateGraph with nodes and edges.
This is extracted from mongodb_structure_agent/utils/nodes.py for reusability.
"""

import logging
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage

from mongodb_agent.config import Config
from mongodb_agent.state import AgentState, InputSchema, ResponseSchema
from mongodb_agent.services.llm import get_llm
from mongodb_agent.services.vector_db import get_vector_client
from mongodb_agent.services.mongodb_router import get_mongodb_client

# Import node modules directly (bypass __init__.py) to set globals first
import sys
import mongodb_agent.nodes.selector
import mongodb_agent.nodes.query_executor
import mongodb_agent.nodes.query_refiner
import mongodb_agent.nodes.output_parser
import mongodb_agent.nodes.router

selector_module = sys.modules["mongodb_agent.nodes.selector"]
executor_module = sys.modules["mongodb_agent.nodes.query_executor"]
refiner_module = sys.modules["mongodb_agent.nodes.query_refiner"]
parser_module = sys.modules["mongodb_agent.nodes.output_parser"]
router_module = sys.modules["mongodb_agent.nodes.router"]


def build_graph(config: Config):
    """
    Build the MongoDB Agent StateGraph

    Flow:
        START → ingress → selector → query_executor → [route] → output_parser → END
                                              ↓
                                      [error] → query_refiner → (retry executor)
                                              ↓
                                      [fatal_error] → END

    Args:
        config: Configuration object

    Returns:
        Compiled StateGraph
    """
    logger = logging.getLogger(__name__)
    logger.info(
        f"Building graph with config: vector_db={config.vector_db}, llm={config.llm_provider}"
    )

    # Initialize global services (will be accessible in nodes via globals)
    llm = get_llm(config)
    vector_client = get_vector_client(config)
    mongodb_client = get_mongodb_client(config)

    # Set global variables in node modules
    selector_module.llm = llm
    selector_module.vector_client = vector_client
    selector_module.config = config

    executor_module.mongodb_client = mongodb_client
    executor_module.config = config

    refiner_module.llm = llm
    refiner_module.config = config

    parser_module.llm = llm
    parser_module.config = config

    logger.info(
        f"DEBUG: Set selector_module.config.semantic_model_path = {config.semantic_model_path}"
    )

    # Build StateGraph
    builder = StateGraph(
        state_schema=AgentState,
        context_schema=None,
        input_schema=InputSchema,
        output_schema=ResponseSchema,
    )

    def ingress(inputs: InputSchema) -> AgentState:
        """Initialize state from user input"""
        logger.info(f"Ingress: question={inputs['question'][:50]}...")
        return {
            "messages": [HumanMessage(content=inputs["question"])],
            "yaml_file_name": inputs.get("yaml_file_name", ""),
            "file_name": inputs.get("yaml_file_name", ""),
            "yaml_content": "",
            "db_details": inputs.get("db_details", {}),
            "iterations": 0,
            "schema": "",
            "raw_extracted_schema_dict": None,
            "content_yaml": "",
            "metrics": "",
            "verified_queries": "",
            "custom_instructions": "",
            "fk_str": "",
            "sql_query": None,
            "query_result": None,
            "error": "",
            "exception_class": "",
        }

    # Add nodes
    builder.add_node("ingress", ingress)
    builder.add_node("selector", selector_module.selector)
    builder.add_node("query_executor", executor_module.query_executor)
    builder.add_node("query_refiner", refiner_module.query_refiner)
    builder.add_node("output_parser", parser_module.output_parser)

    # Add edges
    builder.add_edge(START, "ingress")
    builder.add_edge("ingress", "selector")
    builder.add_edge("selector", "query_executor")  # Simplified flow: skip query_builder

    # Conditional routing from query_executor
    builder.add_conditional_edges(
        "query_executor",
        router_module.route_to_decide,
        {"success": "output_parser", "error": "query_refiner", "fatal_error": END},
    )

    builder.add_edge("query_refiner", "query_executor")
    builder.add_edge("output_parser", END)
    builder.set_entry_point("ingress")

    # Compile
    try:
        compiled_graph = builder.compile()
        logger.info("Graph compiled successfully")
        return compiled_graph
    except Exception as e:
        logger.error(f"Failed to build graph: {e}")
        raise

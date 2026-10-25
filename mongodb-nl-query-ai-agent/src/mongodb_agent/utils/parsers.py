# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Parser utilities for MongoDB query processing.

Provides functions for parsing JSON responses, extracting MongoDB queries,
and handling various query formats.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Constants for MongoDB operators
COUNT_OPERATOR = "$count"
LIMIT_OPERATOR = "$limit"
MATCH_OPERATOR = "$match"


def parse_json(input_string: str) -> Optional[Dict[str, Any]]:
    """
    Safely parse JSON from a string, handling code blocks and malformed JSON.

    Args:
        input_string: String potentially containing JSON

    Returns:
        Parsed JSON dictionary or None if parsing fails
    """
    # Try to find JSON code block first
    json_pattern = r"```json(.*?)```"
    json_matches = []

    for match in re.finditer(json_pattern, input_string, re.DOTALL):
        json_matches.append(match.group(1).strip())

    if json_matches:
        try:
            # Parse the last JSON match (most recent)
            return json.loads(json_matches[-1])
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON from code block: {e}")

    # Fallback: try parsing the whole string
    try:
        return json.loads(input_string)
    except json.JSONDecodeError:
        logger.debug("Could not parse input as JSON")
        return None


def parse_mongodb_query_from_string(
    input_string: str, yaml_content: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Parse MongoDB query response from JSON format.
    Expected format: ```json {...} ```
    Returns: Dictionary with mongodb_query, aggregation_pipeline, collection_name, etc.

    Args:
        input_string: The response string containing JSON
        yaml_content: Optional YAML content for YAML-driven join fixing

    Returns:
        Dictionary with query components
    """
    # Try to find JSON code block first
    json_pattern = r"```json(.*?)```"
    json_matches = []

    for match in re.finditer(json_pattern, input_string, re.DOTALL):
        json_matches.append(match.group(1).strip())

    if json_matches:
        try:
            # Parse the last JSON match
            mongodb_response = json.loads(json_matches[-1])

            # Extract MongoDB query components
            mongodb_query = mongodb_response.get("mongodb_query", "")

            # TODO: APPLY JOIN FIXES (if yaml_content has business_rules)
            # This will be added when we implement the join fixing logic

            # Initialize defaults
            aggregation_pipeline = []
            collection_name = "default_collection"
            database_name = "default_database"

            # NEW FORMAT: mongodb_query directly contains aggregation pipeline array
            if isinstance(mongodb_query, list):
                logger.debug("Detected new aggregation pipeline format")
                aggregation_pipeline = mongodb_query

                # Extract collection name from entities
                entities = mongodb_response.get("entities", [])
                for entity in entities:
                    if entity.get("type") == "collection":
                        collection_name = entity.get("name", "default_collection")
                        break

            # LEGACY FORMAT: Extract from db.collection.aggregate() string
            elif isinstance(mongodb_query, str) and mongodb_query:
                logger.warning("Detected legacy string format, converting to aggregation pipeline")

                # Extract collection name from query
                if "db." in mongodb_query:
                    # Pattern: db.collection.method(...)
                    collection_match = re.search(r"db\.([^.]+)\.", mongodb_query)
                    if collection_match:
                        collection_name = collection_match.group(1)

                # Convert simple queries to aggregation pipelines
                if ".countDocuments()" in mongodb_query:
                    # Convert countDocuments() to aggregation pipeline
                    aggregation_pipeline = [{COUNT_OPERATOR: "total"}]
                    logger.debug(f"Converted countDocuments() to: {aggregation_pipeline}")

                elif ".find(" in mongodb_query and ".limit(" in mongodb_query:
                    # Convert find().limit() to aggregation pipeline
                    # Extract filter from find()
                    find_match = re.search(r"\.find\(({.*?})\)", mongodb_query, re.DOTALL)
                    limit_match = re.search(r"\.limit\((\d+)\)", mongodb_query)

                    if find_match and limit_match:
                        try:
                            filter_obj = json.loads(find_match.group(1))
                            limit_num = int(limit_match.group(1))
                            aggregation_pipeline = [
                                {MATCH_OPERATOR: filter_obj},
                                {LIMIT_OPERATOR: limit_num},
                            ]
                            logger.debug(f"Converted find().limit() to: {aggregation_pipeline}")
                        except (ValueError, json.JSONDecodeError):
                            aggregation_pipeline = [{LIMIT_OPERATOR: 100}]

                elif ".aggregate(" in mongodb_query:
                    # Extract the pipeline array from the query
                    pipeline_match = re.search(r"\.aggregate\(([^\]]*)\]", mongodb_query, re.DOTALL)
                    if pipeline_match:
                        try:
                            # Extract just the array content
                            pipeline_text = "[" + pipeline_match.group(1) + "]"
                            aggregation_pipeline = json.loads(pipeline_text)
                            logger.debug(f"Extracted aggregation pipeline: {aggregation_pipeline}")
                        except json.JSONDecodeError:
                            logger.warning("Could not parse aggregation pipeline from query")
                            aggregation_pipeline = [{LIMIT_OPERATOR: 100}]
                else:
                    # Default to simple count for unsupported queries
                    logger.warning("Unsupported query format, defaulting to count")
                    aggregation_pipeline = [{COUNT_OPERATOR: "total"}]

            else:
                logger.error("No valid MongoDB query found, using default count")
                aggregation_pipeline = [{COUNT_OPERATOR: "total"}]

            return {
                "mongodb_query": mongodb_query,
                "aggregation_pipeline": aggregation_pipeline,
                "collection_name": collection_name,
                "database_name": database_name,
                "parameters": mongodb_response.get("parameters", {}),
                "entities": mongodb_response.get("entities", []),
                "query_type": mongodb_response.get("query_type", "aggregate"),
            }

        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON response: {e}")
            return {
                "mongodb_query": "error: Invalid JSON in response",
                "aggregation_pipeline": [{COUNT_OPERATOR: "total"}],  # Default fallback
                "collection_name": "default_collection",
                "database_name": "default_database",
                "parameters": {},
                "entities": [],
                "query_type": "error",
            }
    else:
        # Fallback: try to extract raw MongoDB query without JSON wrapper
        mongodb_pattern = r"db\.[^.]+\.(find|aggregate|updateOne|deleteOne|insertOne)\([^)]*\)"
        mongodb_matches = re.findall(mongodb_pattern, input_string)

        if mongodb_matches:
            # Extract the full query
            full_query_match = re.search(r"(db\.[^.]+\.[^;]+)", input_string)
            if full_query_match:
                return {
                    "mongodb_query": full_query_match.group(1),
                    "aggregation_pipeline": [],
                    "collection_name": "default_collection",
                    "database_name": "default_database",
                    "parameters": {},
                    "entities": [],
                    "query_type": "find",
                }

        return {
            "mongodb_query": "error: No MongoDB query found in input string",
            "aggregation_pipeline": [],
            "collection_name": "default_collection",
            "database_name": "default_database",
            "parameters": {},
            "entities": [],
            "query_type": "error",
        }


def extract_array_fields(fields: Dict[str, Any]) -> List[str]:
    """
    Extract array field paths from collection fields.
    These fields require $unwind in the aggregation pipeline.

    Args:
        fields: Dictionary of field definitions

    Returns:
        List of array field paths
    """
    array_fields = []

    for field_name, field_info in fields.items():
        if not isinstance(field_info, dict):
            continue

        # Check data type
        data_type = field_info.get("data_type", "").lower()
        if "array" in data_type or data_type == "list":
            # Use nested_path if available, otherwise field name
            path = field_info.get("nested_path", field_info.get("path", field_name))
            array_fields.append(path)

    logger.debug(f"Identified {len(array_fields)} array fields: {array_fields}")
    return array_fields


def format_query_for_display(aggregation_pipeline: List[Dict[str, Any]]) -> str:
    """
    Format aggregation pipeline for user-friendly display.

    Args:
        aggregation_pipeline: MongoDB aggregation pipeline

    Returns:
        Formatted string representation
    """
    try:
        return json.dumps(aggregation_pipeline, indent=2)
    except (TypeError, ValueError):
        return str(aggregation_pipeline)


def validate_aggregation_pipeline(pipeline: List[Dict[str, Any]]) -> bool:
    """
    Validate that an aggregation pipeline is well-formed.

    Args:
        pipeline: MongoDB aggregation pipeline

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(pipeline, list):
        logger.error(f"Pipeline must be a list, got {type(pipeline)}")
        return False

    if len(pipeline) == 0:
        logger.warning("Pipeline is empty")
        return False

    # Check that each stage is a dictionary with one key (the stage operator)
    for i, stage in enumerate(pipeline):
        if not isinstance(stage, dict):
            logger.error(f"Stage {i} must be a dict, got {type(stage)}")
            return False

        if len(stage) != 1:
            logger.warning(f"Stage {i} should have exactly one operator, has {len(stage)}")

        # Check for valid stage operators (starts with $)
        for key in stage.keys():
            if not key.startswith("$"):
                logger.error(f"Stage {i} operator '{key}' must start with $")
                return False

    return True

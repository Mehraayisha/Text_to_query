# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Schema retrieval and MongoDB query generation node.

This node:
1. Retrieves semantic model from vector DB or local YAML file
2. Parses YAML content (supports 3 formats)
3. Optimizes schema fields based on user query (max 30 fields)
4. Identifies array fields requiring $unwind
5. Builds LLM prompt with context
6. Generates MongoDB aggregation pipeline
7. Parses and validates the response

Extracted from mongodb_structure_agent/utils/nodes.py lines 63-400
"""

import os
import logging
import json
import yaml
from typing import Dict, Any
from langchain_core.messages import AIMessage

from mongodb_agent.state import AgentState
from mongodb_agent.semantic_models import process_semantic_model
from mongodb_agent.prompts import build_selector_prompt
from mongodb_agent.utils.parsers import parse_json, extract_array_fields

# Global instances (set by build_graph)
llm = None
vector_client = None
config = None

logger = logging.getLogger(__name__)


def selector(state: AgentState) -> Dict[str, Any]:
    """
    Retrieve semantic model and generate MongoDB query.

    Args:
        state: Current agent state containing messages, yaml_file_name, db_details

    Returns:
        Updated state with sql_query, schema, relationships, etc.
    """
    logger.info("Executing selector node...")

    try:
        # Extract user query from messages
        user_query = ""
        messages = state.get("messages", [])
        if messages and len(messages) > 0:
            first_message = messages[0]
            if hasattr(first_message, "content"):
                user_query = first_message.content
            elif isinstance(first_message, dict):
                user_query = first_message.get("content", "")
            else:
                user_query = str(first_message)

        logger.info(f"User query: '{user_query[:100]}...'")

        # Initialize db_details
        db_details = state.get("db_details", {})
        yaml_file_name = state.get("file_name", "") or state.get("yaml_file_name", "")  # AgentState uses 'file_name'

        if not yaml_file_name:
            default_db = getattr(config, "mongodb_database", None) or db_details.get("db_name") or db_details.get("dbName") or "sample_mflix"
            yaml_file_name = f"{default_db}.yaml"
            logger.info(f"No yaml_file_name provided, defaulting to: {yaml_file_name}")

        logger.info(f"DEBUG: yaml_file_name from state = '{yaml_file_name}'")
        logger.info(f"DEBUG: config object = {config}")
        logger.info(
            f"DEBUG: config.semantic_model_path = {getattr(config, 'semantic_model_path', 'NOT FOUND')}"
        )

        # Step 1: Retrieve semantic model (from vector DB or local file)
        yaml_content = None
        text = ""

        # Try vector DB first if available
        if vector_client and yaml_file_name:
            try:
                logger.info(f"Querying vector DB for: {yaml_file_name}")
                results = vector_client.search(
                    query=yaml_file_name, filters={"source": yaml_file_name}
                )

                if results and len(results) > 0:
                    text = results[0].get("text", "")

                    # Extract db details from vector DB result
                    db_name = results[0].get("db_name")
                    schema_name = results[0].get("schema_name")
                    app_name = results[0].get("app_name")
                    db_type = results[0].get("db_type", "mongodb")

                    if db_name or schema_name:
                        db_details.update(
                            {
                                "db_name": db_name,
                                "schema_name": schema_name,
                                "app_name": app_name or "GenAI-Agent",
                                "db_type": db_type,
                            }
                        )

                    logger.info(f"Retrieved {len(text)} characters from vector DB")
                    logger.info(f"DB Details: {db_details}")
            except Exception as e:
                logger.warning(f"Vector DB query failed: {e}, falling back to local file")

        # Fallback to local file if no vector DB result
        if not text or text.strip() == "":
            if yaml_file_name:
                logger.info(f"Loading semantic model from local file: {yaml_file_name}")

                # Try multiple path resolution strategies (prioritizing JSON, with YAML fallback)
                cwd = os.getcwd()
                semantic_model_dir = getattr(config, "semantic_model_path", "semantic_models")

                candidates = []
                if yaml_file_name.endswith(".yaml"):
                    candidates = [yaml_file_name.replace(".yaml", ".json"), yaml_file_name]
                elif yaml_file_name.endswith(".yml"):
                    candidates = [yaml_file_name.replace(".yml", ".json"), yaml_file_name]
                elif yaml_file_name.endswith(".json"):
                    candidates = [yaml_file_name, yaml_file_name.replace(".json", ".yaml")]
                else:
                    candidates = [f"{yaml_file_name}.json", f"{yaml_file_name}.yaml", yaml_file_name]

                possible_paths = []
                for cand in candidates:
                    possible_paths.extend([
                        cand,
                        os.path.join(cwd, "semantic_models", cand),
                        os.path.join(cwd, cand),
                        os.path.join(semantic_model_dir, cand),
                    ])

                # Find the first existing file
                resolved_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        resolved_path = path
                        logger.info(f"✅ Found semantic model file at: {resolved_path}")
                        break

                if not resolved_path:
                    # Attempt automatic schema discovery
                    try:
                        logger.info(f"Model file '{yaml_file_name}' not found. Attempting automatic schema discovery...")
                        from mongodb_agent.schema_discovery import SchemaDiscoverer
                        discoverer = SchemaDiscoverer(config=config)
                        # Default auto-discovery target is .json
                        target_out = candidates[0] if candidates else yaml_file_name
                        resolved_path = discoverer.discover_and_save(output_filename=target_out)
                        logger.info(f"Auto-discovery succeeded: {resolved_path}")
                    except Exception as disc_err:
                        logger.warning(f"Auto-discovery fallback failed: {disc_err}")

                if resolved_path:
                    with open(resolved_path, "r", encoding="utf-8") as f:
                        text = f.read()
                    logger.info(f"Loaded {len(text)} characters from file")
                else:
                    raise FileNotFoundError(
                        f"Semantic model file not found: {yaml_file_name}\n"
                        f"Searched in:\n  - {cwd}/semantic_models/\n  - {cwd}/\n  - {semantic_model_dir}/"
                    )
            else:
                raise ValueError("No yaml_file_name provided")

        # Parse JSON / YAML content
        try:
            yaml_content = json.loads(text)
        except Exception:
            yaml_content = yaml.safe_load(text)
        logger.info(f"Parsed YAML content type: {type(yaml_content)}")

        # Step 2: Extract database details from YAML if available
        if isinstance(yaml_content, dict):
            yaml_db_name = None
            yaml_schema_name = None
            yaml_app_name = None
            yaml_db_type = "mongodb"

            # Format 1: MongoDB semantic model format
            if "database" in yaml_content and "schema" in yaml_content:
                yaml_db_name = yaml_content.get("database")
                yaml_schema_name = yaml_content.get("schema")
                yaml_db_type = "mongodb"
                logger.debug(
                    f"Detected MongoDB format: db={yaml_db_name}, schema={yaml_schema_name}"
                )

            # Format 1.5: MongoDB semantic model with collection_info
            elif "collection_info" in yaml_content:
                collection_info = yaml_content["collection_info"]
                if isinstance(collection_info, dict):
                    yaml_db_name = collection_info.get("database")
                    yaml_schema_name = collection_info.get("schema_name")
                    yaml_db_type = "mongodb"
                    logger.debug(f"Detected MongoDB collection_info format: db={yaml_db_name}")

            # Format 2: Oracle semantic model format
            elif "tables" in yaml_content and len(yaml_content["tables"]) > 0:
                first_table = yaml_content["tables"][0]
                if "base_table" in first_table:
                    base_table = first_table["base_table"]
                    yaml_db_name = base_table.get("database")
                    yaml_schema_name = base_table.get("schema")
                    yaml_db_type = "oracle"
                    logger.debug(f"Detected Oracle format: db={yaml_db_name}")

            # Format 3: Collections format
            elif "collections" in yaml_content:
                if "metadata" in yaml_content:
                    metadata = yaml_content["metadata"]
                    yaml_db_name = metadata.get("database") or metadata.get("source_database")
                    yaml_schema_name = metadata.get("schema_name")
                yaml_db_type = "mongodb"
                logger.debug(f"Detected Collections format: db={yaml_db_name}")

            # Update db_details with extracted values
            if yaml_db_name or yaml_schema_name:
                db_details.update(
                    {
                        "db_name": yaml_db_name or db_details.get("db_name"),
                        "schema_name": yaml_schema_name or db_details.get("schema_name"),
                        "app_name": yaml_app_name or db_details.get("app_name", "GenAI-Agent"),
                        "db_type": yaml_db_type,
                    }
                )
                # Also update the legacy keys for MCP compatibility
                if yaml_db_name:
                    db_details["dbName"] = yaml_db_name
                if yaml_schema_name:
                    db_details["userName"] = yaml_schema_name
                if yaml_app_name:
                    db_details["applicationName"] = yaml_app_name
                logger.info(f"Updated db_details from YAML: {db_details}")

        # Step 3: Process semantic model with field optimization
        logger.info("Processing semantic model with field optimization...")
        schema, verified_queries, custom_instructions, fk_str, content_yaml, metrics = (
            process_semantic_model(
                yaml_content, user_query=user_query, optimize_fields=True, max_fields=30
            )
        )

        logger.info(f"Schema length: {len(schema)} chars")
        logger.info(f"Verified queries: {len(verified_queries)} chars")
        logger.info(f"FK relationships: {len(fk_str)} chars")

        # Step 4: Extract array fields for $unwind hints
        array_fields_info = ""
        if content_yaml and "collections" in content_yaml:
            for collection_name, collection_data in content_yaml.get("collections", {}).items():
                fields = collection_data.get("fields", {})
                array_fields = extract_array_fields(fields)

                if array_fields:
                    array_fields_info += f"\n[ARRAY FIELDS IN {collection_name}]\n"
                    for field_path in array_fields:
                        array_fields_info += (
                            f'  - {field_path} is an ARRAY → Use $unwind: "${field_path}"\n'
                        )

        if array_fields_info:
            logger.info(f"Array fields extracted:\n{array_fields_info}")

        # Step 5: Build LLM prompt
        logger.info("Building selector prompt...")
        prompt = build_selector_prompt(
            context=schema + array_fields_info,
            fk_str=fk_str,
            question=user_query,
            evidence=custom_instructions,
            metrics=metrics,
            verified_queries=verified_queries,
        )

        logger.info(f"Prompt length: {len(prompt)} chars")
        logger.debug(f"Prompt preview (first 500 chars):\n{prompt[:500]}...")

        # Step 6: Call LLM to generate MongoDB query
        logger.info("Calling LLM to generate MongoDB query...")
        logger.info("=" * 80)
        logger.info("LLM CALL #1: SCHEMA SELECTOR")
        logger.info("=" * 80)
        logger.info(f"📤 LLM REQUEST PROMPT ({len(prompt)} chars):\n{prompt}")
        logger.info("=" * 80)

        response = llm.invoke(prompt)
        llm_response = response.content if hasattr(response, "content") else str(response)

        logger.info(f"LLM response length: {len(llm_response)} chars")
        logger.info(f"📝 LLM RESPONSE:\n{llm_response}")
        logger.info("=" * 80)

        # Step 7: Parse JSON response
        logger.info("Parsing LLM response...")
        parsed_response = parse_json(llm_response)

        if parsed_response and isinstance(parsed_response, dict):
            mongodb_query = parsed_response.get("mongodb_query", "")
            collection_name = parsed_response.get("collection_name", "")
            logger.info(f"MongoDB query generated for collection: {collection_name}")
            logger.debug(f"Query: {mongodb_query[:200]}...")
        else:
            logger.error(f"Failed to parse MongoDB query response: {parsed_response}")
            mongodb_query = ""
            collection_name = ""

        # Step 8: Return state update
        return {
            "raw_extracted_schema_dict": parsed_response,
            "sql_query": mongodb_query,
            "collection_name": collection_name,
            "messages": [AIMessage(content=llm_response)],
            "schema": schema,
            "verified_queries": verified_queries,
            "custom_instructions": custom_instructions,
            "fk_str": fk_str,
            "content_yaml": content_yaml,
            "metrics": metrics,
            "error": "",
            "iterations": state.get("iterations", 0),
            "db_details": db_details,
        }

    except Exception as e:
        logger.error(f"Error in selector: {e}", exc_info=True)
        raise

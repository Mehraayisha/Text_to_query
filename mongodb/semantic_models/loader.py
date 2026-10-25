# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Semantic model loader for MongoDB collections.

Supports YAML-driven processing with intelligent field optimization,
collection filtering, and relationship handling.
"""

import logging
import re
from typing import Dict, Any, List, Tuple, Optional, Set
import json
import yaml

logger = logging.getLogger(__name__)

# Feature flag for YAML-driven filtering
ENABLE_YAML_DRIVEN_FILTERING = True


class YAMLSemanticProcessor:
    """Generic YAML-driven semantic model processor - NO HARDCODING"""

    def __init__(self, yaml_content: Dict[str, Any]):
        self.yaml_content = yaml_content
        self.business_rules = yaml_content.get("business_rules", {})
        self.collections = yaml_content.get("collections", {})

    def get_core_collections_from_yaml(self) -> Set[str]:
        """Extract core collections from YAML configuration"""
        core_collections = set()

        # Get from business_rules section
        business_core = self.business_rules.get("core_collections", {})

        for category in ["primary", "bridge", "dependent"]:
            for collection_def in business_core.get(category, []):
                # Include all primary and bridge collections as core
                if category in ["primary", "bridge"]:
                    core_collections.add(collection_def["name"])
                # Include dependent collections only if critical or mandatory
                elif (
                    collection_def.get("mandatory", False)
                    or collection_def.get("priority") == "critical"
                ):
                    core_collections.add(collection_def["name"])

        return core_collections

    def get_join_patterns_from_yaml(self) -> Dict[str, Any]:
        """Extract join patterns from YAML configuration"""
        return self.business_rules.get("join_patterns", {})

    def get_field_priorities_from_yaml(self, query_type: Optional[str] = None) -> Dict[str, Any]:
        """Extract field priorities based on query type"""
        field_priorities = self.business_rules.get("field_priorities", {})

        if query_type and query_type in field_priorities:
            return field_priorities[query_type]

        # Return general priorities if no specific type
        return field_priorities.get("default", {})

    def classify_query_type(self, query_text: str) -> str:
        """Classify query type based on domain keywords"""
        query_lower = query_text.lower()
        domain_keywords = self.business_rules.get("domain_keywords", {})

        scores = {}
        for query_type, keywords in domain_keywords.items():
            score = sum(1 for keyword in keywords if keyword.lower() in query_lower)
            if score > 0:
                scores[query_type] = score

        # Return highest scoring type or default
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return "default"

    def get_query_specific_rules(self, query_text: str) -> Dict[str, Any]:
        """Determine query type and get specific rules - PURE YAML-DRIVEN"""
        query_type_rules = self.business_rules.get("query_type_rules", {})

        # Classify by domain keywords defined in YAML
        classified_type = self.classify_query_type(query_text)
        if classified_type in query_type_rules:
            return query_type_rules[classified_type]

        # Return default rules if no specific type matched
        return query_type_rules.get("default", {})


def load_semantic_model(yaml_input: Any) -> Dict[str, Any]:
    """
    Load semantic model from file path or dictionary (supports both JSON and YAML).

    Args:
        yaml_input: Either a file path (string) or parsed content (dictionary)

    Returns:
        Parsed content as dictionary

    Raises:
        ValueError: If model cannot be loaded or is invalid
    """
    if isinstance(yaml_input, str):
        # It's a file path - load the content
        try:
            with open(yaml_input, "r", encoding="utf-8") as file:
                if yaml_input.endswith(".json"):
                    yaml_content = json.load(file)
                else:
                    try:
                        yaml_content = json.load(file)
                    except Exception:
                        file.seek(0)
                        yaml_content = yaml.safe_load(file)
        except Exception as e:
            raise ValueError(f"Error loading semantic model file {yaml_input}: {e}")
    elif isinstance(yaml_input, dict):
        # It's already parsed content
        yaml_content = yaml_input
    else:
        raise ValueError(f"Expected file path (str) or content (dict), got {type(yaml_input)}")

    return yaml_content


def filter_relevant_collections(
    yaml_content: Dict[str, Any], user_query: str, max_collections: Optional[int] = None
) -> Dict[str, Any]:
    """
    YAML-driven collection filtering - NO HARDCODING.
    All business logic comes from YAML configuration.

    Args:
        yaml_content: Parsed YAML semantic model
        user_query: User's natural language query
        max_collections: Maximum collections to include (default from YAML)

    Returns:
        Filtered YAML content with only relevant collections
    """
    logger.info("Using YAML-DRIVEN collection filtering")

    processor = YAMLSemanticProcessor(yaml_content)

    # Get query-specific rules from YAML
    query_rules = processor.get_query_specific_rules(user_query)
    max_collections = max_collections or query_rules.get("max_collections", 5)

    # Get core collections from YAML
    core_collections = processor.get_core_collections_from_yaml()

    # Get essential collections for this query type
    essential_collections = set(query_rules.get("essential_collections", []))

    all_collections = yaml_content.get("collections", {})
    scored_collections = []

    for collection_name, collection_data in all_collections.items():
        # Always include core collections with high score
        if collection_name in core_collections:
            scored_collections.append((collection_name, 1.0, "CORE_COLLECTION"))
            continue

        # Always include essential collections for this query type
        if collection_name in essential_collections:
            scored_collections.append((collection_name, 0.9, "ESSENTIAL_FOR_QUERY"))
            continue

        # Score other collections based on relevance
        relevance_score = _calculate_collection_relevance(
            collection_name, collection_data, user_query, processor
        )

        relevance_threshold = query_rules.get("relevance_threshold", 0.7)
        if relevance_score >= relevance_threshold:
            scored_collections.append((collection_name, relevance_score, "RELEVANT"))

    # Sort by score and limit
    scored_collections.sort(key=lambda x: x[1], reverse=True)
    selected_collections = [item[0] for item in scored_collections[:max_collections]]

    logger.info(
        f"YAML-Based Collection Selection: {len(selected_collections)}/{len(all_collections)} collections"
    )
    for name, score, reason in scored_collections[:max_collections]:
        logger.debug(f"   Selected {name} (score: {score:.2f}, reason: {reason})")

    # Filter YAML content
    filtered_yaml = yaml_content.copy()
    filtered_yaml["collections"] = {
        name: data for name, data in all_collections.items() if name in selected_collections
    }

    return filtered_yaml


def _calculate_collection_relevance(
    collection_name: str,
    collection_data: Dict[str, Any],
    user_query: str,
    processor: YAMLSemanticProcessor,
) -> float:
    """
    Calculate collection relevance using YAML configuration - PURE YAML-DRIVEN
    """
    score = 0.0
    query_lower = user_query.lower()

    # Business importance from YAML
    business_importance = collection_data.get("business_importance", "normal")
    importance_weights = {"critical": 0.3, "high": 0.2, "normal": 0.1, "low": 0.05}
    score += importance_weights.get(business_importance, 0.1)

    # Query frequency from YAML
    query_frequency = collection_data.get("query_frequency", "medium")
    frequency_weights = {"very_high": 0.3, "high": 0.2, "medium": 0.1, "low": 0.05}
    score += frequency_weights.get(query_frequency, 0.1)

    # Domain-specific keyword matching from YAML - no hardcoded collection names
    domain_keywords = processor.business_rules.get("domain_keywords", {})
    collection_categories = collection_data.get("categories", [])

    for category, keywords in domain_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            # Check if this collection belongs to this category (from YAML)
            if category in collection_categories:
                score += 0.4

    # Description relevance (reduced weight to avoid false positives)
    description = collection_data.get("description", "")
    if any(keyword in description.lower() for keyword in query_lower.split() if len(keyword) > 3):
        score += 0.2

    # Collection name relevance (more selective)
    specific_terms = [
        word
        for word in query_lower.split()
        if len(word) > 3 and word not in ["details", "information", "data"]
    ]
    if any(term in collection_name.lower() for term in specific_terms):
        score += 0.2

    return min(score, 1.0)


def optimize_schema_for_query(
    yaml_content: Dict[str, Any], user_query: str, max_fields: int = 30
) -> Dict[str, Any]:
    """
    YAML-driven field optimization - NO HARDCODING.

    Args:
        yaml_content: Parsed YAML semantic model
        user_query: User's natural language query
        max_fields: Maximum fields per collection (default 30)

    Returns:
        Optimized YAML content with reduced field sets
    """
    logger.info(f"Using YAML-DRIVEN field optimization (max_fields={max_fields})")

    processor = YAMLSemanticProcessor(yaml_content)
    query_rules = processor.get_query_specific_rules(user_query)

    # Get query-specific field priorities
    query_type = processor.classify_query_type(user_query)
    field_priorities = processor.get_field_priorities_from_yaml(query_type)

    optimized_yaml = yaml_content.copy()
    collections = optimized_yaml.get("collections", {})

    for collection_name, collection_data in collections.items():
        fields = collection_data.get("fields", {})

        if len(fields) <= max_fields:
            logger.debug(
                f"{collection_name}: No optimization needed ({len(fields)} fields <= {max_fields})"
            )
            continue  # No optimization needed

        # Get essential and high priority fields for this query type
        essential_fields = set(field_priorities.get("essential_fields", []))
        high_priority_fields = set(field_priorities.get("high_priority_fields", []))

        # Always include essential fields
        selected_fields = {}

        # Add essential fields first
        for field_name in essential_fields:
            if field_name in fields:
                selected_fields[field_name] = fields[field_name]

        # Add high priority fields if space remains
        remaining_slots = max_fields - len(selected_fields)
        for field_name in high_priority_fields:
            if field_name in fields and field_name not in selected_fields and remaining_slots > 0:
                selected_fields[field_name] = fields[field_name]
                remaining_slots -= 1

        # Fill remaining slots with relevant fields
        if remaining_slots > 0:
            remaining_fields = {k: v for k, v in fields.items() if k not in selected_fields}
            scored_fields = []

            for field_name, field_data in remaining_fields.items():
                relevance_score = _calculate_field_relevance(field_name, field_data, user_query)
                scored_fields.append((field_name, relevance_score))

            # Sort by relevance and take top remaining fields
            scored_fields.sort(key=lambda x: x[1], reverse=True)
            for field_name, score in scored_fields[:remaining_slots]:
                selected_fields[field_name] = fields[field_name]

        # Update collection with optimized fields
        optimized_yaml["collections"][collection_name]["fields"] = selected_fields

        logger.info(f"{collection_name}: Optimized {len(fields)} → {len(selected_fields)} fields")

    return optimized_yaml


def _calculate_field_relevance(
    field_name: str, field_data: Dict[str, Any], user_query: str
) -> float:
    """Calculate field relevance for YAML-driven optimization"""
    score = 0.0
    query_lower = user_query.lower()
    field_name_lower = field_name.lower()

    # Field name relevance
    if any(keyword in field_name_lower for keyword in query_lower.split()):
        score += 0.4

    # Description relevance
    description = field_data.get("description", "").lower()
    if any(keyword in description for keyword in query_lower.split()):
        score += 0.3

    # Data type preference (strings and dates often more useful)
    data_type = field_data.get("data_type", "").lower()
    if data_type in ["string", "date", "datetime"]:
        score += 0.1

    return min(score, 1.0)


def process_semantic_model(
    yaml_input: Any,
    user_query: Optional[str] = None,
    optimize_fields: bool = True,
    max_fields: int = 30,
) -> Tuple[str, str, str, str, Dict[str, Any], str]:
    """
    Process MongoDB semantic model YAML content and return formatted data for LLM processing.
    Supports both YAML-driven (NEW) and hardcoded (LEGACY) approaches for gradual migration.

    Args:
        yaml_input: Either a file path (string) or parsed YAML content (dictionary)
        user_query: User's natural language query for field relevance filtering
        optimize_fields: Whether to apply field optimization (default True)
        max_fields: Maximum number of fields to include when optimizing (default 30)

    Returns:
        Tuple of (llm_format, verified_queries, custom_instructions, relationships, yaml_content, metrics)
    """
    # Load YAML content
    yaml_content = load_semantic_model(yaml_input)

    # Check if YAML has business_rules section (indicates YAML-driven support)
    has_business_rules = "business_rules" in yaml_content

    if ENABLE_YAML_DRIVEN_FILTERING and has_business_rules and user_query:
        logger.info("Using YAML-DRIVEN processing (NEW ARCHITECTURE)")

        # Apply YAML-driven field optimization
        if optimize_fields:
            yaml_content = optimize_schema_for_query(yaml_content, user_query, max_fields)
            logger.info(
                f"Applied YAML-driven field optimization: targeting {max_fields} most relevant fields per collection"
            )

        # Apply YAML-driven collection filtering
        yaml_content = filter_relevant_collections(yaml_content, user_query)
        logger.info("Applied YAML-driven collection filtering")

    else:
        # LEGACY: YAML without business_rules - skip optimization
        logger.warning("WARNING: YAML missing 'business_rules' section - using unoptimized schema")
        logger.info("TIP: Add 'business_rules' section to YAML for intelligent filtering")

    # Extract collection info
    collection_info = yaml_content.get("collection_info", {})
    collections = yaml_content.get("collections", {})

    if not collections:
        raise ValueError("No collections found in the semantic model YAML content.")

    llm_format = ""

    # Process verified queries from YAML - check both root level and collection level
    queries = yaml_content.get("verified_queries", [])

    # If no queries at root level, check the first collection for verified_queries
    if not queries and collections:
        first_collection = next(iter(collections.values()))
        if isinstance(first_collection, dict):
            queries = first_collection.get("verified_queries", [])

    verified_queries = "Queries:\n"
    if not queries:
        verified_queries += "# No predefined queries in semantic model\n"
    else:
        for query in queries:
            if isinstance(query, dict):
                # Handle both legacy format and new format
                name = query.get("name", "Unknown")
                description = query.get("question", query.get("description", "Unknown"))
                mongodb_query = query.get("mongodb_query", query.get("query", "No query provided"))
                verified_queries += f"- Name: {name}\n"
                verified_queries += f"  Question: {description}\n"
                verified_queries += f"  MongoDB Query: {mongodb_query}\n\n"
            elif isinstance(query, str):
                verified_queries += f"- {query}\n"

    # Process custom instructions - check both root level and collection level
    custom_instructions = yaml_content.get("custom_instructions", "")

    # If no custom instructions at root level, check the first collection
    if not custom_instructions and collections:
        first_collection = next(iter(collections.values()))
        if isinstance(first_collection, dict):
            collection_instructions = first_collection.get("custom_instructions", [])
            if isinstance(collection_instructions, list):
                custom_instructions = "\n".join(collection_instructions)
            elif isinstance(collection_instructions, str):
                custom_instructions = collection_instructions

    # Extract relationships (equivalent to fk_str for MongoDB)
    relationships = yaml_content.get("relationships", [])
    if isinstance(relationships, list) and relationships:
        # Check if relationships are already formatted strings or dictionary objects
        relationship_entries = []
        for rel_info in relationships:
            if isinstance(rel_info, str):
                # Relationship is already a formatted string - use as-is
                relationship_entries.append(rel_info)
            elif isinstance(rel_info, dict):
                # Relationship is a dictionary - format it
                from_collection = rel_info.get("from_collection", "")
                to_collection = rel_info.get("to_collection", "")
                from_field = rel_info.get("from_field", "")
                to_field = rel_info.get("to_field", "")
                rel_type = rel_info.get("relationship_type", "")
                description = rel_info.get("description", "")

                rel_entry = (
                    f"{from_collection}.{from_field} -> {to_collection}.{to_field} ({rel_type})"
                )
                if description:
                    rel_entry += f" - {description}"
                relationship_entries.append(rel_entry)
            else:
                # Fallback for unknown format
                relationship_entries.append(str(rel_info))

        fk_str = "MongoDB Collection Relationships:\n" + "\n".join(relationship_entries)
    elif isinstance(relationships, dict) and relationships:
        # Fallback for dictionary format
        relationship_entries = []
        for rel_name, rel_info in relationships.items():
            from_collection = rel_info.get("from", "")
            to_collection = rel_info.get("to", "")
            rel_type = rel_info.get("type", "")
            reference_field = rel_info.get("reference_field", "")
            description = rel_info.get("description", "")

            rel_entry = f"{rel_name}: {from_collection} -> {to_collection} ({rel_type}) via {reference_field}"
            if description:
                rel_entry += f" - {description}"
            relationship_entries.append(rel_entry)

        fk_str = "MongoDB Collection Relationships:\n" + "\n".join(relationship_entries)
    else:
        fk_str = "No explicit relationships defined in semantic model"

    # Extract and format metrics
    metrics = yaml_content.get("metrics", {})
    if isinstance(metrics, dict) and metrics:
        formatted_metrics = f"### Metrics\n{metrics}\n"
    else:
        formatted_metrics = "### Metrics\nNo predefined metrics in semantic model - can calculate from monetary/value and count fields\n"

    # Process each collection
    for collection_name, collection_data in collections.items():
        logger.debug(f"Processing collection: {collection_name}")

        # Safety check: ensure collection_data is a dictionary
        if not isinstance(collection_data, dict):
            logger.warning(
                f"collection_data for {collection_name} is not a dict: {type(collection_data)}"
            )
            collection_data = {}

        # Extract fields - support both formats
        try:
            # Try our standardized template format first: collections.SLShippingDocuments.fields
            fields = collection_data.get("fields", {})

            if not fields:
                # Fallback to legacy format: collections.SLShippingDocuments.field_mappings.fields
                field_mappings = collection_data.get("field_mappings", {})
                logger.debug(f"Trying legacy field_mappings format for {collection_name}")

                # Safety check for field_mappings
                if not isinstance(field_mappings, dict):
                    logger.warning(f"field_mappings is not a dict: {type(field_mappings)}")
                    field_mappings = {}

                fields = field_mappings.get("fields", {})
            else:
                logger.debug(f"Successfully got fields directly for {collection_name}")

            # Safety check for fields
            if not isinstance(fields, dict):
                logger.warning(f"fields is not a dict: {type(fields)}")
                fields = {}

            logger.debug(f"Successfully got {len(fields)} fields")
        except Exception as e:
            logger.error(f"Error accessing fields for {collection_name}: {e}")
            fields = {}

        # Build collection description - use collection_info.database (from root level)
        llm_format += f"# MongoDB Collection: {collection_name}\n"
        llm_format += f"Database: {collection_info.get('database', 'unknown')}\n"
        llm_format += f"Business Flow: {collection_info.get('business_flow', 'unknown')}\n\n"

        # Build field structure grouped by path type
        llm_format += f"## Collection: {collection_name}\n[\n"

        # Group fields by their base path (headers, lines, documents, etc.)
        path_groups = {}
        for field_name, field_info in fields.items():
            # Safety check: ensure field_info is a dictionary
            if not isinstance(field_info, dict):
                logger.warning(f"field_info for {field_name} is not a dict: {type(field_info)}")
                field_info = {
                    "nested_path": str(field_info),
                    "data_type": "String",
                    "description": "",
                }

            # Use nested_path if available, otherwise use the field name
            path = field_info.get("nested_path", field_info.get("path", field_name))
            base_path = path.split(".")[0] if "." in path else "root"

            if base_path not in path_groups:
                path_groups[base_path] = []

            field_entry = {
                "name": field_name,
                "path": path,
                "type": field_info.get("data_type", field_info.get("type", "Unknown")),
                "description": field_info.get("description", ""),
            }
            path_groups[base_path].append(field_entry)

        # Format grouped fields
        entries = []
        for base_path, fields_list in sorted(path_groups.items()):
            for field in fields_list:
                # Get field information from the original field_info
                field_name = field["name"]
                field_info = fields.get(field_name, {})

                # Extract sample values from the YAML structure
                description = field["description"]
                sample_values_list = field_info.get("sample_values", [])
                sample_values = ""

                # Handle sample values from YAML with quote safety
                if sample_values_list and isinstance(sample_values_list, list):
                    # Ensure all sample values are properly quoted and escaped
                    safe_samples = []
                    for v in sample_values_list[:3]:
                        str_v = str(v).replace(
                            '"', "'"
                        )  # Replace double quotes with single quotes to avoid JSON issues
                        safe_samples.append(str_v)
                    sample_values = f"Value examples: {', '.join(safe_samples)}..."
                elif "sample values:" in description.lower():
                    # Fallback for legacy format
                    parts = description.split("sample values:")
                    if len(parts) > 1:
                        safe_sample_text = (
                            parts[1].strip()[:100].replace('"', "'")
                        )  # Replace quotes
                        sample_values = f"Value examples: {safe_sample_text}..."
                        description = parts[0].strip()

                parts = []
                try:
                    parts.append(f"{field['path']}")
                    parts.append(f"name: {field['name']}")
                    parts.append(f"type: {field['type']}")
                    if description and description != "Data field":
                        parts.append(description)
                    if sample_values:
                        parts.append(sample_values)

                    entry = "(" + ", ".join(parts) + ")"
                    entries.append(entry)
                except Exception as e:
                    logger.error(f"Error processing field {field['name']}: {e}")
                    # Add a safe fallback entry
                    safe_entry = f"({field['path']}, name: {field['name']}, type: {field['type']})"
                    entries.append(safe_entry)

        llm_format += ",\n".join(entries) + "\n]\n\n"

    # Use custom instructions from YAML if available, otherwise provide generic fallback
    if not custom_instructions:
        # Extract actual values from YAML instead of hardcoding
        first_collection_name = list(collections.keys())[0] if collections else "Unknown"
        database_name = collection_info.get("database", "Unknown")
        business_flow_name = collection_info.get("business_flow", "Unknown")

        # Try to get document count from first collection
        doc_count = "Unknown"
        if collections:
            first_collection_data = list(collections.values())[0]
            if isinstance(first_collection_data, dict):
                doc_count = first_collection_data.get("metadata", {}).get(
                    "document_count", "Unknown"
                )

        custom_instructions = f"""
MongoDB Semantic Model Instructions:
- Primary Collection: {first_collection_name}
- Database: {database_name}
- Business Flow: {business_flow_name}
- Document Count: {doc_count}

General MongoDB Query Guidelines:
1. Use the collection schemas provided above for accurate field paths
2. Follow the relationship patterns specified in the semantic model
3. Use appropriate aggregation pipeline stages for complex queries
4. Reference field paths exactly as shown in the collection schemas
5. Apply filters using the correct field data types

Important:
- All business rules and join patterns are defined in the YAML configuration
- Consult the 'relationships' section for proper collection joins
- Use the 'business_rules' section for domain-specific logic
"""

    return (
        llm_format,
        verified_queries,
        custom_instructions,
        fk_str,
        yaml_content,
        formatted_metrics,
    )

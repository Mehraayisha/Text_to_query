# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Automatic MongoDB Schema Discovery & Semantic Model Generator.

This module inspects a live MongoDB database, samples representative documents,
infers field types and nested structures, detects relationships, and generates
a YAML semantic model compatible with MongoDB Agent.
"""

import os
import json
import re
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Set, Tuple
import yaml
from bson import ObjectId

from mongodb.config import Config

logger = logging.getLogger(__name__)


class SchemaDiscoverer:
    """Discovers schema from a live MongoDB database and produces YAML semantic models."""

    def __init__(
        self,
        config: Optional[Config] = None,
        uri: Optional[str] = None,
        database_name: Optional[str] = None,
        sample_size: int = 50,
    ):
        """
        Initialize the discoverer.

        Args:
            config: Optional Config instance.
            uri: Optional MongoDB connection URI (falls back to config/env).
            database_name: Optional database name (falls back to config/env).
            sample_size: Number of documents to sample per collection (default: 50).
        """
        if config is None:
            config = Config.from_env()

        self.config = config
        self.uri = uri or config.mongodb_uri or os.getenv("MONGODB_URI")
        self.database_name = (
            database_name
            or config.mongodb_database
            or os.getenv("MONGODB_DATABASE")
            or "sample_mflix"
        )
        self.sample_size = sample_size
        self.output_dir = config.semantic_model_path or "./semantic_models"

        if not self.uri:
            raise ValueError("MONGODB_URI is required for schema discovery.")
        if not self.database_name:
            raise ValueError("MONGODB_DATABASE is required for schema discovery.")

        self.client = None
        self.db = None

    def connect(self):
        """Connect to the MongoDB database."""
        from pymongo import MongoClient

        logger.info(f"Connecting to MongoDB: {self.database_name}")
        self.client = MongoClient(self.uri, serverSelectionTimeoutMS=10000)
        self.db = self.client[self.database_name]
        return self.db

    def list_collections(self) -> List[str]:
        """List all non-system collections in the database."""
        if self.db is None:
            self.connect()

        all_collections = self.db.list_collection_names()
        # Filter out system collections and GridFS internal chunks
        filtered = [
            c
            for c in all_collections
            if not c.startswith("system.") and not c.endswith(".chunks")
        ]
        logger.info(f"Discovered {len(filtered)} collections: {filtered}")
        return sorted(filtered)

    def sample_documents(self, collection_name: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Sample representative documents from a collection."""
        limit = limit or self.sample_size
        coll = self.db[collection_name]

        # Try $sample aggregation first for random representative distribution
        try:
            docs = list(coll.aggregate([{"$sample": {"size": limit}}]))
            if docs:
                return docs
        except Exception as e:
            logger.debug(f"$sample failed on {collection_name} ({e}), falling back to find().limit()")

        # Fallback to standard find()
        return list(coll.find().limit(limit))

    @staticmethod
    def infer_primitive_type(val: Any) -> str:
        """Map Python/BSON value types to clean YAML schema types."""
        if isinstance(val, ObjectId):
            return "ObjectId"
        elif isinstance(val, bool):
            return "boolean"
        elif isinstance(val, (int, float)):
            return "number"
        elif isinstance(val, (datetime, date)):
            return "date"
        elif isinstance(val, str):
            return "string"
        elif isinstance(val, list):
            return "array"
        elif isinstance(val, dict):
            return "object"
        return "string"

    @staticmethod
    def format_sample_value(val: Any) -> Any:
        """Format a sample value safely for YAML output."""
        if isinstance(val, ObjectId):
            return str(val)
        elif isinstance(val, (datetime, date)):
            return val.isoformat()
        elif isinstance(val, str):
            # Truncate very long text
            return val[:80] + "..." if len(val) > 80 else val
        elif isinstance(val, (int, float, bool)):
            return val
        elif isinstance(val, list):
            # Sample first 2-3 items of primitive list
            if val and not isinstance(val[0], (dict, list)):
                return [SchemaDiscoverer.format_sample_value(v) for v in val[:3]]
            return f"[Array of {len(val)} items]"
        elif isinstance(val, dict):
            return f"{{Object with {len(val)} keys}}"
        return str(val)

    def analyze_collection(self, collection_name: str) -> Dict[str, Any]:
        """
        Analyze a collection's sampled documents and produce its fields and nested fields.
        """
        docs = self.sample_documents(collection_name)
        total_docs = len(docs)
        logger.info(f"Analyzing {collection_name} ({total_docs} sampled docs)")

        fields_meta: Dict[str, Dict[str, Any]] = {}
        nested_fields_meta: Dict[str, Dict[str, Any]] = {}
        array_fields: List[str] = []

        for doc in docs:
            self._walk_document(
                doc,
                fields_meta=fields_meta,
                nested_fields_meta=nested_fields_meta,
                array_fields=array_fields,
            )

        # Clean up sample values into lists
        for f_name, f_info in fields_meta.items():
            f_info["sample_values"] = list(f_info["sample_values"])[:3]

        return {
            "name": collection_name,
            "description": f"Contains records for {collection_name}",
            "fields": fields_meta,
            "nested_fields": nested_fields_meta,
            "array_fields": sorted(list(set(array_fields))),
            "sample_doc_count": total_docs,
        }

    def _walk_document(
        self,
        obj: Dict[str, Any],
        fields_meta: Dict[str, Dict[str, Any]],
        nested_fields_meta: Dict[str, Dict[str, Any]],
        array_fields: List[str],
        parent_path: str = "",
    ):
        """Recursively walk through a document's fields and nested structures."""
        for key, val in obj.items():
            if val is None:
                continue

            current_path = f"{parent_path}.{key}" if parent_path else key
            val_type = self.infer_primitive_type(val)

            # Record top-level or dotted fields in fields_meta
            if current_path not in fields_meta:
                fields_meta[current_path] = {
                    "data_type": val_type,
                    "description": self._generate_description(key, val_type),
                    "nested_path": current_path,
                    "sample_values": set(),
                    "unique": (key == "_id" and not parent_path),
                }

            # Update sample values if primitive
            if val_type not in ["object", "array"]:
                sample_formatted = self.format_sample_value(val)
                if sample_formatted is not None and len(fields_meta[current_path]["sample_values"]) < 3:
                    fields_meta[current_path]["sample_values"].add(sample_formatted)

            # Handle Nested Objects
            if isinstance(val, dict):
                base_parent = current_path.split(".")[0]
                if base_parent not in nested_fields_meta:
                    nested_fields_meta[base_parent] = {
                        "data_type": "object",
                        "description": f"Nested {base_parent} details",
                        "nested_path": base_parent,
                        "fields": {},
                    }
                # Recurse
                self._walk_document(
                    val,
                    fields_meta=fields_meta,
                    nested_fields_meta=nested_fields_meta,
                    array_fields=array_fields,
                    parent_path=current_path,
                )

            # Handle Arrays
            elif isinstance(val, list):
                if current_path not in array_fields:
                    array_fields.append(current_path)

                # Check if array of objects vs array of primitives
                if val and isinstance(val[0], dict):
                    # Sample first item object schema
                    self._walk_document(
                        val[0],
                        fields_meta=fields_meta,
                        nested_fields_meta=nested_fields_meta,
                        array_fields=array_fields,
                        parent_path=current_path,
                    )
                elif val:
                    # Array of primitives (e.g. genres: ["Action", "Drama"])
                    elem_type = self.infer_primitive_type(val[0])
                    fields_meta[current_path]["data_type"] = f"array[{elem_type}]"
                    for item in val[:3]:
                        formatted_item = self.format_sample_value(item)
                        if formatted_item is not None and len(fields_meta[current_path]["sample_values"]) < 3:
                            fields_meta[current_path]["sample_values"].add(formatted_item)

    @staticmethod
    def _generate_description(field_name: str, data_type: str) -> str:
        """Generate a meaningful description based on field name conventions."""
        lower = field_name.lower()
        if lower == "_id":
            return "Unique MongoDB document identifier"
        elif "date" in lower or "time" in lower or lower in ["created_at", "updated_at", "released"]:
            return f"Timestamp or date field ({data_type})"
        elif "id" in lower:
            return f"Identifier reference ({data_type})"
        elif lower in ["title", "name"]:
            return f"Name or title ({data_type})"
        elif lower in ["email", "mail"]:
            return "Email address"
        elif lower in ["rating", "score", "votes"]:
            return f"Rating/Score metric ({data_type})"
        elif lower in ["genres", "tags", "categories"]:
            return f"Categorization list ({data_type})"
        elif lower in ["price", "cost", "amount", "total"]:
            return f"Monetary or numeric amount ({data_type})"
        return f"{field_name} value ({data_type})"

    def detect_relationships(
        self, collections_analysis: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """
        Detect cross-collection relationships using name heuristics and sample values.
        """
        relationships = []
        coll_names = list(collections_analysis.keys())

        for src_coll, src_data in collections_analysis.items():
            for field_name, field_info in src_data["fields"].items():
                # Ignore self _id
                if field_name == "_id":
                    continue

                # Pattern 1: target_id or targetId (e.g., movie_id -> movies._id)
                base_name = field_name.split(".")[-1]
                match = re.match(r"^([a-zA-Z0-9]+)[_-]?(?:id|Id)$", base_name)
                if match:
                    ref_token = match.group(1).lower()
                    for target_coll in coll_names:
                        if target_coll == src_coll:
                            continue
                        target_singular = target_coll.rstrip("s").lower()
                        if target_singular == ref_token or target_coll.lower() == ref_token:
                            rel_str = f"{src_coll}.{field_name} -> {target_coll}._id"
                            relationships.append(
                                {
                                    "from": f"{src_coll}.{field_name}",
                                    "to": f"{target_coll}._id",
                                    "pattern_type": "direct",
                                    "description": f"Links {src_coll} to {target_coll}",
                                    "string_repr": rel_str,
                                }
                            )

                # Pattern 2: Natural keys like email
                if base_name in ["email", "user_email"] and "users" in coll_names and src_coll != "users":
                    rel_str = f"{src_coll}.{field_name} -> users.email"
                    relationships.append(
                        {
                            "from": f"{src_coll}.{field_name}",
                            "to": "users.email",
                            "pattern_type": "direct",
                            "description": f"Links {src_coll} to users by email",
                            "string_repr": rel_str,
                        }
                    )

        logger.info(f"Detected {len(relationships)} relationships across collections.")
        return relationships

    def generate_yaml_dict(
        self,
        collections_analysis: Dict[str, Dict[str, Any]],
        relationships: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Assemble the complete YAML semantic model structure.
        """
        coll_names = list(collections_analysis.keys())
        # Pick primary collection (most fields or largest doc sample)
        primary_coll = "movies" if "movies" in coll_names else coll_names[0]

        # Categorize collections into primary, bridge, dependent
        primary_list = [
            {
                "name": primary_coll,
                "role": "primary_entity",
                "mandatory": True,
                "priority": "critical",
                "description": f"Primary collection: {primary_coll}",
                "business_importance": "critical",
                "query_frequency": "very_high",
            }
        ]
        dependent_list = []
        for c in coll_names:
            if c != primary_coll:
                dependent_list.append(
                    {
                        "name": c,
                        "role": "direct_relationship",
                        "priority": "high",
                        "description": f"Related collection: {c}",
                        "business_importance": "high",
                        "query_frequency": "high",
                    }
                )

        # Build direct joins
        direct_joins = []
        for r in relationships:
            direct_joins.append(
                {
                    "from": r["from"],
                    "to": r["to"],
                    "description": r["description"],
                    "pattern_type": r["pattern_type"],
                }
            )

        # Identify essential & high priority fields from primary
        prim_fields = collections_analysis.get(primary_coll, {}).get("fields", {})
        essential_fields = ["_id"]
        high_priority_fields = []
        for f in prim_fields:
            if any(term in f.lower() for term in ["name", "title", "status"]):
                essential_fields.append(f)
            elif any(term in f.lower() for term in ["rating", "year", "date", "genre", "category", "price"]):
                high_priority_fields.append(f)

        # Verified sample queries
        verified_queries = [
            {
                "name": f"All{primary_coll.capitalize()}",
                "question": f"Show all records from {primary_coll}",
                "mongodb_query": f"db.{primary_coll}.find({{}}).limit(10)",
            },
            {
                "name": f"Count{primary_coll.capitalize()}",
                "question": f"How many records are in {primary_coll}?",
                "mongodb_query": f"db.{primary_coll}.countDocuments({{}})",
            },
        ]
        if high_priority_fields:
            sort_field = high_priority_fields[0]
            verified_queries.append(
                {
                    "name": f"Top{primary_coll.capitalize()}By{sort_field.replace('.', '_')}",
                    "question": f"Show top 5 {primary_coll} sorted by {sort_field}",
                    "mongodb_query": f'db.{primary_coll}.find({{}}).sort({{"{sort_field}": -1}}).limit(5)',
                }
            )

        # Construct final dict
        yaml_model = {
            "collection_info": {
                "database": self.database_name,
                "schema_name": primary_coll,
                "business_flow": self.database_name,
                "application_domain": "MongoDB NL Query AI Agent",
            },
            "business_rules": {
                "core_collections": {
                    "primary": primary_list,
                    "bridge": [],
                    "dependent": dependent_list,
                },
                "join_patterns": {
                    "direct_joins": direct_joins,
                },
                "field_priorities": {
                    "general_queries": {
                        "essential_fields": list(dict.fromkeys(essential_fields))[:5],
                        "high_priority_fields": list(dict.fromkeys(high_priority_fields))[:10],
                    }
                },
                "query_type_rules": {
                    "listing_queries": {
                        "max_collections": min(len(coll_names), 3),
                        "max_fields": 15,
                        "essential_collections": [primary_coll],
                        "relevance_threshold": 0.8,
                    },
                    "detailed_queries": {
                        "max_collections": min(len(coll_names), 5),
                        "max_fields": 25,
                        "essential_collections": [primary_coll],
                        "relevance_threshold": 0.7,
                    },
                    "default": {
                        "max_collections": min(len(coll_names), 4),
                        "max_fields": 20,
                        "essential_collections": [primary_coll],
                        "relevance_threshold": 0.7,
                    },
                },
                "domain_keywords": {
                    "listing_related": ["list", "all", "show all", "find all", "get all"],
                    "detail_related": ["details", "information", "about", "specific"],
                    "reporting_related": ["report", "summary", "count", "average", "total", "top"],
                },
            },
            "description": f"Auto-discovered semantic model for MongoDB database '{self.database_name}'",
            "collections": {
                name: {
                    "name": name,
                    "description": data["description"],
                    "fields": data["fields"],
                    "nested_fields": data["nested_fields"],
                }
                for name, data in collections_analysis.items()
            },
            "verified_queries": verified_queries,
            "custom_instructions": (
                "MongoDB Query Guidelines:\n"
                "- Use ISODate('YYYY-MM-DD') for date comparisons\n"
                "- Field names are case-sensitive\n"
                "- Place $match as early as possible in aggregation pipelines\n"
                "- For case-insensitive search, use $regex with 'i' option\n"
                "- Unwind array fields using $unwind when aggregating nested array elements\n"
            ),
            "relationships": [r["string_repr"] for r in relationships],
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "total_collections": len(coll_names),
                "database": self.database_name,
                "schema_name": primary_coll,
                "has_relationships": len(relationships) > 0,
            },
        }

        return yaml_model

    def discover(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Execute full schema discovery workflow.

        Returns:
            Tuple of (collections_analysis, relationships, yaml_dict)
        """
        self.connect()
        collections = self.list_collections()
        if not collections:
            raise ValueError(f"No collections found in database '{self.database_name}'")

        collections_analysis = {}
        for coll_name in collections:
            collections_analysis[coll_name] = self.analyze_collection(coll_name)

        relationships = self.detect_relationships(collections_analysis)
        yaml_dict = self.generate_yaml_dict(collections_analysis, relationships)
        return collections_analysis, relationships, yaml_dict

    def discover_and_save(self, output_filename: Optional[str] = None) -> str:
        """
        Execute full discovery workflow and save the semantic model JSON (or YAML if explicitly requested).

        Returns:
            Path to the saved JSON/YAML file.
        """
        collections_analysis, relationships, yaml_dict = self.discover()

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        filename = output_filename or f"{self.database_name}.json"
        output_path = os.path.join(self.output_dir, filename)

        if filename.endswith(".yaml") or filename.endswith(".yml"):
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(yaml_dict, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(yaml_dict, f, indent=2, default=str)

        logger.info(f"Schema discovery complete. Semantic model saved to: {output_path}")
        return output_path


def main():
    """CLI runner for schema discovery."""
    import argparse
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Auto-discover MongoDB schema and generate semantic model YAML."
    )
    parser.add_argument("--uri", help="MongoDB connection URI (default: from .env)")
    parser.add_argument("--database", help="MongoDB database name (default: from .env)")
    parser.add_argument("--output", help="Output JSON filename (default: <database>.json)")
    parser.add_argument("--sample-size", type=int, default=50, help="Sample size per collection")

    args = parser.parse_args()

    discoverer = SchemaDiscoverer(
        uri=args.uri,
        database_name=args.database,
        sample_size=args.sample_size,
    )
    saved_path = discoverer.discover_and_save(output_filename=args.output)
    print(f"\n[SUCCESS] Successfully discovered schema and generated: {saved_path}")


if __name__ == "__main__":
    main()

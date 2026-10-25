# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Tests for automatic MongoDB schema discovery and YAML generation.
"""

import unittest
from datetime import datetime
from bson import ObjectId

from mongodb_agent.schema_discovery import SchemaDiscoverer
from mongodb_agent.semantic_models.loader import process_semantic_model


class TestSchemaDiscovery(unittest.TestCase):
    """Test suite for automatic schema discovery."""

    def test_type_inference(self):
        """Test primitive type inference."""
        self.assertEqual(SchemaDiscoverer.infer_primitive_type(ObjectId()), "ObjectId")
        self.assertEqual(SchemaDiscoverer.infer_primitive_type("hello"), "string")
        self.assertEqual(SchemaDiscoverer.infer_primitive_type(42), "number")
        self.assertEqual(SchemaDiscoverer.infer_primitive_type(3.14), "number")
        self.assertEqual(SchemaDiscoverer.infer_primitive_type(True), "boolean")
        self.assertEqual(SchemaDiscoverer.infer_primitive_type(datetime.now()), "date")
        self.assertEqual(SchemaDiscoverer.infer_primitive_type([1, 2, 3]), "array")
        self.assertEqual(SchemaDiscoverer.infer_primitive_type({"a": 1}), "object")

    def test_document_walking_and_nesting(self):
        """Test recursive document walking on nested and array structures."""
        discoverer = SchemaDiscoverer.__new__(SchemaDiscoverer)
        fields_meta = {}
        nested_fields_meta = {}
        array_fields = []

        doc = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "title": "Inception",
            "year": 2010,
            "genres": ["Action", "Sci-Fi"],
            "imdb": {
                "rating": 8.8,
                "votes": 2000000,
            },
            "released": datetime(2010, 7, 16),
        }

        discoverer._walk_document(
            doc,
            fields_meta=fields_meta,
            nested_fields_meta=nested_fields_meta,
            array_fields=array_fields,
        )

        # Check top level fields
        self.assertIn("_id", fields_meta)
        self.assertEqual(fields_meta["_id"]["data_type"], "ObjectId")
        self.assertIn("title", fields_meta)
        self.assertIn("year", fields_meta)

        # Check arrays
        self.assertIn("genres", fields_meta)
        self.assertIn("genres", array_fields)
        self.assertIn("array", fields_meta["genres"]["data_type"])

        # Check nested fields
        self.assertIn("imdb.rating", fields_meta)
        self.assertEqual(fields_meta["imdb.rating"]["data_type"], "number")
        self.assertIn("imdb.votes", fields_meta)
        self.assertIn("imdb", nested_fields_meta)

    def test_relationship_detection(self):
        """Test heuristic detection of relationships."""
        discoverer = SchemaDiscoverer.__new__(SchemaDiscoverer)

        collections_analysis = {
            "movies": {
                "fields": {
                    "_id": {"data_type": "ObjectId"},
                    "title": {"data_type": "string"},
                }
            },
            "comments": {
                "fields": {
                    "_id": {"data_type": "ObjectId"},
                    "movie_id": {"data_type": "ObjectId"},
                    "email": {"data_type": "string"},
                }
            },
            "users": {
                "fields": {
                    "_id": {"data_type": "ObjectId"},
                    "email": {"data_type": "string"},
                }
            },
        }

        rels = discoverer.detect_relationships(collections_analysis)
        rel_strings = [r["string_repr"] for r in rels]

        self.assertIn("comments.movie_id -> movies._id", rel_strings)
        self.assertIn("comments.email -> users.email", rel_strings)

    def test_yaml_compatibility_with_agent(self):
        """Verify that generated YAML structure is fully compatible with agent's process_semantic_model."""
        discoverer = SchemaDiscoverer.__new__(SchemaDiscoverer)
        discoverer.database_name = "test_db"

        collections_analysis = {
            "movies": {
                "name": "movies",
                "description": "Movies collection",
                "fields": {
                    "_id": {"data_type": "ObjectId", "description": "ID", "nested_path": "_id", "sample_values": ["123"]},
                    "title": {"data_type": "string", "description": "Title", "nested_path": "title", "sample_values": ["Avatar"]},
                    "year": {"data_type": "number", "description": "Year", "nested_path": "year", "sample_values": [2009]},
                },
                "nested_fields": {},
                "array_fields": [],
            }
        }

        relationships = []
        yaml_dict = discoverer.generate_yaml_dict(collections_analysis, relationships)

        # Process with the agent's semantic loader
        schema, verified_queries, custom_instructions, fk_str, content_yaml, metrics = process_semantic_model(
            yaml_dict, user_query="Show all movies", optimize_fields=True
        )

        self.assertIn("Collection: movies", schema)
        self.assertIn("name: title", schema)
        self.assertIn("name: year", schema)
        self.assertTrue(len(verified_queries) > 0)


if __name__ == "__main__":
    unittest.main()


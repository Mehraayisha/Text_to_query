# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Semantic model processing for MongoDB collections.

This module provides utilities for loading, parsing, and optimizing
semantic models defined in YAML format.
"""

from .loader import (
    load_semantic_model,
    process_semantic_model,
    optimize_schema_for_query,
    filter_relevant_collections,
)

__all__ = [
    "load_semantic_model",
    "process_semantic_model",
    "optimize_schema_for_query",
    "filter_relevant_collections",
]

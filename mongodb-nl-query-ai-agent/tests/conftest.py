# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""Pytest configuration and fixtures for mongodb_agent tests."""

import pytest
import os
from unittest.mock import Mock, MagicMock


@pytest.fixture
def mock_mongodb_client():
    """Mock MongoDB client for testing."""
    client = MagicMock()
    db = MagicMock()
    collection = MagicMock()

    client.__getitem__.return_value = db
    db.__getitem__.return_value = collection

    return client


@pytest.fixture
def mock_llm():
    """Mock LLM for testing."""
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content="Test response")
    return llm


@pytest.fixture
def sample_semantic_model():
    """Sample semantic model for testing."""
    return {
        "collection": "test_collection",
        "description": "Test collection for unit tests",
        "fields": [
            {"name": "id", "type": "string", "description": "Unique identifier"},
            {"name": "name", "type": "string", "description": "Name field"},
            {"name": "value", "type": "number", "description": "Numeric value"},
        ],
    }


@pytest.fixture
def test_config():
    """Test configuration."""
    return {
        "mongodb_uri": "mongodb://localhost:27017",
        "database_name": "test_db",
        "llm_provider": "test_provider",
        "model_name": "test-model",
    }

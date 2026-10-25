# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""Service layer initialization"""

from mongodb_agent.services.llm import get_llm
from mongodb_agent.services.vector_db import get_vector_client
from mongodb_agent.services.mcp_client import get_mcp_client

__all__ = ["get_llm", "get_vector_client", "get_mcp_client"]

#!/usr/bin/env python
"""
Run Schema Discovery on configured MongoDB database and output YAML semantic model.

Usage:
    python scripts/discover_schema.py
    python scripts/discover_schema.py --database sample_mflix
"""
import sys
import os

# Add src to python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mongodb_agent.schema_discovery import main

if __name__ == "__main__":
    main()


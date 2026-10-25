#!/usr/bin/env python3
"""
MongoDB Agent Server - FastAPI Server for NL-to-MongoDB Query Agent
"""

import os
import sys

# Ensure UTF-8 output on Windows to prevent UnicodeEncodeError in logging
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure local src directory has absolute highest priority in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
os.environ["PYTHONPATH"] = f"{src_dir}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"

import uvicorn
from mongodb_agent.api import app

if __name__ == "__main__":
    host = os.getenv("SERVER_HOST", "127.0.0.1")
    port = int(os.getenv("SERVER_PORT", "8000"))
    reload = os.getenv("DEV_MODE", "true").lower() == "true"

    print("=" * 60)
    print("🚀 MongoDB Natural Language Query Agent Server")
    print(f"📡 API Running at:  http://{host}:{port}")
    print(f"📚 Interactive Swagger Docs: http://{host}:{port}/docs")
    print(f"🔍 ReDoc Reference: http://{host}:{port}/redoc")
    print("=" * 60)

    uvicorn.run(
        "mongodb_agent.api:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )

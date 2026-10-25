# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Cisco Systems, Inc. and its affiliates

"""
Command-line interface for MongoDB Agent
"""

import argparse
import sys
import os
from typing import Optional


def start_server(host="127.0.0.1", port=8000, reload=False, log_level="info", mode="auto"):
    """Start the MongoDB Agent FastAPI server

    Args:
        host: Host to bind to (default: 127.0.0.1)
        port: Port to bind to (default: 8000)
        reload: Enable auto-reload for development (default: False)
        log_level: Logging level (default: info)
        mode: Server mode - 'auto', 'rest', or 'mcp' (default: auto)
    """
    try:
        # Import here to avoid loading dependencies during package installation
        import uvicorn

        # Create logs directory
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "mongodb_agent.log")

        print(f"🚀 Starting MongoDB Agent Server")
        print(f"📡 Mode: {mode}")
        print(f"📡 Server URL: http://{host}:{port}")
        print(f"📚 API Docs: http://{host}:{port}/docs")
        print(f"🔍 ReDoc: http://{host}:{port}/redoc")
        print(f"🏥 Health Check: http://{host}:{port}/health")
        print(f"📝 Logs: {log_file}")
        print()

        if mode == "rest":
            print("✅ REST API Mode: Includes /api/mongodb endpoint for Postman/HTTP testing")
            module_path = "mongodb_agent.api:app"
        elif mode == "mcp":
            print("✅ MCP Mode: Pure MCP protocol server for Claude Desktop")
            # TODO: Implement pure MCP server
            module_path = "mongodb_agent.server:app"
        else:
            print("✅ Auto Mode: Detects available configuration")
            module_path = "mongodb_agent.server:app"

        print(f"📦 Loading module: {module_path}")
        print()

        uvicorn.run(
            module_path,
            host=host,
            port=port,
            reload=reload,
            log_level=log_level,
            access_log=False,  # Reduce console noise
        )
    except ImportError as e:
        print(f"❌ Error: Missing required dependencies: {e}")
        print("Please install the package with: pip install cisco-mongodb-agent")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="MongoDB Agent - Natural Language to MongoDB Query Converter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start server
  mongodb-agent-server
  
  # Start on custom port
  mongodb-agent-server --port 9000
  
  # Enable auto-reload for development
  mongodb-agent-server --reload

For more information, visit:
https://github.com/cisco-it-supply-chain/sc-genai-sql-mcp-agent
        """,
    )

    parser.add_argument("--version", action="version", version="cisco-mongodb-agent 1.0.0")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    server_parser = subparsers.add_parser("server", help="Start the MongoDB Agent server")
    server_parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    server_parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    server_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    server_parser.add_argument(
        "--mode",
        choices=["auto", "rest", "mcp"],
        default="auto",
        help="Server mode: auto (default), rest (HTTP API), mcp (MCP protocol)",
    )

    args = parser.parse_args()

    if args.command == "server":
        start_server(
            host=args.host, port=args.port, reload=args.reload, log_level="info", mode=args.mode
        )
    elif not args.command:
        # Default: start server with default settings
        start_server()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

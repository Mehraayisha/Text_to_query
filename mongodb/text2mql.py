"""
Text2MQL Terminal Application for MongoDB.
Translates plain English queries to MongoDB aggregation pipelines using the MongoDBAgent,
executes the query on MongoDB, and renders the results in an interactive terminal.
"""

import os
import sys
import json
import time
from typing import Dict, Any, List, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from mongodb.config import Config
from mongodb.agent import MongoDBAgent

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(parent_dir, ".env"))
    load_dotenv(os.path.join(current_dir, ".env"))
except ImportError:
    pass


def print_banner():
    print("\n" + "=" * 70)
    print("🍃 MongoDB Text2MQL Interactive Terminal Engine")
    print("=" * 70)
    print("Type your questions in plain English (or 'exit' / 'quit' to stop).\n")


def format_results(results: Any) -> str:
    """Format MongoDB query results nicely for terminal display."""
    if not results:
        return "(No documents returned)"
    if isinstance(results, list):
        if len(results) == 0:
            return "(Empty list)"
        try:
            return json.dumps(results[:10], indent=2, default=str)
        except Exception:
            return str(results[:10])
    try:
        return json.dumps(results, indent=2, default=str)
    except Exception:
        return str(results)


def run_cli():
    print_banner()

    config = Config.from_env()
    print(f"[*] Target Database : {config.mongodb_database or 'sample_mflix'}")
    print(f"[*] LLM Provider    : {config.llm_provider} ({config.openai_model})")
    print("[*] Initializing MongoDB Agent...")

    try:
        agent = MongoDBAgent(config)
        print("[OK] MongoDB Agent initialized successfully!\n")
    except Exception as e:
        print(f"[ERROR] Could not initialize MongoDB Agent: {e}")
        print("Check your .env settings (MONGODB_URI, OPENAI_API_KEY, etc.)")
        return

    while True:
        try:
            user_input = input("\n[Question] > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("Exiting Text2MQL. Goodbye!")
                break

            start_t = time.time()
            print("\n[-] Generating MongoDB query and executing...")
            response = agent.query(question=user_input)
            elapsed = time.time() - start_t

            print("-" * 70)
            mql = response.get("mongodb_query") or response.get("sql_query") or response.get("aggregation_pipeline") or "N/A"
            print(f"[Generated MQL]:\n{mql}\n")

            raw_res = response.get("raw_mongo_result")
            if raw_res is not None:
                count = len(raw_res) if isinstance(raw_res, list) else 1
                print(f"[Database Result ({count} document{'s' if count != 1 else ''})]:\n{format_results(raw_res)}\n")
            else:
                db_res = response.get("query_result")
                if db_res:
                    print(f"[Database Result]:\n{db_res}\n")

            if response.get("error"):
                print(f"[Error]: {response['error']}\n")

            print(f"[Time Elapsed]: {elapsed:.2f}s")
            print("-" * 70)

        except KeyboardInterrupt:
            print("\nInterrupted. Exiting...")
            break
        except Exception as e:
            print(f"\n[ERROR]: {e}")


if __name__ == "__main__":
    run_cli()


# SPDX-License-Identifier: MIT
"""
MongoDB Agent - Basic Query Example
"""

import sys
import json
from mongodb_agent import MongoDBAgent, Config

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def main():
    """Run a basic MongoDB query from natural language"""
    question = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "Show me 3 sci-fi movies released after 2010"
    )

    print("=" * 60)
    print("🚀 MongoDB Agent - Natural Language Query")
    print("=" * 60)
    print(f"❓ Question: {question}")
    print()

    # Load configuration
    config = Config.from_env()
    print(f"✅ Database: {config.mongodb_database}")
    print(f"✅ LLM Model: {config.openai_model}")
    print()

    # Initialize agent
    print("🤖 Initializing agent...")
    agent = MongoDBAgent(config)
    print("✅ Ready. Executing query...")
    print()

    result = agent.query(question=question)

    print("=" * 60)
    print("📊 RESULTS")
    print("=" * 60)
    print(f"Generated Pipeline:\n{result.get('aggregation_pipeline') or result.get('sql_query')}\n")
    print(f"Natural Language Summary:\n{result.get('query_result')}\n")

    raw_docs = result.get("raw_mongo_result")
    if raw_docs and isinstance(raw_docs, list):
        print(f"Matched Documents ({len(raw_docs)}):")
        for i, doc in enumerate(raw_docs[:3], 1):
            print(f" {i}. {doc.get('title') or doc.get('name')} (Year: {doc.get('year', 'N/A')})")


if __name__ == "__main__":
    main()

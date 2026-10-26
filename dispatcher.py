"""
Step 1 Dispatcher: High-Level Federated AI Data Router (Cross-Database Capable).

Evaluates natural language questions against the abstract master semantic layer
(master_semantic_layer.json) with shared federation keys, detecting whether a query
requires a single database or a cross-database join across BigQuery and Neo4j.
"""

import os
import sys
import json
import re
import time
import requests
from typing import Dict, Any, List, Optional

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

# ==============================================================================
# Configuration
# ==============================================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_CATALOG_FILE = os.path.join(CURRENT_DIR, "master_semantic_layer.json")

OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "180"))


# ==============================================================================
# 1. Master Semantic Layer Loader & Context Formatter
# ==============================================================================
def load_master_catalog(file_path: Optional[str] = None) -> Dict[str, Any]:
    """Loads the abstract master catalog JSON file."""
    path = file_path or MASTER_CATALOG_FILE
    if not os.path.exists(path):
        raise FileNotFoundError(f"Master catalog file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_catalog_for_prompt(catalog: Dict[str, Any]) -> str:
    """Formats the abstract catalog and shared keys into a concise prompt context."""
    databases = catalog.get("databases", {})
    shared_keys = catalog.get("shared_keys", {})
    lines = ["AVAILABLE DATABASES IN OUR ENTERPRISE:"]

    for db_name, db_info in databases.items():
        domain = db_info.get("business_domain", "")
        desc = db_info.get("description", "")
        lines.append(f"\n1. Database ID: '{db_name}' ({domain})")
        lines.append(f"   Description: {desc}")

        # SQL Tables
        tables = db_info.get("tables")
        if tables:
            lines.append("   Available Tables:")
            for tbl, tbl_desc in tables.items():
                lines.append(f"     - {tbl}: {tbl_desc}")

        # Graph Nodes & Relationships
        nodes = db_info.get("core_nodes")
        if nodes:
            lines.append("   Core Graph Nodes:")
            for node, node_desc in nodes.items():
                lines.append(f"     - {node}: {node_desc}")

        rels = db_info.get("core_relationships")
        if rels:
            lines.append("   Core Graph Relationships:")
            for rel, rel_desc in rels.items():
                lines.append(f"     - {rel}: {rel_desc}")

    if shared_keys:
        lines.append("\nFEDERATED SHARED KEYS (FOR CROSS-DATABASE JOINS):")
        for key_name, key_info in shared_keys.items():
            bq_f = key_info.get("bigquery_field", "")
            neo_f = key_info.get("neo4j_field", "")
            desc = key_info.get("description", "")
            lines.append(f"  - Join Key '{key_name}': {bq_f} <==> {neo_f}")
            lines.append(f"    Purpose: {desc}")

    return "\n".join(lines)


# ==============================================================================
# 2. Ollama LLM Interaction & JSON Extraction
# ==============================================================================
def check_ollama_status(endpoint: str = OLLAMA_ENDPOINT) -> bool:
    """Verifies that the local Ollama service is reachable."""
    base_url = endpoint.split("/api")[0] + "/api/tags"
    try:
        r = requests.get(base_url, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def build_dispatch_prompt(catalog_text: str, user_question: str) -> str:
    """Constructs the routing prompt enforcing strict JSON output for single or cross-DB queries."""
    return f"""You are an enterprise AI Query Dispatcher (Step 1 Router).
Your task is to analyze the user's natural language question and determine which database(s) are needed based on our catalog of available tables, nodes, and federated shared join keys.

{catalog_text}

ROUTING CRITERIA:
1. Single Database Queries:
   - Route to ['bigquery_thelook'] with requires_join=false: If the question ONLY asks about online store transactions, retail consumer accounts, shopping carts, e-commerce orders, digital products, inventory items, distribution centers, or website clickstream events.
   - Route to ['neo4j_northwind'] with requires_join=false: If the question ONLY asks about internal HR, organizational reporting hierarchy (employees, reports_to), supply chain logistics, vendors/suppliers, product manufacturing categories, or corporate B2B clients.
2. Cross-Database Queries:
   - If the question requires data from both the e-commerce store and internal HR/Supply chain, include both databases in the array and set requires_join to true.
     For example: questions correlating online sales revenue with backend suppliers, or checking if company employees (HR) placed retail web orders, require both databases joined via our federated shared keys.

OUTPUT REQUIREMENTS:
Output ONLY a strict JSON object with no markdown fences, no backticks, and no conversational explanation.
Expected JSON format:
{{"selected_dbs": ["database_name"], "requires_join": true_or_false, "reason": "short explanation of why based on the tables/nodes available"}}

Valid database_name values: 'bigquery_thelook', 'neo4j_northwind'.

User Question: {user_question}
JSON:"""


def call_ollama_router(prompt: str, model: str = OLLAMA_MODEL, endpoint: str = OLLAMA_ENDPOINT, timeout: int = OLLAMA_TIMEOUT) -> str:
    """Calls the local Ollama LLM with zero temperature for deterministic routing."""
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "top_p": 0.9,
        }
    }
    response = requests.post(endpoint, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    return data.get("response", "").strip()


def normalize_db_name(name: str) -> str:
    """Normalizes colloquial or raw LLM names to official database IDs."""
    n = name.lower()
    if "bigquery" in n or "thelook" in n:
        return "bigquery_thelook"
    elif "neo4j" in n or "northwind" in n:
        return "neo4j_northwind"
    return name


def parse_routing_json(raw_text: str) -> Dict[str, Any]:
    """Extracts and validates the strict multi-database routing JSON from LLM output."""
    text = raw_text.strip()

    # Clean markdown code fences if wrapped
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|JSON)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Extract outermost JSON object bounds
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback regex extraction
        dbs_match = re.search(r'"selected_dbs"\s*:\s*\[([^\]]+)\]', text)
        db_single_match = re.search(r'"selected_db"\s*:\s*"([^"]+)"', text)
        join_match = re.search(r'"requires_join"\s*:\s*(true|false)', text, re.IGNORECASE)
        reason_match = re.search(r'"reason"\s*:\s*"([^"]+)"', text)

        dbs = []
        if dbs_match:
            dbs = [item.strip().strip('"').strip("'") for item in dbs_match.group(1).split(",") if item.strip()]
        elif db_single_match:
            dbs = [db_single_match.group(1).strip()]

        requires_join = join_match.group(1).lower() == "true" if join_match else (len(dbs) > 1)
        reason = reason_match.group(1) if reason_match else "Extracted via pattern matching."

        data = {
            "selected_dbs": dbs,
            "requires_join": requires_join,
            "reason": reason
        }

    raw_dbs = data.get("selected_dbs")
    if raw_dbs is None:
        single = data.get("selected_db")
        raw_dbs = [single] if single else ["bigquery_thelook"]
    elif isinstance(raw_dbs, str):
        raw_dbs = [raw_dbs]

    # Normalize database names and deduplicate
    normalized_dbs = []
    for db in raw_dbs:
        norm = normalize_db_name(db)
        if norm and norm not in normalized_dbs:
            normalized_dbs.append(norm)

    requires_join = bool(data.get("requires_join", False))
    if len(normalized_dbs) > 1:
        requires_join = True

    reason = data.get("reason", "").strip()

    return {
        "selected_dbs": normalized_dbs,
        "requires_join": requires_join,
        "reason": reason
    }


# ==============================================================================
# 3. Interactive REPL Loop
# ==============================================================================
def start_dispatcher():
    """Runs the interactive Step 1 Dispatcher REPL loop."""
    print("=" * 75)
    print("     STEP 1 DISPATCHER: FEDERATED AI DATA ROUTER (CROSS-DB CAPABLE)")
    print("=" * 75)

    # 1. Load Abstract Catalog
    print("\n[*] Loading Master Semantic Layer Abstract Catalog...")
    try:
        catalog = load_master_catalog()
        catalog_prompt = format_catalog_for_prompt(catalog)
        dbs = list(catalog.get("databases", {}).keys())
        shared_keys = list(catalog.get("shared_keys", {}).keys())
        print(f"    [OK] Loaded catalog from: {os.path.basename(MASTER_CATALOG_FILE)}")
        print(f"    [OK] Registered databases: {', '.join(dbs)}")
        print(f"    [OK] Shared join keys:    {', '.join(shared_keys)}")
    except Exception as e:
        print(f"    [ERROR] Failed to load catalog: {e}")
        return

    # 2. Check Ollama Service
    print(f"\n[*] Checking Ollama Router LLM at {OLLAMA_ENDPOINT}...")
    if check_ollama_status():
        print(f"    [OK] Ollama is active. Router model: '{OLLAMA_MODEL}'")
    else:
        print(f"    [WARNING] Ollama is NOT reachable at {OLLAMA_ENDPOINT}!")
        print("    Please ensure Ollama is running ('ollama serve').")

    print("\n" + "-" * 75)
    print(" Enter your question to route (single-DB or cross-DB). Commands:")
    print("   'catalog' -> View high-level abstract catalog and shared join keys")
    print("   'clear'   -> Clear terminal screen")
    print("   'exit'    -> Quit dispatcher")
    print("-" * 75)

    while True:
        try:
            user_input = input("\nDispatcher > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\nExiting Dispatcher. Goodbye!")
            break

        if not user_input:
            continue

        cmd = user_input.lower()
        if cmd in ("exit", "quit", "q"):
            print("Exiting Dispatcher. Goodbye!")
            break
        elif cmd in ("catalog", "schema"):
            print("\n" + catalog_prompt + "\n")
            continue
        elif cmd == "clear":
            os.system("cls" if os.name == "nt" else "clear")
            continue

        # Route User Query
        print(f"\n[Evaluating question via {OLLAMA_MODEL}...]")
        prompt = build_dispatch_prompt(catalog_prompt, user_input)
        t0 = time.time()
        try:
            raw_response = call_ollama_router(prompt)
            routing_result = parse_routing_json(raw_response)
            selected_dbs = routing_result["selected_dbs"]
            requires_join = routing_result["requires_join"]
            reason = routing_result["reason"]
            elapsed = time.time() - t0

            # Required dispatch output formatting
            if requires_join or len(selected_dbs) > 1:
                db_str = ", ".join(selected_dbs)
                print(f"\nRouting to [{db_str}] (Cross-Database Join Required)...")
            else:
                target = selected_dbs[0] if selected_dbs else "bigquery_thelook"
                print(f"\nRouting to [{target}]...")

            print(f"Reason: {reason}")
            print(f"(Decision resolved in {elapsed:.2f}s)")

        except Exception as e:
            print(f"[DISPATCH ERROR] Could not route query: {e}")


if __name__ == "__main__":
    start_dispatcher()

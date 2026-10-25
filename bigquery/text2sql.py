"""
Text2SQL Terminal Application for Google Cloud BigQuery.
Translates plain English queries to BigQuery Standard SQL using a local Ollama LLM (llama3.1),
executes the query on BigQuery, and renders the results in an interactive terminal.
"""

import os
import sys
import json
import re
import time
import requests
from typing import Dict, Any, List, Tuple, Optional

# Support running directly from inside bigquery folder or from project root
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from google.cloud import bigquery

try:
    from dotenv import load_dotenv
    # Load .env from project root or current dir
    load_dotenv(os.path.join(os.path.dirname(current_dir), ".env"))
    load_dotenv(os.path.join(current_dir, ".env"))
except ImportError:
    pass

# ==============================================================================
# Configuration
# ==============================================================================
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

BIGQUERY_BILLING_PROJECT = os.getenv("BIGQUERY_BILLING_PROJECT", "mainpro-507007")
BIGQUERY_TARGET_PROJECT = os.getenv("BIGQUERY_TARGET_PROJECT", "bigquery-public-data")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "thelook_ecommerce")
KEY_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "jsonkeybq.json")

SEMANTIC_LAYER_FILE = os.path.join(current_dir, "unified_semantic_layer_bq_thelook.json")

# Fully-qualified prefix for tables in queries
DATASET_PREFIX = f"`{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}`"

# ==============================================================================
# Business Logic & Metric Calculation Rules
# ==============================================================================
BUSINESS_RULES = [
    f"Fully-Qualified Table References: Always reference tables using backticks with the dataset prefix, for example: `{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}.orders`, `{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}.order_items`, etc.",
    "Total Revenue / Sales Amount: Calculated as SUM(order_items.sale_price) for non-returned items (e.g., WHERE order_items.status NOT IN ('Cancelled', 'Returned')).",
    "Gross Margin / Profit: Calculated as SUM(order_items.sale_price - inventory_items.cost) by joining order_items and inventory_items on inventory_item_id = inventory_items.id.",
    "Completed Orders: Filter using orders.status = 'Complete' (or order_items.status = 'Complete').",
    "Customer Lifetime Spend: Calculated by grouping by users.id, users.first_name, users.last_name and summing order_items.sale_price.",
    "Date & Timestamp Operations: For dates stored as TIMESTAMP (e.g. created_at, delivered_at), use BigQuery standard functions like EXTRACT(YEAR FROM created_at) or FORMAT_TIMESTAMP('%Y-%m', created_at)."
]

# ==============================================================================
# Few-Shot Examples (Guiding BigQuery Standard SQL Syntax & Strict Joins)
# ==============================================================================
FEW_SHOT_EXAMPLES = [
    {
        "question": "What are the top 5 product categories by total sales revenue?",
        "sql": (
            f"SELECT p.category, ROUND(SUM(oi.sale_price), 2) AS total_revenue\n"
            f"FROM `{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}.order_items` oi\n"
            f"JOIN `{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}.products` p ON oi.product_id = p.id\n"
            f"WHERE oi.status NOT IN ('Cancelled', 'Returned')\n"
            f"GROUP BY p.category\n"
            f"ORDER BY total_revenue DESC\n"
            f"LIMIT 5"
        )
    },
    {
        "question": "Find all customers who have spent more than $1000 in total. Return User ID, Name, and Total Spend.",
        "sql": (
            f"SELECT u.id AS user_id, CONCAT(u.first_name, ' ', u.last_name) AS customer_name, ROUND(SUM(oi.sale_price), 2) AS total_spend\n"
            f"FROM `{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}.users` u\n"
            f"JOIN `{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}.order_items` oi ON u.id = oi.user_id\n"
            f"WHERE oi.status = 'Complete'\n"
            f"GROUP BY u.id, customer_name\n"
            f"HAVING total_spend > 1000\n"
            f"ORDER BY total_spend DESC"
        )
    },
    {
        "question": "How many orders were completed each month in 2023?",
        "sql": (
            f"SELECT FORMAT_TIMESTAMP('%Y-%m', created_at) AS order_month, COUNT(order_id) AS completed_orders\n"
            f"FROM `{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}.orders`\n"
            f"WHERE status = 'Complete' AND EXTRACT(YEAR FROM created_at) = 2023\n"
            f"GROUP BY order_month\n"
            f"ORDER BY order_month ASC"
        )
    }
]


# ==============================================================================
# 1. Semantic Layer Schema Loader & Formatter
# ==============================================================================
def resolve_key_path(path: str) -> str:
    """Finds the BigQuery service account JSON credentials file."""
    if os.path.isabs(path) and os.path.exists(path):
        return path
    local_path = os.path.join(current_dir, os.path.basename(path))
    if os.path.exists(local_path):
        return local_path
    root_path = os.path.join(os.path.dirname(current_dir), os.path.basename(path))
    if os.path.exists(root_path):
        return root_path
    return path


def load_semantic_layer(file_path: Optional[str] = None) -> Dict[str, Any]:
    """Loads the unified BigQuery semantic layer JSON file."""
    path = file_path or SEMANTIC_LAYER_FILE
    if not os.path.exists(path):
        root_path = os.path.join(os.path.dirname(current_dir), os.path.basename(path))
        if os.path.exists(root_path):
            path = root_path
        else:
            raise FileNotFoundError(f"Semantic layer file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_schema_for_llm(semantic_data: Dict[str, Any]) -> str:
    """
    Extracts tables, exact column data types, and foreign key JOIN paths
    from the unified semantic layer into a high-density, context-rich format.
    """
    entities = semantic_data.get("entities", {})
    relationships = semantic_data.get("relationships", [])

    lines = [f"Tables & Columns (Dataset Prefix: `{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}`):"]
    for table_name, table_info in entities.items():
        columns = table_info.get("attributes", [])
        col_strs = []
        for c in columns:
            name = c.get("name")
            data_type = c.get("data_type", "STRING")
            col_strs.append(f"{name}: {data_type}")
        
        cols_formatted = ", ".join(col_strs) if col_strs else "no columns"
        lines.append(f"  `{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}.{table_name}` ({cols_formatted})")

    lines.append("\nExplicit Foreign Key JOIN Paths (Use ONLY these join conditions):")
    seen_joins = set()
    for rel in relationships:
        src = rel.get("source_entity")
        src_attr = rel.get("source_attribute")
        tgt = rel.get("target_entity")
        tgt_attr = rel.get("target_attribute")
        if src and src_attr and tgt and tgt_attr:
            join_str = f"  {src}.{src_attr} = {tgt}.{tgt_attr}"
            if join_str not in seen_joins:
                seen_joins.add(join_str)
                lines.append(join_str)

    return "\n".join(lines)


# ==============================================================================
# 2. Ollama LLM Interaction & SQL Extraction
# ==============================================================================
def check_ollama_status(endpoint: str = OLLAMA_ENDPOINT) -> bool:
    """Checks whether the local Ollama instance is reachable."""
    base_url = endpoint.split("/api")[0] + "/api/tags"
    try:
        r = requests.get(base_url, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def build_system_prompt(schema_text: str, user_question: str) -> str:
    """
    Builds the system prompt payload combining BigQuery schema context,
    exact column data types, explicit JOIN paths, business rules, and few-shot examples.
    """
    examples_block = "\n\n".join(
        f"Example Question: {ex['question']}\nSQL:\n{ex['sql']}"
        for ex in FEW_SHOT_EXAMPLES
    )

    business_rules_block = "\n".join(f"{i+1}. {rule}" for i, rule in enumerate(BUSINESS_RULES))

    return f"""Task: Generate a valid Google Cloud BigQuery Standard SQL query to answer the user's question.

Database Schema (Tables, Columns with Exact Data Types, and Foreign Key JOIN Paths):
{schema_text}

Business Rules & Calculation Definitions:
{business_rules_block}

Strict Constraints & SQL Generation Rules:
1. Standard SQL: Generate only Google Cloud BigQuery Standard SQL.
2. Fully-Qualified Tables: Always qualify table names using backticks with the dataset prefix: `{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}.<table_name>`.
3. Strict Joins: Adhere strictly to the explicit foreign key JOIN paths defined above. Never invent relationships or join on mismatched columns.
4. Type Safety: Respect column data types (INT64, FLOAT64, STRING, TIMESTAMP, BOOL). For timestamp calculations, use standard BigQuery functions like EXTRACT() or FORMAT_TIMESTAMP().
5. Output ONLY the raw SQL query. Do not wrap in markdown or include conversational text.

Few-Shot Examples:
{examples_block}

Question: {user_question}
SQL query:"""


def call_ollama(prompt: str, model: str = OLLAMA_MODEL, endpoint: str = OLLAMA_ENDPOINT, timeout: int = 120) -> str:
    """Sends the generation prompt to the local Ollama model."""
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


def extract_sql(raw_text: str) -> str:
    """
    Strips markdown code blocks, conversational preamble, comments,
    and literal escapes to extract pure BigQuery Standard SQL.
    """
    text = raw_text.strip()

    # Unescape literal escaped newlines or tabs from LLM text
    if "\\n" in text:
        text = text.replace("\\n", "\n")
    if "\\t" in text:
        text = text.replace("\\t", "\t")

    # Extract inside ```sql ... ``` or ``` ... ``` if present
    match = re.search(r"```(?:sql)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()

    # Strip prefixes like "SQL query:" or "Query:"
    text = re.sub(r"^(?:SQL\s*query|Query|BigQuery\s*SQL|SQL):\s*", "", text, flags=re.IGNORECASE).strip()

    # Keep only SQL statement lines
    lines = text.split("\n")
    sql_lines = []
    sql_keywords = ("SELECT", "WITH", "INSERT", "UPDATE", "DELETE", "CREATE")
    
    in_query = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Stop if model starts explaining after query
        if in_query and (stripped.startswith("Explanation:") or stripped.startswith("Note:") or stripped.startswith("This query")):
            break
        if any(stripped.upper().startswith(kw) for kw in sql_keywords):
            in_query = True
        if in_query:
            sql_lines.append(line)

    if sql_lines:
        text = "\n".join(sql_lines).strip()

    # Strip trailing semicolon
    if text.endswith(";"):
        text = text[:-1].strip()

    return text


# ==============================================================================
# 3. BigQuery Execution & Terminal Table Rendering
# ==============================================================================
def execute_bigquery_sql(client: bigquery.Client, query: str) -> Tuple[List[str], List[List[Any]]]:
    """Executes a SQL query on BigQuery and returns column headers and rows."""
    query_job = client.query(query)
    results = query_job.result()
    
    # Extract column names from schema
    headers = [field.name for field in results.schema] if results.schema else []
    
    rows = []
    for row in results:
        rows.append([row[k] for k in headers])
        
    return headers, rows


def render_table(headers: List[str], rows: List[List[Any]], max_col_width: int = 40):
    """
    Renders an ASCII tabular representation of the query results in the terminal.
    Works out-of-the-box without requiring third-party formatting libraries.
    """
    if not headers:
        print("  [Empty result: No columns returned]")
        return

    # Convert all values to formatted strings
    str_rows = []
    for r in rows:
        str_rows.append([_format_cell(v, max_col_width) for v in r])

    # Compute column widths
    col_widths = [len(h) for h in headers]
    for r in str_rows:
        for idx, cell in enumerate(r):
            col_widths[idx] = max(col_widths[idx], len(cell))

    # Construct borders
    sep_line = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_line = "|" + "|".join(f" {headers[i].ljust(col_widths[i])} " for i in range(len(headers))) + "|"

    print(sep_line)
    print(header_line)
    print(sep_line)

    for r in str_rows:
        row_line = "|" + "|".join(f" {r[i].ljust(col_widths[i])} " for i in range(len(r))) + "|"
        print(row_line)

    print(sep_line)


def _format_cell(value: Any, max_width: int) -> str:
    """Formats cell values cleanly and truncates if overly long."""
    if value is None:
        return "NULL"
    if isinstance(value, float):
        s = f"{value:.2f}" if value % 1 != 0 else f"{value:.0f}"
    else:
        s = str(value)

    if len(s) > max_width:
        return s[:max_width - 3] + "..."
    return s


# ==============================================================================
# 4. Interactive Terminal REPL Loop
# ==============================================================================
def start_terminal_app():
    """Runs the main interactive Text2SQL terminal application loop."""
    print("=" * 65)
    print("      BIGQUERY TEXT2SQL TERMINAL APPLICATION")
    print("=" * 65)

    # 1. Load Semantic Layer
    print(f"\n[*] Loading BigQuery Unified Semantic Layer...")
    try:
        semantic_data = load_semantic_layer()
        schema_text = format_schema_for_llm(semantic_data)
        db_id = semantic_data.get("database_id", "bq_thelook_ecommerce")
        table_count = len(semantic_data.get("entities", {}))
        rel_count = len(semantic_data.get("relationships", []))
        print(f"    [OK] Loaded schema for '{db_id}' ({table_count} Tables, {rel_count} Foreign Key Joins)")
    except Exception as e:
        print(f"    [ERROR] Failed to load semantic layer: {e}")
        return

    # 2. Check Ollama Service
    print(f"\n[*] Checking Ollama service at {OLLAMA_ENDPOINT}...")
    ollama_ok = check_ollama_status()
    if ollama_ok:
        print(f"    [OK] Ollama is active. Using model:\n         '{OLLAMA_MODEL}'")
    else:
        print(f"    [WARNING] Ollama is NOT reachable at {OLLAMA_ENDPOINT}!")
        print("    Please ensure Ollama is running ('ollama serve').")

    # 3. Connect to BigQuery Client
    key_file = resolve_key_path(KEY_PATH)
    print(f"\n[*] Initializing BigQuery Client (billing_project={BIGQUERY_BILLING_PROJECT})...")
    try:
        client = bigquery.Client.from_service_account_json(key_file, project=BIGQUERY_BILLING_PROJECT)
        print(f"    [OK] Connected to Google Cloud BigQuery successfully!")
    except Exception as e:
        print(f"    [ERROR] Failed to initialize BigQuery client: {e}")
        return

    print("\n" + "-" * 65)
    print(" Type your questions in English. Available commands:")
    print("   'schema' -> View current database schema & join paths passed to LLM")
    print("   'clear'  -> Clear terminal screen")
    print("   'exit'   -> Quit the application")
    print("-" * 65 + "\n")

    # 4. REPL Loop
    try:
        while True:
            try:
                user_input = input("\nText2SQL > ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nExiting Text2SQL. Goodbye!")
                break

            if not user_input:
                continue

            cmd = user_input.lower()
            if cmd in ("exit", "quit", "q"):
                print("Exiting Text2SQL. Goodbye!")
                break
            elif cmd == "schema":
                print("\n--- SCHEMA CONTEXT ---")
                print(schema_text)
                print("----------------------\n")
                continue
            elif cmd == "clear":
                os.system("cls" if os.name == "nt" else "clear")
                continue
            elif cmd == "help":
                print("Commands: 'schema', 'clear', 'exit', 'quit'")
                continue

            # Process User Query
            print(f"\n[1/3] Generating BigQuery SQL using Ollama ({OLLAMA_MODEL})...")
            prompt = build_system_prompt(schema_text, user_input)
            
            start_time = time.time()
            try:
                raw_response = call_ollama(prompt)
                sql_query = extract_sql(raw_response)
            except requests.exceptions.ConnectionError:
                print(f"  [ERROR] Could not connect to Ollama at {OLLAMA_ENDPOINT}.")
                print("  Please ensure Ollama is running.")
                continue
            except Exception as e:
                print(f"  [ERROR] Ollama generation failed: {e}")
                continue

            llm_time = time.time() - start_time
            print(f"      (Generated in {llm_time:.2f}s)")
            print("\n[2/3] Generated BigQuery SQL Query:")
            print("  \033[96m" + sql_query + "\033[0m")

            # Execute Query
            print(f"\n[3/3] Executing query on BigQuery...")
            db_start = time.time()
            try:
                headers, rows = execute_bigquery_sql(client, sql_query)
                db_time = time.time() - db_start
                print(f"      (Executed in {db_time:.2f}s | Returned {len(rows)} record{'s' if len(rows) != 1 else ''})\n")
                
                if rows:
                    render_table(headers, rows)
                else:
                    print("  [Query executed successfully, but returned 0 records]")
            except Exception as e:
                print(f"  [ERROR] Query execution failed: {e}")

    finally:
        client.close()


if __name__ == "__main__":
    start_terminal_app()

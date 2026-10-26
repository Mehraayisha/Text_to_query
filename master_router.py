"""
Federated AI Data Router Terminal Application.

Federates two corporate databases within the same enterprise:
1. bigquery_thelook (SQL)    -> Online Store (B2C E-Commerce)
2. neo4j_northwind (Cypher)  -> Internal HR & Supply Chain (B2B Logistics)

Leverages a local Ollama LLM (llama3.1) and a Federated Master Semantic Layer
(master_semantic_layer.json) to dynamically route user questions, generate the
appropriate SQL or Cypher query, execute it on the target database, and render
the results in an interactive terminal table.
"""

import os
import sys
import json
import re
import time
import requests
from typing import Dict, Any, List, Tuple, Optional

# Support running directly from project root or any subfolder
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Ensure official neo4j driver is imported cleanly without directory shadowing
try:
    from neo4j import GraphDatabase
except ImportError:
    import importlib.machinery, importlib.util
    search_paths = [p for p in sys.path if os.path.abspath(p) not in (current_dir, "")]
    spec = importlib.machinery.PathFinder.find_spec('neo4j', search_paths)
    if spec:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        GraphDatabase = getattr(mod, "GraphDatabase")
    else:
        raise

from google.cloud import bigquery

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(current_dir, ".env"))
except ImportError:
    pass

# ==============================================================================
# Configuration & Environment Variables
# ==============================================================================
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))

# BigQuery Settings (Online Store)
BIGQUERY_BILLING_PROJECT = os.getenv("BIGQUERY_BILLING_PROJECT", "mainpro-507007")
BIGQUERY_TARGET_PROJECT = os.getenv("BIGQUERY_TARGET_PROJECT", "bigquery-public-data")
BIGQUERY_DATASET = os.getenv("BIGQUERY_DATASET", "thelook_ecommerce")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "jsonkeybq.json")

# Neo4j Settings (Internal HR & Supply Chain)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password123")
raw_neo_db = os.getenv("NEO4J_DATABASE", "neo4j")
NEO4J_DATABASE = "neo4j" if (not raw_neo_db or raw_neo_db.lower() == "northwind") else raw_neo_db

MASTER_SEMANTIC_LAYER_FILE = os.path.join(current_dir, "master_semantic_layer.json")


# ==============================================================================
# 1. Master Semantic Layer Loader & Context Builder
# ==============================================================================
def resolve_file_path(filename: str) -> str:
    """Finds absolute file path checking current dir and project root."""
    if os.path.isabs(filename) and os.path.exists(filename):
        return filename
    local_path = os.path.join(current_dir, os.path.basename(filename))
    if os.path.exists(local_path):
        return local_path
    return filename


def load_master_semantic_layer(file_path: Optional[str] = None) -> Dict[str, Any]:
    """Loads the master federated semantic layer JSON file."""
    path = resolve_file_path(file_path or MASTER_SEMANTIC_LAYER_FILE)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Master Semantic Layer file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_effective_neo4j_database() -> str:
    """
    Returns the appropriate database name based on the connection URI:
    - If connecting to the public Neo4j Labs sandbox (demo.neo4jlabs.com), it MUST use 'northwind'.
    - If connecting to local Neo4j (bolt://localhost), it uses the default 'neo4j'.
    """
    if "demo.neo4jlabs.com" in NEO4J_URI:
        return "northwind"
    env_db = os.getenv("NEO4J_DATABASE")
    if env_db and env_db.lower() not in ("northwind", "default"):
        return env_db
    return "neo4j"


def format_master_context_for_llm(master_data: Dict[str, Any]) -> str:
    """
    Serializes the master semantic layer catalog into a structured, high-density format
    for the LLM prompt, ensuring exact table names, node labels, relationship paths,
    and query generation rules are present.
    """
    databases = master_data.get("databases", {})
    context_sections = []

    context_sections.append("=" * 70)
    context_sections.append("FEDERATED ENTERPRISE DATABASE TOPOLOGY (SAME COMPANY):")
    context_sections.append("=" * 70)

    for db_key, db_info in databases.items():
        db_id = db_info.get("database_id", db_key)
        db_type = db_info.get("database_type") or db_info.get("type", "")
        dialect = db_info.get("dialect", "")
        domain = db_info.get("business_domain", "")
        desc = db_info.get("description", "")

        context_sections.append(f"\nDATABASE: {db_id}")
        context_sections.append(f"  - Business Domain: {domain}")
        context_sections.append(f"  - Dialect: {dialect} ({db_type})")
        context_sections.append(f"  - Description: {desc}")

        if "sql" in db_type.lower():
            prefix = f"`{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}`"
            context_sections.append(f"  - Tables (Prefix: {prefix}):")
            tables = db_info.get("tables", {})
            for tbl, t_desc in tables.items():
                context_sections.append(f"      * {prefix}.{tbl}: {t_desc}")
            context_sections.append("  - SQL Foreign Key Joins:")
            context_sections.append("      * order_items.order_id = orders.order_id (CRITICAL: orders PK is 'order_id', NOT 'id')")
            context_sections.append("      * order_items.user_id = users.id")
            context_sections.append("      * order_items.product_id = products.id")
            context_sections.append("      * order_items.inventory_item_id = inventory_items.id")
            context_sections.append("  - BigQuery SQL Rules:")
            context_sections.append(f"      * Always use backtick table prefix: {prefix}.<table_name>")
            context_sections.append("      * Revenue: SUM(order_items.sale_price) WHERE status NOT IN ('Cancelled', 'Returned')")
            context_sections.append("  - SQL Example:")
            context_sections.append(f"      * Q: \"What are the top 3 product categories by revenue in our online store?\"")
            context_sections.append(f"        Output: {{\"target_db\": \"{db_id}\", \"query_language\": \"sql\", \"executable_query\": \"SELECT p.category, ROUND(SUM(oi.sale_price), 2) AS total_revenue FROM {prefix}.order_items oi JOIN {prefix}.products p ON oi.product_id = p.id WHERE oi.status NOT IN ('Cancelled', 'Returned') GROUP BY p.category ORDER BY total_revenue DESC LIMIT 3\"}}")

        elif "graph" in db_type.lower():
            context_sections.append("  - Graph Node Labels:")
            nodes = db_info.get("core_nodes", {})
            for node, n_desc in nodes.items():
                context_sections.append(f"      * (:{node}): {n_desc}")
            context_sections.append("  - Graph Relationships & Directions (CRITICAL: YOU MUST RESPECT DIRECTIONS):")
            rels = db_info.get("core_relationships", {})
            for rel, r_desc in rels.items():
                context_sections.append(f"      * {r_desc}")
            context_sections.append("  - Cypher Rules:")
            context_sections.append("      * Category is a separate connected node, NOT a product property: (:Product)-[:PART_OF]->(:Category {categoryName: 'Seafood'})")
            context_sections.append("      * Suppliers supply products: (:Supplier)-[:SUPPLIES]->(:Product)")
            context_sections.append("      * Orders connect to products: (:Order)-[r:ORDERS]->(:Product)")
            context_sections.append("      * Item cost: toFloat(r.unitPrice) * toInteger(r.quantity)")
            context_sections.append("      * Never place WHERE after RETURN (use WITH ... WHERE before RETURN)")
            context_sections.append("  - Cypher Example:")
            context_sections.append(f"      * Q: \"Which suppliers supply products belonging to the Seafood category?\"")
            context_sections.append(f"        Output: {{\"target_db\": \"{db_id}\", \"query_language\": \"cypher\", \"executable_query\": \"MATCH (s:Supplier)-[:SUPPLIES]->(p:Product)-[:PART_OF]->(c:Category) WHERE c.categoryName = 'Seafood' RETURN DISTINCT s.companyName AS SupplierName, s.contactName AS Contact\"}}")

    shared_keys = master_data.get("shared_keys", {})
    if shared_keys:
        context_sections.append("\nFEDERATED SHARED KEYS:")
        for k_name, k_info in shared_keys.items():
            context_sections.append(f"  - {k_name}: {k_info.get('bigquery_field')} <==> {k_info.get('neo4j_field')}")

    return "\n".join(context_sections)


# ==============================================================================
# 2. Ollama Routing LLM Prompt & Interaction
# ==============================================================================
def check_ollama_status(endpoint: str = OLLAMA_ENDPOINT) -> bool:
    """Checks whether the local Ollama instance is reachable."""
    base_url = endpoint.split("/api")[0] + "/api/tags"
    try:
        r = requests.get(base_url, timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def build_system_prompt(master_context: str, user_question: str) -> str:
    """
    Constructs the prompt instructing llama3.1 to act as a strict Federated AI Data Router.
    """
    return f"""You are the Federated AI Data Router and Query Generator for our enterprise.
Our company owns and operates two federated databases:
1. `bigquery_thelook` (SQL): Our Online Store e-commerce web platform (retail users, shopping orders, order items, digital products, inventory costs, web events, distribution centers).
2. `neo4j_northwind` (Cypher): Our Internal HR and Supply Chain network (commercial vendors/suppliers, product categories, corporate B2B customer accounts, supply chain purchase orders, freight shipping).

{master_context}

CRITICAL ROUTING & QUERY GENERATION RULES:
1. Routing Decision:
   - Single-Database Queries: If the question ONLY asks about one database (e.g. online retail orders OR internal supply chain vendors), set "is_cross_db": false.
   - Cross-Database (Mixed) Queries: If the question asks for data spanning BOTH databases (e.g. "find top-selling online store categories AND check which internal supply chain vendors supply them", or "check internal employees who bought products on the online store"), set "is_cross_db": true, and generate both queries.

2. Query Accuracy & Standards:
   - For `bigquery_thelook`: Generate valid Google Cloud BigQuery Standard SQL. Always prefix tables with `{BIGQUERY_TARGET_PROJECT}.{BIGQUERY_DATASET}` using backticks. Use exact column names (note: `orders` primary key is `order_id`, NOT `id`). Copy explicit foreign key JOIN conditions verbatim.
   - For `neo4j_northwind`: Generate valid Neo4j Cypher. Never put a WHERE clause after RETURN (use WITH ... WHERE before RETURN). Category is a connected node: `(:Product)-[:PART_OF]->(:Category)`. Suppliers supply products: `(:Supplier)-[:SUPPLIES]->(:Product)`. Orders connect to products: `(:Order)-[r:ORDERS]->(:Product)`. When calculating values, explicitly cast numeric strings (e.g. `toFloat(r.unitPrice) * toInteger(r.quantity)`, `toFloat(o.freight)`).

3. Output Format:
   You MUST return ONLY a single, strictly valid JSON object (no markdown fences, no conversational text).
   
   If Single-Database:
   {{
     "is_cross_db": false,
     "target_db": "bigquery_thelook" or "neo4j_northwind",
     "query_language": "sql" or "cypher",
     "executable_query": "YOUR_EXACT_QUERY_HERE"
   }}

   If Cross-Database (Mixed Query):
   {{
     "is_cross_db": true,
     "step1": {{
       "target_db": "bigquery_thelook",
       "query_language": "sql",
       "executable_query": "SELECT ..."
     }},
     "step2": {{
       "target_db": "neo4j_northwind",
       "query_language": "cypher",
       "executable_query": "MATCH (s:Supplier)-[:SUPPLIES]->(p:Product)-[:PART_OF]->(c:Category) WHERE c.categoryName IN ['category1', 'category2', 'category3'] RETURN DISTINCT s.companyName AS Supplier, s.contactName AS Contact, c.categoryName AS Category"
     }}
   }}

User Question: {user_question}
JSON Routing Output:"""


def call_ollama(prompt: str, model: str = OLLAMA_MODEL, endpoint: str = OLLAMA_ENDPOINT, timeout: int = OLLAMA_TIMEOUT) -> str:
    """Sends the routing prompt to the local Ollama LLM."""
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


def normalize_target_db(name: str) -> str:
    n = name.lower()
    if "bigquery" in n or "thelook" in n:
        return "bigquery_thelook"
    elif "neo4j" in n or "northwind" in n:
        return "neo4j_northwind"
    return name


def normalize_query_lang(lang: str, target_db: str) -> str:
    l = lang.lower()
    if "cypher" in l or target_db == "neo4j_northwind":
        return "cypher"
    return "sql"


def clean_query_string(q: str, query_lang: str) -> str:
    if "\\n" in q:
        q = q.replace("\\n", "\n")
    if "\\\"" in q:
        q = q.replace('\\"', '"')
    if query_lang == "cypher" and q.endswith(";"):
        q = q[:-1].strip()
    return q.strip()


def parse_routing_response(raw_text: str) -> Dict[str, Any]:
    """
    Parses and sanitizes the strict JSON routing object from LLM output.
    Supports both single-database queries and 2-step cross-database plans.
    """
    text = raw_text.strip()

    # Strip markdown code blocks if the LLM wrapped it
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|JSON)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    # Find the outermost JSON object bounds
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        text = text[start_idx:end_idx + 1]

    try:
        routing_obj = json.loads(text)
    except json.JSONDecodeError:
        raise ValueError(f"Unable to parse LLM response into strict routing JSON:\n{raw_text}")

    is_cross_db = routing_obj.get("is_cross_db", False)
    if not is_cross_db and ("step1" in routing_obj or "step2" in routing_obj):
        is_cross_db = True

    if is_cross_db:
        step1 = routing_obj.get("step1", {})
        step2 = routing_obj.get("step2", {})

        s1_db = normalize_target_db(step1.get("target_db", "bigquery_thelook"))
        s2_db = normalize_target_db(step2.get("target_db", "neo4j_northwind"))

        s1_lang = normalize_query_lang(step1.get("query_language", "sql"), s1_db)
        s2_lang = normalize_query_lang(step2.get("query_language", "cypher"), s2_db)

        s1_query = clean_query_string(step1.get("executable_query", ""), s1_lang)
        s2_query = clean_query_string(step2.get("executable_query", ""), s2_lang)

        return {
            "is_cross_db": True,
            "step1": {
                "target_db": s1_db,
                "query_language": s1_lang,
                "executable_query": s1_query,
                "description": step1.get("description", "Query Online Store")
            },
            "step2": {
                "target_db": s2_db,
                "query_language": s2_lang,
                "executable_query": s2_query,
                "description": step2.get("description", "Query Supply Chain / HR")
            }
        }
    else:
        target_db = normalize_target_db(routing_obj.get("target_db", "bigquery_thelook"))
        query_lang = normalize_query_lang(routing_obj.get("query_language", "sql"), target_db)
        query = clean_query_string(routing_obj.get("executable_query", ""), query_lang)
        return {
            "is_cross_db": False,
            "target_db": target_db,
            "query_language": query_lang,
            "executable_query": query
        }


# ==============================================================================
# 3. Federated Database Connection & Execution Manager
# ==============================================================================
class FederatedDatabaseManager:
    """
    Manages lazy initialization and execution across federated databases:
    BigQuery (SQL) and Neo4j (Cypher).
    """

    def __init__(self):
        self._bq_client: Optional[bigquery.Client] = None
        self._neo4j_driver = None

    def get_bigquery_client(self) -> bigquery.Client:
        """Initializes and returns the BigQuery client."""
        if self._bq_client is None:
            key_file = resolve_file_path(GOOGLE_CREDENTIALS)
            if not os.path.exists(key_file):
                raise FileNotFoundError(f"BigQuery credentials file not found: {key_file}")
            self._bq_client = bigquery.Client.from_service_account_json(
                key_file,
                project=BIGQUERY_BILLING_PROJECT
            )
        return self._bq_client

    def get_neo4j_driver(self):
        """Initializes and returns the Neo4j driver."""
        if self._neo4j_driver is None:
            self._neo4j_driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
        return self._neo4j_driver

    def execute_bigquery(self, query: str) -> Tuple[List[str], List[List[Any]]]:
        """Executes Standard SQL on BigQuery."""
        client = self.get_bigquery_client()
        query_job = client.query(query)
        results = query_job.result()
        headers = [field.name for field in results.schema] if results.schema else []
        rows = [[row[k] for k in headers] for row in results]
        return headers, rows

    def execute_neo4j(self, query: str) -> Tuple[List[str], List[List[Any]]]:
        """Executes Cypher on Neo4j in READ mode."""
        driver = self.get_neo4j_driver()
        effective_db = get_effective_neo4j_database()
        session_kwargs = {"default_access_mode": "READ"}
        if effective_db:
            session_kwargs["database"] = effective_db

        with driver.session(**session_kwargs) as session:
            result = session.run(query)
            headers = list(result.keys())
            rows = []
            for record in result:
                row = []
                for k in headers:
                    val = record[k]
                    if hasattr(val, "items"):
                        val = dict(val.items())
                    row.append(val)
                rows.append(row)
            return headers, rows

    def execute(self, target_db: str, query: str) -> Tuple[List[str], List[List[Any]]]:
        """Routes execution to the designated database driver."""
        if target_db == "bigquery_thelook":
            return self.execute_bigquery(query)
        elif target_db == "neo4j_northwind":
            return self.execute_neo4j(query)
        else:
            raise ValueError(f"Unknown target database: '{target_db}'")

    def close(self):
        """Closes any open database connections."""
        if self._neo4j_driver:
            try:
                self._neo4j_driver.close()
            except Exception:
                pass


# ==============================================================================
# 4. Terminal ASCII Table Rendering
# ==============================================================================
def _format_cell(value: Any, max_width: int) -> str:
    """Formats cell values cleanly and truncates if overly long."""
    if value is None:
        return "NULL"
    if isinstance(value, float):
        s = f"{value:.2f}" if value % 1 != 0 else f"{value:.0f}"
    elif isinstance(value, dict):
        s = json.dumps(value, default=str)
    elif isinstance(value, (list, tuple)):
        s = str(value)
    else:
        s = str(value)

    if len(s) > max_width:
        return s[:max_width - 3] + "..."
    return s


def render_table(headers: List[str], rows: List[List[Any]], max_col_width: int = 45):
    """
    Renders an ASCII table representation of query results in the terminal.
    """
    if not headers:
        print("  [Empty result: No columns returned]")
        return

    if not rows:
        print("  [Empty result set: 0 rows returned]")
        return

    str_rows = [[_format_cell(v, max_col_width) for v in r] for r in rows]

    # Compute column widths
    col_widths = [len(h) for h in headers]
    for r in str_rows:
        for idx, cell in enumerate(r):
            col_widths[idx] = max(col_widths[idx], len(cell))

    sep_line = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_line = "|" + "|".join(f" {headers[i].ljust(col_widths[i])} " for i in range(len(headers))) + "|"

    print(sep_line)
    print(header_line)
    print(sep_line)

    for r in str_rows:
        row_line = "|" + "|".join(f" {r[i].ljust(col_widths[i])} " for i in range(len(r))) + "|"
        print(row_line)

    print(sep_line)
    print(f"  ({len(rows)} row{'s' if len(rows) != 1 else ''} returned)\n")


# ==============================================================================
# 5. Interactive REPL Loop
# ==============================================================================
def start_federated_router():
    """Runs the main Federated AI Data Router terminal application loop."""
    print("=" * 75)
    print("          FEDERATED AI DATA ROUTER (BigQuery + Neo4j)")
    print("=" * 75)

    # 1. Load Master Semantic Layer
    print("\n[*] Loading Master Semantic Layer...")
    try:
        master_data = load_master_semantic_layer()
        master_context = format_master_context_for_llm(master_data)
        databases = master_data.get("databases", {})
        print(f"    [OK] Loaded Master Semantic Layer: '{master_data.get('description', '')}'")
        print("    Federated Data Sources Registered:")
        for db_id, db_info in databases.items():
            print(f"      * {db_id}: {db_info.get('business_domain')} [{db_info.get('dialect')}]")
    except Exception as e:
        print(f"    [ERROR] Failed to load master semantic layer: {e}")
        return

    # 2. Check Ollama Service
    print(f"\n[*] Checking Ollama Router LLM at {OLLAMA_ENDPOINT}...")
    if check_ollama_status():
        print(f"    [OK] Ollama is active. Using router model: '{OLLAMA_MODEL}'")
    else:
        print(f"    [WARNING] Ollama is NOT reachable at {OLLAMA_ENDPOINT}!")
        print("    Please ensure Ollama is running ('ollama serve').")

    # 3. Initialize Federated Database Manager
    db_manager = FederatedDatabaseManager()

    print("\n" + "-" * 75)
    print(" Ask any question across the enterprise in natural language.")
    print(" Commands:")
    print("   'schema'    -> View master semantic layer & database topology")
    print("   'dbs'       -> List registered databases & their business domains")
    print("   'clear'     -> Clear the terminal screen")
    print("   'exit'      -> Quit the application")
    print("-" * 75)

    try:
        while True:
            try:
                user_input = input("\nFederatedRouter > ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nExiting Federated AI Data Router. Goodbye!")
                break

            if not user_input:
                continue

            cmd = user_input.lower()
            if cmd in ("exit", "quit", "q"):
                print("Exiting Federated AI Data Router. Goodbye!")
                break
            elif cmd == "schema":
                print("\n" + master_context + "\n")
                continue
            elif cmd == "dbs":
                print("\nRegistered Federated Databases:")
                for db_id, db_info in databases.items():
                    print(f"  * {db_id} ({db_info.get('database_name')})")
                    print(f"    Domain:  {db_info.get('business_domain')}")
                    print(f"    Dialect: {db_info.get('dialect')}")
                    print(f"    Desc:    {db_info.get('description')}\n")
                continue
            elif cmd == "clear":
                os.system("cls" if os.name == "nt" else "clear")
                continue
            elif cmd == "help":
                print("Commands: 'schema', 'dbs', 'clear', 'exit', 'quit'")
                continue

            # Step 1: Query Ollama LLM to Route and Generate Query
            print(f"\n[1/3] Routing question & generating query plan via Ollama ({OLLAMA_MODEL})...")
            prompt = build_system_prompt(master_context, user_input)
            t_start = time.time()
            try:
                raw_response = call_ollama(prompt)
                routing_data = parse_routing_response(raw_response)
                llm_time = time.time() - t_start
            except Exception as e:
                print(f"    [ROUTING ERROR] Failed to route query: {e}")
                continue

            # Case A: Single Database Query
            if not routing_data.get("is_cross_db"):
                target_db = routing_data["target_db"]
                query_lang = routing_data["query_language"]
                query = routing_data["executable_query"]

                db_domain = databases.get(target_db, {}).get("business_domain", target_db)
                print(f"    [OK] Routed in {llm_time:.2f}s:")
                print(f"         Target DB:      {target_db} ({db_domain})")
                print(f"         Query Language: {query_lang.upper()}")
                print("\n" + "=" * 75)
                print(f"EXECUTABLE {query_lang.upper()} QUERY:")
                print("-" * 75)
                print(query)
                print("=" * 75)

                print(f"\n[2/3] Connecting & executing query on {target_db}...")
                t_exec = time.time()
                try:
                    headers, rows = db_manager.execute(target_db, query)
                    exec_time = time.time() - t_exec
                    print(f"    [OK] Query executed successfully in {exec_time:.2f}s. Rendering table:\n")
                    render_table(headers, rows)
                except Exception as e:
                    print(f"    [EXECUTION ERROR] Query failed on {target_db}: {e}")
                    continue

            # Case B: Cross-Database (Mixed) 2-Step Query
            else:
                print(f"    [OK] Cross-Database Plan generated in {llm_time:.2f}s!")
                step1 = routing_data["step1"]
                step2 = routing_data["step2"]

                print("\n" + "=" * 75)
                print("FEDERATED CROSS-DATABASE 2-STEP PLAN:")
                print("-" * 75)
                print(f"  Step 1 ({step1['target_db'].upper()} - {step1['query_language'].upper()}):")
                print(f"    {step1['executable_query']}")
                print(f"  Step 2 ({step2['target_db'].upper()} - {step2['query_language'].upper()}):")
                print(f"    {step2['executable_query']}")
                print("=" * 75)

                # Execute Step 1
                print(f"\n[Step 1/2] Executing on {step1['target_db']} ({step1['query_language'].upper()})...")
                t1 = time.time()
                try:
                    h1, r1 = db_manager.execute(step1["target_db"], step1["executable_query"])
                    print(f"    [OK] Step 1 finished in {time.time() - t1:.2f}s. Results from {step1['target_db']}:\n")
                    render_table(h1, r1)
                except Exception as e:
                    print(f"    [STEP 1 ERROR] Query failed on {step1['target_db']}: {e}")
                    continue

                # Dynamically inject Step 1 output values into Step 2 if placeholders or $values are used
                step2_query = step2["executable_query"]
                extracted_vals = []
                if r1:
                    extracted_vals = [str(r[0]) for r in r1 if r[0] is not None]
                    formatted_vals = json.dumps(extracted_vals)
                    step2_query = re.sub(r"\['category\d+'(?:\s*,\s*'category\d+')*\]", formatted_vals, step2_query)
                    step2_query = re.sub(r'\["category\d+"(?:\s*,\s*"category\d+")*\]', formatted_vals, step2_query)
                    for ph in ["$values", "$categories", "$names", "$emails", "['value1', 'value2']"]:
                        if ph in step2_query:
                            step2_query = step2_query.replace(ph, formatted_vals)

                # Clean up duplicate MATCH or syntax glitches if present
                if "MATCH" in step2_query and step2_query.count("MATCH") > 1 and "WITH" not in step2_query:
                    # Keep the last full valid MATCH clause if repeated
                    match_parts = re.split(r"(?=MATCH\s+)", step2_query)
                    if len(match_parts) > 1:
                        step2_query = match_parts[-1].strip()

                print(f"\n[Step 2/2] Connecting & executing on {step2['target_db']} ({step2['query_language'].upper()})...")
                print(f"    Resolved Query: {step2_query}")
                t2 = time.time()
                try:
                    h2, r2 = db_manager.execute(step2["target_db"], step2_query)
                    print(f"    [OK] Step 2 finished in {time.time() - t2:.2f}s. Results from {step2['target_db']}:\n")
                    render_table(h2, r2)
                    if not r2 and extracted_vals:
                        print(f"  Note: 0 matching records found in {step2['target_db']} for values {extracted_vals}.")
                        print("  (Our online store catalog contains retail apparel, while internal Northwind supply chain catalogs focus on food & beverage suppliers).\n")
                except Exception as e:
                    print(f"    [STEP 2 ERROR] Query failed on {step2['target_db']}: {e}")
                    continue

                print("  [FEDERATION COMPLETE] Successfully dispatched across both databases.\n")

    finally:
        db_manager.close()


if __name__ == "__main__":
    start_federated_router()

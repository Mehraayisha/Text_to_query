"""
Text2Cypher Terminal Application for Neo4j.
Translates plain English queries to Cypher using a local Ollama LLM,
executes the query on Neo4j, and renders the results in an interactive terminal.
"""

import os
import sys
import json
import re
import time
import requests
from typing import Dict, Any, List, Tuple, Optional

# Support running directly from inside neo4j folder or from project root
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Ensure official neo4j driver is imported cleanly
try:
    from neo4j import GraphDatabase
except ImportError:
    import importlib.machinery, importlib.util
    parent_dir = os.path.dirname(current_dir)
    search_paths = [p for p in sys.path if os.path.abspath(p) not in (current_dir, parent_dir, "")]
    spec = importlib.machinery.PathFinder.find_spec('neo4j', search_paths)
    if spec:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        GraphDatabase = getattr(mod, "GraphDatabase")
    else:
        raise

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

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://demo.neo4jlabs.com")
NEO4J_USER = os.getenv("NEO4J_USER", "northwind")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "northwind")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "northwind")

SEMANTIC_LAYER_FILE = os.path.join(current_dir, "unified_semantic_layer_neo4j_northwind.json")


# ==============================================================================
# 1. Semantic Layer Schema Loader & Formatter
# ==============================================================================
def load_semantic_layer(file_path: Optional[str] = None) -> Dict[str, Any]:
    """Loads the unified semantic layer JSON file."""
    path = file_path or SEMANTIC_LAYER_FILE
    if not os.path.exists(path):
        # Look in project root
        root_path = os.path.join(os.path.dirname(current_dir), os.path.basename(path))
        if os.path.exists(root_path):
            path = root_path
        else:
            raise FileNotFoundError(f"Semantic layer file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# Business Logic & Calculation Rules
BUSINESS_RULES = [
    "Total Cost of an Order: An Order connects to its items through the ORDERS relationship: (o:Order)-[r:ORDERS]->(p:Product). Each item cost is computed by multiplying unitPrice by quantity: toFloat(r.unitPrice) * toInteger(r.quantity).",
    "Customer Total Purchases / Spend: To find total cost of customer purchases, traverse Customer -> Order -> Product and sum the item costs: MATCH (c:Customer)-[:PURCHASED]->(o:Order)-[r:ORDERS]->(p:Product) WITH c, SUM(toFloat(r.unitPrice) * toInteger(r.quantity)) AS TotalCost.",
    "Freight Cost: Freight on the Order node is stored as a String (e.g., o.freight). When performing math or aggregation on freight, you MUST cast it: SUM(toFloat(o.freight))."
]

# Few-shot examples to guide model syntax, type casting, and business calculations
FEW_SHOT_EXAMPLES = [
    {
        "question": "Which suppliers supply products in the Seafood category?",
        "cypher": (
            "MATCH (s:Supplier)-[:SUPPLIES]->(p:Product)-[:PART_OF]->(c:Category)\n"
            "WHERE c.categoryName = 'Seafood'\n"
            "RETURN DISTINCT s.companyName"
        )
    },
    {
        "question": "find all customers who have made purchases with a total cost greater than $1000. Return the Customer ID, Company Name, and the Total Cost, sorted by the total cost.",
        "cypher": (
            "MATCH (c:Customer)-[:PURCHASED]->(o:Order)-[r:ORDERS]->(p:Product)\n"
            "WITH c, round(SUM(toFloat(r.unitPrice) * toInteger(r.quantity)), 2) AS TotalCost\n"
            "WHERE TotalCost > 1000\n"
            "RETURN c.customerID AS CustomerID, c.companyName AS CompanyName, TotalCost\n"
            "ORDER BY TotalCost DESC"
        )
    },
    {
        "question": "What is the total freight cost for all orders shipped to Germany?",
        "cypher": (
            "MATCH (o:Order)\n"
            "WHERE o.shipCountry = 'Germany'\n"
            "RETURN round(SUM(toFloat(o.freight)), 2) AS TotalFreight"
        )
    }
]


def format_schema_for_llm(semantic_data: Dict[str, Any]) -> str:
    """
    Extracts entity nodes and relationships from the unified semantic layer
    and formats node and relationship properties along with their native database types.
    """
    entities = semantic_data.get("entities", {})
    relationships = semantic_data.get("relationships", [])

    lines = ["Node Labels and Properties (with Data Types):"]
    for entity_name, entity_info in entities.items():
        attrs = entity_info.get("attributes", [])
        attr_strs = []
        for a in attrs:
            name = a.get("name")
            d_type = a.get("data_type", a.get("generic_type", "String"))
            attr_strs.append(f"{name}: {d_type}")
        
        props_formatted = ", ".join(attr_strs) if attr_strs else "no properties"
        lines.append(f"  (:{entity_name} {{{props_formatted}}})")

    lines.append("\nStrict Directional Relationship Triplets and Relationship Properties:")
    seen_patterns = set()
    for rel in relationships:
        src = rel.get("source_entity")
        rel_type = rel.get("name")
        tgt = rel.get("target_entity")
        props = rel.get("properties", [])
        if src and rel_type and tgt:
            if props:
                prop_strs = [f"{p.get('name')}: {p.get('data_type', 'String')}" for p in props if p.get('name')]
                triplet = f"  (:{src})-[:{rel_type} {{{', '.join(prop_strs)}}}]->(:{tgt})"
            else:
                triplet = f"  (:{src})-[:{rel_type}]->(:{tgt})"
            if triplet not in seen_patterns:
                seen_patterns.add(triplet)
                lines.append(triplet)

    return "\n".join(lines)


# ==============================================================================
# 2. Ollama LLM Interaction & Cypher Extraction
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
    Builds the system prompt payload combining database schema context,
    property data types, type casting rules, business rules, and few-shot examples.
    """
    examples_block = "\n\n".join(
        f"Example Question: {ex['question']}\nCypher:\n{ex['cypher']}"
        for ex in FEW_SHOT_EXAMPLES
    )

    business_rules_block = "\n".join(f"{i+1}. {rule}" for i, rule in enumerate(BUSINESS_RULES))

    return f"""Task: Generate a valid Cypher query for the Neo4j graph database to answer the user's question.

Database Schema (Node and Relationship Properties with Types):
{schema_text}

Business Rules & Calculations:
{business_rules_block}

Strict Constraints & Type Casting Rules:
1. Type Casting: Several properties in the database are stored as String (e.g., Order.freight, ORDERS.unitPrice, ORDERS.discount). Neo4j throws a TypeError if arithmetic operators (*, +, -, /) or aggregation functions (SUM, AVG, MIN, MAX) are used on String properties. You MUST explicitly cast String properties using toFloat() or toInteger() (e.g., toFloat(r.unitPrice) * toInteger(r.quantity), SUM(toFloat(o.freight))).
2. Relationship Direction: You must strictly adhere to the provided relationship directions. Never invent new paths or reverse the direction of the provided schema triplets.
3. Quantity & Pricing Location: In the Northwind model, quantity and order unitPrice are located on the ORDERS relationship [r:ORDERS], NOT on the Order node!
4. Use only the node labels, relationships, and property names defined in the schema above.
5. Output ONLY the raw Cypher query. Do not wrap in markdown or include conversational text.

Few-Shot Examples:
{examples_block}

Question: {user_question}
Cypher query:"""


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


def extract_cypher(raw_text: str) -> str:
    """
    Strips markdown code blocks, preamble text, and comments
    to extract only the pure Cypher statement.
    """
    text = raw_text.strip()

    # Unescape literal escaped newlines or tabs from LLM text
    if "\\n" in text:
        text = text.replace("\\n", "\n")
    if "\\t" in text:
        text = text.replace("\\t", "\t")

    # Extract inside ```cypher ... ``` or ``` ... ``` if present
    match = re.search(r"```(?:cypher)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()

    # Strip prefixes like "Cypher query:" or "Query:"
    text = re.sub(r"^(?:Cypher\s*query|Query|Cypher):\s*", "", text, flags=re.IGNORECASE).strip()

    # If multiple lines, remove leading/trailing conversational text
    lines = [l for l in text.split("\n")]
    cypher_lines = []
    cypher_keywords = ("MATCH", "OPTIONAL MATCH", "RETURN", "WITH", "WHERE", "ORDER BY", "LIMIT", "CALL", "UNWIND")
    
    in_query = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Stop if model starts explaining after query
        if in_query and (stripped.startswith("Explanation:") or stripped.startswith("Note:") or stripped.startswith("This query")):
            break
        if any(stripped.upper().startswith(kw) for kw in cypher_keywords):
            in_query = True
        if in_query:
            cypher_lines.append(line)

    if cypher_lines:
        text = "\n".join(cypher_lines).strip()

    # Strip trailing semicolon
    if text.endswith(";"):
        text = text[:-1].strip()

    return text


# ==============================================================================
# 3. Neo4j Execution & Terminal Table Rendering
# ==============================================================================
def execute_cypher(driver, query: str, database: str = NEO4J_DATABASE) -> Tuple[List[str], List[List[Any]]]:
    """Executes a Cypher query on Neo4j and returns column headers and rows."""
    with driver.session(database=database) as session:
        result = session.run(query)
        keys = list(result.keys())
        rows = []
        for record in result:
            row = []
            for k in keys:
                val = record[k]
                # Format Neo4j Node / Relationship objects to cleaner representation
                if hasattr(val, "items"):
                    val = dict(val.items())
                row.append(val)
            rows.append(row)
        return keys, rows


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
    if isinstance(value, dict):
        s = json.dumps(value, default=str)
    elif isinstance(value, (list, tuple)):
        s = str(value)
    else:
        s = str(value)

    if len(s) > max_width:
        return s[:max_width - 3] + "..."
    return s


# ==============================================================================
# 4. Interactive Terminal REPL Loop
# ==============================================================================
def start_terminal_app():
    """Runs the main interactive Text2Cypher terminal application loop."""
    print("=" * 65)
    print("      NEO4J TEXT2CYPHER TERMINAL APPLICATION")
    print("=" * 65)

    # 1. Load Semantic Layer
    print(f"\n[*] Loading Unified Semantic Layer...")
    try:
        semantic_data = load_semantic_layer()
        schema_text = format_schema_for_llm(semantic_data)
        db_id = semantic_data.get("database_id", "neo4j_northwind")
        entity_count = len(semantic_data.get("entities", {}))
        rel_count = len(semantic_data.get("relationships", []))
        print(f"    [OK] Loaded schema for '{db_id}' ({entity_count} Node Labels, {rel_count} Relationships)")
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

    # 3. Connect to Neo4j
    print(f"\n[*] Connecting to Neo4j database ({NEO4J_URI}, db={NEO4J_DATABASE})...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        print(f"    [OK] Connected to Neo4j successfully!")
    except Exception as e:
        print(f"    [ERROR] Failed to connect to Neo4j: {e}")
        return

    print("\n" + "-" * 65)
    print(" Type your questions in English. Available commands:")
    print("   'schema' -> View current database schema passed to the LLM")
    print("   'clear'  -> Clear terminal screen")
    print("   'exit'   -> Quit the application")
    print("-" * 65 + "\n")

    # 4. REPL Loop
    try:
        while True:
            try:
                user_input = input("\nText2Cypher > ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nExiting Text2Cypher. Goodbye!")
                break

            if not user_input:
                continue

            cmd = user_input.lower()
            if cmd in ("exit", "quit", "q"):
                print("Exiting Text2Cypher. Goodbye!")
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
            print(f"\n[1/3] Generating Cypher using Ollama...")
            prompt = build_system_prompt(schema_text, user_input)
            
            start_time = time.time()
            try:
                raw_response = call_ollama(prompt)
                cypher_query = extract_cypher(raw_response)
            except requests.exceptions.ConnectionError:
                print(f"  [ERROR] Could not connect to Ollama at {OLLAMA_ENDPOINT}.")
                print("  Please ensure Ollama is running.")
                continue
            except Exception as e:
                print(f"  [ERROR] Ollama generation failed: {e}")
                continue

            llm_time = time.time() - start_time
            print(f"      (Generated in {llm_time:.2f}s)")
            print("\n[2/3] Generated Cypher Query:")
            print("  \033[96m" + cypher_query + "\033[0m")

            # Execute Query
            print(f"\n[3/3] Executing query on Neo4j...")
            db_start = time.time()
            try:
                headers, rows = execute_cypher(driver, cypher_query)
                db_time = time.time() - db_start
                print(f"      (Executed in {db_time:.2f}s | Returned {len(rows)} record{'s' if len(rows) != 1 else ''})\n")
                
                if rows:
                    render_table(headers, rows)
                else:
                    print("  [Query executed successfully, but returned 0 records]")
            except Exception as e:
                print(f"  [ERROR] Query execution failed: {e}")

    finally:
        driver.close()


if __name__ == "__main__":
    start_terminal_app()

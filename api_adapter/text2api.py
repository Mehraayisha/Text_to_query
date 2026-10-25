"""
Text-to-API Terminal Application.
Translates plain English queries to REST API requests for Fake Store API (https://fakestoreapi.com)
using a local Ollama model (llama3.1), executes the HTTP request, and renders results
as a clean terminal table.
"""

import os
import sys
import json
import re
import time
from typing import Dict, Any, List, Optional, Tuple, Union
import requests

# Optional tabulate support; fallback to built-in formatter if not installed
try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

# Support running directly from api_adapter folder or project root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)

# Ensure proper encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
    load_dotenv(os.path.join(CURRENT_DIR, ".env"))
except ImportError:
    pass

# ==============================================================================
# Configuration
# ==============================================================================
OLLAMA_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
SEMANTIC_LAYER_PATH = os.path.join(CURRENT_DIR, "unified_semantic_layer_http.json")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT", "15"))

# ANSI Color Codes for clean terminal output
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_MAGENTA = "\033[95m"
COLOR_BOLD = "\033[1m"
COLOR_DIM = "\033[2m"
COLOR_RESET = "\033[0m"


# ==============================================================================
# 1. Semantic Layer Loader & Prompt Constructor
# ==============================================================================
class SemanticLayer:
    """Loads and formats the HTTP semantic layer metadata for LLM prompt injection."""

    def __init__(self, filepath: str):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Semantic layer specification not found at: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            self.data: Dict[str, Any] = json.load(f)

        self.base_url: str = self.data.get("base_url", "https://fakestoreapi.com").rstrip("/")
        self.endpoints: Dict[str, Any] = self.data.get("endpoints", {})
        self.few_shot_examples: List[Dict[str, Any]] = self.data.get("few_shot_examples", [])
        self.system_prompt: str = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        prompt_parts = [
            "You are an expert Text-to-HTTP API translation assistant for an e-commerce dashboard.",
            f"Target API Base URL: {self.base_url}",
            "",
            "### TASK:",
            "Translate the user's natural language request into a single, valid JSON HTTP request object.",
            "You MUST output ONLY a valid JSON object matching this exact schema:",
            "{",
            '  "method": "GET",',
            '  "url": "https://fakestoreapi.com/...",',
            '  "params": {',
            '    "param_name": "param_value"',
            "  }",
            "}",
            "",
            "### AVAILABLE ENDPOINTS AND SPECIFICATIONS:"
        ]

        for path, ep in self.endpoints.items():
            method = ep.get("method", "GET")
            desc = ep.get("description", "")
            allowed_params = ep.get("allowed_params", {})
            path_params = ep.get("path_params", {})

            endpoint_desc = f"- [{method}] {self.base_url}{path} : {desc}"
            if path_params:
                params_str = ", ".join(f"{k} ({v.get('type')})" for k, v in path_params.items())
                endpoint_desc += f" (Path params: {params_str})"
            if allowed_params:
                qp_list = []
                for qk, qv in allowed_params.items():
                    enum_vals = f", choices: {qv['enum']}" if "enum" in qv else ""
                    qp_list.append(f"{qk} ({qv.get('type')}{enum_vals})")
                endpoint_desc += f" [Query params: {', '.join(qp_list)}]"

            prompt_parts.append(endpoint_desc)

        prompt_parts.extend([
            "",
            "### CRITICAL RULES:",
            "1. Output ONLY a valid JSON object. No explanation, no markdown ticks, no preamble.",
            f"2. The 'url' MUST be an absolute URL starting with '{self.base_url}'.",
            "3. If query parameters like 'limit' or 'sort' are requested, place them in the 'params' dictionary.",
            "4. For specific categories, the valid categories are: 'electronics', 'jewelery', \"men's clothing\", \"women's clothing\".",
            "5. If no query parameters are needed, provide an empty dictionary: 'params': {}.",
            "6. Always use 'method': 'GET'.",
            "",
            "### FEW-SHOT EXAMPLES:"
        ])

        for eg in self.few_shot_examples:
            q = eg.get("question", "")
            req = json.dumps(eg.get("request", {}), indent=2)
            prompt_parts.append(f"User: {q}\nJSON Output:\n{req}\n")

        return "\n".join(prompt_parts)


# ==============================================================================
# 2. Ollama LLM Client
# ==============================================================================
def call_ollama(
    prompt: str,
    system_prompt: str,
    endpoint: str = OLLAMA_ENDPOINT,
    model: str = OLLAMA_MODEL,
    timeout: int = 45
) -> Dict[str, Any]:
    """
    Sends the user prompt to Ollama with strict JSON formatting mode enabled.
    Returns the parsed JSON request dictionary.
    """
    payload = {
        "model": model,
        "prompt": f"User Request: {prompt}\nJSON Output:",
        "system": system_prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.0,
            "top_p": 0.9
        }
    }

    try:
        resp = requests.post(endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            f"Could not connect to Ollama at {endpoint}. Ensure Ollama is running (`ollama serve`)."
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(f"Ollama request timed out after {timeout} seconds.")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Ollama request error: {e}")

    result_json = resp.json()
    raw_response = result_json.get("response", "").strip()

    if not raw_response:
        raise ValueError("Ollama returned an empty response.")

    return _parse_json_resilient(raw_response)


def _parse_json_resilient(raw_text: str) -> Dict[str, Any]:
    """Attempts direct JSON parse with fallback to regex extraction."""
    # Attempt 1: Direct parse
    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # Attempt 2: Extract JSON from markdown fences or bracket boundaries
    match = re.search(r"\{[\s\S]*\}", raw_text)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to extract valid JSON from LLM response:\n{raw_text}")


# ==============================================================================
# 3. Request Dispatcher
# ==============================================================================
def execute_api_request(
    request_spec: Dict[str, Any],
    base_url: str,
    timeout: int = REQUEST_TIMEOUT_SECONDS
) -> Tuple[int, Any, float]:
    """
    Validates and executes the HTTP request specified by the LLM.
    Returns (status_code, response_data, duration_seconds).
    """
    url = request_spec.get("url", "").strip()
    method = request_spec.get("method", "GET").upper()
    params = request_spec.get("params", {})

    if not url:
        raise ValueError("Request specification missing 'url'.")

    # If the model produced a relative path, resolve it with base_url
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"{base_url}/{url.lstrip('/')}"

    start_time = time.time()
    headers = {"User-Agent": "Text2API-Client/1.0", "Accept": "application/json"}

    try:
        response = requests.request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            timeout=timeout
        )
        duration = time.time() - start_time
    except requests.exceptions.Timeout:
        raise TimeoutError(f"API request to {url} timed out after {timeout} seconds.")
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"Failed to connect to target API: {url}")
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"HTTP request error: {e}")

    try:
        data = response.json()
    except ValueError:
        data = response.text

    return response.status_code, data, duration


# ==============================================================================
# 4. Dynamic Response Flattener & Terminal Table Formatter
# ==============================================================================
def flatten_item(item: Dict[str, Any], max_str_len: int = 45) -> Dict[str, Any]:
    """
    Flattens nested dictionaries and structures into clean, tabular-friendly key-value pairs.
    Handles ratings, addresses, cart items, user names, and long text truncation.
    """
    flat: Dict[str, Any] = {}

    for k, v in item.items():
        # Omit image URLs, MongoDB version fields, and sensitive fields
        if k in ["image", "__v", "password"]:
            continue

        # Flatten nested rating (e.g. {"rate": 3.9, "count": 120})
        if k == "rating" and isinstance(v, dict):
            flat["rating"] = f"{v.get('rate', 0)}/5 ({v.get('count', 0)})"
            continue

        # Flatten name (e.g. {"firstname": "john", "lastname": "doe"})
        if k == "name" and isinstance(v, dict):
            flat["name"] = f"{v.get('firstname', '')} {v.get('lastname', '')}".strip()
            continue

        # Flatten address (e.g. {"city": "...", "street": "..."})
        if k == "address" and isinstance(v, dict):
            city = v.get("city", "")
            street = v.get("street", "")
            flat["city"] = f"{street}, {city}".strip(", ")
            continue

        # Flatten cart products (e.g. [{"productId": 1, "quantity": 4}])
        if k == "products" and isinstance(v, list):
            items_summary = [f"P#{p.get('productId')} (x{p.get('quantity')})" for p in v if isinstance(p, dict)]
            flat["items"] = ", ".join(items_summary)
            continue

        # Format date strings
        if k == "date" and isinstance(v, str) and "T" in v:
            flat["date"] = v.split("T")[0]
            continue

        # Truncate overly long descriptions
        if isinstance(v, str):
            clean_str = " ".join(v.split())
            if len(clean_str) > max_str_len:
                flat[k] = clean_str[: max_str_len - 3] + "..."
            else:
                flat[k] = clean_str
        elif isinstance(v, (int, float, bool)):
            flat[k] = v
        elif v is None:
            flat[k] = ""
        else:
            flat[k] = str(v)

    return flat


def render_ascii_table(headers: List[str], rows: List[List[str]]) -> str:
    """Builds a clean, self-contained ASCII grid table with proper column alignment."""
    if not headers:
        return "(empty table)"

    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            if idx < len(col_widths):
                col_widths[idx] = max(col_widths[idx], len(str(val)))

    # Format helpers
    sep = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    header_sep = "+" + "+".join("=" * (w + 2) for w in col_widths) + "+"

    lines = [sep]
    header_row = "| " + " | ".join(f"{h:<{col_widths[i]}}" for i, h in enumerate(headers)) + " |"
    lines.append(header_row)
    lines.append(header_sep)

    for row in rows:
        row_str = "| " + " | ".join(
            f"{str(row[i]) if i < len(row) else '':<{col_widths[i]}}" for i in range(len(col_widths))
        ) + " |"
        lines.append(row_str)

    lines.append(sep)
    return "\n".join(lines)


def format_response_as_table(data: Any) -> str:
    """
    Inspects response data and renders it as an aligned terminal table:
    - List of dictionaries: Multi-column grid.
    - Single dictionary: Two-column key/value table.
    - List of primitives: Single-column enumerated list.
    """
    if data is None:
        return f"{COLOR_DIM}(Empty response){COLOR_RESET}"

    # Case 1: List of Dictionaries (e.g. /products, /carts, /users)
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        flattened_rows = [flatten_item(d) for d in data]
        # Collect all unique headers preserving sensible priority
        priority_keys = ["id", "title", "price", "category", "rating", "items", "userId", "date", "name", "email", "city", "username"]
        all_keys = set().union(*(d.keys() for d in flattened_rows))
        ordered_headers = [k for k in priority_keys if k in all_keys] + [k for k in all_keys if k not in priority_keys]

        rows = [[str(d.get(h, "")) for h in ordered_headers] for d in flattened_rows]

        if HAS_TABULATE:
            return tabulate(rows, headers=ordered_headers, tablefmt="grid")
        return render_ascii_table(ordered_headers, rows)

    # Case 2: Single Dictionary (e.g. /products/1, /users/2)
    if isinstance(data, dict):
        flat = flatten_item(data, max_str_len=80)
        headers = ["Field", "Value"]
        rows = [[k, str(v)] for k, v in flat.items()]

        if HAS_TABULATE:
            return tabulate(rows, headers=headers, tablefmt="grid")
        return render_ascii_table(headers, rows)

    # Case 3: List of Primitives (e.g. /products/categories)
    if isinstance(data, list) and len(data) > 0:
        headers = ["#", "Category / Item"]
        rows = [[str(i + 1), str(item)] for i, item in enumerate(data)]

        if HAS_TABULATE:
            return tabulate(rows, headers=headers, tablefmt="grid")
        return render_ascii_table(headers, rows)

    # Case 4: Empty list
    if isinstance(data, list) and len(data) == 0:
        return f"{COLOR_YELLOW}[!] Query returned 0 records.{COLOR_RESET}"

    # Fallback: pretty JSON
    return json.dumps(data, indent=2)


# ==============================================================================
# 5. Interactive REPL Terminal Application
# ==============================================================================
def print_banner(base_url: str, model: str, endpoints_count: int):
    """Prints a styled startup banner."""
    print(f"{COLOR_CYAN}{COLOR_BOLD}")
    print("+" + "=" * 72 + "+")
    print("|" + "TEXT-TO-API TERMINAL ADAPTER".center(72) + "|")
    print("|" + "Natural Language to REST API via Local llama3.1".center(72) + "|")
    print("+" + "=" * 72 + "+")
    print(f"{COLOR_RESET}", end="")
    print(f" • Target API    : {COLOR_GREEN}{base_url}{COLOR_RESET}")
    print(f" • LLM Engine    : {COLOR_MAGENTA}{model}{COLOR_RESET} via Ollama ({OLLAMA_ENDPOINT})")
    print(f" • Endpoints     : {COLOR_YELLOW}{endpoints_count} routes loaded{COLOR_RESET}")
    print(f" • Type {COLOR_BOLD}'help'{COLOR_RESET} for sample queries, {COLOR_BOLD}'endpoints'{COLOR_RESET} to view routes, {COLOR_BOLD}'exit'{COLOR_RESET} to quit.")
    print("-" * 74)


def print_help(examples: List[Dict[str, Any]]):
    """Prints help instructions and few-shot query ideas."""
    print(f"\n{COLOR_BOLD}COMMANDS:{COLOR_RESET}")
    print("  exit / quit : Terminate the REPL session")
    print("  endpoints   : Display available API routes and filters")
    print("  help        : Show this help guide")
    print("  clear       : Clear the console screen\n")
    print(f"{COLOR_BOLD}EXAMPLE NATURAL LANGUAGE QUERIES:{COLOR_RESET}")
    for eg in examples:
        print(f"  • {COLOR_CYAN}\"{eg.get('question')}\"{COLOR_RESET}")
    print()


def print_endpoints(endpoints: Dict[str, Any], base_url: str):
    """Prints all registered endpoints and allowed parameters."""
    print(f"\n{COLOR_BOLD}AVAILABLE REST ENDPOINTS:{COLOR_RESET}")
    for path, ep in endpoints.items():
        method = ep.get("method", "GET")
        desc = ep.get("description", "")
        allowed = ep.get("allowed_params", {})
        print(f"  {COLOR_GREEN}{method:<4}{COLOR_RESET} {base_url}{path}")
        print(f"       {COLOR_DIM}{desc}{COLOR_RESET}")
        if allowed:
            print(f"       {COLOR_YELLOW}Query Params: {', '.join(allowed.keys())}{COLOR_RESET}")
    print()


def run_repl():
    """Runs the continuous interactive REPL loop."""
    # Step 1: Load Semantic Layer
    try:
        semantic = SemanticLayer(SEMANTIC_LAYER_PATH)
    except Exception as e:
        print(f"{COLOR_RED}[FATAL ERROR] Failed to load semantic layer: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    print_banner(semantic.base_url, OLLAMA_MODEL, len(semantic.endpoints))

    while True:
        try:
            print(f"{COLOR_BOLD}{COLOR_CYAN}Text2API >>> {COLOR_RESET}", end="", flush=True)
            user_input = input().strip()

            if not user_input:
                continue

            # Command Handling
            cmd = user_input.lower()
            if cmd in ["exit", "quit", "q"]:
                print(f"{COLOR_GREEN}Exiting Text-to-API. Goodbye!{COLOR_RESET}")
                break
            elif cmd == "help":
                print_help(semantic.few_shot_examples)
                continue
            elif cmd == "endpoints":
                print_endpoints(semantic.endpoints, semantic.base_url)
                continue
            elif cmd == "clear":
                os.system("cls" if os.name == "nt" else "clear")
                continue

            # Step 2: Ollama LLM Inference
            print(f"{COLOR_DIM}Translating query with {OLLAMA_MODEL}...{COLOR_RESET}", flush=True)
            t_llm_start = time.time()
            try:
                request_spec = call_ollama(
                    prompt=user_input,
                    system_prompt=semantic.system_prompt,
                    endpoint=OLLAMA_ENDPOINT,
                    model=OLLAMA_MODEL
                )
                t_llm_elapsed = time.time() - t_llm_start
            except Exception as e:
                print(f"{COLOR_RED}[LLM Error] {e}{COLOR_RESET}\n")
                continue

            # Step 3: Display Generated HTTP Request
            method = request_spec.get("method", "GET").upper()
            url = request_spec.get("url", "")
            params = request_spec.get("params", {})

            print(f"{COLOR_YELLOW}{COLOR_BOLD}[HTTP Request]{COLOR_RESET} {COLOR_GREEN}{method} {url}{COLOR_RESET}")
            if params:
                print(f"  {COLOR_DIM}Params: {json.dumps(params)}{COLOR_RESET}")
            print(f"  {COLOR_DIM}(LLM took {t_llm_elapsed:.2f}s){COLOR_RESET}")

            # Step 4: Execute API Call
            print(f"{COLOR_DIM}Executing request...{COLOR_RESET}", flush=True)
            try:
                status_code, data, t_req_elapsed = execute_api_request(
                    request_spec=request_spec,
                    base_url=semantic.base_url,
                    timeout=REQUEST_TIMEOUT_SECONDS
                )
            except Exception as e:
                print(f"{COLOR_RED}[API Request Failed] {e}{COLOR_RESET}\n")
                continue

            # Step 5: Format and Display Results
            status_color = COLOR_GREEN if 200 <= status_code < 300 else COLOR_RED
            print(f"Status: {status_color}{status_code}{COLOR_RESET} | Time: {t_req_elapsed:.2f}s")

            table_output = format_response_as_table(data)
            print()
            print(table_output)
            print("-" * 74)

        except (KeyboardInterrupt, EOFError):
            print(f"\n{COLOR_GREEN}Session cancelled. Exiting Text-to-API.{COLOR_RESET}")
            break
        except Exception as e:
            print(f"\n{COLOR_RED}[Unexpected Error] {e}{COLOR_RESET}\n")


if __name__ == "__main__":
    run_repl()

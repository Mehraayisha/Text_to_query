"""
OpenAPI & Swagger to Unified Semantic Layer Converter.
Programmatically converts OpenAPI 3.0/3.1 or Swagger 2.0 JSON specifications
(from a local file path or remote URL) into the Unified Semantic Layer HTTP schema
for the Text-to-API adapter.
"""

import os
import sys
import json
import re
import argparse
from typing import Dict, Any, List, Optional, Tuple
from urllib.parse import urlparse
import requests

# Ensure stdout handles UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class OpenAPIConverter:
    """
    Parses OpenAPI 3.0/3.1 and Swagger 2.0 specifications and converts them
    into the standardized Unified Semantic Layer HTTP JSON format.
    """

    def __init__(self, source: str, output_path: Optional[str] = None):
        self.source = source.strip()
        self.output_path = output_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "unified_semantic_layer_http.json"
        )
        self.raw_spec: Dict[str, Any] = {}
        self.is_openapi3 = False
        self.is_swagger2 = False

    def load_spec(self) -> Dict[str, Any]:
        """Loads specification from a remote HTTP(S) URL or local file path."""
        parsed = urlparse(self.source)
        if parsed.scheme in ["http", "https"]:
            print(f"[*] Fetching specification from URL: {self.source} ...")
            try:
                resp = requests.get(
                    self.source,
                    headers={"Accept": "application/json, application/yaml, text/plain"},
                    timeout=20
                )
                resp.raise_for_status()
                self.raw_spec = resp.json()
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Failed to fetch specification from URL '{self.source}': {e}")
            except ValueError:
                raise ValueError(f"Content from URL '{self.source}' is not valid JSON.")
        else:
            local_path = os.path.abspath(self.source)
            if not os.path.exists(local_path):
                raise FileNotFoundError(f"Local specification file not found: {local_path}")
            print(f"[*] Reading specification from local file: {local_path} ...")
            with open(local_path, "r", encoding="utf-8") as f:
                try:
                    self.raw_spec = json.load(f)
                except json.JSONDecodeError as e:
                    raise ValueError(f"File '{local_path}' is not valid JSON: {e}")

        # Detect version
        if "openapi" in self.raw_spec:
            self.is_openapi3 = True
            version = self.raw_spec.get("openapi", "3.x")
            print(f"[+] Detected OpenAPI Specification version: {version}")
        elif "swagger" in self.raw_spec:
            self.is_swagger2 = True
            version = self.raw_spec.get("swagger", "2.0")
            print(f"[+] Detected Swagger Specification version: {version}")
        else:
            raise ValueError(
                "Unrecognized specification format. Must contain top-level 'openapi' or 'swagger' key."
            )

        return self.raw_spec

    def extract_base_url(self) -> str:
        """
        Extracts base_url from servers (OpenAPI 3) or host/schemes/basePath (Swagger 2.0).
        """
        if self.is_openapi3:
            servers = self.raw_spec.get("servers", [])
            if servers and isinstance(servers, list):
                first_server = servers[0]
                url = first_server.get("url", "").strip()

                # Handle variable substitutions in server URL, e.g. {server}:{port}/v1
                variables = first_server.get("variables", {})
                for var_name, var_info in variables.items():
                    default_val = var_info.get("default", "")
                    url = url.replace(f"{{{var_name}}}", str(default_val))

                # Handle relative server URL (e.g. "/api/v1") when source is a full URL
                if url.startswith("/") and urlparse(self.source).scheme in ["http", "https"]:
                    parsed_source = urlparse(self.source)
                    url = f"{parsed_source.scheme}://{parsed_source.netloc}{url}"

                if url:
                    return url.rstrip("/")

        elif self.is_swagger2:
            schemes = self.raw_spec.get("schemes", ["https"])
            scheme = schemes[0] if schemes else "https"
            host = self.raw_spec.get("host", "").strip()
            base_path = self.raw_spec.get("basePath", "").strip()

            if host:
                if base_path and not base_path.startswith("/"):
                    base_path = f"/{base_path}"
                return f"{scheme}://{host}{base_path}".rstrip("/")

        # Fallback if no server information provided
        parsed_source = urlparse(self.source)
        if parsed_source.scheme in ["http", "https"] and parsed_source.netloc:
            return f"{parsed_source.scheme}://{parsed_source.netloc}".rstrip("/")

        return "https://api.example.com"

    def _resolve_param_ref(self, ref_str: str) -> Dict[str, Any]:
        """Resolves internal $ref references for parameters."""
        if not ref_str or not ref_str.startswith("#/"):
            return {}
        parts = ref_str.lstrip("#/").split("/")
        curr = self.raw_spec
        for part in parts:
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            else:
                return {}
        return curr if isinstance(curr, dict) else {}

    def _extract_param_type_and_enum(self, param: Dict[str, Any]) -> Tuple[str, Optional[List[Any]]]:
        """Extracts native data type and enum values across OpenAPI 3 and Swagger 2."""
        schema = param.get("schema", {})
        param_type = "string"
        enum_vals = None

        if self.is_openapi3:
            if isinstance(schema, dict):
                param_type = schema.get("type", "string")
                enum_vals = schema.get("enum")
            else:
                param_type = param.get("type", "string")
                enum_vals = param.get("enum")
        else:  # Swagger 2.0
            param_type = param.get("type", "string")
            enum_vals = param.get("enum")

        return param_type, enum_vals

    def extract_endpoints(self) -> Dict[str, Any]:
        """
        Iterates over the paths dictionary, extracting endpoints, HTTP methods,
        descriptions, path variables, and allowed query parameters.
        """
        paths = self.raw_spec.get("paths", {})
        extracted: Dict[str, Any] = {}

        for path_str, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue

            # Shared path-level parameters
            path_level_params = path_item.get("parameters", [])

            for method_key, operation in path_item.items():
                method = method_key.upper()
                # Focus on standard REST methods
                if method not in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    continue
                if not isinstance(operation, dict):
                    continue

                description = (
                    operation.get("summary")
                    or operation.get("description")
                    or f"Endpoint {method} {path_str}"
                ).strip()
                # Sanitize newlines in description
                description = " ".join(description.split())

                path_params: Dict[str, Any] = {}
                allowed_params: Dict[str, Any] = {}

                # Combine path-level and operation-level parameters
                raw_params = list(path_level_params) + list(operation.get("parameters", []))

                for param in raw_params:
                    # Resolve $ref if present
                    if "$ref" in param:
                        param = self._resolve_param_ref(param["$ref"])
                    if not isinstance(param, dict):
                        continue

                    p_name = param.get("name")
                    p_in = param.get("in", "")
                    p_desc = param.get("description", "").strip()
                    p_type, p_enum = self._extract_param_type_and_enum(param)

                    if not p_name:
                        continue

                    param_obj: Dict[str, Any] = {
                        "type": p_type,
                        "description": p_desc or f"Parameter '{p_name}' ({p_type})"
                    }
                    if p_enum:
                        param_obj["enum"] = p_enum

                    if p_in == "path":
                        path_params[p_name] = param_obj
                    elif p_in == "query":
                        allowed_params[p_name] = param_obj

                # Create structured endpoint definition
                endpoint_def = {
                    "path": path_str,
                    "method": method,
                    "description": description,
                    "path_params": path_params,
                    "allowed_params": allowed_params
                }

                # Construct key in endpoints map:
                # Use clean path if GET (or single method), else disambiguate if multiple methods share same path
                endpoint_key = path_str if method == "GET" or path_str not in extracted else f"{path_str} [{method}]"
                extracted[endpoint_key] = endpoint_def

        return extracted

    def extract_entities(self) -> Dict[str, Any]:
        """
        Extracts entities and attributes from components.schemas (OpenAPI 3)
        or definitions (Swagger 2.0).
        """
        schemas: Dict[str, Any] = {}
        if self.is_openapi3:
            schemas = self.raw_spec.get("components", {}).get("schemas", {})
        elif self.is_swagger2:
            schemas = self.raw_spec.get("definitions", {})

        entities: Dict[str, Any] = {}

        type_mapping = {
            "integer": "NUMBER",
            "number": "NUMBER",
            "string": "STRING",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT"
        }

        for schema_name, schema_def in schemas.items():
            if not isinstance(schema_def, dict):
                continue

            properties = schema_def.get("properties", {})
            required_fields = schema_def.get("required", [])
            attributes: List[Dict[str, Any]] = []
            primary_keys: List[str] = []

            for prop_name, prop_def in properties.items():
                if not isinstance(prop_def, dict):
                    continue

                native_type = prop_def.get("type", "string")
                generic_type = type_mapping.get(native_type, "STRING")
                desc = prop_def.get("description", f"Attribute '{prop_name}'")

                is_pk = prop_name.lower() in ["id", f"{schema_name.lower()}_id", f"{schema_name.lower()}id"]
                if is_pk and not primary_keys:
                    primary_keys.append(prop_name)

                attributes.append({
                    "name": prop_name,
                    "data_type": native_type,
                    "generic_type": generic_type,
                    "is_primary_key": is_pk,
                    "is_foreign_key": False,
                    "description": desc
                })

            if not primary_keys and "id" in properties:
                primary_keys = ["id"]

            entity_desc = schema_def.get("description", f"Entity {schema_name}")
            entities[schema_name] = {
                "name": schema_name,
                "entity_type": "dataset",
                "description": " ".join(entity_desc.split()),
                "attributes": attributes,
                "primary_keys": primary_keys
            }

        return entities

    def generate_few_shots(self, endpoints: Dict[str, Any], base_url: str) -> List[Dict[str, Any]]:
        """
        Automatically generates 2-3 template few-shot examples based on extracted GET endpoints.
        """
        few_shots: List[Dict[str, Any]] = []
        get_endpoints = [ep for ep in endpoints.values() if ep.get("method") == "GET"]

        if not get_endpoints:
            return [
                {
                    "question": "Fetch all items (template example)",
                    "request": {
                        "method": "GET",
                        "url": f"{base_url}/items",
                        "params": {}
                    }
                }
            ]

        # Scenario 1: Collection endpoint without path parameters (e.g. /products, /users)
        collection_candidates = [
            ep for ep in get_endpoints if not ep.get("path_params")
        ]
        if collection_candidates:
            # Prefer candidate with limit or sort query parameter if available
            cand = next(
                (ep for ep in collection_candidates if "limit" in ep.get("allowed_params", {})),
                collection_candidates[0]
            )
            resource_name = cand["path"].strip("/").split("/")[-1] or "items"
            has_limit = "limit" in cand.get("allowed_params", {})

            params = {"limit": 5} if has_limit else {}
            limit_text = " (limit to 5)" if has_limit else ""
            few_shots.append({
                "question": f"Get all {resource_name}{limit_text}",
                "request": {
                    "method": "GET",
                    "url": f"{base_url}{cand['path']}",
                    "params": params
                }
            })

        # Scenario 2: Item by ID / Path Parameter endpoint (e.g. /products/{id}, /users/{id})
        detail_candidates = [
            ep for ep in get_endpoints if ep.get("path_params")
        ]
        if detail_candidates:
            cand = detail_candidates[0]
            path_template = cand["path"]
            resolved_path = path_template

            sample_vals = {"id": "1", "userId": "1", "username": "admin", "category": "electronics"}
            for p_name in cand.get("path_params", {}).keys():
                val = sample_vals.get(p_name, "1")
                resolved_path = resolved_path.replace(f"{{{p_name}}}", val)

            resource_name = path_template.strip("/").split("/")[0] or "item"
            few_shots.append({
                "question": f"Show details for {resource_name} with ID 1",
                "request": {
                    "method": "GET",
                    "url": f"{base_url}{resolved_path}",
                    "params": {}
                }
            })

        # Scenario 3: Filtered or Sub-resource endpoint (e.g. /category/{category} or filtered by query)
        filtered_candidates = [
            ep for ep in get_endpoints
            if ep not in [collection_candidates[0] if collection_candidates else None,
                          detail_candidates[0] if detail_candidates else None]
        ]
        if filtered_candidates:
            cand = filtered_candidates[0]
            path_template = cand["path"]
            resolved_path = path_template

            for p_name in cand.get("path_params", {}).keys():
                resolved_path = resolved_path.replace(f"{{{p_name}}}", "1")

            params = {}
            if cand.get("allowed_params"):
                first_param = list(cand["allowed_params"].keys())[0]
                params[first_param] = "sample_value"

            path_segment = cand["path"].strip("/").replace("/", " ")
            few_shots.append({
                "question": f"Fetch {path_segment}",
                "request": {
                    "method": "GET",
                    "url": f"{base_url}{resolved_path}",
                    "params": params
                }
            })

        # Fallback if less than 2 generated
        if len(few_shots) < 2 and get_endpoints:
            ep = get_endpoints[-1]
            few_shots.append({
                "question": f"Query {ep['path']}",
                "request": {
                    "method": "GET",
                    "url": f"{base_url}{ep['path']}",
                    "params": {}
                }
            })

        return few_shots[:3]

    def convert(self) -> Dict[str, Any]:
        """Performs full conversion pipeline and saves output file."""
        self.load_spec()

        info = self.raw_spec.get("info", {})
        title = info.get("title", "REST API Service")
        api_id = re.sub(r"[^a-zA-Z0-9_]+", "_", title.lower()).strip("_") or "api_service"

        base_url = self.extract_base_url()
        endpoints = self.extract_endpoints()
        entities = self.extract_entities()
        few_shots = self.generate_few_shots(endpoints, base_url)

        semantic_layer_output = {
            "database_id": api_id,
            "database_name": f"{title} (REST API)",
            "database_type": "api",
            "dialect": "http_rest",
            "base_url": base_url,
            "endpoints": endpoints,
            "entities": entities,
            "relationships": [],
            "few_shot_examples": few_shots
        }

        # Write output file
        os.makedirs(os.path.dirname(os.path.abspath(self.output_path)), exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(semantic_layer_output, f, indent=2, ensure_ascii=False)

        print("-" * 65)
        print("[+] SUCCESS: Converted OpenAPI/Swagger to Semantic Layer!")
        print(f" • API Title          : {title}")
        print(f" • Base URL           : {base_url}")
        print(f" • Endpoints Extracted: {len(endpoints)}")
        print(f" • Entities Extracted : {len(entities)}")
        print(f" • Few-Shots Generated: {len(few_shots)}")
        print(f" • Saved Output File  : {self.output_path}")
        print("-" * 65)

        return semantic_layer_output


# ==============================================================================
# CLI Entry Point
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Convert OpenAPI 3.0 / Swagger 2.0 specifications into Unified Semantic Layer HTTP JSON."
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="Local file path or remote HTTP(S) URL to OpenAPI/Swagger JSON specification."
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Target output file path (default: api_adapter/unified_semantic_layer_http.json)."
    )

    args = parser.parse_args()
    source = args.source

    if not source:
        print("=" * 65)
        print("  OPENAPI / SWAGGER TO UNIFIED SEMANTIC LAYER CONVERTER")
        print("=" * 65)
        print("Please enter a local file path or remote URL to your Swagger/OpenAPI JSON.")
        print("Example: https://petstore.swagger.io/v2/swagger.json")
        try:
            source = input("\nEnter Specification Path or URL: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)

    if not source:
        print("[!] Error: No specification source provided.")
        parser.print_help()
        sys.exit(1)

    try:
        converter = OpenAPIConverter(source, args.output)
        converter.convert()
    except Exception as e:
        print(f"\n[!] Conversion Failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

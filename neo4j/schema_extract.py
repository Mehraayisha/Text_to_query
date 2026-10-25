import json
import os
import sys

# Ensure site-packages neo4j driver is imported cleanly if present
GraphDatabase = None
try:
    import importlib.machinery, importlib.util
    cur_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(cur_dir)
    search_paths = [p for p in sys.path if os.path.abspath(p) not in (cur_dir, parent_dir, "")]
    spec = importlib.machinery.PathFinder.find_spec('neo4j', search_paths)
    if spec:
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        GraphDatabase = getattr(mod, "GraphDatabase", None)
except Exception:
    GraphDatabase = None


def extract_neo4j_schema(uri, user, password, database="neo4j"):
    """
    Extracts schema metadata for all node labels, properties, and relationships from Neo4j.
    """
    if GraphDatabase is None:
        raise ImportError("The 'neo4j' Python driver package is not installed. Please install it via 'pip install neo4j'.")

    # Initialize the Neo4j driver
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    schema_metadata = {
        "nodes": {},
        "relationships": {}
    }
    
    with driver.session(database=database) as session:
        # 1. Fetch all Node Labels (including those with no properties)
        try:
            labels_result = session.run("CALL db.labels() YIELD label RETURN label")
            for record in labels_result:
                label = record.get("label")
                if label:
                    schema_metadata["nodes"][label] = {"properties": []}
        except Exception as e:
            print(f"Warning: Could not fetch all labels via db.labels(): {e}")
            
        # 2. Fetch Node Properties and their Types
        try:
            node_props_query = """
                CALL db.schema.nodeTypeProperties() 
                YIELD nodeLabels, propertyName, propertyTypes 
                RETURN nodeLabels, propertyName, propertyTypes
            """
            node_results = session.run(node_props_query)
            for record in node_results:
                labels = record.get("nodeLabels")
                prop_name = record.get("propertyName")
                prop_types = record.get("propertyTypes")
                
                if not labels:
                    continue
                    
                for label in labels:
                    if label not in schema_metadata["nodes"]:
                        schema_metadata["nodes"][label] = {"properties": []}
                    
                    if prop_name:
                        # Avoid duplicates
                        existing_props = [p["property_name"] for p in schema_metadata["nodes"][label]["properties"]]
                        if prop_name not in existing_props:
                            schema_metadata["nodes"][label]["properties"].append({
                                "property_name": prop_name,
                                "data_type": prop_types[0] if prop_types else "Unknown"
                            })
        except Exception as e:
            print(f"Warning: Could not fetch node properties: {e}")

        # 3. Fetch all Relationship Types
        try:
            rels_result = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
            for record in rels_result:
                rel_type = record.get("relationshipType")
                if rel_type:
                    schema_metadata["relationships"][rel_type] = {
                        "properties": [],
                        "connections": []
                    }
        except Exception as e:
            print(f"Warning: Could not fetch all relationship types via db.relationshipTypes(): {e}")

        # 4. Fetch Relationship Properties and their Types
        try:
            rel_props_query = """
                CALL db.schema.relTypeProperties() 
                YIELD relType, propertyName, propertyTypes 
                RETURN relType, propertyName, propertyTypes
            """
            rel_results = session.run(rel_props_query)
            for record in rel_results:
                rel_types = record.get("relType")
                prop_name = record.get("propertyName")
                prop_types = record.get("propertyTypes")
                
                if not rel_types:
                    continue
                    
                if isinstance(rel_types, str):
                    rel_types = [rel_types]
                    
                for raw_rel in rel_types:
                    # Clean relType (e.g. :`ORDERS` -> ORDERS)
                    rel_type = str(raw_rel).replace(":", "").replace("`", "").strip()
                    if not rel_type:
                        continue

                    if rel_type not in schema_metadata["relationships"]:
                        schema_metadata["relationships"][rel_type] = {
                            "properties": [],
                            "connections": []
                        }
                    
                    if prop_name:
                        existing_props = [p["property_name"] for p in schema_metadata["relationships"][rel_type]["properties"]]
                        if prop_name not in existing_props:
                            schema_metadata["relationships"][rel_type]["properties"].append({
                                "property_name": prop_name,
                                "data_type": prop_types[0] if prop_types else "Unknown"
                            })
        except Exception as e:
            print(f"Warning: Could not fetch relationship properties: {e}")
        
        # 5. Fetch Graph Topology (Connections between nodes)
        try:
            topology_query = """
                MATCH (n)-[r]->(m)
                WITH labels(n) AS source_labels, type(r) AS rel_type, labels(m) AS target_labels
                UNWIND source_labels AS source
                UNWIND target_labels AS target
                RETURN DISTINCT source, rel_type, target
            """
            topology_results = session.run(topology_query)
            for record in topology_results:
                source = record.get("source")
                rel_type = record.get("rel_type")
                target = record.get("target")
                
                if rel_type and source and target:
                    if rel_type not in schema_metadata["relationships"]:
                        schema_metadata["relationships"][rel_type] = {
                            "properties": [],
                            "connections": []
                        }
                    
                    # Avoid duplicate connections
                    connection_exists = any(
                        c["source"] == source and c["target"] == target
                        for c in schema_metadata["relationships"][rel_type]["connections"]
                    )
                    if not connection_exists:
                        schema_metadata["relationships"][rel_type]["connections"].append({
                            "source": source,
                            "target": target
                        })
        except Exception as e:
            print(f"Warning: Could not fetch graph topology: {e}")
            
    driver.close()
    return schema_metadata


if __name__ == "__main__":
    NEO4J_URI = "neo4j+s://demo.neo4jlabs.com"
    NEO4J_USER = "northwind"
    NEO4J_PASSWORD = "northwind"
    NEO4J_DB = "northwind"
    
    output_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), "semantic_layer_neo4j_northwind.json")
    
    print(f"Extracting schema from public Neo4j dataset at {NEO4J_URI}...")
    try:
        raw_schema = extract_neo4j_schema(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, database=NEO4J_DB)
        with open(output_filename, "w") as f:
            json.dump(raw_schema, f, indent=2)
        print(f"Extraction complete! Saved to {output_filename}")
    except Exception as e:
        print(f"Error during schema extraction: {e}")

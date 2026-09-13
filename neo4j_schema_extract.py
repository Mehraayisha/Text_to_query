import json
from neo4j import GraphDatabase

def extract_neo4j_schema(uri, user, password, database="neo4j"):
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

        # 4. Fetch Relationship Properties and their Types (Fixed field name to 'relType')
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
                    
                for rel_type in rel_types:
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
    # Neo4j public labs demo server configuration (Northwind dataset)
    NEO4J_URI = "neo4j+s://demo.neo4jlabs.com"
    NEO4J_USER = "northwind"
    NEO4J_PASSWORD = "northwind"
    NEO4J_DB = "northwind"
    
    # --- EDIT THIS VARIABLE TO CHANGE YOUR SAVE FILE ---
    OUTPUT_FILENAME = "semantic_layer_neo4j_northwind.json"
    
    print(f"Extracting schema from public Neo4j dataset at {NEO4J_URI}...")
    try:
        raw_schema = extract_neo4j_schema(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, database=NEO4J_DB)
        
        with open(OUTPUT_FILENAME, "w") as f:
            json.dump(raw_schema, f, indent=2)
            
        print(f"Extraction complete! Check {OUTPUT_FILENAME}")
    except Exception as e:
        print(f"Error during schema extraction: {e}")
from google.cloud import bigquery
import json
import os

def extract_bigquery_schema(billing_project_id, target_project_id, dataset_id, key_path):
    """
    Extracts schema metadata for all tables in a BigQuery dataset using INFORMATION_SCHEMA.
    """
    # Resolve key_path if relative
    if not os.path.isabs(key_path) and not os.path.exists(key_path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        local_key = os.path.join(current_dir, os.path.basename(key_path))
        parent_key = os.path.join(os.path.dirname(current_dir), os.path.basename(key_path))
        if os.path.exists(local_key):
            key_path = local_key
        elif os.path.exists(parent_key):
            key_path = parent_key

    # Initialize the client using your billing project ID
    client = bigquery.Client.from_service_account_json(key_path, project=billing_project_id)
    
    # Query the dataset from project context
    query = f"""
        SELECT 
            table_name, 
            column_name, 
            data_type, 
            description
        FROM 
            `{target_project_id}.{dataset_id}.INFORMATION_SCHEMA.COLUMN_FIELD_PATHS`
    """
    
    query_job = client.query(query)
    results = query_job.result()
    
    schema_metadata = {}
    for row in results:
        table = row.table_name
        if table not in schema_metadata:
            schema_metadata[table] = {
                "table_name": table,
                "columns": []
            }
        
        schema_metadata[table]["columns"].append({
            "column_name": row.column_name,
            "data_type": row.data_type,
            "description": row.description or "" 
        })
        
    return schema_metadata

if __name__ == "__main__":
    # Test run standalone
    my_billing_project = "mainpro-507007" 
    public_project = "bigquery-public-data"
    my_dataset = "thelook_ecommerce"
    key_file_path = "jsonkeybq.json" 
    
    print(f"Extracting schema from public dataset: {public_project}.{my_dataset}...")
    raw_schema = extract_bigquery_schema(my_billing_project, public_project, my_dataset, key_file_path)
    
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "semantic_layer_public.json")
    with open(output_file, "w") as f:
        json.dump(raw_schema, f, indent=2)
        
    print(f"Extraction complete! Saved to {output_file}")

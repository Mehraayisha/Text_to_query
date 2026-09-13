from google.cloud import bigquery
import json

def extract_bigquery_schema(billing_project_id, target_project_id, dataset_id, key_path):
    # CRITICAL: Initialize the client using YOUR project ID for running jobs
    client = bigquery.Client.from_service_account_json(key_path, project=billing_project_id)
    
    # Query the public dataset from your own project context
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
    # 1. Your GCP project where your service account has "BigQuery User" permissions
    my_billing_project = "mainpro-507007" 
    
    # 2. Google's public data project and dataset
    public_project = "bigquery-public-data"
    my_dataset = "thelook_ecommerce"
    
    key_file_path = "jsonkeybq.json" 
    
    print(f"Extracting schema from public dataset: {public_project}.{my_dataset}...")
    raw_schema = extract_bigquery_schema(my_billing_project, public_project, my_dataset, key_file_path)
    
    with open("semantic_layer_public.json", "w") as f:
        json.dump(raw_schema, f, indent=2)
        
    print("Extraction complete! Check semantic_layer_public.json")
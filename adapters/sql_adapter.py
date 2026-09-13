"""
BigQuery SQL Database Adapter.
Handles connecting to BigQuery, extracting SQL schema (tables, columns, data types),
and building the Unified Semantic Layer.
"""

import os
from typing import Optional
from .base_adapter import BaseAdapter
from semantic_layer import DatabaseMetadata, normalize_sql_schema
from bq_schema_extract import extract_bigquery_schema

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class BigQuerySQLAdapter(BaseAdapter):
    """SQL Adapter for Google Cloud BigQuery."""

    def __init__(
        self,
        billing_project_id: Optional[str] = None,
        target_project_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        key_path: Optional[str] = None
    ):
        billing_project_id = billing_project_id or os.getenv("BIGQUERY_BILLING_PROJECT", "mainpro-507007")
        target_project_id = target_project_id or os.getenv("BIGQUERY_TARGET_PROJECT", "bigquery-public-data")
        dataset_id = dataset_id or os.getenv("BIGQUERY_DATASET", "thelook_ecommerce")
        key_path = key_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "jsonkeybq.json")

        super().__init__(
            database_id=f"bq_{dataset_id}",
            database_name=f"BigQuery ({target_project_id}.{dataset_id})",
            dialect="bigquery"
        )
        self.billing_project_id = billing_project_id
        self.target_project_id = target_project_id
        self.dataset_id = dataset_id
        self.key_path = key_path

    def extract_schema(self) -> DatabaseMetadata:
        """Extracts schema from BigQuery and normalizes into DatabaseMetadata."""
        raw_schema = extract_bigquery_schema(
            self.billing_project_id,
            self.target_project_id,
            self.dataset_id,
            self.key_path
        )
        return normalize_sql_schema(
            raw_schema=raw_schema,
            database_id=self.database_id,
            database_name=self.database_name,
            dialect=self.dialect
        )

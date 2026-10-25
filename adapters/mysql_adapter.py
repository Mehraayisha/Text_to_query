"""MySQL database adapter."""

import os
from typing import Optional

from bigquery.base_adapter import BaseAdapter
from mysql_schema_extract import extract_mysql_schema
from bigquery.models import DatabaseMetadata
from mysql_normalizer import normalize_mysql_schema

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class MySQLAdapter(BaseAdapter):
    """SQL adapter for MySQL."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        host = host or os.getenv("MYSQL_HOST", "localhost")
        port = port or int(os.getenv("MYSQL_PORT", "3306"))
        user = user or os.getenv("MYSQL_USER", "root")
        password = password if password is not None else os.getenv("MYSQL_PASSWORD", "")
        database = database or os.getenv("MYSQL_DATABASE", "")

        if not database:
            raise ValueError("MYSQL_DATABASE must be configured before running the MySQL adapter")

        super().__init__(
            database_id=f"mysql_{database}",
            database_name=f"MySQL ({database})",
            dialect="mysql",
        )
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database

    def extract_schema(self) -> DatabaseMetadata:
        raw_schema = extract_mysql_schema(
            self.host,
            self.port,
            self.user,
            self.password,
            self.database,
        )
        return normalize_mysql_schema(
            raw_schema=raw_schema,
            database_id=self.database_id,
            database_name=self.database_name,
            dialect=self.dialect,
        )

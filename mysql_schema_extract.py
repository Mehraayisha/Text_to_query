"""MySQL schema extraction using INFORMATION_SCHEMA."""

from typing import Any, Dict

import mysql.connector


def extract_mysql_schema(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
) -> Dict[str, Any]:
    """Return tables, columns, primary keys, and foreign keys for a database."""
    connection = mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
    )

    schema_metadata: Dict[str, Any] = {}
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, COLUMN_TYPE,
                   COLUMN_COMMENT, COLUMN_KEY
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME, ORDINAL_POSITION
            """,
            (database,),
        )
        for row in cursor.fetchall():
            table_name = row["TABLE_NAME"]
            schema_metadata.setdefault(
                table_name,
                {"table_name": table_name, "columns": []},
            )
            schema_metadata[table_name]["columns"].append(
                {
                    "column_name": row["COLUMN_NAME"],
                    "data_type": row["COLUMN_TYPE"] or row["DATA_TYPE"],
                    "description": row["COLUMN_COMMENT"] or "",
                    "is_primary_key": row["COLUMN_KEY"] == "PRI",
                    "is_foreign_key": False,
                }
            )

        cursor.execute(
            """
            SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME,
                   REFERENCED_COLUMN_NAME, CONSTRAINT_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = %s
              AND REFERENCED_TABLE_NAME IS NOT NULL
            ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION
            """,
            (database,),
        )
        for row in cursor.fetchall():
            table_name = row["TABLE_NAME"]
            column_name = row["COLUMN_NAME"]
            for column in schema_metadata.get(table_name, {}).get("columns", []):
                if column["column_name"] == column_name:
                    column["is_foreign_key"] = True
                    column["referenced_table"] = row["REFERENCED_TABLE_NAME"]
                    column["referenced_column"] = row["REFERENCED_COLUMN_NAME"]
                    break
    finally:
        connection.close()

    return schema_metadata


if __name__ == "__main__":
    import json
    import os

    result = extract_mysql_schema(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", ""),
    )
    with open("semantic_layer_mysql.json", "w", encoding="utf-8") as output:
        json.dump(result, output, indent=2)
    print("Extraction complete! Check semantic_layer_mysql.json")

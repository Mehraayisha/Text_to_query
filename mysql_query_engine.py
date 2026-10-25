"""Natural-language querying for a MySQL database."""

import json
import re
from typing import Any, Dict, List, Tuple

import mysql.connector

from adapters import MySQLAdapter
from llm_client import LLMClient


def _schema_context(metadata: Any) -> str:
    """Build a compact, explicit schema description for the model."""
    return json.dumps(metadata.to_dict(), indent=2)


def _clean_sql(response: str) -> str:
    sql = response.strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", sql, re.IGNORECASE | re.DOTALL)
    if fenced:
        sql = fenced.group(1).strip()
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise ValueError("The model returned no SQL query")
    return sql


def _validate_read_only_sql(sql: str) -> None:
    """Reject multi-statement and mutating SQL before it reaches MySQL."""
    if ";" in sql:
        raise ValueError("Only one SQL statement is allowed")
    if not re.match(r"^(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed")
    if re.search(
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|CALL|"
        r"LOAD\s+DATA|INTO\s+OUTFILE|INTO\s+DUMPFILE)\b",
        sql,
        re.IGNORECASE,
    ):
        raise ValueError("The generated query contains a forbidden SQL operation")


def generate_sql(client: LLMClient, question: str, schema: str) -> str:
    response = client.chat(
        [
            {
                "role": "system",
                "content": (
                    "You generate safe MySQL read-only queries. Return only one SQL "
                    "SELECT statement, with no markdown or explanation. Use only "
                    "tables and columns in the supplied schema. Never modify data."
                ),
            },
            {
                "role": "user",
                "content": f"Schema:\n{schema}\n\nQuestion:\n{question}",
            },
        ]
    )
    sql = _clean_sql(response)
    _validate_read_only_sql(sql)
    return sql


def execute_query(
    sql: str,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    max_rows: int = 100,
) -> Tuple[List[Dict[str, Any]], bool]:
    try:
        connection = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
        )
    except mysql.connector.Error as exc:
        raise RuntimeError(f"MySQL connection failed: {exc}") from exc
    try:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(sql)
        except mysql.connector.Error as exc:
            raise RuntimeError(f"MySQL query failed: {exc}") from exc
        rows = cursor.fetchmany(max_rows + 1)
        truncated = len(rows) > max_rows
        return rows[:max_rows], truncated
    finally:
        connection.close()


def summarize_results(
    client: LLMClient,
    question: str,
    sql: str,
    rows: List[Dict[str, Any]],
    truncated: bool,
) -> str:
    row_text = json.dumps(rows, default=str, indent=2)
    suffix = " Only the first 100 rows are shown." if truncated else ""
    return client.chat(
        [
            {
                "role": "system",
                "content": (
                    "Answer the user's question using only the SQL result. Be concise "
                    "and mention when no rows were found. Do not invent facts."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question}\nSQL: {sql}\nResults: {row_text}{suffix}"
                ),
            },
        ],
        max_tokens=300,
    )


def answer_question(question: str) -> Tuple[str, str, List[Dict[str, Any]], bool]:
    adapter = MySQLAdapter()
    metadata = adapter.extract_schema()
    if not metadata.entities:
        raise RuntimeError("The configured MySQL database has no tables")

    client = LLMClient()
    sql = generate_sql(client, question, _schema_context(metadata))
    rows, truncated = execute_query(
        sql,
        adapter.host,
        adapter.port,
        adapter.user,
        adapter.password,
        adapter.database,
    )
    answer = summarize_results(client, question, sql, rows, truncated)
    return answer, sql, rows, truncated

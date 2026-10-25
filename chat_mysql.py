"""Interactive natural-language chat over the configured MySQL database."""

from mysql_query_engine import answer_question


if __name__ == "__main__":
    print("Text-to-MySQL chat. Type 'exit' to quit.")
    while True:
        try:
            question = input("\nQuestion: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue

        try:
            answer, sql, rows, truncated = answer_question(question)
            print(f"\nAnswer: {answer}")
            print(f"SQL: {sql}")
            print(f"Rows returned: {len(rows)}{' (limited)' if truncated else ''}")
        except (ValueError, RuntimeError, ConnectionError) as exc:
            print(f"\nError: {exc}")

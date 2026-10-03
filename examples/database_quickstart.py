from __future__ import annotations

import asyncio
import sqlite3

from schemarouter import ExecutionPlan, SchemaRouter, ToolCall


async def main() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        """
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL
        )
        """
    )
    connection.executemany(
        "INSERT INTO employees(id, name, department) VALUES (?, ?, ?)",
        [
            (1, "Alice", "sales"),
            (2, "Bob", "engineering"),
        ],
    )
    connection.commit()

    router = SchemaRouter()
    try:
        keys = router.add_sqlite_database(
            connection,
            database_name="company",
        )
        tool = router.registry.get(keys[0])
        endpoint = tool.endpoint("select")

        plan = ExecutionPlan(
            query="employee directory",
            registry_version=router.registry.version,
            calls=[
                ToolCall(
                    tool=tool.key,
                    endpoint=endpoint.name,
                    arguments={"id": 2, "limit": 10},
                    fields=["id", "name", "department"],
                    schema_fingerprint=endpoint.fingerprint,
                    tool_fingerprint=tool.fingerprint,
                )
            ],
        )
        result = (await router.execute(plan))[0]
        print(result.data)
    finally:
        await router.aclose()
        connection.close()


if __name__ == "__main__":
    asyncio.run(main())

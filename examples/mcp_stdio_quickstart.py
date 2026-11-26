"""Run a real MCP stdio subprocess through SchemaRouter."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from schemarouter import ExecutionPlan, ExecutionPolicy, SchemaRouter, ToolCall


async def main() -> None:
    server = Path(__file__).with_name("mcp_stdio_server.py")
    router = SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True),
    )
    try:
        tool = await router.add_mcp_stdio(
            sys.executable,
            args=[str(server)],
            allowed_commands=[sys.executable],
            provider="schemarouter-gallery",
        )
        endpoint = tool.endpoint("add")
        plan = ExecutionPlan(
            query="add result",
            registry_version=router.registry.version,
            calls=[
                ToolCall(
                    tool=tool.key,
                    endpoint=endpoint.name,
                    arguments={"a": 2, "b": 3},
                    fields=["result"],
                    schema_fingerprint=endpoint.fingerprint,
                    tool_fingerprint=tool.fingerprint,
                )
            ],
        )
        results = await router.execute(plan)
        assert results[0].data == {"result": 5}
        print(results[0].data)
    finally:
        await router.aclose()


if __name__ == "__main__":
    asyncio.run(main())

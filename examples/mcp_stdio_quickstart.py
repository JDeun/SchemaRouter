"""Run a real MCP stdio subprocess through SchemaRouter."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from schemarouter import ExecutionPolicy, PlanRequest, SchemaRouter


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
        results = await router.ainvoke(
            PlanRequest(
                query="add result",
                preferred_tools=[tool.key],
                arguments={"a": 2, "b": 3},
            )
        )
        assert results[0].data == {"result": 5}
        print(results[0].data)
    finally:
        await router.aclose()


if __name__ == "__main__":
    asyncio.run(main())

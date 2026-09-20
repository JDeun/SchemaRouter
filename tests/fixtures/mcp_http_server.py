from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel

mcp = MCPServer("SchemaRouterIntegrationServer")


class AddResult(BaseModel):
    result: int


@mcp.tool()
def add(a: int, b: int) -> AddResult:
    """Add two integers and return a structured result."""
    return AddResult(result=a + b)


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="127.0.0.1",
        port=int(os.environ["SCHEMAROUTER_MCP_TEST_PORT"]),
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )

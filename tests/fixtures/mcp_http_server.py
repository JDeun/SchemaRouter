from __future__ import annotations

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel

mcp = MCPServer("SchemaRouterIntegrationServer")


class AddResult(BaseModel):
    result: int


@mcp.tool()
def add(a: int, b: int) -> AddResult:
    """Add two integers and return a structured result."""
    audit_path = os.environ.get("SCHEMAROUTER_MCP_HTTP_CALL_AUDIT")
    if audit_path:
        with Path(audit_path).open("a", encoding="utf-8") as audit:
            audit.write(f"{a},{b}\n")
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

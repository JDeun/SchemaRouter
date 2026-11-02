from __future__ import annotations

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel

mcp = MCPServer("SchemaRouterStdioServer")


class AddResult(BaseModel):
    result: int


@mcp.tool()
def add(a: int, b: int) -> AddResult:
    """Add two integers."""
    audit_path = os.environ.get("SCHEMAROUTER_MCP_STDIO_CALL_AUDIT")
    if audit_path:
        with Path(audit_path).open("a", encoding="utf-8") as audit:
            audit.write(f"{a},{b}\n")
    return AddResult(result=a + b)


if __name__ == "__main__":
    mcp.run(transport="stdio")

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel

mcp = MCPServer("SchemaRouterStdioServer")


class AddResult(BaseModel):
    result: int


@mcp.tool()
def add(a: int, b: int) -> AddResult:
    """Add two integers."""
    return AddResult(result=a + b)


if __name__ == "__main__":
    mcp.run(transport="stdio")

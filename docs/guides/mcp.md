# MCP

SchemaRouter uses the official MCP Python SDK for Streamable HTTP discovery and execution.

## Install

```bash
pip install -e ".[mcp]"
```

## Import a server

```python
from schemarouter import ExecutionPolicy, SchemaRouter

router = await SchemaRouter.from_url(
    "http://localhost:8000/mcp",
    kind="mcp",
    policy=ExecutionPolicy(
        allow_unclassified_remote=True,
    ),
)
```

Discovery performs protocol negotiation through the SDK, paginates `list_tools()`, and imports each
advertised `inputSchema` and `outputSchema`.

## Execution

The bound invoker calls `call_tool()`. Structured content is preferred because it can be validated
against the advertised output schema before projection.

## Why MCP annotations do not grant permission

Tool annotations arrive from a remote server and are therefore descriptive metadata, not trusted
local authority.

By default, remote MCP operations are treated as unclassified for side effects. Trusted application
code can opt in with:

```python
ExecutionPolicy(allow_unclassified_remote=True)
```

A future local classification layer can make this more granular without trusting the remote server
to classify itself.

## Integration coverage

The repository CI starts a real Streamable HTTP MCP server using the official SDK and verifies:

```text
HTTP server
 -> discovery
 -> input/output schema import
 -> planning
 -> execution policy
 -> call_tool()
 -> structured output validation
```

This is separate from the normal core test matrix so the base package does not depend on MCP.

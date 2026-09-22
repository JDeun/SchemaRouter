# MCP

SchemaRouter uses the official MCP Python SDK for Streamable HTTP discovery and execution.

## Install

For consumers:

```bash
pip install --pre "schemarouter[mcp]"
```

For repository development:

```bash
pip install -e ".[dev,mcp]"
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

Discovery performs protocol negotiation, paginates `list_tools()`, and imports each advertised
`inputSchema` and `outputSchema`.

## Authenticated Streamable HTTP

HTTP authentication is trusted runtime configuration, not a model-selectable parameter.

```python
import os

router = await SchemaRouter.from_url(
    "https://mcp.example.com/mcp",
    kind="mcp",
    trusted_headers={
        "Authorization": f"Bearer {os.environ['MCP_TOKEN']}",
    },
)
```

The same trusted header set is used for discovery and runtime calls, but the header values are not
copied into `ToolSpec`, endpoint metadata, planner state, or model-visible arguments.

MCP protocol headers such as `Mcp-Protocol-Version` cannot be overridden through trusted headers,
and credentials embedded in the URL are rejected.

## Custom OAuth, mTLS, proxies, or gateway transports

For more complex authentication, inject an `MCPClientFactory`:

```python
router = await SchemaRouter.from_url(
    "https://mcp.example.com/mcp",
    kind="mcp",
    mcp_client_factory=my_trusted_factory,
)
```

The factory owns the official SDK client/transport lifecycle. It can configure OAuth, client
credentials, mTLS, proxies, enterprise gateways, or application-specific HTTP clients without
moving secrets into SchemaRouter's planning contract.

This follows the MCP SDK's transport layering: HTTP authentication belongs on the caller-owned HTTP
client passed to the Streamable HTTP transport.

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

For stronger control, combine this with per-call approval:

```python
ExecutionPolicy(
    allow_unclassified_remote=True,
    approval_mode="non_read_only",
)
```

## Integration coverage

Repository CI starts a real Streamable HTTP MCP server using the official SDK and verifies:

```text
HTTP server
 -> discovery
 -> input/output schema import
 -> planning
 -> execution policy
 -> call_tool()
 -> structured output validation
```

Separate transport tests verify credential isolation and unsafe-header rejection.

# MCP

SchemaRouter uses the official MCP Python SDK for Streamable HTTP discovery and execution.

## Install

For consumers:

```bash
pip install "schemarouter[mcp]"
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

## Declare a result contract the server does not publish

`outputSchema` is optional in MCP, and many servers serialize their whole result
into a text block. SchemaRouter derives output fields only from a declared
`outputSchema`, so such an endpoint arrives with none, and there is nothing to
project or normalize.

Trusted local code can declare that contract itself:

```python
from schemarouter import FieldSpec

tool = router.registry.get(key)
endpoint = tool.endpoint("lookup")

amended = tool.model_copy(
    update={
        "endpoints": [
            endpoint.model_copy(
                update={
                    "output_fields": [
                        FieldSpec(
                            name="band_gap",
                            semantic_id="materials.band_gap",
                            unit="eV",
                            qualifiers={"method": "measured"},
                        ),
                    ]
                }
            )
        ]
    }
)

router.amend_capability(key, amended)
```

The capability stays executable; the invoker is never exposed to your code.

You may declare fields the server did not publish and annotate what existing
ones mean. You may not change execution identity — path, method, parameters,
read-only or destructive classification — or the validation shape of a field the
server did publish. Anything else raises `ContractAmendmentError` and changes
nothing.

**This is not inert annotation.** Accepted amendments can change what the
caller receives and which routes are reachable:

- **Routing.** Declaring a semantic ID or unit may make a cross-provider
  fallback compatible that previously was not. That is the point of
  provider-neutral field naming, but it is a real effect worth knowing.
- **Values.** A declared `unit_normalization` rescales the numeric value on
  the result path before the caller sees it — `item * scale + offset`.
- **Projection boundary.** `path` / `result_path` on an existing field
  re-point which value a sanctioned field name returns. Projection is the
  redaction boundary for a field-selecting call, so amending these can move
  previously unprojected response content into the answer under the same
  field name. For example, the same request can go from returning
  `{"public": {"band_gap": 1.1}}` to returning
  `{"internal": {"unreleased_band_gap": 9.9}}` if the amended `path` points
  there.
- **Evidence gates.** `source_type`, `license`, and `unit` feed evidence
  availability, which the executor enforces as a hard gate. An amendment can
  unblock an evidence-gated route by declaration alone, with no change to
  what the underlying source actually returns.

# Choose an ingestion path

Use the most authoritative schema source available. SchemaRouter intentionally does **not** treat all
inputs as equivalent.

| Source | Registration | Execution binding | Trust level |
| --- | --- | --- | --- |
| Typed Python callable | Automatic | Automatic | Local code |
| OpenAPI 3.x | Automatic common subset | Same-origin automatic; cross-origin explicit | Remote schema is descriptive |
| MCP Streamable HTTP | Automatic discovery | Automatic transport, policy-gated | Remote annotations are untrusted |
| Human-readable docs | Model-assisted proposal | Explicit approval required | Inferred, evidence-grounded |

## Decision guide

Use **Python tools** when you own the implementation and want the lowest-friction typed path.

Use **OpenAPI** when a service already exposes a machine-readable HTTP contract. SchemaRouter keeps
schema-fetch credentials separate from runtime credentials and does not let a cross-origin
`servers` declaration silently grant execution authority.

Use **MCP** when the capability already participates in the MCP ecosystem. The official SDK handles
protocol negotiation; SchemaRouter imports the tool schemas and applies its own policy and runtime
validation.

Use **human-readable documentation** only when no structured contract exists. This path creates a
non-executable proposal first because model inference is weaker evidence than a published schema.

## What kind="auto" does

For `SchemaRouter.from_url(..., kind="auto")`, SchemaRouter checks structured sources in this order:

```text
URL
 -> OpenAPI 3.x JSON/YAML?
    -> yes: import OpenAPI
    -> no: attempt MCP discovery
```

A normal HTML documentation page is not silently converted into an executable tool. Use
`inspect_url()` for that path.

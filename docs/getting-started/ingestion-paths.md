# Choose an ingestion path

Use the most authoritative schema source available. SchemaRouter intentionally does **not** treat all
inputs as equivalent.

| Source | Registration | Execution binding | Trust level |
| --- | --- | --- | --- |
| Typed Python callable | Automatic | Automatic | Local code |
| OpenAPI 3.x | Automatic common subset | Same-origin automatic; cross-origin explicit | Remote schema is descriptive |
| OPTIMADE | `/info` + `/info/<entry_type>` discovery | Automatic read-only HTTP binding | Remote schema is descriptive |
| MCP Streamable HTTP | Automatic discovery | Automatic transport, policy-gated | Remote annotations are untrusted |
| Custom `SourceAdapter` | Adapter-defined | Adapter-defined | Must preserve local policy authority |
| Human-readable docs | Model-assisted proposal | Explicit approval required | Inferred, evidence-grounded |

## Decision guide

Use **Python tools** when you own the implementation and want the lowest-friction typed path.

Use **OpenAPI** when a service already exposes a machine-readable HTTP contract. SchemaRouter keeps
schema-fetch credentials separate from runtime credentials and does not let a cross-origin
`servers` declaration silently grant execution authority.

Use **OPTIMADE** when querying interoperable materials databases. SchemaRouter discovers each entry
type and its available properties, creates read-only search/get endpoints, and maps planned output
fields to OPTIMADE `response_fields`.

Use **MCP** when the capability already participates in the MCP ecosystem. The official SDK handles
protocol negotiation; SchemaRouter imports the tool schemas and applies its own policy and runtime
validation.

Use a **custom adapter** when the source follows another structured protocol such as GraphQL, OData,
STAC, FHIR, or a domain-specific standard. Adapters compile protocol semantics into canonical
SchemaRouter contracts rather than adding protocol-specific branches to the planner.

Use **human-readable documentation** only when no structured contract exists. This path creates a
non-executable proposal first because model inference is weaker evidence than a published schema.

## What `kind="auto"` does

`SchemaRouter.from_url(..., kind="auto")` asks registered adapters in priority order.

The built-in order is:

```text
OpenAPI
  -> OPTIMADE
  -> MCP
```

The first adapter that recognizes the source returns a canonical `ToolSpec` and optional trusted
invoker. Additional adapters can be registered without changing the core loader.

A normal HTML documentation page is not silently converted into an executable tool. Use
`inspect_url()` for that path.

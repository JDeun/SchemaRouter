# Choose an ingestion path

Use the most authoritative schema source available. SchemaRouter does **not** treat all
inputs as equivalent.

| Source | Registration | Execution binding | Trust level |
| --- | --- | --- | --- |
| Typed Python callable | Automatic | Automatic | Local code |
| OpenAPI 3.x | Automatic common subset | Same-origin automatic; cross-origin explicit | Remote schema is descriptive |
| GraphQL introspection | Automatic query/mutation discovery | Same-endpoint automatic | Query narrows to read-only; mutations remain policy-gated |
| OPTIMADE | `/info` + `/info/<entry_type>` discovery | Automatic read-only HTTP binding | Remote schema is descriptive |
| MCP Streamable HTTP | Automatic discovery | Automatic transport, policy-gated | Remote annotations are untrusted |
| Declarative HTTP/JSON | Trusted local ToolSpec | Automatic fixed-origin HTTP binding | Local manifest; secrets stay runtime-only |
| Custom `SourceAdapter` | Adapter-defined | Adapter-defined | Must preserve local policy authority |
| Human-readable docs | Model-assisted proposal | Explicit approval required | Inferred, evidence-grounded |

## Decision guide

Use **Python tools** when you own the implementation and want the lowest-friction typed path.

Use **OpenAPI** when a service already exposes a machine-readable HTTP contract. SchemaRouter keeps
schema-fetch credentials separate from runtime credentials and does not let a cross-origin
`servers` declaration silently grant execution authority.

Use **GraphQL** when introspection is available and native field-selection semantics matter.
SchemaRouter maps root fields and arguments into canonical contracts and turns selected output
fields into GraphQL selection sets. Mutations remain denied unless trusted local policy grants them.

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
  -> GraphQL
```

The first adapter that recognizes the source returns a canonical `ToolSpec` and optional trusted
invoker. Additional adapters can be registered without changing the core loader.

A normal HTML documentation page is not silently converted into an executable tool. Use
`inspect_url()` for that path.

## Declarative HTTP/JSON

When an API has a precise trusted contract but no discoverable OpenAPI/MCP/OPTIMADE schema, use a
locally declared `ToolSpec` and bind it with `router.add_http_tool(...)`. This preserves the
normal parameter, field, validation, policy, provenance, and secret-separation boundaries without
inventing a second REST-specific schema language.


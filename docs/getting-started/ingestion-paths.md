# Choose an ingestion path

Use the most authoritative schema source available. SchemaRouter does **not** treat all
inputs as equivalent.

If the user knows a **provider identity** rather than its protocol details, prefer
`router.add_provider(...)` first. A `ProviderProfile` maps that provider to known OpenAPI,
OPTIMADE, HTTP/JSON, or SDK access methods and then delegates to the same protocol-neutral ingestion
pipeline. It is an onboarding convenience layer, not a provider-specific planner.

| Source | Registration | Execution binding | Trust level |
| --- | --- | --- | --- |
| Known provider profile | Resolve provider identity into declared access methods | Per-method existing binding rules | Profile metadata is trusted local configuration; credentials remain process-local |
| Typed Python callable | Automatic | Automatic | Local code |
| OpenAPI 3.x | Automatic common subset | Same-origin automatic; cross-origin explicit | Remote schema is descriptive |
| OpenRPC / JSON-RPC | Automatic method/result discovery | Same-origin automatic; cross-origin explicit | Interface schema does not grant side-effect authority |
| OData v4 CSDL | Automatic entity-set discovery | Automatic read-only binding | Metadata narrows shape; writes remain ungranted |
| GraphQL introspection | Automatic query/mutation discovery | Same-endpoint automatic | Query narrows to read-only; mutations remain policy-gated |
| OPTIMADE | `/info` + `/info/<entry_type>` discovery | Automatic read-only HTTP binding | Remote schema is descriptive |
| MCP Streamable HTTP | Automatic discovery | Automatic HTTP transport, policy-gated | Remote annotations are untrusted |
| MCP stdio | Automatic discovery from trusted subprocess | Trusted local stdio lifecycle | command/argv/env are local configuration |
| MCP custom client factory | Automatic discovery through caller-owned client | Caller-owned transport lifecycle | transport state stays outside ToolSpec |
| Declarative HTTP/JSON | Trusted local ToolSpec | Automatic fixed-origin HTTP binding | Local manifest; secrets stay runtime-only |
| Custom `SourceAdapter` | Adapter-defined | Adapter-defined | Must preserve local policy authority |
| Human-readable docs | Model-assisted proposal | Explicit approval required | Inferred, evidence-grounded |

## Decision guide

Use **Python tools** when you own the implementation and want the lowest-friction typed path.

Use **OpenAPI** when a service already exposes a machine-readable HTTP contract. SchemaRouter keeps
schema-fetch credentials separate from runtime credentials and does not let a cross-origin
`servers` declaration silently grant execution authority.

Use **OpenRPC** when a JSON-RPC 2.0 service publishes a machine-readable OpenRPC document.
Methods, params, result schemas, and local references compile into the same canonical contracts.
Remote methods remain side-effect-unclassified until trusted local policy classifies them.

Use **OData** when a service publishes CSDL through `$metadata`. Entity sets become read
capabilities, complex types become nested fields, and planner-selected fields are translated to
native `$select` selectors.

Use **GraphQL** when introspection is available and native field-selection semantics matter.
SchemaRouter maps root fields and arguments into canonical contracts and turns selected output
fields into GraphQL selection sets. Mutations remain denied unless trusted local policy grants them.

Use **OPTIMADE** when querying interoperable materials databases. SchemaRouter discovers each entry
type and its available properties, creates read-only search/get endpoints, and maps planned output
fields to OPTIMADE `response_fields`.

Use **MCP** when the capability already participates in the MCP ecosystem. Streamable HTTP is the
URL-oriented path; local servers can use `add_mcp_stdio(...)`, and caller-owned/in-process or
enterprise transports can use `add_mcp_client_factory(...)`. Command arguments, environment
secrets, sockets, credentials, and client state remain trusted transport configuration rather than
model-selectable schema fields.

Use an **existing LangChain/LlamaIndex tool** when the capability is already packaged in one of
those ecosystems. SchemaRouter imports the declared tool contract and binds its trusted invocation
path instead of requiring a service-specific adapter.

Use an **explicit ToolSpec + trusted invoker** when an SDK/client cannot be safely introspected.
This is the universal escape hatch for yfinance, mp-api helpers, internal SDKs, database clients,
CLI wrappers, and similar trusted transports.

Use a **custom adapter** when the source follows another structured protocol that is not built in,
such as a STAC overlay, FHIR-specific surface, gRPC descriptor plugin, WSDL/SOAP integration, or an
organization-specific standard. Adapters compile protocol semantics into canonical SchemaRouter
contracts rather than adding provider-specific branches to the planner.

Use **human-readable documentation** only when no structured contract exists. This path creates a
non-executable proposal first because model inference is weaker evidence than a published schema.

## What `kind="auto"` does

`SchemaRouter.from_url(..., kind="auto")` is intentionally **passive by default**. It asks only
registered adapters whose trusted local discovery profile declares bounded GET/HEAD-style
inspection with no protocol session.

The built-in passive order is:

```text
OpenAPI
  -> OpenRPC
  -> OPTIMADE
  -> OData
```

GraphQL and MCP are active discovery protocols:

- GraphQL introspection sends a POST;
- MCP Streamable HTTP establishes a protocol client/session.

They are therefore skipped by default auto-detection. Use an explicit kind when you know the
protocol:

```python
await router.add_url(url, kind="graphql")
await router.add_url(url, kind="mcp")
```

If an application deliberately wants the historical broad probing behavior, it must opt in locally:

```python
await router.add_url(
    url,
    kind="auto",
    allow_active_probes=True,
)
```

The same safety boundary applies to `probe_url()` and `from_url()`. The CLI equivalent is
`schemarouter source probe URL --allow-active-probes`.

Adapters without a trusted discovery profile are treated as active for auto-detection, so a
third-party plugin cannot acquire surprise probing authority merely by being installed. Explicit
`kind="plugin_kind"` remains supported.

A normal HTML documentation page is not silently converted into an executable tool. If passive
detection fails, diagnostics name the skipped active protocols. Use `inspect_url()` for
human-readable documentation.


## Declarative HTTP/JSON

When an API has a precise trusted contract but no discoverable OpenAPI/MCP/OPTIMADE schema, use a
locally declared `ToolSpec` and bind it with `router.add_http_tool(...)`. This preserves the
normal parameter, field, validation, policy, provenance, and secret-separation boundaries without
inventing a second REST-specific schema language.

For a cross-domain view of these modes and concrete service examples, see
[Universal capability ingestion](../guides/universal-ingestion.md).


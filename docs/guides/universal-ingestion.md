# Universal capability ingestion

SchemaRouter is domain-neutral. The core target is not a hard-coded catalog of providers; it is a
small set of ingestion modes that compile external capabilities into one canonical contract:

```text
ToolSpec
  -> EndpointSpec
      -> ParameterSpec
      -> FieldSpec
```

Once compiled, every capability goes through the same planner, validation, policy, execution,
fallback, fingerprint, health, drift, and observability boundaries.

## Ingestion modes

| Mode | Best source | Typical examples |
| --- | --- | --- |
| OpenAPI | REST API with machine-readable operation schemas | Crossref, Materials Project, GitHub-style APIs |
| MCP | MCP server tool catalog | local/remote MCP tools |
| OPTIMADE | materials provider implementing OPTIMADE | Materials Project, NOMAD, Materials Cloud |
| Python callable | typed SDK/client wrapper | mp-api, yfinance, arXiv Python client |
| LangChain tool import | existing BaseTool / StructuredTool | search, scholarly, finance, SaaS tools |
| LlamaIndex tool import | existing BaseTool / FunctionTool | agent/retrieval ecosystem tools |
| GraphQL | introspection schema + selection sets | GitHub GraphQL and other typed GraphQL APIs |
| OData | CSDL / `$metadata` + `$select` | enterprise/entity APIs |
| OpenRPC | OpenRPC document / JSON-RPC 2.0 | typed RPC services |
| Declarative HTTP/JSON | trusted REST contract without a discoverable schema | Brave Search, Tavily, bespoke SaaS APIs |
| SourceAdapter plugin | protocol/provider needs custom discovery or transport | organization-specific adapters |
| Documentation proposal | only human-readable docs exist | grounded proposal followed by explicit approval |

The preferred order is the richest authoritative machine-readable contract first. A service-specific
SchemaRouter adapter should be the exception, not the default.

## Broad-domain acceptance matrix

The machine-readable source for this table is
`tests/fixtures/domain_ingestion_matrix.json`.

| Service | Domain | Primary path | Additional paths |
| --- | --- | --- | --- |
| Materials Project | materials science | OpenAPI | OPTIMADE, Python/mp-api |
| DuckDuckGo | web search | LangChain tool | Python wrapper |
| Tavily | web search | HTTP/JSON | LangChain tool, Python SDK |
| Brave Search | web search | HTTP/JSON | Python wrapper, plugin |
| Yahoo Finance | finance | Python callable | LangChain tool |
| arXiv | scholarly search | LangChain tool | Python wrapper, plugin |
| Crossref | scholarly metadata | OpenAPI | HTTP/JSON |
| GitHub REST | developer platform | OpenAPI | HTTP/JSON, plugin |
| GitHub GraphQL | developer platform | GraphQL | OpenAPI/HTTP fallback through same provider |
| Microsoft Graph OData | enterprise productivity | OData | HTTP/JSON |
| Generic OpenRPC service | RPC platform | OpenRPC | HTTP/JSON |

This matrix is intentionally heterogeneous. Passing only materials-science fixtures is not enough to
claim that SchemaRouter's ingestion layer is domain-neutral.

## Same provider, multiple access paths

A single provider may expose the same logical capability several ways.

For example:

```text
provider="materials-project"
  access_mode="openapi"
  access_mode="optimade"
  access_mode="python"
```

or:

```text
provider="tavily"
  access_mode="http_json"
  access_mode="langchain"
  access_mode="python"
```

These routes may coexist in the registry. SchemaRouter may use
`fallback_scope="same_provider"` only when its normal semantic compatibility checks pass:
semantic identity, datatype, unit/dimension, qualifiers, and the configured execution policy still
matter. Sharing a provider name never makes two routes automatically interchangeable.

## What gets preserved

Every ingestion mode should preserve the richest declared contract it can legitimately know:

- input JSON Schema and parameter requiredness;
- output JSON Schema;
- projectable fields with path/result-path semantics;
- provider and access-mode identity;
- source units when explicitly declared;
- identifiers and conservative aliases;
- execution authority;
- trusted secret boundary.

Semantic IDs, unit conversions, physical dimensions, qualifiers, licence, and provenance remain
trusted contracts. They can be imported from an authoritative structured source or attached through
trusted enrichment, but must not be guessed from descriptions.

## What does not require a provider adapter

A provider does **not** need a bespoke SchemaRouter adapter merely because it is a new brand or
domain.

Examples:

- a web-search service with an existing LangChain tool enters through the inbound tool bridge;
- a finance SDK becomes a typed Python callable;
- a REST API with a Swagger/OpenAPI schema enters through OpenAPI;
- a stable REST endpoint without OpenAPI uses a trusted declarative HTTP/JSON ToolSpec;
- an unusual protocol can be implemented as a SourceAdapter plugin without changing core.

A first-class protocol adapter is justified only when it adds machine-readable semantics or
transport behavior that the generic modes cannot preserve cleanly, such as GraphQL selection sets,
OData `$select`, gRPC descriptors, or streaming/event lifecycles.

## Remaining protocol evaluation

GraphQL, OData, STAC, JSON-RPC, gRPC/Protobuf, SOAP/WSDL, and AsyncAPI are tracked separately.
They should not be added merely to lengthen a compatibility list. Each must demonstrate concrete
schema-discovery, field-projection, or execution-lifecycle value over the generic paths.

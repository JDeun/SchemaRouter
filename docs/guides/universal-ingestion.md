# Universal capability ingestion

SchemaRouter is domain-neutral. The intended compatibility boundary is not a catalog of brands; it
is a small set of ingestion modes that compile external capabilities into the same canonical
contract:

~~~text
ToolSpec
  -> EndpointSpec
      -> ParameterSpec
      -> FieldSpec
~~~

Once registered, capabilities share the same planner, validation, execution policy, fingerprints,
fallback, health, schema-drift, projection, evidence, and observability boundaries.

## Supported ingestion modes

| Mode | Use when | Public entry point |
| --- | --- | --- |
| Direct ToolSpec | the application already owns a canonical contract | router.add_tool(...) |
| Typed Python callable | an SDK/function has a stable typed signature | router.add_callable(...) |
| ToolSpec + trusted invoker | an SDK/client is not safely introspectable | router.add_bound_tool(...) |
| OpenAPI / Swagger | an HTTP API publishes OpenAPI | from_url(..., kind="openapi") |
| MCP Streamable HTTP | a remote server publishes MCP tools over HTTP | from_url(..., kind="mcp") |
| MCP stdio | a local MCP server is launched as a trusted subprocess | router.add_mcp_stdio(...) |
| MCP custom transport | the application already owns a trusted MCP lifecycle | router.add_mcp_client_factory(...) |
| OPTIMADE | materials data is exposed through OPTIMADE | from_url(..., kind="optimade") |
| GraphQL | introspection and native selection sets are available | from_url(..., kind="graphql") |
| OData | CSDL/$metadata and $select are available | from_url(..., kind="odata") |
| OpenRPC / JSON-RPC | a JSON-RPC service publishes OpenRPC | from_url(..., kind="openrpc") |
| LangChain tool import | the capability already exists as a LangChain tool | router.add_langchain_tool(...) |
| LlamaIndex tool import | the capability already exists as a LlamaIndex tool | router.add_llamaindex_tool(...) |
| Declarative HTTP/JSON | REST is stable but no discoverable schema exists | router.add_http_tool(...) |
| SourceAdapter plugin | another protocol needs custom discovery/transport | router.register_adapter(...) |
| Human-readable docs | only documentation exists | inspect -> proposal -> explicit approval |

Protocol-specific code is added to core only when it preserves useful machine-readable semantics
that generic HTTP, Python, or plugin paths would lose.

## Broad-domain conformance matrix

The machine-readable regression fixture is
tests/fixtures/domain_ingestion_matrix.json. It intentionally includes domains unrelated to
materials science.

| Service/example | Domain | Preferred ingestion | Other supported paths |
| --- | --- | --- | --- |
| Materials Project | materials science | OpenAPI | OPTIMADE, Python/mp-api, bound SDK |
| DuckDuckGo/DDGS | web search | LangChain tool | Python wrapper, bound SDK |
| Tavily | web search | HTTP/JSON | LangChain tool, Python SDK, bound SDK |
| Brave Search | web search | HTTP/JSON | Python wrapper, bound SDK, plugin |
| Yahoo Finance/yfinance | finance | bound SDK | Python callable, LangChain tool |
| arXiv | scholarly search | LangChain tool | Python wrapper, bound SDK, plugin |
| Crossref | scholarly metadata | OpenAPI | HTTP/JSON, bound SDK |
| GitHub REST | developer platform | OpenAPI | HTTP/JSON, bound SDK, plugin |
| GraphQL business API | business application | GraphQL | bound SDK |
| OData enterprise API | enterprise data | OData | bound SDK |
| OpenRPC service | generic RPC | OpenRPC | HTTP/JSON, bound SDK |
| Local MCP stdio server | local tooling | MCP stdio | custom MCP client factory |

The matrix is validated in CI. Adding a new advertised ingestion mode without a corresponding
public API or built-in adapter makes the conformance test fail.

## Same provider, multiple access paths

One provider can expose the same logical data through several access modes.

~~~text
provider="materials-project"
  access_mode="openapi"
  access_mode="optimade"
  access_mode="python"
  access_mode="sdk"
~~~

or:

~~~text
provider="tavily"
  access_mode="http_json"
  access_mode="langchain"
  access_mode="python"
~~~

These routes may coexist. They are not automatically equivalent merely because the provider name
matches. Same-provider fallback still checks the normal semantic/type/unit/qualifier and execution
policy compatibility gates.

## Field coverage is shared across adapters

Structured adapters use the same typed field contract. Where the source declares it, SchemaRouter
preserves:

- JSON datatype and shape;
- descriptions and conservative aliases;
- source path and projected result path;
- identifiers;
- source unit;
- provider/access identity;
- nested object and record-preserving array-item paths.

Array descendants use explicit record-preserving paths such as:

~~~text
results[].title
results[].url
~~~

rather than flattening sibling arrays independently.

Semantic IDs, canonical-unit conversions, dimensions, qualifiers, licence, and provenance are
trusted contracts. They can come from an authoritative structured source or trusted enrichment, but
are never guessed from arbitrary prose.

## When a service has several interfaces

Prefer the richest authoritative machine-readable path, but registering multiple paths is useful for
availability/fallback.

Materials Project is a representative example:

~~~text
Materials Project
  -> OpenAPI
  -> OPTIMADE
  -> mp-api / Python
  -> explicit ToolSpec + trusted SDK invoker
~~~

SchemaRouter does not need a special Materials Project router for this. All paths compile into the
same provider-neutral capability model.

The same principle applies outside science:

~~~text
web search
  -> existing LangChain/LlamaIndex tool
  -> direct REST/HTTP JSON
  -> typed Python SDK
  -> SourceAdapter plugin when protocol semantics require it
~~~

## Protocols kept outside core

STAC, gRPC/Protobuf, SOAP/WSDL, and AsyncAPI currently use the plugin/overlay boundary unless a
future implementation demonstrates enough discovery/projection/lifecycle value to justify core
promotion. See the protocol-ingestion decision guide for the rationale.

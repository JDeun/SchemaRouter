# Declarative HTTP/JSON tool

모든 API가 OpenAPI, MCP 또는 다른 machine-discoverable capability schema를 제공하는 것은 아닙니다.
SchemaRouter can bind a trusted local `ToolSpec` directly to an HTTP/JSON base URL.

`ToolSpec` 자체가 manifest입니다. 별도의 REST-specific schema language는 없습니다.

## REST capability 등록

```python
from schemarouter import EndpointSpec, FieldSpec, ParameterSpec, SchemaRouter, ToolSpec

crossref = ToolSpec(
    name="crossref",
    provider="crossref",
    access_mode="rest",
    endpoints=[
        EndpointSpec(
            name="get_work",
            method="GET",
            path="/works/{doi}",
            read_only=True,
            parameters=[
                ParameterSpec(
                    name="doi",
                    required=True,
                    location="path",
                    json_schema={"type": "string"},
                ),
            ],
            output_fields=[
                FieldSpec(
                    name="message.DOI",
                    path=["message", "DOI"],
                    result_path=["message.DOI"],
                    json_schema={"type": "string"},
                    identifier=True,
                ),
            ],
            output_schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "object",
                        "properties": {
                            "DOI": {"type": "string"},
                        },
                    }
                },
            },
        )
    ],
)

router = SchemaRouter()
router.add_http_tool(
    crossref,
    base_url="https://api.crossref.org/v1",
)
```

The same path handles query, path, non-sensitive header, flattened JSON-body, and root JSON-body
parameters supported by SchemaRouter's trusted HTTP transport.

## Secrets stay outside the manifest

Authentication belongs to the trusted binding:

```python
router.add_http_tool(
    brave_search,
    base_url="https://api.search.brave.com",
    trusted_headers={
        "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
    },
)
```

Trusted headers are never copied into `ToolSpec`, planner state, or model-selectable arguments.
A declared header argument cannot override a trusted header or common sensitive authorization
headers.

## When to use this path

Prefer a richer machine-readable source when one is available:

1. native MCP, OPTIMADE, or OpenAPI;
2. an existing typed LangChain/LlamaIndex tool import;
3. a typed Python callable / SDK wrapper;
4. a declarative HTTP/JSON ToolSpec;
5. grounded human-readable documentation proposal plus explicit approval.

The HTTP/JSON path is useful for stable REST APIs that have precise machine-known contracts in your
application but do not expose a schema endpoint SchemaRouter can discover automatically.

## Same provider, multiple access modes

A provider may be registered through several access paths:

```text
provider="materials-project"
  access_mode="optimade"
  access_mode="openapi"
  access_mode="python"
```

or:

```text
provider="tavily"
  access_mode="langchain"
  access_mode="python"
  access_mode="http_json"
```

If the routes expose compatible semantic IDs, datatypes, units, and qualifiers,
`fallback_scope="same_provider"` can use them as alternatives without treating them as different
scientific sources.

## Safety boundaries

Declarative HTTP registration is trusted local configuration. SchemaRouter does not crawl an
arbitrary REST service to guess endpoints or permissions.

- `method` and `path` must be explicit.
- mutation authority remains governed by `ExecutionPolicy`.
- the base origin is fixed by the trusted binding.
- credentials cannot be embedded in the base URL.
- redirects are not followed by the transport.
- input/output JSON Schema validation still runs.
- response size limits remain enforced.
- units, semantic IDs, qualifiers, licence, and normalization contracts are never inferred from
  prose.

For human-readable documentation, use the proposal/approval workflow instead.

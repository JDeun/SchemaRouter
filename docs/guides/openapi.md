# OpenAPI

SchemaRouter can import a common, production-oriented subset of OpenAPI 3.x from JSON or YAML.

## Import

```python
from schemarouter import SchemaRouter

router = await SchemaRouter.from_url(
    "https://api.example.com/openapi.json",
    kind="openapi",
)
```

The adapter imports operations, path/query/header parameters, JSON request-body properties, response
schemas, local component references, local reference chains, local Path Item references, and
read/write classification inferred from the HTTP method. Object properties and required fields
reachable through `allOf` are flattened for planner visibility while the original composition is
retained for runtime JSON Schema validation.

## Same-origin and cross-origin servers

A same-origin runtime server can be bound automatically.

If the OpenAPI document declares a server on another origin, SchemaRouter imports the schema but
does not silently grant execution authority.

```python
router.bind_openapi(
    "users_api",
    base_url="https://api.example.com/",
    trusted_headers={"Authorization": "Bearer ..."},
)
```

## Schema credentials versus runtime credentials

```python
router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    kind="openapi",
    schema_headers={"X-Docs-Token": "..."},
    base_url="https://api.example.com/",
    trusted_headers={"Authorization": "Bearer ..."},
)
```

`schema_headers` never become runtime API headers, and `trusted_headers` are never exposed as
model-selectable arguments.

## Parameter collisions

OpenAPI identifies parameters by both name and location. If an operation defines the same wire name
in multiple places, SchemaRouter creates distinct logical argument keys.

```text
path:id   -> path__id
query:id  -> query__id
header:id -> header__id
body:id   -> body__id
```

The transport maps those keys back to the original wire name.

## Local and same-document references

Nested `#/components/...` reference chains are resolved for planner-side schema discovery while
their component root remains available to runtime JSON Schema validation, including array item
schemas and recursive structures.

When a document is loaded from a URL, URI references that resolve back to that exact document are
normalized to local JSON Pointer references. For example,
`./openapi.json#/components/schemas/User` is treated as a local reference when the loaded resource
is that same `openapi.json`.

SchemaRouter does **not** fetch cross-document references automatically. Doing so would expand the
schema-fetch trust boundary and requires separate bounded origin/size/depth controls.

## Current common subset

Supported paths include:

- OpenAPI 3.x JSON and YAML;
- operations under `paths`;
- path/query/header parameters;
- object-like JSON request bodies;
- JSON responses;
- local component/path-item reference chains;
- same-document URI-reference normalization;
- planner-side object-property/required flattening through `allOf`;
- explicit cross-origin binding;
- runtime origin confinement.

Cross-document references, planner-side `oneOf`/`anyOf` variant selection, and more ergonomic
non-object request bodies remain follow-up work. Unsupported constructs should not be guessed.


## Runtime response bound

OpenAPI runtime responses are streamed and capped at **16 MiB by default** before JSON/text decoding.
The bound applies even when a server omits or lies about `Content-Length`.

When constructing `OpenAPIRemoteInvoker` manually, trusted local code may choose a smaller or
larger positive integer through `max_response_bytes`. Keep the limit appropriate for the endpoint
contract; a high limit weakens protection against unexpectedly large remote responses.

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
retained for runtime JSON Schema validation. For response schemas, object fields reachable through
`oneOf` / `anyOf` variants are also exposed as conditional planner-visible output fields. The
original composed response schema remains authoritative at runtime.

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

SchemaRouter does **not** fetch cross-document references by default. Trusted callers may opt in to
bounded same-origin resolution:

```python
router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    kind="openapi",
    openapi_external_refs=True,
)
```

The resolver follows relative/absolute HTTP(S) references only when they stay on the entry
document's origin. It reuses `schema_headers` only after this explicit opt-in and applies independent
limits for recursion depth, unique referenced documents, aggregate referenced bytes, per-document
bytes, and redirects.

Defaults:

```text
openapi_ref_max_depth      = 3
openapi_ref_max_documents  = 8
openapi_ref_max_bytes      = 10 MiB
per referenced document    = 5 MiB
redirects per document     = 5
```

These bounds can be reduced by trusted application code through the corresponding
`SchemaRouter.from_url()` / `add_url()` keyword arguments.

Referenced JSON/YAML documents are fetched completely, indexed as JSON Schema resources, rewritten
into a local in-memory bundle, and then consumed through the same local-ref parser and runtime JSON
Schema validator. This avoids fragment-only parsing and keeps execution schemas self-contained.

With `openapi_external_refs=True`, the bounded resolver understands static JSON Schema resource
scope:

- same-origin absolute or relative `$id` values rebase descendant `$ref` resolution;
- nested `$id` values are indexed as virtual resources inside the already loaded document;
- static `$anchor` fragments such as `schema.json#User` resolve to their indexed subschema;
- fetched/rebased resources remain confined to the entry document's origin;
- resolved `$ref` values are rewritten to local JSON Pointers;
- `$id` and `$anchor` are removed from the final runtime bundle after rewriting so validation
  does not trigger a second external-resolution path.

The current bounded resolver intentionally fails closed for:

- cross-origin referenced documents or cross-origin `$id` base URIs;
- `$id` values with fragments;
- missing, duplicate, or invalid static anchors;
- `$dynamicRef`, `$dynamicAnchor`, `$recursiveRef`, and `$recursiveAnchor`;
- depth/document/byte limit exhaustion;
- unstructured referenced content.

Dynamic JSON Schema scope is deliberately excluded because statically rewriting it as an ordinary
anchor could change validation semantics.

## Current common subset

Supported paths include:

- OpenAPI 3.x JSON and YAML;
- operations under `paths`;
- path/query/header parameters;
- object-like JSON request bodies;
- JSON responses;
- local component/path-item reference chains;
- same-document URI-reference normalization;
- explicitly enabled bounded same-origin cross-document `$ref` bundling;
- bounded same-origin JSON Schema `$id` rebasing and static `$anchor` resolution;
- planner-side object-property/required flattening through `allOf`;
- planner-visible response-field discovery across `oneOf` / `anyOf` object variants while
  preserving composed runtime validation;
- explicit cross-origin binding;
- runtime origin confinement.

Dynamic JSON Schema references/anchors, planner-side schema-variant selection, variant request-body
flattening, and more ergonomic non-object request bodies remain follow-up work. Response variant
fields may be selected for projection, but a field that is absent from the actual validated
response variant is simply absent from the projected result. Unsupported constructs should not be
guessed.


## Runtime response bound

OpenAPI runtime responses are streamed and capped at **16 MiB by default** before JSON/text decoding.
The bound applies even when a server omits or lies about `Content-Length`.

When constructing `OpenAPIRemoteInvoker` manually, trusted local code may choose a smaller or
larger positive integer through `max_response_bytes`. Keep the limit appropriate for the endpoint
contract; a high limit weakens protection against unexpectedly large remote responses.

# OpenRPC / JSON-RPC

SchemaRouter can ingest an OpenRPC document and compile its JSON-RPC methods into the same
`ToolSpec -> EndpointSpec -> ParameterSpec -> FieldSpec` model used by other sources.

## Register an OpenRPC service

```python
router = await SchemaRouter.from_url(
    "https://rpc.example/openrpc.json",
    kind="openrpc",
)
```

OpenRPC method names become endpoint names. Declared params become typed arguments and the result
JSON Schema becomes the output contract.

Local `$ref` values under `components` are resolved. Nested object fields and declared array-item
fields become planner-visible. A result such as `results: [{title, score}, ...]` can expose
`results[].title` and `results[].score`, with record alignment preserved through projection.
Root result arrays keep implicit record semantics and expose their item fields directly.

## Execution authority remains local

OpenRPC describes interface shape, not trusted side-effect policy. SchemaRouter therefore does not
mark methods read-only or mutating from descriptions or tags.

Remote OpenRPC methods are unclassified by default and fail closed under the default execution
policy. Grant authority through trusted local policy or a trusted contract amendment.

## Server binding

If an OpenRPC document advertises an HTTP(S) server on the same origin as the schema URL,
SchemaRouter may bind it automatically.

A cross-origin advertised server is treated as a suggestion only:

```python
router = await SchemaRouter.from_url(
    "https://schema.example/openrpc.json",
    kind="openrpc",
    base_url="https://approved-rpc.example/rpc",
)
```

This explicit `base_url` is a trusted local approval boundary.

Authentication headers belong to the trusted runtime binding and never enter the model-visible
contract:

```python
router = await SchemaRouter.from_url(
    "https://rpc.example/openrpc.json",
    kind="openrpc",
    trusted_headers={"Authorization": f"Bearer {token}"},
)
```

## Parameter structures

OpenRPC `by-name` and `either` methods are sent with JSON object params.

`by-position` methods are supported conservatively. SchemaRouter preserves declared order and
refuses an invocation that skips an earlier optional positional parameter while supplying a later
one, because silently shifting positions would change semantics.

## Response validation

The transport verifies:
- HTTP status;
- response-size bounds;
- JSON decoding;
- `jsonrpc == "2.0"`;
- matching request/response IDs;
- absence of an application-level `error`;
- presence of `result`.

The resulting value then goes through the ordinary SchemaRouter output JSON Schema validation and
field projection pipeline.

## Scope

Initial support covers ordinary request/response JSON-RPC methods.

Notifications, batch requests, and long-lived/streaming RPC lifecycles are intentionally deferred
until they have explicit runtime semantics.

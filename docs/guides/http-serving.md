# HTTP serving

SchemaRouter can expose a configured router through an optional FastAPI application.

Install the server extra:

```bash
pip install "schemarouter[server]"
```

The serving layer is intentionally narrow. It exposes health, schema introspection, planning, and
optionally execution. It does not expose ingestion, registry mutation, proposal approval, adapter
loading, Python callable registration, or credential configuration.

## Create a plan-only app

```python
from schemarouter.serving import create_app

app = create_app(router)
```

The default routes are:

- `GET /healthz`
- `GET /v1/schemas`
- `POST /v1/plan`

`/v1/invoke` is not registered by default.

Run the app with an ASGI server:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000
```

## Enable authenticated execution

Actual tool execution requires an explicit serving policy.

```python
from schemarouter.serving import HTTPServerPolicy, create_app

app = create_app(
    router,
    policy=HTTPServerPolicy(
        bearer_token="replace-with-a-secret",
        enable_execution=True,
    ),
)
```

When a bearer token is configured, all `/v1/*` routes require:

```text
Authorization: Bearer replace-with-a-secret
```

`/healthz` remains unauthenticated for health probes.

Execution cannot be enabled without authentication unless the application makes a second explicit
choice:

```python
HTTPServerPolicy(
    enable_execution=True,
    allow_unauthenticated_execution=True,
)
```

That mode is intended only for an already trusted/local network boundary.

## Request envelopes

Planning:

```json
{
  "request": {
    "query": "city temperature",
    "arguments": {
      "city": "Seoul"
    }
  }
}
```

Invocation:

```json
{
  "request": {
    "query": "city temperature",
    "arguments": {
      "city": "Seoul"
    }
  },
  "config": {
    "max_concurrency": 4
  }
}
```

The same planner, policy, approval, execution-budget, schema-validation, hook, and binding-drift
checks used by the in-process runtime remain authoritative.

## Schema endpoint

`GET /v1/schemas` returns the public SchemaRouter input, output, and runtime configuration schemas.
It does not expose registry mutation or transport credentials.

## Error privacy

By default, HTTP error bodies contain only a stable error class:

```json
{
  "error": "ExecutionError"
}
```

Request validation details and SchemaRouter exception messages are not echoed by default because
they can contain user input or provider details.

Trusted development environments can opt in:

```python
HTTPServerPolicy(expose_error_messages=True)
```

Do not enable this casually on an internet-facing service.

## Request-size boundary

Request bodies are bounded before FastAPI/Pydantic processing:

```python
HTTPServerPolicy(max_request_bytes=1024 * 1024)
```

The default is 1 MiB and the hard policy ceiling is 16 MiB. Both declared `Content-Length` and
actual received body length are checked.

## API documentation

Swagger/ReDoc/OpenAPI endpoints are disabled by default.

Enable them explicitly:

```python
HTTPServerPolicy(expose_docs=True)
```

When enabled, protect them with the surrounding network/authentication boundary if the generated
schema itself is sensitive.

## Deployment boundary

The built-in bearer token is deliberately simple. For production internet-facing systems, prefer a
reverse proxy, service mesh, gateway, or platform-native identity layer for TLS, token rotation,
rate limiting, audit, and organization policy. The SchemaRouter serving layer should remain a thin
ASGI boundary rather than become a general identity platform.

# Execution and trust boundaries

Execution is deliberately stricter than planning.

## Execution pipeline

```text
ToolCall
  -> current endpoint lookup
  -> schema fingerprint check
  -> argument allowlist
  -> required-argument recomputation
  -> input JSON Schema validation
  -> execution policy
  -> invoker binding check
  -> trusted invocation
  -> raw output JSON Schema validation
  -> field projection
  -> ToolResult
```

## Plans are not permissions

A plan can describe a mutation without being allowed to perform it. Local `ExecutionPolicy` remains
the authority for side effects.

Remote OpenAPI descriptions, MCP annotations, and model output cannot raise policy permissions.

## Credentials stay out of model arguments

OpenAPI distinguishes:

- `schema_headers`: used only while fetching the OpenAPI document;
- `trusted_headers`: injected only by the runtime transport.

Sensitive runtime headers are not exposed as tool parameters.

## Network origin

OpenAPI runtime calls are confined to the approved API origin. Cross-origin `servers` declarations
are descriptive until trusted local code supplies an explicit base URL.

Schema and documentation redirects are limited to their original origin.

## Runtime validation

Input is validated immediately before invocation. Raw structured output is validated immediately
after invocation and **before** response-field projection.

Projection therefore cannot hide an invalid unrequested field in an otherwise malformed response.

## Error categories

SchemaRouter keeps failures distinct so callers can decide what is retryable or actionable:

- `PlanningError`
- `PlanValidationError`
- `SchemaValidationError`
- `PolicyViolationError`
- `SchemaDriftError`
- `BindingDriftError`
- `ExecutionError`
- `SchemaSourceError`

Schema contract violations are never automatically retried.

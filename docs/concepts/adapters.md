# Adapter ecosystem

SchemaRouter treats external protocols as **compilers into one canonical execution model**.

```text
OpenAPI ─┐
OPTIMADE ├─> AdapterRegistry ─> ToolSpec / EndpointSpec ─> Planner ─> Executor
MCP ─────┤
Custom ──┘
```

The planner does not need an `if optimade` or `if graphql` branch. Protocol-specific discovery,
query syntax, and transport rules stay inside adapters.

## AdapterRegistry

The registry owns:

- a unique string `kind`;
- a deterministic priority used only for `kind="auto"`;
- explicit kind lookup;
- registration/replacement of third-party adapters.

It does **not** own execution policy or authorization.

## Canonical boundary

Every structured adapter compiles its source into the same contracts:

```text
ToolSpec
  -> EndpointSpec
      -> ParameterSpec
      -> FieldSpec
      -> input/output JSON Schema
```

This keeps schema fingerprints, planning, validation, policy, retries, and observability independent
of the source protocol.

Runtime-affecting adapter state belongs in fingerprinted `execution_metadata`, not ordinary
descriptive `metadata`. Remote adapters also set the first-class `ToolSpec.remote` contract.
This prevents a transport/origin change from occurring behind an unchanged plan fingerprint.

## Call-aware transport

Most adapters bind a normal `endpoint + arguments` invoker.

Some protocols support server-side field selection. A call-aware invoker receives the full validated
`ToolCall` so it can map `call.fields` onto protocol-native selection:

| Protocol | Field selection |
| --- | --- |
| OPTIMADE | `response_fields` |
| GraphQL | selection set |
| OData | `$select` |
| STAC | fields extension when available |

This is a transport optimization. The executor still validates the current schema and local policy
before invoking it.

## Auto discovery

Built-ins are currently ordered:

```text
OpenAPI (100)
OPTIMADE (90)
MCP (80)
```

Third-party adapters choose a priority deliberately. Explicit `kind="..."` bypasses priority and
selects that adapter directly.

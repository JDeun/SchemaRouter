# System One compatible decision providers

SchemaRouter can use any provider that is compatible with the typed System One decision
contract through a single bounded backend.

This integration is intentionally **model-neutral**. Hosted Jev, self-hosted decision models,
and future compatible runtimes can share the same SchemaRouter adapter when they expose the
compatible System One client contract.

## Install

```bash
pip install "schemarouter[systemone]"
```

The existing Jev-specific extra remains supported:

```bash
pip install "schemarouter[jev]"
```

## Connect a compatible provider

```python
from schemarouter.integrations import SystemOneDecisionBackend

backend = SystemOneDecisionBackend(
    base_url="http://127.0.0.1:8000/v1",
    model="kev-4b",
    provider_name="kev-local",
    min_confidence=0.70,
)
```

Pass the backend to the normal SchemaRouter decision surface. The model may choose only from
the finite option IDs supplied by SchemaRouter.

Changing models should normally require only configuration changes:

```python
backend = SystemOneDecisionBackend(
    base_url=SYSTEM_ONE_BASE_URL,
    model=SYSTEM_ONE_MODEL,
    provider_name=SYSTEM_ONE_PROVIDER,
)
```

No model-specific SchemaRouter class is required merely because the server changes.

## What remains local

A compatible provider is a decision signal, not an execution authority.

SchemaRouter still:

- constructs the finite candidate set from registered schema;
- omits `DecisionOption.metadata` from provider-visible questions;
- validates the returned option ID against the local candidate set;
- rejects malformed, non-finite, or out-of-range confidence values;
- applies the configured confidence abstention rule;
- constructs and validates the execution plan locally;
- retains policy, schema, fingerprint, and execution authority.

A provider therefore cannot create a tool, endpoint, field, argument, or permission.

## Direct Laya vs System One wire compatibility

`LayaDecisionBackend` remains useful when running the official Python Laya package directly,
including its local checkpoint routing and CPU/CUDA/MPS controls.

Use `SystemOneDecisionBackend` instead when a Laya-compatible, Kev-compatible, or other
System One model is served behind a compatible endpoint. This keeps deployment/runtime choice
outside SchemaRouter's planning semantics.

## Jev compatibility

`JevDecisionBackend` remains available and backward compatible. It is now the TypeSafe Jev
specialization of the same generic provider contract, so existing applications do not need to
migrate.

## Evaluating new models

Wire compatibility does **not** imply quality equivalence. Before replacing a production decision
model, evaluate the candidate on the same frozen workload and record:

- exact-route accuracy;
- unsupported and out-of-domain rejection;
- false-route rate;
- calibration/abstention behavior;
- per-language and per-route behavior;
- p50/p95 latency and model residency;
- provider/runtime errors;
- authority violations.

SchemaRouter's research harness uses this principle: infrastructure compatibility is reusable,
while model promotion requires independent evidence.

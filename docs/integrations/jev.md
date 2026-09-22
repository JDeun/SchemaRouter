# Jev / TypeSafe System One

SchemaRouter provides an optional bounded-decision adapter for TypeSafe System One models such as
Jev. The adapter is deliberately outside the core dependency graph and is **off by default**.

Jev does not author a SchemaRouter execution plan. It receives a finite set of option IDs and
returns one of those IDs. SchemaRouter validates the result before the planner can use it.

## Install

For consumers, install the published optional extra:

```bash
pip install "schemarouter[jev]"
```

The bridge is included in the published `0.3.0` release.

The integration currently supports `typesafe-sdk>=0.7,<1`.

Set the API key through the official SDK environment variable:

```bash
export TYPESAFE_API_KEY="..."
```

The SDK default model is `jev-latest`. You may override it explicitly.

## Synchronous usage

```python
from schemarouter import DecisionPolicy, SchemaPlanner
from schemarouter.integrations import JevDecisionBackend

backend = JevDecisionBackend(
    min_confidence=0.65,
)

planner = SchemaPlanner(
    registry,
    decision_backend=backend,
    decision_policy=DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
        fallback="deterministic",
    ),
)

plan = planner.plan("find the band gap for silicon")
```

If the Jev confidence is below `min_confidence`, the backend abstains. With the default
`fallback="deterministic"`, SchemaRouter resumes its deterministic ranking and records a warning.

## Asynchronous usage

```python
backend = JevDecisionBackend(
    async_mode=True,
    min_confidence=0.65,
)

planner = SchemaPlanner(
    registry,
    decision_backend=backend,
    decision_policy=DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
    ),
)

plan = await planner.aplan("find the band gap for silicon")
```

## Data boundary

The provider receives:

- the user query;
- `DecisionRequest.context` when `include_context=True`;
- locally generated option IDs;
- option labels and descriptions.

The adapter intentionally does **not** forward `DecisionOption.metadata`. Runtime credentials,
transport credentials, invokers, and execution policy are never added to the model state.

Set `include_context=False` when even bounded request context should remain local.

Do not put secrets in the user query or decision context. Those values are provider input when
context forwarding is enabled.

## Fail-closed behavior

The adapter rejects:

- option IDs that were not offered, even when the returned confidence is below the abstention
  threshold;
- non-finite confidence values;
- confidence outside `[0, 1]`;
- malformed responses;
- an asynchronous client accidentally supplied to synchronous mode.

Provider errors are handled by the surrounding `DecisionPolicy`. Use
`fallback="deterministic"` for graceful degradation or `fallback="error"` when decision-provider
failure must stop planning.

## Current scope

The Jev adapter currently asks one TypeSafe `choice` question and therefore returns at most one
candidate per decision call. `DecisionRequest.max_selections` remains an upper bound; the provider
does not attempt multi-select ranking.

This is intentional for the first provider integration. Multi-selection should use a dedicated
bounded contract rather than synthesizing additional choices from untrusted free-form output.

## Benchmarking

The repository contains a provider-neutral benchmark harness:

```bash
python scripts/benchmark_decision_routing.py
```

Run Jev when an API key is available:

```bash
TYPESAFE_API_KEY="..." \
python scripts/benchmark_decision_routing.py --jev --min-confidence 0.65
```

The report records routing accuracy, abstentions, latency, token usage, provider errors, and optional
cost estimates. See [Decision routing benchmark](../guides/decision-benchmark.md).

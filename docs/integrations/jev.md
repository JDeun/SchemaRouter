# Jev / TypeSafe System One

**Research archive (development branch):** This decision adapter or plugin loader is no longer part of the installed SchemaRouter API. The following contracts and examples are retained for historical comparison in a source checkout under `scripts/research_legacy_decision_adapters/`. The development package also removes the `jev`, `systemone`, and `laya` extras; install research SDKs explicitly from a source checkout. Do not use this path as the paper-first router.

**Development migration:** The former `DecisionPolicy` and final candidate, field, and evidence decision callbacks have been removed from the installed planner. Examples using `LegacyDecisionPlanner` are historical comparisons that require a source checkout; they are not installed product APIs. The remaining semantic candidate recall, capability/operation fit and endpoint disambiguation callbacks have also moved into the research-only comparison planner. The paper-first path uses the existing deterministic field and evidence contracts, not a second model decision.

SchemaRouter provides an optional bounded-decision adapter for TypeSafe System One models such as
Jev. The adapter sits outside the core dependency graph and is **off by default**.

Jev does not author a SchemaRouter execution plan and does not act as an agent/orchestrator. It
receives a finite set of option IDs and returns one of those IDs. It never owns tool execution,
memory, or an agent loop. SchemaRouter validates the result before the planner can use it.

## Install

For historical comparison, install the research SDK from a source checkout:

```bash
pip install -e . "typesafe-sdk>=0.7,<1"
```

The archived bridge is not shipped in the development distribution. The published v0.17.0 wheel retains its original `jev` extra.

The integration currently supports `typesafe-sdk>=0.7,<1`.

Set the API key through the official SDK environment variable:

```bash
export TYPESAFE_API_KEY="..."
```

The SDK default model is `jev-latest`. You may override it explicitly.

## Synchronous usage

```python
from scripts.research_legacy_decision_policy import DecisionPolicy, LegacyDecisionPlanner
from scripts.research_legacy_decision_adapters import JevDecisionBackend

backend = JevDecisionBackend(
    min_confidence=0.65,
)

planner = LegacyDecisionPlanner(
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

planner = LegacyDecisionPlanner(
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

The adapter does **not** forward `DecisionOption.metadata`. Runtime credentials,
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

The Jev adapter currently asks one TypeSafe `choice` question, so it returns at most one
candidate per decision call. `DecisionRequest.max_selections` remains an upper bound; the provider
does not attempt multi-select ranking.

Multi-selection should use a dedicated
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

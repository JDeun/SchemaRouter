# Jev / TypeSafe System One

SchemaRouter는 Jev와 같은 TypeSafe System One model을 위한 optional bounded-decision adapter를 제공합니다. Adapter는 core dependency graph 밖에 있으며 **기본적으로 비활성화**됩니다.

Jev는 SchemaRouter execution plan을 작성하지 않으며 agent/orchestrator 역할도 하지 않습니다. 유한한 option ID 집합을 받아 그중 하나를 반환할 뿐입니다. Tool execution, memory, agent loop를 소유하지 않으며 planner가 결과를 사용하기 전에 SchemaRouter가 이를 검증합니다.

## 설치

사용자는 배포된 optional extra를 설치합니다.

```bash
pip install "schemarouter[jev]"
```

Bridge는 현재 SchemaRouter distribution에 optional `jev` extra로 포함됩니다.

현재 integration은 `typesafe-sdk>=0.7,<1`을 지원합니다.

Set the API key through the official SDK environment variable:

```bash
export TYPESAFE_API_KEY="..."
```

SDK 기본 model은 `jev-latest`이며 명시적으로 override할 수 있습니다.

## Synchronous 사용

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

## Asynchronous 사용

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

Provider는 다음을 받습니다.

- the user query;
- `DecisionRequest.context` when `include_context=True`;
- locally generated option IDs;
- option labels and descriptions.

The adapter does **not** forward `DecisionOption.metadata`. Runtime credentials,
transport credentials, invokers, and execution policy are never added to the model state.

Set `include_context=False` when even bounded request context should remain local.

Do not put secrets in the user query or decision context. Those values are provider input when
context forwarding is enabled.

## Fail-closed 동작

Adapter는 다음을 거부합니다.

- option IDs that were not offered, even when the returned confidence is below the abstention
  threshold;
- non-finite confidence values;
- confidence outside `[0, 1]`;
- malformed responses;
- an asynchronous client accidentally supplied to synchronous mode.

Provider errors are handled by the surrounding `DecisionPolicy`. Use
`fallback="deterministic"` for graceful degradation or `fallback="error"` when decision-provider
failure must stop planning.

## 현재 범위

The Jev adapter currently asks one TypeSafe `choice` question, so it returns at most one
candidate per decision call. `DecisionRequest.max_selections` remains an upper bound; the provider
does not attempt multi-select ranking.

Multi-selection should use a dedicated
bounded contract rather than synthesizing additional choices from untrusted free-form output.

## Benchmark

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

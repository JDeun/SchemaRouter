# Jev / TypeSafe System One

SchemaRouter는 Jev 같은 TypeSafe System One model을 위한 optional bounded-decision adapter를 제공합니다. Adapter는 core dependency graph 밖에 있으며 기본적으로 **off**입니다.

Jev는 SchemaRouter execution plan을 작성하거나 agent/orchestrator로 동작하지 않습니다. Finite option ID 집합을 받고 그중 하나를 반환합니다. Tool execution, memory, agent loop를 소유하지 않으며 SchemaRouter가 planner 사용 전에 결과를 검증합니다.

## 설치

```bash
pip install "schemarouter[jev]"
```

Bridge는 optional `jev` extra로 배포되며 현재 `typesafe-sdk>=0.7,<1`을 지원합니다.

```bash
export TYPESAFE_API_KEY="..."
```

SDK default model은 `jev-latest`이며 명시적으로 override할 수 있습니다.

## Sync 사용

```python
from schemarouter import DecisionPolicy, SchemaPlanner
from schemarouter.integrations import JevDecisionBackend

backend = JevDecisionBackend(min_confidence=0.65)
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

Jev confidence가 `min_confidence`보다 낮으면 abstain합니다. Default `fallback="deterministic"`이면 SchemaRouter가 deterministic ranking을 재개하고 warning을 기록합니다.

## Async 사용

```python
backend = JevDecisionBackend(async_mode=True, min_confidence=0.65)
planner = SchemaPlanner(
    registry,
    decision_backend=backend,
    decision_policy=DecisionPolicy(enabled=True, endpoint_selection=True),
)
plan = await planner.aplan("find the band gap for silicon")
```

## Data boundary

Provider가 받는 것은 user query, `include_context=True`일 때 `DecisionRequest.context`, locally generated option ID, option label/description입니다.

Adapter는 `DecisionOption.metadata`를 전달하지 않습니다. Runtime/transport credential, invoker, execution policy는 model state에 추가하지 않습니다. Bounded request context도 local에 남겨야 하면 `include_context=False`를 사용합니다.

User query/decision context에 secret을 넣지 마십시오. Context forwarding이 활성화되면 해당 값은 provider input입니다.

## Fail-closed behavior

Adapter는 offered되지 않은 option ID, non-finite confidence, `[0,1]` 밖 confidence, malformed response, sync mode에 실수로 전달된 async client를 거부합니다. Unknown option은 confidence가 낮아도 먼저 거부합니다.

Provider error는 주변 `DecisionPolicy`가 처리합니다. Graceful degradation은 `fallback="deterministic"`, provider failure가 planning을 중단해야 하면 `fallback="error"`를 사용합니다.

## 현재 범위

Jev adapter는 TypeSafe `choice` 질문 하나를 사용하므로 decision call당 최대 candidate 하나를 반환합니다. `DecisionRequest.max_selections`는 upper bound로 남고 provider가 multi-select ranking을 시도하지 않습니다.

Multi-selection은 untrusted free-form output에서 추가 choice를 합성하지 말고 전용 bounded contract를 사용해야 합니다.

## Benchmark

```bash
python scripts/benchmark_decision_routing.py
```

API key가 있으면:

```bash
TYPESAFE_API_KEY="..." \
python scripts/benchmark_decision_routing.py --jev --min-confidence 0.65
```

Report는 routing accuracy, abstention, latency, token usage, provider error, optional cost estimate를 기록합니다. [Decision routing benchmark](../guides/decision-benchmark.md)를 참고하십시오.

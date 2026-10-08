# Ollama

SchemaRouter는 로컬에서 실행되는 Ollama model을 **bounded decision backend**로 사용할 수 있습니다. 그렇다고 SchemaRouter가 Ollama agent system이 되는 것은 아닙니다. Ollama는 tool loop를 소유하거나 임의의 execution plan을 구성하거나 등록된 tool을 실행하지 않습니다. SchemaRouter가 이미 승인한 유한한 option ID 중 하나를 선택할 뿐입니다.

이 integration은 Ollama structured-output `format`과 기존 `httpx` dependency를 사용하므로 Ollama Python SDK가 필요하지 않습니다.

## 사전 조건

Ollama는 별도로 실행하고 사용할 model이 해당 server에 이미 준비되어 있는지 확인합니다. SchemaRouter는 model을 자동으로 pull하지 않습니다.

```bash
pip install schemarouter
```

## 로컬 backend 설정

```python
from schemarouter import DecisionPolicy, SchemaPlanner
from schemarouter.integrations import OllamaDecisionBackend

backend = OllamaDecisionBackend("your-installed-model")

planner = SchemaPlanner(
    registry,
    decision_backend=backend,
    decision_policy=DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
        fallback="deterministic",
    ),
)
```

기본 API base URL은 `http://127.0.0.1:11434`입니다. Trusted application code는 다른 absolute HTTP(S) base URL을 명시적으로 지정할 수 있습니다.

## Bounded structured output

For each request, SchemaRouter sends Ollama a JSON Schema whose `option_id` is constrained to an
enum of the finite locally authorized option IDs. The model receives the query, `max_selections`,
option IDs/labels/descriptions, and optional bounded context. `DecisionOption.metadata` is never
forwarded.

After the server responds, SchemaRouter validates the result again. Unknown or duplicate IDs,
selection-count overflow, invalid scores, malformed JSON, and inconsistent abstention fail closed
before the result can affect planning.

Structured generation is a reliability aid, not the authority boundary. Local SchemaRouter
validation remains authoritative even if a server or model ignores the supplied schema.

## Sync 및 async

```python
backend = OllamaDecisionBackend("your-installed-model")

async_backend = OllamaDecisionBackend(
    "your-installed-model",
    async_mode=True,
)
```

Both paths use non-streaming `/api/chat` requests. Temperature defaults to zero. Trusted local
code can pass additional generation settings through `options={...}`.

## Context privacy

Request context는 기본적으로 포함됩니다. Context가 불필요하거나 민감하다면 비활성화합니다.

```python
backend = OllamaDecisionBackend(
    "your-installed-model",
    include_context=False,
)
```

## 로컬 model benchmark

```bash
python scripts/benchmark_decision_routing.py --corpus benchmarks/decision-routing-v1.json --ollama-model your-installed-model --json-out artifacts/ollama-decision-benchmark.json
```

Use `--ollama-base-url` when a trusted Ollama endpoint is not on the default loopback address.
Ollama token counters are retained in benchmark metadata when present.

Reported selection scores are model self-assessments. SchemaRouter does not treat them as
calibrated probabilities.

## 범위

This backend provides a practical local/open-model path behind the generic `DecisionBackend`
contract. It does not claim equivalence to Jev/System One or to research routers such as
TRINITY/TinyRouter. Those systems have different training objectives and need separate measured
evidence before quality comparisons are made.

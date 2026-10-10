# Ollama

SchemaRouter는 로컬 Ollama model을 **bounded decision backend**로 사용할 수 있습니다. SchemaRouter가 Ollama agent system이 되는 것은 아닙니다. Ollama는 tool loop나 arbitrary execution plan을 소유하지 않고 registered tool을 실행하지 않으며 SchemaRouter가 이미 authorize한 finite option ID 중에서만 선택합니다.

Integration은 Ollama structured-output `format`과 기존 `httpx` dependency를 사용하므로 Ollama Python SDK가 필요하지 않습니다.

## 사전 준비

Ollama를 별도로 실행하고 model이 server에 이미 준비되어 있어야 합니다. SchemaRouter는 model을 자동 pull하지 않습니다.

```bash
pip install schemarouter
```

## Local backend 설정

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

기본 API base URL은 `http://127.0.0.1:11434`입니다. Trusted application code는 다른 absolute HTTP(S) base URL을 명시할 수 있습니다.

## Bounded structured output

각 request에서 SchemaRouter는 `option_id`를 finite locally authorized option ID enum으로 제한한 JSON Schema를 Ollama에 전송합니다. Model은 query, `max_selections`, option ID/label/description, optional bounded context를 받으며 `DecisionOption.metadata`는 전달하지 않습니다.

Server response 뒤에도 SchemaRouter가 다시 검증합니다. Unknown/duplicate ID, selection-count overflow, invalid score, malformed JSON, inconsistent abstention은 planning에 영향을 주기 전에 fail closed합니다.

Structured generation은 reliability aid이지 authority boundary가 아닙니다. Server/model이 supplied schema를 무시해도 local SchemaRouter validation이 authoritative합니다.

## Sync와 async

```python
backend = OllamaDecisionBackend("your-installed-model")

async_backend = OllamaDecisionBackend(
    "your-installed-model",
    async_mode=True,
)
```

두 path 모두 non-streaming `/api/chat` request를 사용합니다. Temperature 기본값은 0입니다. Trusted local code는 `options={...}`로 추가 generation setting을 전달할 수 있습니다.

## Context privacy

Request context는 기본 포함됩니다. 불필요하거나 민감하면 비활성화합니다.

```python
backend = OllamaDecisionBackend(
    "your-installed-model",
    include_context=False,
)
```

## Local model benchmark

```bash
python scripts/benchmark_decision_routing.py --corpus benchmarks/decision-routing-v1.json --ollama-model your-installed-model --json-out artifacts/ollama-decision-benchmark.json
```

Trusted Ollama endpoint가 기본 loopback이 아니면 `--ollama-base-url`을 사용합니다. Ollama token counter가 있으면 benchmark metadata에 유지됩니다.

Reported selection score는 model self-assessment이며 SchemaRouter는 calibrated probability로 취급하지 않습니다.

## 범위

이 backend는 generic `DecisionBackend` contract 뒤에서 practical local/open-model path를 제공합니다. Jev/System One 또는 TRINITY/TinyRouter 같은 research router와 동등하다고 주장하지 않습니다. Training objective가 다르므로 quality 비교 전 별도의 measured evidence가 필요합니다.

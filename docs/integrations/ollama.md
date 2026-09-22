# Ollama

SchemaRouter can use a locally running Ollama model as a bounded decision backend. The integration
uses Ollama structured-output `format` and the existing `httpx` dependency, so no Ollama Python
SDK is required.

## Prerequisites

Run Ollama separately and make sure the model is already available to that server.
SchemaRouter does not pull models automatically.

```bash
pip install schemarouter
```

## Configure a local backend

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

The default API base URL is `http://127.0.0.1:11434`. Trusted application code may explicitly
supply another absolute HTTP(S) base URL.

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

## Sync and async

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

Request context is included by default. Disable it when the context is unnecessary or sensitive:

```python
backend = OllamaDecisionBackend(
    "your-installed-model",
    include_context=False,
)
```

## Benchmark a local model

```bash
python scripts/benchmark_decision_routing.py --corpus benchmarks/decision-routing-v1.json --ollama-model your-installed-model --json-out artifacts/ollama-decision-benchmark.json
```

Use `--ollama-base-url` when a trusted Ollama endpoint is not on the default loopback address.
Ollama token counters are retained in benchmark metadata when present.

Reported selection scores are model self-assessments. SchemaRouter does not treat them as
calibrated probabilities.

## Scope

This backend provides a practical local/open-model path behind the generic `DecisionBackend`
contract. It does not claim equivalence to Jev/System One or to research routers such as
TRINITY/TinyRouter. Those systems have different training objectives and need separate measured
evidence before quality comparisons are made.

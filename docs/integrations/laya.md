# Laya

SchemaRouter can use [Laya](https://github.com/NandhaKishorM/laya) as an optional local
`DecisionBackend`.

Laya is a non-autoregressive decision model rather than a general text-generation model. The
SchemaRouter adapter uses only Laya's finite `choice` primitive: the backend may select one of the
opaque option IDs that SchemaRouter already authorized, but it cannot invent a tool, endpoint,
field, parameter, credential, or execution permission.

## Install

Published packages:

```bash
pip install "schemarouter[laya]"
```

Development checkout:

```bash
pip install -e ".[laya]"
```

The extra installs the Laya runtime and its local model dependencies. Model weights are downloaded
by Laya/Hugging Face only when a checkpoint is first loaded unless they are already cached.

## Automatic local routing

By default, SchemaRouter lets Laya choose its English or multilingual checkpoint from the request
state:

```python
from schemarouter.integrations import LayaDecisionBackend

backend = LayaDecisionBackend(
    min_confidence=0.65,
)
```

The adapter passes:

- the user query;
- optional bounded decision context;
- finite option IDs;
- option labels and descriptions.

`DecisionOption.metadata` is never forwarded.

Laya routing metadata such as the selected checkpoint and routing reason is returned only as
non-authoritative `DecisionResult.metadata`.

## Pin a checkpoint

Use `model=` when the application has already chosen the checkpoint:

```python
backend = LayaDecisionBackend(
    model="multilingual",
    device="mps",
    min_confidence=0.65,
)
```

Common Laya checkpoint names include `english`, `multilingual`, and
`typed-decisions`. SchemaRouter intentionally does not select the benchmark-specific
`typed-decisions` checkpoint automatically.

## Preload for a long-running process

Laya can lazily load checkpoints, but switching between uncached checkpoints can dominate latency.
A server that has enough memory can preload checkpoints:

```python
backend = LayaDecisionBackend(
    preload=True,
    max_loaded=2,
)
```

Choose `max_loaded` according to available CPU/GPU/MPS memory. Preloading is trusted local
configuration and is never controlled by the model or request.

## Async planning

Laya inference is synchronous. With `async_mode=True`, SchemaRouter moves the local inference call
to a worker thread so an async planner does not execute the blocking call directly on the event
loop:

```python
backend = LayaDecisionBackend(
    async_mode=True,
)
```

This does not make a single model forward pass intrinsically asynchronous; it only preserves the
async SchemaRouter contract.

## Confidence and abstention

Set `min_confidence` to make a valid low-confidence Laya choice abstain:

```python
backend = LayaDecisionBackend(
    min_confidence=0.70,
)
```

SchemaRouter checks the returned option ID **before** confidence-based abstention. An unknown option
therefore fails closed even when Laya reports low confidence.

Confidence is provider/model evidence, not execution authority. It should be calibrated on the
actual workload before it is used as an operational threshold.

## Trust boundary

The adapter preserves the same bounded-decision invariants as the Jev and Ollama integrations:

- only locally authorized finite option IDs are exposed;
- unknown IDs fail closed;
- `DecisionOption.metadata` is not forwarded;
- Hugging Face tokens stay in trusted local router configuration;
- provider metadata cannot grant execution authority;
- SchemaRouter revalidates the final decision locally;
- deterministic fallback policy remains owned by SchemaRouter.

## Current scope and limitations

The SchemaRouter adapter deliberately maps only Laya's `choice` primitive to the generic
`DecisionBackend` contract. Laya also exposes score/probability-oriented primitives, but adding
those to SchemaRouter would require a separate typed contract rather than overloading finite
selection semantics.

Laya quality is checkpoint-, language-, option-count-, and domain-dependent. In particular,
high-cardinality choice sets can require a larger option/head budget or a shortlist strategy.
Do not treat published third-party or upstream benchmark numbers as a guarantee for a SchemaRouter
workload.

Use the shared SchemaRouter corpus to measure the exact checkpoint and hardware before choosing a
default backend or confidence threshold.

## Benchmark

Run Laya on the same corpus used by deterministic, embedding, Jev, and Ollama paths:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --laya
```

Pin a checkpoint or device when needed:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --laya \
  --laya-model multilingual \
  --laya-device mps \
  --laya-min-confidence 0.65
```

For a long-running benchmark on mixed languages, `--laya-preload` avoids repeated cold checkpoint
loads. Record the exact Laya version, checkpoint, hardware/device, preload policy, and confidence
threshold when publishing results.

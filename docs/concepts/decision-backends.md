# Decision backends

SchemaRouter can optionally use a bounded decision model to refine choices that were already
derived from the local schema catalog. This feature is **off by default**.

Decision backends are not plan generators. They receive a finite set of locally authorized option
IDs and may select only from that set. SchemaRouter still constructs the typed execution plan and
retains policy, schema-validation, fingerprint, and execution authority.

## Opt in

```python
from schemarouter import CallableDecisionBackend, DecisionPolicy, SchemaPlanner

backend = CallableDecisionBackend(my_decision_model)
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

The master `enabled` switch must be true. Individual surfaces are separately configurable:

- `tool_selection`
- `endpoint_selection`
- `field_selection`
- `evidence_sufficiency`

In the initial v0.3 contract, bounded candidate selection is active when tool or endpoint selection
is enabled. Field and evidence switches are reserved controls and fail closed until their dedicated
bounded contracts are implemented.

## Fallbacks

`fallback="deterministic"` is the default. Invalid output, provider failure, unknown option IDs,
or abstention falls back to SchemaRouter's deterministic ranking and adds a warning to the plan.

Use `fallback="error"` when a decision failure must stop planning.

## Contract invariants

A decision provider:

- receives finite opaque option IDs;
- cannot create a `ToolCall`;
- cannot add tools, endpoints, fields, parameters, credentials, or execution permissions;
- cannot make an unknown option executable;
- must return bounded, finite scores;
- may abstain;
- supplies metadata that is always non-authoritative.

The planner, execution policy, schema fingerprint checks, argument validation, and output validation
remain unchanged.

## Local embedding similarity

`EmbeddingDecisionBackend` provides a zero-provider-dependency path for local or hosted embedding
models. The embedder receives the user query followed by one text representation per authorized
option; SchemaRouter computes cosine similarity locally and maps ranked vector positions back to the
original opaque option IDs.

```python
from schemarouter import EmbeddingDecisionBackend

backend = EmbeddingDecisionBackend(
    embed_batch,
    min_similarity=0.35,
    min_margin=0.05,
)
```

The backend can use any sync or async callable that returns one finite, same-dimensional vector per
input text. This makes it compatible with application-owned SentenceTransformers, FastEmbed,
semantic-router encoders, remote embedding APIs, or custom domain encoders without adding any of
those packages to SchemaRouter's core dependency graph.

The default option-text formatter does not pass `DecisionOption.metadata` to the embedder. A
custom `option_text` callback is trusted application code and may intentionally choose a different
data boundary. A zero-norm vector, NaN/Infinity, dimension mismatch, wrong batch size, or malformed
vector fails closed. `min_similarity` can
abstain on weak matches; `min_margin` can abstain when the selection boundary is ambiguous.

For asymmetric retrieval encoders, wrap the callable so the first input (the query) uses the
encoder's query path and option texts use its passage/document path.

## Jev / TypeSafe System One

SchemaRouter includes an optional `JevDecisionBackend` on current unreleased `main`:

```bash
pip install -e ".[jev]"
```

The normal packaged extra name will be `schemarouter[jev]` in the next release.

```python
from schemarouter.integrations import JevDecisionBackend

backend = JevDecisionBackend(
    min_confidence=0.65,
)
```

The provider uses a TypeSafe `choice` primitive over the offered option IDs. Unknown IDs fail
closed before confidence-based abstention is evaluated. Low-confidence valid choices may abstain and
fall back to deterministic routing.

The adapter does not forward `DecisionOption.metadata`, and API credentials are client
configuration rather than model state.

See [Jev / TypeSafe System One](../integrations/jev.md) for sync/async usage and security details.

## Local Ollama models

SchemaRouter also includes an `OllamaDecisionBackend` that uses Ollama structured outputs over the
native HTTP API. No Ollama Python SDK is required.

```python
from schemarouter.integrations import OllamaDecisionBackend

backend = OllamaDecisionBackend(
    "your-installed-model",
    async_mode=True,
)
```

The backend constrains `option_id` with a JSON Schema enum, includes that schema in the prompt for
grounding, and then revalidates the returned `DecisionResult` locally. `DecisionOption.metadata`
is never forwarded. Model-reported scores are treated as self-assessments rather than calibrated
probabilities.

See [Ollama](../integrations/ollama.md) for configuration and benchmark usage.

## Experimental providers

Other System-One-style or decision-model providers should implement `DecisionBackend` rather than
being imported into SchemaRouter core. Provider integrations remain optional and explicitly enabled.
Embedding libraries should likewise remain application-owned unless a stable provider-specific
contract justifies a dedicated adapter.

This separation lets applications change, disable, or compare a decision provider without changing
registered tools, execution policy, or the deterministic planner.

## Benchmarking

Use `scripts/benchmark_decision_routing.py` to compare the deterministic baseline,
`ModelQueryAnalyzer`, local embedding backends, Jev, and explicitly selected local Ollama models
on the same cases.

See [Decision routing benchmark](../guides/decision-benchmark.md).

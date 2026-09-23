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

Bounded candidate selection is active when tool or endpoint selection is enabled. `field_selection`
lets the backend choose only from declared non-identifier output fields while identifier fields are
preserved locally. `evidence_sufficiency` is also implemented as a conservative binary gate:
SchemaRouter first proves the requested provenance/license/unit/source-type requirements from local
schema metadata, then the backend may only keep that locally sufficient call or veto it as
insufficient. A provider can never upgrade missing local evidence.

## Bounded field selection

Enable field selection explicitly:

```python
policy = DecisionPolicy(
    enabled=True,
    field_selection=True,
    fallback="deterministic",
)
```

For each already-selected endpoint, SchemaRouter offers only declared non-identifier output fields
as finite `field:N` options. Identifier fields never enter the provider's choice set and are
always retained locally.

The decision request's `max_selections` never exceeds the deterministic projection's answer-field
width. When deterministic projection is in recall-first mode and keeps all fields, the backend may
select any bounded subset of those declared fields.

Provider failure, malformed/unknown field IDs, duplicate IDs, overflow, or abstention follows the
same fallback policy as candidate routing. Evidence requirements are recomputed from the final
locally validated field set.

## Bounded evidence sufficiency

Enable the surface explicitly and request evidence on the plan request:

```python
policy = DecisionPolicy(
    enabled=True,
    evidence_sufficiency=True,
    fallback="deterministic",
)

request = PlanRequest(
    query="band gap",
    evidence=EvidenceRequirements(
        provenance=True,
        license=True,
        units=True,
        source_type="calculated",
    ),
)
```

SchemaRouter performs a deterministic local precheck before contacting the backend. Tool-level
`source_type` / `license` metadata and selected answer-field `source_type`, `license`, and
`unit` metadata are the only evidence that can satisfy this precheck.

If any requested requirement is locally missing, the call is rejected without asking the provider.
If local evidence is sufficient, the provider receives exactly two finite options:
`evidence:sufficient` and `evidence:insufficient`. Selecting `insufficient` acts only as a
conservative veto. Selecting `sufficient` cannot add provenance, licenses, units, fields, tools, or
execution authority.

Provider failure or abstention can fall back to the local evidence assessment when
`fallback="deterministic"`; `fallback="error"` fails planning instead.

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
- cannot upgrade locally missing evidence;
- may only veto a call that already passed the local evidence precheck;
- must return bounded, finite scores;
- may abstain;
- supplies metadata that is always non-authoritative.

The planner, execution policy, schema fingerprint checks, argument validation, and output validation
remain unchanged.

## Choosing a decision backend

The optional backends serve different deployment goals:

| Backend | Best fit | Trade-off |
| --- | --- | --- |
| Deterministic / embedding | Zero provider dependency and predictable local behavior | Lower semantic flexibility on ambiguous language |
| Laya | Fast local finite decisions, including Apple Silicon through PyTorch MPS/Metal | Single-selection adapter today; quality is checkpoint/domain dependent |
| Ollama | Reuse a general local LLM that is already deployed for other application tasks | Autoregressive generation is heavier and slower than a purpose-built decision model |
| Jev / TypeSafe | Hosted purpose-built bounded decisions without local model operations | External service/network dependency |

Ollama is therefore **not required** when Laya or a deterministic backend meets the workload. It
remains useful as a broad compatibility path for teams that already operate local instruction
models, for side-by-side benchmark evidence, and as a fallback when a task benefits from a general
language model rather than a specialized System-One decision model.

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

## Local Laya decision models

The 0.6 development line includes an optional `LayaDecisionBackend` for local non-autoregressive
bounded decisions:

```bash
pip install -e ".[laya]"
```

The packaged extra will be `schemarouter[laya]` after a release containing this integration.

```python
from schemarouter.integrations import LayaDecisionBackend

backend = LayaDecisionBackend(
    min_confidence=0.65,
)
```

By default, Laya may route between its English and multilingual checkpoints from the bounded request
state. Applications may pin a checkpoint with `model=` and may preload checkpoints for a
long-running process.

The adapter maps Laya's finite `choice` primitive to SchemaRouter's existing
`DecisionBackend` contract. Unknown option IDs fail closed before confidence gating,
`DecisionOption.metadata` is not forwarded, and Hugging Face credentials remain trusted local
configuration.

See [Laya](../integrations/laya.md) for checkpoint, device, preload, confidence, and benchmark
guidance.

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
`ModelQueryAnalyzer`, local embedding backends, Jev, Laya, and explicitly selected local Ollama models
on the same cases.

See [Decision routing benchmark](../guides/decision-benchmark.md).

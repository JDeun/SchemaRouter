# Decision routing benchmark

SchemaRouter includes `scripts/benchmark_decision_routing.py` to compare deterministic routing,
model-assisted query analysis, and bounded Jev decisions on the same reference cases.

The benchmark is a measurement harness, not a claim that one provider is universally better.

## Deterministic baseline

```bash
python scripts/benchmark_decision_routing.py
```

This runs the default `KeywordAnalyzer` baseline.

## ModelQueryAnalyzer

Pass a provider callable using `module:function` syntax:

```bash
python scripts/benchmark_decision_routing.py \
  --model-callable my_bench_provider:analyze
```

The callable must satisfy the same structured contract used by `ModelQueryAnalyzer`: it receives
one dictionary payload and returns a dictionary, or an awaitable dictionary, matching the model
intent schema.

This keeps the benchmark provider-neutral. OpenAI, Anthropic, Gemini, local models, or test doubles
can be compared without adding those SDKs to SchemaRouter core.

## Jev

Install the optional integration and set the TypeSafe API key:

```bash
pip install -e ".[jev]"
export TYPESAFE_API_KEY="..."
python scripts/benchmark_decision_routing.py --jev
```

Useful options:

```bash
python scripts/benchmark_decision_routing.py \
  --jev \
  --jev-model jev-latest \
  --min-confidence 0.65 \
  --input-cost-per-million 0 \
  --output-cost-per-million 0
```

Use actual provider pricing when supplying cost rates. SchemaRouter does not hard-code a price that
can become stale.

## Metrics

Each row records:

- expected and predicted `tool.endpoint`;
- correctness;
- end-to-end planning latency;
- Jev abstention state when available;
- input/output token counts when the provider reports them;
- optional estimated cost;
- provider or planner errors.

The summary reports aggregate accuracy, error count, abstention count, mean successful latency,
tokens, and optional cost.

## Interpretation

Use repeated runs and a workload representative of the target application before making routing
decisions. The included reference cases are only a smoke-quality common comparison set.

A production benchmark should add:

- ambiguous and adversarial queries;
- large catalogs;
- near-duplicate endpoints;
- multilingual prompts;
- provider timeouts and rate limits;
- cost and latency distributions rather than only means.

# Decision routing benchmark

SchemaRouter includes a reproducible routing benchmark harness and a checked-in v1 corpus.

The benchmark is a measurement tool, not a claim that one provider is universally better.

## Smoke run

```bash
python scripts/benchmark_decision_routing.py
```

This keeps the original three-case deterministic smoke test for packaging and CI.

## Full checked-in corpus

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json
```

The v1 corpus contains 144 cases across:

- normal routing;
- near-duplicate tools/endpoints;
- Korean/English multilingual queries;
- long-tail phrasings;
- prompt-injection-style requests;
- out-of-domain requests where a bounded backend may abstain.

The corpus references only the stable benchmark registry embedded in the script and is validated in
tests so unknown expected routes cannot silently enter the dataset.

## Persist results

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --repeat 3 \
  --json-out artifacts/decision-benchmark.json \
  --csv-out artifacts/decision-benchmark.csv
```

Useful controls:

- `--max-cases N` for a bounded local sample;
- `--repeat N` for repeated latency measurements;
- JSON output for aggregate/report automation;
- CSV output for row-level analysis.

## ModelQueryAnalyzer

Pass a provider callable using `module:function` syntax:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --model-callable my_bench_provider:analyze
```

The callable receives the same structured request used by `ModelQueryAnalyzer` and may be sync or
async. This keeps the benchmark provider-neutral.

## Embedding backend

Pass a batch embedding callable using `module:function` syntax:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --embedding-callable my_embeddings:embed_batch \
  --min-similarity 0.35 \
  --min-margin 0.05
```

The callable receives a list containing the query followed by one text representation per offered
option, and returns one vector per input. It may be synchronous or asynchronous. SchemaRouter
performs cosine ranking locally, so the benchmark can compare FastEmbed, SentenceTransformers,
semantic-router encoders, or an application-specific embedding service without changing the
benchmark contract.

The threshold values are workload/model specific. Do not reuse a threshold measured for a different
embedding model without recalibration.

## Jev

Install the optional integration and configure TypeSafe locally:

```bash
pip install -e ".[jev]"
export TYPESAFE_API_KEY="..."
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --jev
```

Optional controls include `--jev-model`, `--min-confidence`,
`--input-cost-per-million`, and `--output-cost-per-million`.

Provider pricing is never hard-coded because it can change independently of SchemaRouter.

## Laya

Install the optional local decision runtime:

```bash
pip install -e ".[laya]"
```

Run Laya against the same checked-in corpus:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --laya
```

By default, Laya uses its local router to choose an English or multilingual checkpoint from the
bounded request state. Optional controls include:

- `--laya-model english|multilingual|typed-decisions` to pin a checkpoint;
- `--laya-device cpu|cuda|mps` to pin the trusted local device;
- `--laya-preload` to preload checkpoints before measurement;
- `--laya-max-loaded N` to control resident checkpoint count;
- `--laya-min-confidence FLOAT` to measure confidence-gated abstention.

Published results should record the exact Laya package version, checkpoint/routing policy, hardware,
device, preload policy, confidence threshold, corpus revision, and repeated-run count. Do not compare
upstream/provider benchmark numbers directly unless the prompts, options, corpus, and measurement
conditions are equivalent.

## Ollama

Run an already-installed local Ollama model against the same corpus:

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --ollama-model your-installed-model
```

The default API endpoint is `http://127.0.0.1:11434`. Use `--ollama-base-url` for another
trusted endpoint and `--ollama-timeout` to adjust the per-request timeout.

The benchmark records Ollama prompt/evaluation token counters when the server reports them. A local
model result should also record the exact model tag, quantization/runtime configuration, hardware,
and Ollama version when publishing evidence; model tags alone are not enough to reproduce local
latency or quality.

Provider pricing is irrelevant for a purely local Ollama run unless the operator explicitly assigns
a local cost model.

## Metrics

Each row records:

- case ID and category;
- expected and predicted `tool.endpoint`;
- correctness;
- invalid-plan state;
- end-to-end planning latency;
- bounded-backend abstention and deterministic fallback state;
- input/output tokens when reported;
- optional cost estimate;
- provider/planner error.

The aggregate report includes:

- final-plan routing accuracy (an abstention case is correct only when the final plan has no route);
- invalid-plan rate;
- error count;
- abstention rate;
- expected-abstention recall for bounded backends, reported separately from final-plan accuracy;
- fallback count;
- mean, p50, and p95 latency;
- category-level accuracy;
- token totals and optional estimated cost.

## Offline versus live evidence

The corpus and deterministic smoke path are suitable for CI because they require no external
provider.

A live provider benchmark is intentionally separate. Network availability, model revisions,
credentials, rate limits, and provider-side changes are external variables. Publish live results
with the exact date, model identifier, configuration, corpus revision, and repeated-run count.

Do not infer provider superiority from the three-case smoke set or from a single live run.

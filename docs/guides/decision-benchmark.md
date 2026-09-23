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
  --csv-out artifacts/decision-benchmark.csv \
  --html-out artifacts/decision-benchmark.html
```

Useful controls:

- `--max-cases N` for a bounded local sample;
- `--repeat N` for repeated latency measurements;
- JSON output for aggregate/report automation;
- CSV output for row-level analysis;
- self-contained HTML output for a portable backend/latency/abstention summary.

The HTML file contains no remote assets or scripts and escapes report metadata before rendering.
It is intended for sharing one reproducible run summary.

For a dated set of benchmark JSON files, render a comparison view without rewriting the raw
measurements:

```bash
python scripts/render_benchmark_history.py \
  artifacts/run-2026-09-23.json \
  artifacts/run-2026-09-30.json \
  --output artifacts/decision-benchmark-history.html
```

The history renderer preserves each run's timestamp, SchemaRouter version, corpus, hardware,
backend, accuracy, abstention, latency, model, and device metadata. It does not normalize unlike
environments, so cross-run comparisons remain valid only when measurement conditions are
equivalent.

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
- `--laya-min-confidence FLOAT` to measure confidence-gated abstention;
- `--hardware-label TEXT` to attach the concrete machine/GPU description to the report;
- `--decision-recall-on-empty` to explicitly let an enabled bounded decision backend inspect the
  registered endpoint catalog when lexical candidate recall is empty.

Laya rows record the routed checkpoint plus `requested_device` and, when Laya exposes the loaded
agent device, `actual_device`. This matters because an unavailable CUDA/MPS target can fall back to
CPU and should not be counted as an accelerator result.

Empty-candidate recall is deliberately off by default. When enabled, SchemaRouter does not invent a
route: it exposes only endpoints already registered in the trusted local catalog. If the decision
backend errors or abstains after this expansion, planning fails closed with no arbitrary
deterministic route because there was no lexical candidate to fall back to.

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
trusted endpoint and `--ollama-timeout` to adjust the per-request timeout. Server-supported local
runtime options can be passed without hard-coding vendor/version-specific knobs:

```bash
python scripts/benchmark_decision_routing.py \
  --ollama-model your-installed-model \
  --ollama-options-json '{"your_runtime_option": 1}' \
  --hardware-label "RTX workstation"
```

SchemaRouter records the options object in the benchmark report. It does not infer the actual
Ollama CPU/GPU placement because that decision belongs to the Ollama server/runtime.

The benchmark records Ollama prompt/evaluation token counters when the server reports them. A local
model result should also record the exact model tag, quantization/runtime configuration, hardware,
and Ollama version when publishing evidence; model tags alone are not enough to reproduce local
latency or quality.

Provider pricing is irrelevant for a purely local Ollama run unless the operator explicitly assigns
a local cost model.

## Metrics

Each row records:

- case ID and category;
- provider/model identifier when reported;
- requested and actual local device when the backend can report them;
- expected and predicted `tool.endpoint`;
- correctness;
- invalid-plan state;
- end-to-end planning latency;
- whether the bounded decision backend was actually invoked;
- bounded-backend abstention and deterministic fallback state;
- input/output tokens when reported;
- optional cost estimate;
- provider/planner error.

The aggregate report includes:

- final-plan routing accuracy (an abstention case is correct only when the final plan has no route);
- invalid-plan rate;
- error count;
- bounded-backend invocation count/rate;
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
credentials, rate limits, provider-side changes, local accelerator availability, memory, and
runtime placement are external variables. Publish live results
with the exact date, model identifier, configuration, corpus revision, and repeated-run count.

Do not infer provider superiority from the three-case smoke set or from a single live run.

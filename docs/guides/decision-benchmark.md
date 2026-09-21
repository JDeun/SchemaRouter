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

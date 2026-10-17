# Actual native source-scoped E5 retrieval scaling to 500 — DEV only

**2026-10-17, issues #1477/#1339.** This is a fully opt-in,
locally CPU-runnable *retrieval* experiment, not a production benchmark,
agent task success, calibrated no-fit, or E2 independent confirmation.

## Scope and preregistered comparison

After PR #1484 froze real-E5 13-route CPU observations, the same model
`intfloat/multilingual-e5-small` at pinned revision
`fd1525a9fd15316a2d503bf26ab031a61d056e98` is applied to **identical**
published 2026-10-15 DEV query/case/gold bytes. The corpus is re-read
and compared to the exact originally tracked bytes each run.

The only changed variable is the number of *source-native registered
read-only routes* from `13` through `100,250,500`, with predeclared
synthetic English templated distractors from the **already existing**
`evaluate_multilingual_embedding_scale_dev.expand_catalog` generator.
A generated `dev_stress.<domain>.<operation>` record is mapped without
semantic reinterpretation to the one-dot native route
`dev_stress_<domain>.<operation>`. The original 13 native target IDs
are unchanged; generated catalogs are deterministic nested prefixes
and hashed. An authorized host-like `SchemaRouter` and explicit reader
principal are built separately for each size. All registered routes
must remain read-only.

The three rankers use the **same original query and principal-scoped
source snapshot**, under strict K=5:
- Native `retrieve_authorized` lexical.
- Source-scoped E5 backend via #1481 decision adapter.
- Nondefault predeclared `RRF(60)` hybrid via #1483.

Every sample checks exact authorized membership, no duplicate/forged
routes, no scope drift, and a bounded model input contract (explicit 256 KiB scale-run option;
the underlying fixed-K5 selector retains its 128 KiB default). Each
synthetic category contains 48 supported + 36 unsupported original
queries across English/Korean/Japanese/Spanish/German/mixed, **eight
supported/six unsupported per language**. Output aggregates per-language
Recall@1 and Recall@5, unsupported **nonempty shortlisted candidates**
(not erroneous provider execution or calibrated no-fit), and local
p50/p95 request selection latency. Model passage vectors use a
bounded cache; source-view capture is outside selection timing, so
timing is **not end-to-end host or agent latency**.

The report from a directly supplied mock backend is unconditionally
`UNATTESTED_BACKEND_RETRIEVAL_DEV_ONLY` and
`real_model_routing_measured=false`. Only the CLI branch that
actually calls `real_cpu_backend()` and executes the full **84 cases
at each size** may mark it
`REAL_E5_CPU_RETRIEVAL_DEV_ONLY`. Partial-smoke results cannot claim
the full score, and source/report never publishes raw task prompts,
gold operation IDs, agent completion or private arguments.

## Evidence boundary and next gate

**This is not 500 real native external tools.** The English-templated
generated distractors are artificial; they do not cover authenticated
permissions, realistic OpenAPI/MCP server downtime, metadata drift,
unsafe operations or actual provider integration. Fixed K5 alone
cannot establish unsupported/no-fit and a model-selected route is
not executable authority. No agent is run.

Do not tune E5, RRF weights, tokenization or no-match thresholds on
this now-exposed synthetic DEV and call it independent multilingual
confirmation. A strong Recall@5 at 500 routes would be useful evidence
of candidate scalability **on this particular synthetic corpus only**.
A first 500-route smoke failed the original **128 KiB model-input cap**.
Rather than silently shrink K/catalog, this PR raises the opt-in ceiling
only to **256 KiB**, forwards the explicit limit through the E5 and hybrid
research selectors, and leaves their default 128 KiB untouched. If the
source-surface metadata still exceeds the explicit 256 KiB cap or CPU
resources, record the failure as a **capacity defect** rather
than shrinking K/catalog or forging a success score.

Code:
```bash
python -m scripts.evaluate_authorized_e5_scale_500_cpu_dev --mode validate
python -m scripts.evaluate_authorized_e5_scale_500_cpu_dev --mode real-e5-cpu \
  --out artifacts/authorized-e5-scale-500-dev/report.json
```

#1346 independent publisher-authored EN/KO/JA/OOD case freeze,
same-agent native host invocation and paired final task completion
remain required for E2. #1356 v0.18.0 hard hold remains unchanged;
the frozen negative #432 canonical science is untouched.


## 2026-10-17: instrumented CPU stage bottleneck, no optimizer claims

After a successful initial 13/100/250/500 real-E5 source-catalog study,
the 500-route observed E5 selection p95 was **673.5 ms** and fixed
RRF(60) p95 **1040.3 ms**. The original metric starts *after* the
scoped tool-surface construction and includes another full authorized
candidate retrieval, model input construction, backend CPU inference and
post-inference validation. It is not actual end-to-end request latency.

The follow-up instrumented runner records **for each fixed source and
query**:

- `source_capture_latency_ms`: native principal-scoped source snapshot
  and tool schema projection performed once before comparing the arms.
- `backend_decision_latency_ms`: the actual `DecisionBackend.decide`
  call in the semantic and hybrid arms; model embedding and cosine sort
  happen here. Lexical's value is zero.
- `nonbackend_selection_latency_ms`: selection minus decision time,
  conservatively clamped to zero only for nanosecond timer ordering.
  This includes repeated native authorized retrieval, result validation
  and all additional pre/post backend operations.
- `source_capture_plus_selection_latency_ms`: the sum of the shared
  snapshot preparation and one arm's selection; **not independent
  end-to-end agent latency**.
  
Each of the four stages is summarized as p50, p95, p99. The wrapper
tracks only elapsed nanoseconds and decision call counts; it never
caches user query embeddings, changes the backend result, exposes
principal claims, captures raw queries/gold, modifies source
fingerprints, or grants invoker authority. A real E5 selector and
hybrid each must call the decision backend **exactly once** per query;
unexpected call counts fail the evaluation. A mock backend remains
marked *unattested*.

The original per-arm retrieval rankings, K=5 limit, 84-case
denominators, authorized snapshots and no-fit nonqualification are
unchanged. **Percentiles of individually measured stages cannot be
arithmetically added** to infer total p95. Use the separately measured
`source_capture_plus_selection_latency_ms` to understand shared-source
overhead. Results distinguish bottlenecks but cannot in themselves
demonstrate optimization or commercial quality; a subsequent
independent A/B code change must reduce a measured stage without
recall degradation on held-out cases.

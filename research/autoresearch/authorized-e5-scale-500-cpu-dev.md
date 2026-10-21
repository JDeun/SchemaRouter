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

## 2026-10-19: Same-query multilingual *rescue vs regression* attribution

Performance is the primary open product question (#1339/#1477). The existing real model A/B already tests native lexical K5, pinned actual multilingual-E5-small K5, and the fixed RRF60 hybrid on the **same** original 84 previously disclosed DEV queries and nested 13/100/250/500 source-native registry sizes. An overall recall improvement is insufficient to decide whether the semantic ranker is safe to promote: it can **rescue** a different subset of supported cases while **regressing** previously successful cases. Simply comparing two average recall percentages conceals both populations.

The expanded report now computes, for each E5/hybrid-versus-lexical condition and each language plus "all", four matched-case K1/K5 counts: `rescued` (lexical miss, candidate hit), `regressed` (lexical hit, candidate miss), `both_hit`, `neither_hit`. The identity invariant is `candidate_hits = lexical_hits + rescued - regressed`, with all 48 supported and 36 unsupported cases accounted for exactly once at each catalog size. A separate unsupported axis counts both systems returning a nonempty shortlist, newly nonempty and newly empty. **A nonempty unsupported shortlist is not evidence of a wrong tool invocation, and empty is not yet calibrated no-fit.** Requiring all 84 rows, exact 8 supported + 6 negative per language, and no per-case query/gold identifiers in the emitted aggregate prevents accidental selective success reporting.

The dedicated Actions run uses the **real pinned CPU E5 encoder**, not the fake used by unit tests, and now includes the explicit 500-route per-language matched rescue/regression matrix in its summary and JSON report. The fixture-only tests validate arithmetic, language/task alignment, malformed/missing rows, and that partial smoke never emits full scores. No scorer, model, rank weights, top-K choice, baseline arm, source corpus or frozen #432 are changed in this PR.

**Decision use:** a real-language regression or persistent unsupported nonempty outcome is a *blocker to automatic promotion*, not a prompt to tune on these exposed cases. Follow with truly fresh query-disjoint publisher-authored permission/field/operation gold, actual downstream same-agent fixed-K task completion, and CPU/token p95 cost in #1477/#1346. No "commercial-quality" or E2 claim is authorized by this DEV matrix.

## 2026-10-19: Verified latency stage *attribution* before optimization

The prior independent same-run Linux CPU retrieval DEV had substantial model-external selection overhead (500 native synthetic routes, actual E5 CPU model). Comparing the earlier and later p95 values from separate GitHub runner executions is **not** a controlled optimization A/B. Moreover, the published "nonbackend" residual includes several unrelated operations and was not actionable.

This draft adds opt-in CPU-only timers to the **existing research-only** fixed-K selector and source-scoped comparator; it does not change candidate ranking, data scope, model inputs, the trust witness, fixed K, the 84 original DEV requests, the model or its cached vectors. The new `e5_substage_profile_ms` aggregates exactly 84 samples at each registered 13/100/250/500 route scale, with independent p50/p95/p99 for:

- `selector_constructor_ms`: original source witness and native-fingerprint capture before candidate selection (excluded from earlier selection latency).
- `bridge_prevalidation_ms`: source/policy view integrity and matching pinned native fingerprints before model exposure.
- `source_validation_ms`: registered bound + current authority/view/route checks inside the existing semantic bridge.
- `request_materialization_ms`: authorized DecisionOption/DecisionRequest construction and exact UTF-8 serialized model input byte cap.
- `choose_sync_ms`: host-owned `choose_sync`, including real model decision **and** validation of the model reply against independently offered option IDs.
- `choose_sync_nonbackend_ms`: measured `choose_sync_ms` minus measured DecisionBackend.decide time; neither field is a model-inference-only metric.
- `post_decision_validation_ms`: original final authority checks and validated native route/fingerprint packaging.
- `bridge_postvalidation_ms`: rechecking the original witness/fingerprints and output contract after the semantic comparator.

Only floating-point aggregate timings leave the evaluation; original source candidate text, personal context, model replies, per-query predictions and held-out gold do not. Timing instrumentation is *not* an acceleration, product SLA or an independent agent E2 result. Instrumented timings perturb the run; any later optimization must use an actual paired A/B on the same pinned model/corpus/runner with original strict correctness and authorization checks, and report the new operation-specific latency distribution **separately** from model inference and end-to-end agent behavior.

## 2026-10-19: Safe per-snapshot fingerprint computation optimization

The above **actual** E5 CPU profile ([run 39272572184](https://github.com/JDeun/SchemaRouter/actions/runs/39272572184), exact code head before any optimization) found p95 selector-construction 99.50ms, bridge prevalidation 98.96ms and bridge postvalidation 107.68ms at 500 original-native *synthetic DEV* routes; decision+host-validation `choose_sync` p95 90.53ms. One-time DecisionRequest materialization p95 was only 1.07ms. These are separate distributions, not additive totals.

Root-cause code audit: `_visible_fingerprints` rescans a **fresh detached copy** of every ToolSpec on every pre/post boundary (required). However its original inner endpoint loop computed the **full ToolSpec fingerprint repeatedly for each visible endpoint** even though that fingerprint already covers the complete parent ToolSpec endpoint contract. `InMemoryRegistry.tools()` returns independently detached snapshots (see `src/schemarouter/registry.py`), so reading a parent tool fingerprint once **within the same fresh scan** does not persist a stale fingerprint across authorization transitions. A tuple membership lookup was also repeated for every route.

The optimization replaces only that inner loop with a local frozenset for route membership and exactly **one ToolSpec.fingerprint per detached visible tool**, still computing every selected EndpointSpec fingerprint and still doing a fresh scan before AND after backend exposure. No cross-call cache, authorization/visibility predicate change, model-rank change, fallback, or cache invalidation policy change. The E0 regression suite checks exact per-route original/optimized fingerprint dictionaries at 13, 100, 250, 500; instrumented tool fingerprints must be invoked once per visible detached tool. Existing forged/tampered source guards and both pre/post authorization assertions remain mandatory.

A separate new no-model **paired** benchmark (`scripts/research_authorized_fingerprint_scan_ab_cpu_dev.py`) runs 24 alternating-order pairs per scope using original vs optimized functions against the same captured principal-approved native route view. Each pair must have **identical exact route+ToolSpec+EndpointSpec fingerprints** and unchanged live authority witness. Publish p50/p95 and faster-pair counts for **this scan operation alone**, never infer full retrieval, model or agent speedup from those values. The actual pinned E5 DEV run and protected CI remain separate gates. The 0.14 #432 independent negative, publisher-authored E2 #1346, #1477 agent utility and v0.18 #1356 HARD HOLD are unchanged.

## 2026-10-19: Whole-selector causal A/B, same pinned E5 CPU

The earlier 24x4 paired microbenchmark demonstrated source-fingerprint *scan-only* speedup with unchanged route/tool/endpoint fingerprints. A separate prior-versus-current GitHub-run model p95 is confounded by runner conditions. A new dedicated research runner (`scripts/research_authorized_fingerprint_selector_paired_e5_cpu_dev.py`) now compares **the complete fixed-K5 selector, including its constructor**, using one shared current principal-scoped source capture and the same pinned actual CPU multilingual E5 model. Each of the original 84 disclosed DEV cases has two calls with alternating order.

The control calls the **original per-endpoint native fingerprint verification** and the treatment calls the optimized once-per-detached-tool verifier; only a synchronous single-worker research-owned scoped patch swaps the private helper for the control. Both arms retain all three full before/after snapshot checks; neither modifies public/default production routing code or introduces a different trust/permission mechanism. Exact source-approved shortlist **order**, status and serialized DecisionRequest byte count must all match, or the entire run fails. No per-case query, candidate, provider field, principal attributes or gold is included in the emitted JSON.

The measured response covers source-validated **constructor plus one candidate selection**, excluding shared source capture; it is not entire agent/task latency. The A/B measures p50/p95/p99 and paired median deltas in one runner. This diagnostic remains exposed synthetic DEV, not held-out E2, calibrated no-fit, source-provider truth, or an SLA. No evidence claim is made until exact-head native-source no-model, actual CPU E5, CodeQL and protected CI all succeed.

## 2026-10-20: Whole-selector verified, measure hidden request-local capture

Completed [same-run Linux actual E5 whole-selector A/B](https://github.com/JDeun/SchemaRouter/actions/runs/39277275789) (all seven exact PR-head checks successful): exact original 84 public DEV tasks, 500 generated native routes, same pinned multilingual-E5-small and actual source/principal. Selector *including constructor* old-vs-new p50 **312.39→147.58ms**, p95 **488.28→314.09ms**, p99 **1784.60→355.57ms**, paired median delta **-164.04ms**; 79/84 optimized faster. Every selected route order, backend status and serialized model input byte count matched exactly. These are **request-local selector-only** CPU timings, excluding source capture, external host invoker, native providers and final response.

The next observation must not silently call the preceding selector-only result an "end-to-end" p95. The same paired runner now times **one original authorized source capture per request** and separately reports that 84-case capture p50/p95/p99. For **each** candidate arm it constructs a *matched per-case* `source_capture_ms + selector_including_constructor_ms` observation and **only then computes its aggregate p50/p95/p99**, which correctly preserves within-request covariance. It does NOT add separate stage percentiles. Each pair shares the same verified capture (both original and optimized validators see precisely the same source/principal), so the before-after paired selection delta is unchanged. The combined diagnostic excludes agent text generation, provider execution, external network and the reported single shared source capture is **not** done again for each arm. Instrumentation does not remove authorization checks or reweight route candidates.

**Promotion gate remains blocked:** 500 native routes here comprise only 13 original tool descriptions plus generated distractors; no independently publisher-authored source/EN-KO-JA task/permission labels (#1346), unobserved no-fit calibration, full external-tool agent pass (#1477) or valid final grounding (#1348) can be inferred. Original frozen #432 independently observed SR-5 agent task pass 29.19% vs FULL 49.62%. Keep #1607 Draft, #1356 release HARD HOLD and original held-out bytes/scores unchanged.

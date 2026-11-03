# Candidate indexing

SchemaRouter uses an exact-recall lexical candidate index before deterministic endpoint scoring.

The index is a performance optimization only. It does not replace or modify the existing
`_score_endpoint()` ranking rules.

## What is indexed

For every registered endpoint, the planner indexes the inputs that can currently produce a positive
deterministic score:

- tool key and tool name;
- preferred endpoint identity;
- tokens from tool/endpoint names and descriptions;
- output field names, aliases, and explicit dotted projection paths;
- normalized output-field strings used by exact/substring concept matching;
- declared parameter names used by supplied request arguments.

The index therefore returns a superset of every endpoint that can receive a positive score under the
current deterministic scorer. The existing scorer still computes the final score and final sorting.

## Cache invalidation

The index is cached against `ToolRegistry.version`.

A successful registry mutation increments the version, which invalidates the planner cache on the
next request. Building an index reads a stable registry snapshot; if the registry changes repeatedly
during construction, planning fails rather than caching a mixed-version view.

## Source-schema preparation

Endpoint validation compares only result paths that share a complete segment prefix, then applies
the source/result overlap and wildcard rules. It preserves duplicate checks and the first error
in declaration order. Registration still validates mutable input before storing its snapshot.
Canonical JSON validation checks terminal scalars without building a recursive error path for
each one, preserving canonical bytes, fingerprints and diagnostics. These reduce preparation work
for wide original schemas; resource limits still require the measured workload below.

## Disable for comparison or debugging

```python
planner = SchemaPlanner(
    registry,
    candidate_index=False,
)
```

The exhaustive mode scores every endpoint. It is useful for benchmark comparison and for verifying
semantic parity.

## Benchmark

A synthetic benchmark harness is included:

```bash
python scripts/benchmark_candidate_index.py --tools 1000 --iterations 50
```

It reports elapsed time and the number of endpoint scorer calls for indexed and exhaustive modes.

Wall-clock results depend on hardware and registry shape. The repository tests also assert a
stronger deterministic property: indexed and exhaustive planning must produce the same plan
while the selective synthetic case reduces scorer calls from the full registry to the exact
candidate subset.

## Public prepared-session load profile

An explicit E0 mode measures public `compile_understood` and `acompile_query`:

```bash
python -m scripts.benchmark_paper_public_pipeline_e0 --load-profile
```

Each 100/250/500-endpoint catalog and concurrency 1/4 condition runs 30 warmups
and 1,000 measured requests **per pathway**. Closed-loop clients submit the next
request after the previous response; outstanding requests stay bounded by the
client count. Wall samples include submission-to-worker/event-loop queue wait,
compilation, the route oracle and receipt serialization. Reports retain raw
queue/service/wall samples, process CPU, lifetime peak RSS, environment and
250/500/1,000 ms exceedance counts. Unsupported platform probes are null, not zero.

For a short diagnostic, add `--load-routes 100 --load-concurrency 1 4 --load-requests 4 --load-warmup 0`.
Legacy 500/5,000-route and refresh modes retain their options. `--load-*` options
require the separate opt-in. Synthetic sources and a deterministic Understand
callback do not measure provider execution or model inference. RSS is a shared
process-lifetime high-water mark. Sample percentiles and exceedance counts alone
do not establish confidence bounds, a commercial SLO or independent E2; apply
the [prospective acceptance contract](../research/product-north-star-and-test-matrix.md)
with separately pinned hardware, workload and confirmation evidence.

## Scope

The current index is in-process and rebuilt from the registry snapshot. It is not a
vector database, remote search service, or approximate-nearest-neighbor layer. Those systems can be
added behind separate explicit contracts if scale eventually requires them, but they must not
silently change deterministic planner recall.

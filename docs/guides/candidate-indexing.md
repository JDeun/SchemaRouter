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

Wall-clock results depend on hardware and registry shape. The repository tests therefore assert the
stronger deterministic property as well: indexed and exhaustive planning must produce the same plan
while the selective synthetic case reduces scorer calls from the full registry to the exact
candidate subset.

## Scope

The current index is in-process and rebuilt from the registry snapshot. It is intentionally not a
vector database, remote search service, or approximate-nearest-neighbor layer. Those systems can be
added behind separate explicit contracts if scale eventually requires them, but they must not
silently change deterministic planner recall.

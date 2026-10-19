# G5 native multi-endpoint index build: amortized full-tool hashes (E0)

**2026-10-20; issue #1560.** This is a narrow performance and
source-integrity improvement to the existing native schema posting index and
canonical typed graph. It is **not** a new graph store, executor, inference
router, product-wide end-to-end latency claim, publisher validation or E2.

## Diagnosis and scope

Existing `NativeSchemaPostingIndex.build` and `NativeSchemaGraphIndex.build`
walk detached native ToolSpec snapshots under the registry version witness.
Each endpoint previously requested `tool.fingerprint`, which serializes the
**entire tool and every endpoint** to produce the same parent hash repeatedly.
For a tool with 50 endpoints, that repeated parent hash computation can
dominate the indexed build phase. The established 5,102-route benchmark
mostly uses one endpoint per tool, so it cannot diagnose this pattern.

Both builders now compute the tool fingerprint **once for each detached ToolSpec
per build scan**, while checking every original EndpointSpec fingerprint. The
posting index still commits to all original route/tool/endpoint SHA-256 values,
source version and content-based snapshot ID. The graph builder still compares
the fresh detached native route identity against the posting index, builds
edges using the **existing canonical** `capability_graph.py` and rejects
source revision drift. No cross-build cache, trust-witness bypass, change
to principal authorization or field projection, or agent invocation.

## Test and measurement contract

- Exact old fingerprint-per-endpoint dictionary equals new posting index
  revisions for all routes in a multi-endpoint registered source.
- The full ToolSpec fingerprint getter is called **exactly once per
  tool per build**. A canonical compatible root→consumer remains discoverable
  with current live principal/availability/scope and fixed K5.
- Native in-place schema replacement increments registry revision, forces old
  index lookup and graph rebuild to fail closed, and produces a new snapshot.
- A new real Linux CPU benchmark builds **100 synthetic registered ToolSpecs ×
  50 endpoints = 5,000 source-native routes** with mixed source-type labels,
  two typed CRM operations and unrelated multilingual descriptions. It
  performs four alternating-order paired original vs new **source-hash
  scan** measurements on freshly detached native snapshots. Each pair
  must exactly match *every* route and both fingerprints.
- It separately measures the **real optimized posting+canonical graph build**,
  proves one authorized typed graph path and records peak process RSS.
  The scan-only old-vs-new A/B is **not** presented as a paired full-index-build
  speedup; four pairs are insufficient for reliable p99 or a production SLA.

There is no independently publisher-authored tool inventory, source-gold,
typed no-fit calibration, unexposed multilingual task cohort, external native
tool invocation or task-completion evidence here. See #1346/#1477 and frozen
#432. Release PR #1356 stays HARD HOLD.

# Clear Your Tools external-validation execution contract

Status: **development protocol — not scored evidence**

This package prepares issue #839 without selecting a winner or tuning on held-out outcomes.

## Frozen comparison strata

The primary end-to-end comparison keeps the agent, model, catalog, tasks, prompts, backend state,
timeouts, and scoring fixed while changing only the tool-selection/context layer:

1. full-catalog baseline;
2. Clear Your Tools (CYT) native proxy/hook;
3. SchemaRouter native typed capability routing.

Secondary CYT modes are pre-registered separately: English BM25, English LLM pruning, English
reranker, Korean LLM pruning, and Korean reranker. Korean BM25 is intentionally excluded.

## State regimes

Never aggregate these regimes:

- `cold_start`: reset CYT learning/session state before each scored task;
- `persistent_session`: preserve session context suppression/reinjection state but do not treat it
  as TierManager learning;
- `sequential_adaptive`: preserve successful-tool-call TierManager history over one frozen ordered
  sequence and report predefined checkpoints.

A scored query must not silently mutate state used by later independent cold-start rows.

## Required per-run provenance

Record exact commits/versions for SchemaRouter, CYT, agent, model, MCP servers, and catalog; model
parameters; task/case digest; hardware/runtime; retry/timeout policy; state-regime identifier; and
all runner configuration. Raw traces must retain tool exposure, tool calls, usage, latency, and task
scorer output.

## Comparable outcomes

Primary end-to-end outcomes are task success, required-tool execution, total model tokens,
cumulative tool-schema/context bytes, agent steps, tool-call counts, end-to-end latency, and cost
when reproducibly exposed. Routing-only metrics remain secondary diagnostics.

Do not claim independent validation from this contract or from maintainer agreement alone.

## Catalog-size boundary

The 21-tool / 33-case fixture is an **integration smoke only**. CYT v2.17.6 defaults to
`tools.policy.minimum_tools: 50`, so the small fixture is below the product's normal pruning
boundary and must not be used for a CYT-vs-SchemaRouter performance claim.

Development scaling therefore uses **100 / 250 / 500 / 1000 tools** before any held-out freeze.
Each size must use the same catalog and queries for full-catalog, native CYT, and SchemaRouter
conditions. CYT must run its native configured BM25 pruning path rather than a locally recreated
threshold. The 21-tool smoke remains useful only for import/API/provenance regression checks.

## Visible scaling preflight observation

The native composite BM25 development run on the visible 33-case fixture shows two distinct
regimes. Supported/ambiguous cases generally prune aggressively (median candidate count 2 at
100, 250, 500, and 1000 tools). The three unsupported/OOD cases (`sm-dev-031..033`) retain the
entire catalog, so they must be reported separately rather than averaged into supported-query
retrieval quality. This is a development diagnostic, not external evidence and not a tuning target.
Tail latency is therefore also stratified by supported vs unsupported/OOD cases in later reports.

## CYT maintainer clarification (2026-10-10) — mode and platform boundaries

The CYT maintainer reports that CYT was designed cross-platform but **has not
been thoroughly tested on Linux**. Its tested agent integrations are **Cursor,
Codex and Claude**; other agents have not been validated. It has two modes,
which **must not** be silently combined as one interchangeable treatment:

| Boundary | Native Proxy | Native Hook |
|---|---|---|
| Integration | Intercept HTTP/reverse-proxy traffic while preserving original MCP servers | Agent hook through CYT-MCP aggregator |
| Can block an actual tool call | **No** | **Yes** (depending on installed hook capability) |
| Can modify built-in agent/system tools | **Yes** | **No** |
| Needs CYT-MCP aggregator | No | **Yes** |
| Cursor Composer models | Cannot reverse-proxy-intercept | Compatibility not established |

Freeze one primary agent/model/OS/interception path after its actual
integration is reproduced. The existing Linux GitHub Actions native
`cyt-indexer-sdk` BM25 microbenchmark validates **only retrieval SDK
behavior**, not full Proxy/Hook integration and not agent success, tool
blocking, prompt prefix caching or E2E latency. Linux can be tested as a
**separately labeled exploratory compatibility stratum**; a macOS/Windows
primary host also requires observed end-to-end integration success and
hardware/runtime provenance, not assumption.

Do not claim Proxy prevents a prohibited tool call. If blocking/authorization
is a required outcome, use a verified Hook path and explicitly record the
CYT-MCP aggregator and agent hook configuration; keep execution authority
and access-control tests separate from routing/context selection. Built-in
system-tool measurements and Cursor Composer belong to separate supported
capability strata, not a shared all-mode aggregate.

CYT also aims to preserve prompt prefixes to improve provider cache economics
and inject relevant examples. Freeze prompt-prefix bytes/identity and report
cache hits, billed input tokens and cost **only when actual provider usage
records are available**; do not infer savings from schema-byte reduction.
Persistent-session suppression, context-compaction reinjection and
successful-tool-call TierManager learning remain three distinct measurement
effects. The planned performance comparison must not use mode-specific
features as if both implementations offered them.

The new `interception-modes.json` declares these as **unscored methodology
constraints**, checked without models by
`python -m scripts.validate_cyt_interception_boundary`. Passing this
preflight never freezes a held-out experiment or authorizes scoring.

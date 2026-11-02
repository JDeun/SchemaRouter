# Knuckles-Team KG tool discovery: architecture and SchemaRouter adoption review

Status: research, **not** a verified runtime equivalence claim. Date: 2026-10-30. Tracking: #1818.

## Primary evidence

- Maintainer's rejection and architectural update: https://github.com/Knuckles-Team/vector-mcp/issues/6
- Agent OS and KG-2.0 lifecycle: https://github.com/Knuckles-Team/agent-utilities/blob/main/docs/overview.md
- Dynamic tool surface and DynamicToolOrchestrator: https://github.com/Knuckles-Team/postiz-agent
- Connector policy and graph deployment: https://github.com/Knuckles-Team/openbao-mcp
- Medulla authority and graph/query separation: https://knuckles-team.github.io/medulla/

## What is documented versus unverified

| Claim | Evidence | Confidence |
| --- | --- | --- |
| Maintainer now uses one MCP tool per API operation, with its own KG selection | Issue #6 reply | Maintainer statement; not independently runtime-tested |
| KG-based tool discovery and routing are central to agent-utilities | Agent OS overview | Documented architecture |
| DynamicToolOrchestrator matches intent to known names/tags/descriptions with fallback | Connector README | Documented; ranking algorithm and precision not measured |
| Client tool allow/deny and tag allow/deny controls exist | Connector README | Documented; enforcement and isolation need source-level tests |
| Cache refresh occurs periodically (24h described) | Connector README | Documented; consistency during changes unverified |
| Medulla stores governed graph knowledge and evidence separately from connector execution | Medulla documentation | Documented responsibility split |

Note: some published connector README sections still describe condensed/intent modes, while the maintainer says the shipped fleet moved to one operation per tool. Treat the maintainer statement as more current for deployment posture, but verify exact version/commit before comparison.

## SchemaRouter implications

1. **Adopt the principle, not the platform:** KG/retrieval results remain candidate visibility, not executable authority. Reuse Registry, scoped retrieval, availability and Executor authorization.
2. **Audit before implementing:** identify whether per-principal tool visibility, tag predicates and registry-change invalidation are already present. Do not duplicate existing mechanisms.
3. **Possible additive opt-in surface:** per-request visibility predicates for allow/deny tool keys/tags, intersected with existing principal scope. Fail closed on unknown keys or stale schema fingerprints. This is a proposal, not an established gap.
4. **Benchmark:** controlled identical API-operation catalogs; authorized recall@k, leak count, surfaced schema tokens, p50/p95 retrieval latency, cold/warm and post-revision behavior. Do not claim superiority without measured baselines.
5. **Reject wholesale dependencies:** no requirement for Medulla, Agent OS, background cache refresh or a new orchestration DAG in the core library.

## Safety and integration constraints

- Discovery must not mutate or expand authorization policy.
- Execution must recheck current principal, tool fingerprint, binding and data scope.
- Any visibility cache key must include registry revision and relevant principal/scope dimensions or be invalidated synchronously.
- Tests must include denied-but-semantic-match, principal A/B, renamed tool, removed endpoint and policy changes.

## Implementation gate

Complete source-level parity audit and add issue-scoped tests before proposing a production implementation. See #1818.

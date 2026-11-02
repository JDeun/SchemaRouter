# CrewAI bounded MCP exposure benchmark

Tracking: SchemaRouter #1828; upstream CrewAI #7853.

This is an acceptance contract, not a runnable benchmark or measured result.

## Experiment

- Pin CrewAI version and commit before implementation.
- Generate deterministic local MCP catalogs of 32, 128 and 512 tools with relevant tools, distractors, ambiguous descriptions, required arguments and denied/unavailable tools.
- Compare full-catalog exposure, native CrewAI dynamic filtering, and SchemaRouter bounded preselection followed by the same CrewAI filter.
- Preserve CrewAI authorization, MCP lifecycle and execution authority.
- Report required-tool recall@k, task success, exposed schema tokens, p50/p95 latency, unsupported-query abstention, seed, trials and hardware.
- Verify denied principal, missing required input, stale binding, unavailable tool and read-only/write safety.

## Completion gate

Requires pinned integration, runnable local MCP fixture, CI smoke, raw results and reproduction commands. No independent E2 qualification implied.

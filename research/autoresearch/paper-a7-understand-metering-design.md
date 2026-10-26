# Original Algorithm 1 A7 — source-scoped Understand metering (E0)

**2026-10-26.** The existing A5 `run_paper_scoped_agent_episode_e0`
already calls the current scoped `Understand` and then the existing fixed5
agent with its own per-turn usage. It does not measure the extra Understand
stage. An additive research-only wrapper can observe that stage without
changing the original executor, source scoping or historic agent conditions.

## Approaches

- **Chosen:** compose an opt-in metered model wrapper around the existing A5
  episode. Return a structured per-stage receipt, using actual host-observed
  elapsed wall time and optional **provider-reported** token usage. Keep
  unverifiable token usage `null`, never estimate from text or schema bytes.
- Mutate every existing agent evaluator row to include model cost: risks
  historical benchmark/schema compatibility and conflates two stages.
- Reimplement the agent loop to measure both stages: duplicates execution
  authority and invalidates the original Algorithm 1 comparison.

## Acceptance and boundary

- Exactly one underlying scoped Understand model callback at most. An empty
  scoped menu invokes zero Understand model calls; its measured time/tokens
  are explicitly absent.
- Strict provider-usage envelope may be returned by an authorized model
  adapter; its token counts are non-negative bounded integers, not a second
  model-generated answer schema. No envelope means tokens unknown (`null`).
- Agent usage is read from the **unchanged existing** generated-agent report;
  agent input/output/tool-schema tokens stay separate from Understand tokens.
  A thin agent proxy counts canonical JSON UTF-8 bytes for **each actual
  model-visible `tools` argument** as it is passed to `agent.generate`, without
  changing the offered list or introducing a new executor. The same canonical
  JSON byte count is made for the `Understand` request. These counts are
  local serialized-payload sizes, **not** provider network-wire sizes or tokens.
- Timers are host monotonic wall clock, not model claimed latency. No
  private prompt, source inventory, route name or raw model answer in the
  metering summary. `understand_model_callback_wall_latency_ms` measures
  **only the awaited model callback**, not the full host analysis, graph
  planning or caller round-trip overhead; `total_wall_latency_ms` includes
  the original A5 plan and agent episode. A5 source/policy drift checks
  remain authoritative.
- This is *mechanical instrumentation*. It is not yet the independently
  paired same-model/agent model-quality experiment, EN/KO/JA gold or E2.

Release/default selection stays HOLD pending independent #1346/#1477.

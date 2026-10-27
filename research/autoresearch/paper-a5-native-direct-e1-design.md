# A5 original-paper direct ToolCall → registered native provider (E1 opt-in)

## Intent and existing gap

The current A5 path proves a principal-scoped P2 direct route and may bind
host-reviewed scalar arguments to the **frozen synthetic fixed5 executor**.
The existing A9 named graph already uses `SchemaRouter.execute`, but A5
direct plans cannot yet reach an actual registered provider via an
agent-selected ToolCall. This implementation supplies that missing opt-in
integration for **one** typed direct call. It does not make an E2 result.

## Considered approaches

- **Chosen:** one asynchronous, host-scoped research bridge: reuse the A5
  original Understand→P2 compiler, the existing agent's `<tool_call>` format,
  exact P2 source call and **original** SchemaRouter registered executor.
- Change the synchronous frozen `run_generated_episode` to await real provider
  I/O: invasive to historical paired fixtures, can silently change benchmarks.
- Invoke a route immediately on model understanding without the agent's
  actual ToolCall selection: useful for A9 graphs, but does not close A5.

## Behavior and boundaries

1. A trusted host supplies the current captured source view, catalog, intent
   declarations, G5 index, optional explicit inputs or literal-True review.
   The scoped model still returns only untrusted route and parameter hints.
2. Only a **single** source-proved `ready` direct P2 call, no dependency edges,
   can be offered. Empty/unproved/ambiguous/deferred menu means **no agent
   generation and zero provider calls**. Multi-route direct alternatives are
   intentionally deferred to an explicit host decision.
3. The agent receives the source-visible function definition but **never**
   the host-approved argument values. The agent must select exactly that
   function in one bounded, parsed `<tool_call>`; no parallel, malformed,
   duplicate-key, hidden or invented tool names. A model-supplied argument object cannot
   add authority. If P2 has approved inputs, materialize only those through
   the existing A5 source-pinned binding closure; if P2 needs no inputs,
   require the agent to send `{}`.
4. Recheck the captured principal/policy, full P2 plan and G5 source graph,
   approved host inputs and original route before and after agent generation
   and awaited execution. Use `SchemaRouter.execute(ExecutionPlan(...),
   config=RunConfig(principal=..., budget=one call/one attempt))`, **not** a
   second executor or an agent-owned provider credential. Provider execution
   policy and transport restrictions remain the source of truth. Pin the
   original native executor identity and bound-invoker generation as well: an opt-in
   task-local witness must be checked **inside the executor binding lookup**
   after async hooks (not just before and after `router.execute`). This
   rejects rebinds even when the registered schema fingerprint is unchanged.
5. Return a host-only `ToolResult` receipt. No provider output is fed back
   into the model in this phase; no automatic final answer or raw public
   trace. `provider_provenance_verified`, `answer_verified`,
   `executable_authority`, `independent_e2` remain false. Count a separately
   approved argument binding; do not interpret it as independent model
   argument quality. Do not change defaults or frozen benchmarks.

## Verification

- Real `SchemaRouter.add_bound_tool` + original registry executor (no fixture
  substitute), wrong/missing agent arguments, approved input, zero-input
  route, denied review, unavailable/hidden/multiple/malformed model calls.
- Reuse the existing, provider-doc-reviewed **noncommercial-only Open-Meteo
  HTTPS** `ToolSpec` plus its real `OpenMeteoBoundInvoker`. A deterministic
  `httpx.MockTransport` checks the genuine HTTP request/response path and a
  provider error. A separately opt-in `--live` run may perform a single
  public anonymous geocoding GET. The report publishes only aggregate counts
  and explicitly labels the tool chooser as host-scripted (zero independent
  model-selected calls).
- Mutation at model generation or inside an awaited invoker; rebind during
  agent generation or awaited native before-call hook. All fail closed; a
  replaced invoker is never called and no success receipt is returned.
- Source-specific external REST/OPTIMADE/MCP live permission/discovery and
  nested output contracts remain separately testable. Existing E1 live
  provider smokes do not become an independent E2 qualification; signed
  publisher gold/permission gates #1346/#1477 and release hold #1356 remain.

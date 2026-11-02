# #1560 — opt-in host review of original-paper model parameter suggestions (E0)

## Existing path and missing connection

The scoped `Understand(q)` adapter already parses bounded `parameter_hints`,
and the original P2 direct/G5 compilers already validate explicit
`host_source_arguments`. The two deliberately do not connect: an untrusted
model-produced scalar cannot be used as a tool argument without host review.
Real registered 1-/2-hop execution and the fixed-K5 direct agent adapter
already exist. Do not add another executor, graph planner or retrieval ranker.

## Narrow opt-in design

1. Inspect a **previously proven**, current principal-visible P2 receipt
   whose first call has actual missing arguments. The original graph status
   can be `requires_observation` despite that incomplete root. The first
   call alone must be an explicitly
   `approved_host_roots` original G5 scalar root, with all required inputs in
   the original closed source-native envelope. Never infer a missing/optional
   parameter or bind an observed dependency consumer.
2. Only when model `parameter_hints` contain **exactly** those required names
   and their types satisfy the current *original* input JSON Schema, expose a
   detached, small proposal to an explicitly supplied host review callback.
   Include route, parameter names and source fingerprints. The model output is
   untrusted evidence, **not** an execution grant.
3. Require a literal `True` decision. Ignore a rejection; reject nonboolean
   decisions, forged names, mismatched scalar/schema, source/authorization
   drift or in-place mutation. Recompile through the **existing** typed
   planner with the approved values and recheck the original source/roles.
4. Wire this same helper into (a) the existing A5 scoped direct-plan adapter
   and episode's optional callback, and (b) the existing A9 scoped named DAG
   runner plus its tool-free final-answer wrapper; no reviewer means **exactly**
   the previous behavior. A9 execution
   remains restricted to explicit invocation of its research-only entrypoint,
   and uses only the original registered SchemaRouter executor.
   Report a graph blocked on root arguments as `request_arguments` in the
   scoped decision taxonomy, retaining the original unchanged typed plan.
   If a host reviewer is supplied and the scoped direct episode remains at
   `request_arguments`, do not disclose its legacy missing-argument agent
   menu: send the existing host-owned empty terminal instead, with zero agent
   generations or tool attempts. Preserve legacy no-reviewer experiments.
5. Test RED→GREEN on real registered direct and 1-/2-hop tools: approved,
   rejected, missing, extra/injected and typed input, nonboolean decision,
   root-not-approved, host callback authorization/schema mutation, no reviewer,
   and no tool invocation on deferral. Run related suites + Ruff, preserve
   exact SHA/CI evidence and Draft stacking, update canonical handoff.

## Boundary

E0 host review is **not** model argument accuracy, human verification,
publisher semantic attestation, authority to infer from the query or evidence
for E2. Caller must independently implement/review the host decision; do not
auto-approve a model proposal in a production caller. #1346/#1477 remain
external evidence gates, #1356 remains on release hold.

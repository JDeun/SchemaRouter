# A9 E0 — Bounded answer presentation from observed named graph

## Intent and limits

Connect the existing opt-in, one-shot scoped `Understand(q)` → source-proven
registered 1-/2-hop graph execution to one **text-only** external agent
generation. The result is a research-only presentation candidate, **not**
Algorithm 1 independent E2, verified answer accuracy, model-authorized tool
execution, or a default agent loop. Draft #1755 stays unmerged and #1356
remains HARD HOLD.

## Approaches

1. Re-enter the frozen fixed5 tool-calling agent loop. **Rejected:** it may
   schedule a second round of tools, bypassing the original graph's exact
   source-scoped execution budget and provenance semantics.
2. Return only the raw final `ToolResult`, with no model. **Safe but
   incomplete:** A9 already exposes this observation; it does not exercise
   answer generation.
3. **Chosen — one tool-free finalizer:** run the existing A9 wrapper unchanged,
   then invoke the supplied existing `GeneratedEpisodeAgent` once with an
   empty tool menu and a tightly bounded, JSON-serialized **final target's
   projected fields only**. This supports answer evaluation without creating
   another invoker, another agent tool-selection loop, or answer quality
   authority.

## Input, prompt and output contracts

- Host-supplied `AuthorizedAgentToolSurface`, source catalog/intents/index,
  model and agent. The original captured query remains the only user question.
- Require a completed `PaperUnderstoodExecutedGraph` and an authorized final
  result. No model call if the original graph abstains, needs host arguments,
  fails or mutates. Recheck the original source view both before and after
  the agent generation.
- Projected final-result data must be exactly a dict or list of dicts with
  keys from **both** original final call's output fields and the executor's
  verified field contracts. No opaque intermediate source IDs, original
  graph call arguments, auth objects, intermediate producer observations,
  schema descriptions or unrelated route inventory are sent. Reject
  malformed/unbounded/non-finite payloads before invoking an agent.
- System instruction treats the JSON observation as **untrusted data**, never
  executable instructions; zero tools are exposed on the finalizer call.
  The prompt and generation are one request each with strict UTF-8 bounds.
- Require the agent's existing `generate(messages, [])` interface and its
  fixed metering response (`text`, input/output/tool tokens, latency,
  context_overflow). Only a valid, bounded JSON `{"answer": "..."}` answer
  can be accepted. Refuse extra commands/tool-call markup or malformed
  outputs; do not parse or execute any model-proposed tools.
- The return receipt reports the generated text and numeric metering,
  `provider_provenance_verified=False`, `answer_verified=False`,
  `executable_authority=False`, `independent_e2=False`. `offer` describes
  locally completed observations + presentation **only**.

## Verification boundaries

Real `SchemaRouter` invoker integration for one-/two-hop cases, plus refusal
for empty menu, missing approved root, unknown named target, output field
leakage, oversized and non-JSON data, agent tool injection / malformed JSON,
context overflow and mutation during agent generation. Tests must prove no
additional tool I/O, exactly one agent generation with `tools=[]`, and that
upstream `contact_id`/`case_id` values never reach the answer prompt.

The independent publisher/source native gold and paired external-agent
quality judgment remain blocked in #1346/#1477. This does not change A9's
unchecked E2 criterion or the original-paper product routing boundary.

# Original Algorithm 1: indexed direct FieldGroup → existing fixed-K agent (E0)

**2026-10-25 · Issues #1535, #1560, #1477 · Parent research PR #1753**

## Implemented experimental handoff

`NativeSchemaPostingIndex.lookup_concepts(..., input_free_only=True)` now
reuses the *existing* pre-K conjunctive, canonical type/unit/qualifier,
source/licence and principal/data-scope checks, while excluding endpoints
whose required input envelope cannot be satisfied without a producer.
This is not a general argument planner: the existing native G5 graph
continues to own proved producer→consumer dependency selection.

`AuthorizedIndexedFieldFixed5Selector` is a **research-only** callable that
connects that direct index to the existing `EVAL-FIXED5-OPTIN` experimental
selector boundary in `run_generated_episode`. No evaluator/agent loop,
registry, execution authority or product default is replaced.

The trusted host supplies:

1. An explicitly authorized, current `SchemaRouter` with native registered
   source descriptions, permissions, availability and data scope.
2. An owner-reviewed `NativeConceptCatalog`, *not* aliases/gold inferred from
   a benchmark task or from the model.
3. A source-version-pinned `NativeSchemaPostingIndex` and the already existing
   `AuthorizedAgentToolSurface` captured for the **same original query** and
   **same principal**. The selector receives only the query and that view's
   registered visible route IDs from the pre-existing evaluator callback.
4. Optionally, a separate bounded research ranker for **6–32 complete
   candidates**. It receives detached source-verified choices, not the source
   registry, private field values, task gold or an invoker.

The selector checks catalog integrity and original tool/endpoint fingerprints
before and after lookup; the posting index repeats policy, scope, health,
source and FieldGroup verification after ranking. Candidate IDs must be
originally registered and present in the captured principal-visible model
surface, otherwise the lookup fails closed. It checks the serialized
model-visible tool-schema byte cap before exposing even a single selected
tool. No invocation or permission is granted by this selection.

## Outcome semantics

| Index outcome | Research agent exposure | Evidence boundary |
| --- | --- | --- |
| `complete` (1–5 direct, input-free routes) | Verified source-scoped routes | Typed field coverage, not model/task success |
| `over_k_unranked` (>5, no valid policy or >32) | None | Never silently pick first five |
| `ranked_unverified` (bounded valid ranked five) | Exactly five | Quality/relevance not independently verified |
| `ranker_abstained_unverified` | None | Not a calibrated unsupported/no-fit decision |
| `no_proven_hit` or unknown declared concept | None | No proof of absence of capability globally |
| Source/policy/schema/availability/query/view drift | Error, no new exposure | Fail-closed, not a host execution receipt |
| Model-visible schema budget exceeded | None (`budget_unsatisfied`) | No late K expansion |

## Explicit remaining gaps

- The original paper's Algorithm 1 also performs `Understand(q)` to extract
  intent, concepts, parameters, source constraints and explicit tool override;
  applies intent-registry required-group recall; attaches field-level metadata;
  and returns `(tool, params, fields, meta)` plans. This E0 bridge only connects
  **owner-declared concept/complete direct-field discovery** to an existing
  external agent. It does **not** implement the other Algorithm 1 branches or
  replace the separately stacked #1748 typed ToolCall plan work.
- The existing authorized model-view capture is a conservative, lexical
  `retrieve_authorized` surface; it **may exclude index-eligible routes**
  that did not pass that separate lexical model-view capture. The selector
  refuses to synthesize those routes into a model tool definition. A future
  source-wide authorization projection must be separately security-reviewed
  before claiming multilingual recall improvements from this bridge.
- This only tests directly usable original tools. Source-attested one-hop
  G5 producer/consumer recipes use `AuthorizedConceptGraphFixed5Selector`.
  Two-hop and broader Algorithm 1 plan completeness remain open.
- Scripted no-model E0 episodes establish evaluator interoperability only.
  They are **not** independent publisher-authored #1346 task/gold, real agent
  task outcomes, calibrated OOD refusal, an actual provider execution or
  general production retrieval improvement.
- Historical frozen #432 is untouched. #1477 independent paired E2 is
  `BLOCKED_EXTERNAL`; v0.18 release #1356 remains **HARD HOLD**.

## Local verification commands

```bash
python -m pytest -q tests/test_native_semantic_index.py \
  tests/test_research_authorized_indexed_fixed5_bridge.py \
  tests/test_research_authorized_concept_graph_fixed5_bridge.py
ruff check src/schemarouter/native_semantic_index.py \
  scripts/research_authorized_concept_fixed5_agent_bridge.py \
  tests/test_native_semantic_index.py \
  tests/test_research_authorized_indexed_fixed5_bridge.py
pyright
python -m pytest -q
```

**Claims must always be paired with the actual HEAD and fresh command output.**

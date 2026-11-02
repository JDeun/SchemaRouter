# CodeGraph E1: host-attested staged Graph Frontier — design for review

Status: **proposed design, not implementation-approved**. Selected approach:
host-attested staged original native tool disclosure (2026-10-23). Parent
issue: [#1723](https://github.com/JDeun/SchemaRouter/issues/1723). Prior
prompt-only treatment: [#1733](https://github.com/JDeun/SchemaRouter/pull/1733).

## Intent and decision basis

On the pinned local four-route, strict-K5, two-source-hop task, the #1733
static path-order cue yielded Qwen3-1.7B full-task success **3/3** across
EN/KO/JA (previous surgical 0/3). Qwen3-0.6B remained **0/3**. The successful
1.7B surgical condition consumed **5,359–5,363 input-plus-output model
tokens**, whereas same-run FULL consumed **2,142–2,151**. A successful path
ordering prompt therefore does **not** establish a context/cost advantage.
Evidence: [pinned local run](https://github.com/JDeun/SchemaRouter/actions/runs/39952057039)
and `codegraph-qwen-path-order-cue-e1.md`. These are one author-declared local
task per language, not independent E2 or statistical evidence.

The new hypothesis is that disclosing only the **currently reachable,
source-attested original native tool definitions**, without a separate model
schema-request turn, reduces model context and eliminates the opportunity to
call a consumer before observing its authorized producer. It must not silently
pick the path, invent bound arguments, execute an unrequested tool or relax
the original host's execution policy.

## Approaches considered

1. **Staged Graph Frontier — selected.** At the first turn offer only
   source-authorized first-hop producer definitions; after an actually
   successful native callback, offer only the consumer definitions on graph
   paths with that observed predecessor. Benefits: smaller menus and one
   fewer schema-request exchange. Trade-off: this is **host menu guidance**,
   not a context-only graph selection; it is a new isolated E1 arm.
2. **Static compressed K5 schema menu — deferred.** Keep all currently
   authorized tools available from the beginning, but compact description
   text. Smaller engineering delta, yet model can still execute the path in
   the wrong order; aggressive compaction could remove critical semantics.
3. **Auto-execute, route repair or argument filling — rejected.** These
   would substitute host decisions for model decisions, conceal native-call
   errors, contaminate accuracy attribution or bypass original provenance.

The user selected approach 1. The concrete constraints below are design
proposals for review, not yet approved code decisions.

## Scope and fixed controls

- Research-only, opt-in new arm `graph_frontier_g5_e1`, initially restricted
  to `condition="joined"`, `catalog_size=4`, strict `k=5` and `max_turns=5`.
  No changes to default/product-visible tool menus or saved evidence.
- Reuse `capture_surgical_episode`, its `public_reference` and
  `selection.route_sets`, `materialize_scoped_original_schemas` and
  `execute_scoped_host_call`. Do not add a new registry, graph database,
  executor, untrusted search, schema synthesizer or authorization token.
- New research runner, rather than silently changing existing
  `run_surgical_model_episode`; the #1733 cue and all prior negative
  evidence remain immutable and independently reproducible.
- Paired source, principal, query, ground-truth validator, strict parser,
  seed, pinned model revisions, CPU environment and tool-result format.
  Contrast FULL, lexical K5, typed G5, #1733 surgical cue and new frontier.
- Use only the original model-generated `parse_one_model_action` format for
  native operations; one action per turn. No native bare-JSON acceptance,
  automatic tool calls, JSON repairs, hidden values, argument repairs or
  model-facing gold/oracle feedback. A final answer is evaluated separately.
- The static system instruction may explain one action per turn and safe
  observed dependency ordering but must not include original route IDs,
  argument values, expected outputs, hidden fields or gold. The dynamically
  offered schema list is the experimental treatment, not a fake executor.
- **Model-visible reference contract (design decision):** keep the complete
  `SurgicalEpisode.public_reference` private to the host, rechecking it at
  each transition. The frontier arm sends the model the same original query,
  a generic source-dependency instruction, and the *currently offered*
  original native tool definitions **without** the old JSON graph-reference
  payload. That old payload says `requires_source_schema_materialization=true`
  and `tool_call_ready=false`, which is misleading when the host already
  materialized the current frontier. Do not mutate the attested reference or
  manufacture a new executable-looking grant field. This deliberate removal
  is part of the combined frontier treatment, not an isolated menu effect.

## Host-side frontier state machine

```text
CAPTURED (trusted complete G5 episode)
  | revalidate original source, policy, principal, catalog and route receipts
  v
FRONTIER_0 = distinct route_sets[*].route_ids[0]
  | re-materialize only original schemas for currently offered roots (<=K5)
  | model selects exactly ONE currently offered original native route + args
  | host verifies trusted input provenance and executes original callback
  v
VERIFIED_ROOT_OBSERVATION
  | only after status=ok; revalidate unchanged episode/source/policy
  v
FRONTIER_1 = distinct route_sets with selected root prefix, next route
  | re-materialize only original schemas for these consumers (<=K5)
  | model selects exactly ONE offered original native route + observed binds
  | host checks exact graph path and equal trusted/observed arguments
  | original read-only callback, original typed/field-scope enforcement
  v
COMPLETE_SOURCE_PATH -> model-generated final -> independent strict gold
```

After a complete original source path, the final-answer turn offers **zero**
native tools (`[]`). The model must still produce a valid final; any attempted
extra or repeated call is denied. This is pinned before measurements because
it changes both safety behavior and the per-turn input-token denominator.

`FRONTIER_0` includes only *actual* first steps from the pinned authorized
selection, never a guessed producer and never an unranked truncation. A direct
single-hop path, if later supported, has no consumer stage; completion occurs
only after its real callback. The first implementation cohort is the proved
two-hop joined source. Before each generation, schema materialization and
callback, obtain the original `public_reference`/checked view again and abort
if its identity, source fingerprint, availability, principal, policy,
field visibility, catalog or route selection changed.

**Model choice remains real:** among multiple first-hop paths the model
chooses the first native route; the host cannot use scorer gold to resolve
an ambiguous path or substitute a second route. A wrong choice is a measured
failure. After a verified first call, restricting the menu to its provable
successors is the disclosed **treatment**, not a hidden accuracy correction.
The model still chooses whether and which offered consumer to call and must
provide exactly the arguments deriving from trusted inputs and the actual
public producer observation.

Host enforcement for each model action:

1. `route_id` must be one of the **current** frontier definitions; a
   reserved research schema request is *not* offered or accepted in this arm.
2. Selected prefix must match a previously pinned complete
   `NativeConceptRouteSet`; no branch jump, repeated source or extra hop.
3. `_expected_arguments`-equivalent binding validation must be exact.
   Missing, ambiguous, hidden, conflicting or non-scalar arguments deny;
   never attempt to fill or normalize them.
4. Call `execute_scoped_host_call` with a freshly validated original
   `AuthorizedAgentToolSurface` and the current offered route IDs. Validate
   original output fields and source status, not a new synthetic callback.
5. Never expose later-stage schemas before successful real predecessor
   observations; never accept a final as successful before a complete
   authorized original path and independent final-output validation.

Every refusal produces a fixed categorical label/count only. Do not
serialize hidden source observations, model raw text/thoughts, full
definitions, private arguments, principals, credentials or scorer gold in
the research report. Only the model receives required user-visible original
observations, subject to existing original scope enforcement.

## Implementation boundaries (after design approval)

- Add an isolated host-frontier runner in
  `scripts/research_codegraph_graph_frontier_e1.py` (or equivalent research
  module), calling existing materializer and scoped executor. No product
  package edits or additional route grammar.
- Extend `scripts/research_codegraph_local_multiroute_e1.py` with one opt-in
  frontier candidate while preserving the existing `ARMS` and their baseline
  prompts and measurements; do not silently change four-arm return contracts
  on unflagged paths.
- Add opt-in flags to both Qwen3-0.6B and Qwen3-1.7B CLI drivers, requiring
  the fixed four-route joined cohort; reject conflicting experimental flags.
- New deterministic fake-agent tests in `tests/` cover the frontend menu,
  original callback receipts and fail-closed cases before model runs.
- Add a separately named Linux CPU GH Actions E1 workflow with six pinned
  model/language cells and archived sanitized per-arm receipts. Record the
  immutable commit SHA and a preregistration **before** interpreting cells.
- Keep all design, plan and measured research Markdown under
  `research/autoresearch/` because placing internal English-only plans in
  `docs/` triggers the repository's mandatory bilingual MkDocs coverage QA.

## Required verification and adversarial tests

- Proof of first offer: exactly roots from `route_sets`, unique, <= K5,
  source-original `tool_definitions`; no consumer, invented tool or special
  reserved schema request at turn zero. The model-facing prompt contains no
  stale materialization-status flags or serialized graph route references.
- Proof of transition: consumers are not offered until **actual** successful
  original root callback; after callback, offer only compatible original
  consumers with unchanged fingerprint, principal, catalog, source, policy
  and visible output fields. No callback -> no transition.
- Unauthorized/mutating/unregistered, disallowed principal, hidden binding
  field, stale index/policy/source revision, changed source availability,
  deleted route, mismatched binding, extra/missing scalar keys, non-scalar
  values, two-tool calls, malformed JSON, repeated/late root, early final,
  attempted reserved schema request -> deny without an unauthorized callback.
- Every test asserts exact original callback counts, not only a final status.
  A final-answer turn must offer zero tools and reject late native calls.
  Verify original read-only executor and #432 frozen comparators unchanged.
- Run targeted suite, Ruff, repo CI and the pinned GitHub Linux E1. Keep
  source-disjoint independent E2 #1346 BLOCKED_EXTERNAL and v0.18 #1356
  HARD HOLD as separate gates.

## Preregistered measurement and interpretation

Per language and pinned model, report exactly **one owner-authored local
task per condition** (no inflated denominator): strict complete two-source
hop + correct final, termination category, original source callback count
and attempts, offered frontier size per turn, schema request count (expected
zero), model turns, input tokens, output tokens, tool-schema subset,
`input+output` total, and model latency. Never add `tool_schema_tokens` a
second time to `input_tokens`.

Primary falsifiable question: does staged frontier preserve the #1733
Qwen3-1.7B strict full-task success **3/3** while reducing total model tokens
and/or turns relative to 5,359–5,363 surgical tokens? Secondary question:
can it match or beat the contemporaneous FULL model-token cost without
losing correctness? The current FULL local reference is 2,142–2,151 tokens
with 2/3 successes. Treat every zero, refusal and extra-turn cost as an
actual result.

If frontier lowers tokens but loses complete-task correctness, classify as
a trade-off, **not** an efficiency win. If it keeps 3/3 yet stays above FULL
tokens, it is **not** an end-to-end cost saving versus FULL. Because N=3
linguistic variants of a single local scenario, even a 3/3 and token win
would only motivate independent held-out E2, never justify product release.

## Open risks and builder decisions

1. Restrict first code to the verified two-hop joined source; generalizing
   direct paths/multiple next-hop alternatives is separate acceptance work.
2. For path ties, preserve *all* authorized next-hop alternatives under the
   same prefix (up to K5); never rank or truncate them using gold.
3. An LLM may prematurely finalize when only one tool is offered, or fail
   without explicit reserved-schema handshake; negative cells are legitimate.
4. Revalidating the source for every menu can increase host CPU even if
   model tokens drop. Report that overhead separately where available.
5. Existing prompt-only and static FULL controls must remain literal
   controls; any change to their prompt or parser invalidates paired causal
   interpretation and requires a separately named experiment.
6. The frontier arm combines staged menus, elimination of the explicit
   schema-request turn and omission of model-visible graph references.
   Therefore any observed gain **cannot** separately identify which one
   caused it without a later factorial ablation. This E1 answers whether
   the complete host-frontier architecture is useful, not why in isolation.

**Review gate:** approve or amend this design before writing an implementation
plan, changing product/research runner code, or initiating new GH Linux model
jobs. Approval of approach A alone does not imply approval of these specific
host-transition and experimental-comparison decisions.

# Original Algorithm 1 — bounded Understand→intent→named-tool direct plan (E0)

**Decision, 2026-10-25.** Continue #1560 on a stacked Draft from #1754. The user approved native sequential implementation and asked not to pause for routine choices. The exact source is `paper/schemarouter.tex` Algorithm 1. This is an opt-in research slice; existing defaults, agent executor, release #1356 and independent E2 #1346/#1477 remain unchanged.

## Goal and boundaries

Take a **structured, untrusted** `Understand(q)` result (`intent_id`, declared `concept_ids`, optional `source_type`, exact `named_tools`, parameter hints) and a separate, host-owned bounded intent registry. Resolve *only* catalog-declared concept contracts, union the registry-required concepts **before** K, use the existing source-pinned native posting index, then emit ordinary non-executing `PaperTypedToolPlan` calls with required fields, visible identifier fields, typed missing-argument status, and source-derived field metadata. Explicit tool names filter eligible candidates **before** the K5 budget, never bypassing current principal/field scope, fingerprints, license, health or source read-only checks.

This proves source-safe **direct** routes only. A named dependent consumer needs the existing G5 producer/consumer path and is not falsely presented as a ready direct call. Parameter hints from an LLM are never used as host-approved argument values; missing inputs stay missing. Semantic accuracy of `Understand(q)` is unverified E0, not a calibrated no-fit decision. An unknown/hidden named tool is indistinguishable from no proven candidate in the public output.

## Alternatives

1. Rebuild the planner and intent/tool registry (rejected: duplicate state, authorization drift, large default impact).
2. Filter an already K-truncated plan after retrieval (rejected: a named sixth tool cannot be recovered and partial/unscoped leaks are tempting).
3. **Chosen:** bounded host intent→catalog field contracts; optional exact-tool pre-K filter in the existing posting lookup; reuse `_compile_one_route` and live source proof for typed output. No new registry of tool schemas or executor.

## Contracts

- `PaperIntentDeclaration(intent_id, required_concept_ids)` and `PaperIntentRegistry` are **owner-reviewed semantic maps**, not another tool catalog. Each referenced ID must be present in the original `NativeConceptCatalog` at evaluation time.
- `PaperUnderstanding(intent_id, concept_ids=(), source_type=None, named_tools=(), parameter_hints={})` is untrusted model/host input. Every field is bounded. Concepts can *add* owner-approved fields but cannot delete the intent's required ones. No unchecked alias, unit, source/license, field, group or endpoint can enter the plan.
- `NativeSchemaPostingIndex.lookup(..., allowed_tool_keys=None)` optionally filters exact registered ToolSpec keys before qualification and before K. Unknown keys return no proven candidates, not privilege or private metadata; duplicate/malformed keys are rejected. Existing calls are byte-/behavior-identical when omitted.
- `compile_paper_understood_direct_plan(router, understanding, *, principal, catalog, intent_registry, index, k=5)` accepts only the native pinned `NativeSchemaGraphIndex` and principal. The posting index proves full field conjunction, original source/license/scope and actual currently visible fields. It attaches *currently visible identifiers* and reuses existing `PaperPlanCall` materialization with no execution.
- If the full source-visible direct candidate set exceeds K without independently verified ranking, `over_k_unranked` with no calls. No alphabetic first-five cut, backfill, hidden counts, claimed provider provenance or agent task outcome.
- Recheck policy/registry/catalog/intent/principal/index/current result after materialization and before publication. A changed snapshot raises a generic `PolicyViolationError`.

## Tests and non-goals

1. Seven equally field-complete original tools: ordinary structured intent abstains at >K, named sixth tool yields its one source-verified ToolCall and identifiers before K; unknown tool gives no hit.
2. Intent-required `A+B` wins over a model-provided `A` only; A-only route never passes. KO/JA/EN aliases are owner mapping, not automatic language inference.
3. Hidden/denied/unavailable/wrong-license or destructive candidate is never exposed even if named; changed source/policy/availability/ontology fails closed; optional K remains exactly 5.
4. Model parameter hints do not enter ToolCall arguments or become execution authority; host-required inputs produce `requires_arguments` (or must be handled by the separate attested G5 flow).
5. Existing native posting, paper P1/P2 and default authorization tests remain green. No new empirical E1/E2 benchmark, merge or release action is authorized by this design.

**Remaining full-paper gaps:** actual `Understand(q)` LLM accuracy; domain-aware intent rank and default routing; typed source-safe one-/two-hop override; parameter extraction-to-approved-value workflow; source-independent E2 and calibrated no-fit. Source-owned `ToolSpec` has no `domain` field today: this slice uses intent-required concepts and original source type/license instead of inventing domain labels.

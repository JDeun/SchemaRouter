# Algorithm 1 source-scoped empty-menu refusal — E0 design

**Decision (2026-10-25):** User requested that unavailable-tool requests be refused. Continue the opt-in original-paper direct candidate path through the *existing* #1477 fixed-K agent evaluator. Do not change frozen #432 modes, the public default, or the executor. Prior source-owned no-match infrastructure already exists; the missing integration is a guaranteed host terminal for a source-scoped empty candidate menu.

## Behavioral contract

- The external agent may only see original registered, authorized, data-scoped, available ToolSpec routes. A pre-parsed `PaperUnderstanding` is **untrusted**: an exact named-tool suggestion has no permission to insert a tool into this menu. The host intent registry and native concept catalog own required fields.
- The optional paper fixed5 selector compiles `compile_paper_understood_direct_plan` against the captured original `AuthorizedAgentToolSurface`; it checks route IDs and tool/endpoint fingerprints against that view, exact K5, byte budget, and immutable source/catalog/intent/understanding before disclosure. Ready and `requires_arguments` are only **tool menus**, not execution grants. A missing host argument is never filled from model hints.
- An optional `experimental_host_empty_menu_terminal=True` applies **only** with `EVAL-FIXED5-OPTIN`, a principal-scoped source view, and a selector. When the resulting authorized menu is empty, the host emits the evaluator's exact generic `REQUEST_MORE_TOOLS` terminal, calls neither model nor executor, and records a sanitized host-terminal boolean. The terminal asks for additional permitted capabilities; it **does not assert that no such tool exists globally**.
- Do **not** call `over_k_unranked`, `budget_unsatisfied`, no source-visible hit, or an unregistered concept an independently calibrated semantic no-fit. A known supported request with an empty menu is a **false refusal** and must fail the existing evaluator's supported oracle. Unknown/denied/hidden tool names have identical outward no-menu behavior; never expose hidden names/counts.
- Nonempty menus continue through the original agent evaluator, unchanged. Mid-request registry/policy/availability/field-scope/catalog drift fails closed before publication. Existing opt-in flag defaults false to preserve other experiments.

## Tests and boundaries

1. Source-scoped empty selector + unsupported fixture → no model generation, no tool attempt, exact host generic terminal, successful strict unsupported grader. Control without the flag still invokes model. A supported fixture with the same empty menu must fail (measures false refusal).
2. Nonempty selector with the flag preserves one normal model-mediated tool call; flag rejected under frozen historical conditions, missing source view or invalid type. Source change after selection must fail, not issue a refusal on stale data.
3. Structured intent + named complete tool selects a currently source-visible, field-complete original direct route. Unknown/denied/hidden/wrong-license tool and source mismatch return no menu; >K ambiguity also no menu with separate selector status. Model parameter hints cannot bind execution values. Malformed/changed contracts fail closed.
4. Public trace includes **only** a typed host terminal boolean, counts and normal safe scalars. No raw terminal, model text, route names, hidden tool identities, authorization internals or semantic no-fit claim.

**Evidence limit:** Local synthetic/host-scripted E0 mechanics only. Not original LLM `Understand(q)` quality, independently calibrated unsupported classification, real provider execution, E2 #1346/#1477, or release #1356 (HARD HOLD). The original paper Algorithm 1 wider candidate ranking and one/two-hop tool selection remain open.

## Opt-in existing-agent integration

The host constructs a reviewed catalog/intent map and pins a native graph
index against the same current `SchemaRouter` source as its principal-scoped
agent tool view. The model-understood hint is parsed but **not trusted** to
authorize a tool or bind parameters:

```python
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION, run_generated_episode,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_authorized_concept_fixed5_agent_bridge import (
    AuthorizedPaperUnderstoodDirectFixed5Selector,
)

view = capture_authorized_agent_tool_surface(
    router, original_query, principal=principal,
)
index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
selector = AuthorizedPaperUnderstoodDirectFixed5Selector(
    view=view,
    catalog=owner_reviewed_catalog,
    index=index,
    intent_registry=host_intents,
    understanding=untrusted_structured_understanding,
)
sanitized_metrics = run_generated_episode(
    agent, router.registry, fixed_e0_task_fixture,
    EXPERIMENTAL_FIXED5_CONDITION,
    experimental_candidate_selector=selector,
    experimental_agent_tool_surface=view,
    experimental_host_empty_menu_terminal=True,
)
```

This entrypoint is the **existing research fixture evaluator**, not an app
runtime with provider execution. Host applications must separately enforce
their production refusal/admission and authorization boundaries. `selector.last_status`
distinguishes `no_proven_hit`, `over_k_unranked`, `budget_unsatisfied`,
`requires_arguments`, and `ready` within the trusted host; it is not an
independent semantic-absence oracle and is intentionally omitted from the
public privacy-scoped trace. A true public `host_empty_menu_terminal` means
zero offered verified tools and **zero model/tool attempts**, not globally
missing capabilities.

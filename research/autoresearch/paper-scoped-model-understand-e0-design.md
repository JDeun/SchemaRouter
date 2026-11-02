# Algorithm 1 `Understand(q)` scoped model-response adapter — E0 design

**Decision (2026-10-25):** Continue #1560/#1477 from canonical
`paper-toolcall-implementation-e0.md` and Draft #1755. Existing
`PaperUnderstanding` is only an externally constructed Pydantic value. Add
a bounded *actual model-callback* bridge without replacing the existing
`ModelQueryAnalyzer`, fixed-K agent evaluator, registry, planner or executor.

## Goal and non-goals

Call an explicitly host-provided sync/async model once with the existing
principal-scoped native `AuthorizedAgentToolSurface.catalog_index()` and an
explicitly host-approved intent/concept disclosure allowlist. Accept either
strict JSON object text or an already decoded dictionary; parse a bounded
`PaperUnderstanding`, recheck source and host declarations, then let the
existing direct selector compile it. This is the missing *mechanical*
`Understand(q)` input from the original paper, not evidence of intent-model
accuracy, trustworthy parameters, semantic no-fit or independent E2.

If the source-visible catalog is **empty**, return `None` without a model
call. This is **no currently offered/verified tool**, never a global absence
classification. The opt-in existing host empty-menu terminal remains the
place that emits `REQUEST_MORE_TOOLS`; the model adapter never invents a
tool or a final user answer. A model hallucination of an unavailable exact
tool name must pass to the existing source filter and yield the same public
`no_proven_hit` as denied/hidden names. Do not leak hidden route names or
counts in parser messages or public traces.

## Disclosure and integrity

- Model input is the current captured *authorized* route **ID and scoped
  description** index, not `ModelQueryAnalyzer._catalog` over unrestricted
  `registry.tools()` and not the full, unaudited model-visible raw schema.
- Host explicitly declares `model_visible_intent_ids` and
  `model_visible_concept_ids`. All are reviewed members of the current
  `PaperIntentRegistry`/`NativeConceptCatalog`, unique and bounded. Every
  disclosed intent's required concepts must be in the visible concept set;
  the host, not model inference, is responsible for whether these IDs are
  safe to disclose. The model may **add only these** concept IDs.
- Bound complete input JSON bytes to <=32768 by default and model raw output
  to <=4096, before decoding. Reject non-JSON text/fences, duplicate keys,
  NaN/Infinity, extra keys, invalid primitive/types, undeclared model
  intent/concept, nested parameter-hint values and model callback exceptions
  with a generic safe `ModelAnalysisError`; do not retry on a different
  source/catalog or silently fall back to an unscoped model.
- Capture `view` authorization/policy/registry identity and host
  catalog/intent JSON before the model call; compare all **after** even
  if the model responds. Changed source, principal, authorization,
  immutable owner declarations or model exposure must abort with
  `PolicyViolationError` before the new understanding is used.
- The accepted `parameter_hints` remain **untrusted suggestions**, never
  `ToolCall.arguments`, a ground-truth value, or an execution grant.

## Caller contract and tests

Research-only `scripts/research_paper_scoped_understand_e0.py` exports
`analyze_paper_understanding_scoped(model, *, view, intent_registry,
catalog, model_visible_intent_ids, model_visible_concept_ids,
max_model_input_bytes=32768, max_model_output_bytes=4096)` returning
`PaperUnderstanding | None`. Model callback receives **one detached JSON-like
dictionary**; returns a dict, JSON str or awaitable thereof. A host then
constructs `AuthorizedPaperUnderstoodDirectFixed5Selector` with that result
and runs the unchanged `EVAL-FIXED5-OPTIN` evaluator. The external model
pre-call's cost is **not** included in the agent evaluator's token/latency
metrics; future paired E2 must account for it separately.

Tests cover visible-only disclosure, unrecognized tool + no model terminal,
normal model→typed direct route→existing agent fixture, no visible routes,
KO/JA query text preservation, strict parser attacks, callback source or
host catalog mutation, input/output byte budgets and ignored model hints.
No real Qwen/publication accuracy claim or frozen benchmark modification.

### Minimal opt-in wiring (existing agent, no new executor)

```python
from scripts.research_paper_scoped_understand_e0 import (
    analyze_paper_understanding_scoped,
)
from scripts.research_authorized_concept_fixed5_agent_bridge import (
    AuthorizedPaperUnderstoodDirectFixed5Selector,
)

# view is the current principal-scoped AuthorizedAgentToolSurface.
# Host owns and reviews the IDs that this model is allowed to see.
understood = await analyze_paper_understanding_scoped(
    model_callback,
    view=view,
    intent_registry=host_intents,
    catalog=owner_catalog,
    model_visible_intent_ids=("case.lookup",),
    model_visible_concept_ids=("case.status", "case.priority"),
)

if understood is None:
    # Host-owned no-offered-tool terminal; never model-generated no-fit.
    refuse_no_currently_verified_tool_menu()
else:
    selector = AuthorizedPaperUnderstoodDirectFixed5Selector(
        view=view,
        catalog=owner_catalog,
        index=pinned_native_graph_index,
        intent_registry=host_intents,
        understanding=understood,
    )
    # Pass selector into the existing EVAL-FIXED5-OPTIN, with
    # experimental_host_empty_menu_terminal=True and same `view`.
```

`refuse_no_currently_verified_tool_menu()` is intentionally a **host-owned
application policy placeholder**, not a new exported SchemaRouter function.
Its wording must be epistemically bounded to the tools currently authorized
and offered to the principal. The model-callback preflight's latency, CPU and
tokens are not yet included in the fixed5 agent evaluator's cost accounting.
**The supplied model callback is not host-deadlined or cancellable by this
research adapter.** Applications must enforce their own bounded generation
deadline/concurrency outside this opt-in E0 function; do not treat it as a
production admission controller.

## Alternatives

1. Use `ModelQueryAnalyzer` directly: rejected because its current prompt
   enumerates the full unscoped registry, including potentially hidden tools,
   and its argument sanitizer can retain model-provided values.
2. Write a new agent/model loop: rejected because #1477 mandates reuse of
   the existing generated-agent evaluator and execution accounting.
3. **Chosen:** one model-callback `Understand` boundary over existing
   source-scoped catalog index; reuse prior checked direct selector afterward.

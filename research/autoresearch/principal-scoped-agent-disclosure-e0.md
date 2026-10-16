# Principal-scoped agent tool-view and trace boundary — E0 research (#1477)

**2026-10-17 · research only · not a product permission receipt**

## Concrete discovered leak path in the legacy research harness

In `scripts/evaluate_agent_utility_phase_b_smollm3.py::_function_tool`,
model-visible tool declarations include original publisher tool/endpoint free
text, unfiltered parameters and output field descriptions. In
`scripts/agent_utility_generated_common.py::run_generated_episode`, the
legacy generated-agent study emits raw executor observations and serialized
`attempts`/tool-call traces, even when an observation_transform makes the
model view narrower. Those are appropriate original frozen synthetic
research artifacts but **not safe for real tenant/principal-sensitive use**.
No claim that the production SchemaRouter public API itself leaks these.

## Narrow implemented scope

`scripts/research_authorized_agent_tool_surface.py` is an independently
callable **read-only model-disclosure and artifact-redaction adapter**.
It is wired ONLY into the explicit #1478 `EVAL-FIXED5-OPTIN` synthetic agent condition and remains completely absent from production routing, public execution and all legacy frozen agent conditions.

1. Accept a host-supplied real `SchemaRouter`, trusted
   `PrincipalContext` and original user query. The default 500-route
   physical catalog cap refuses huge scans rather than truncating source
   identity.
2. Call public `retrieve_authorized(query, principal, k=physical_count)`
   to form ONLY principal-visible, positively scored original provider route
   IDs. Reject source/version/availability/policy object changes and
   incomplete ranked catalogs. Also pin the **trusted PrincipalContext roles,
   departments, teams and mutable attributes** at capture and fail closed if
   any claim changes before/after model inference, tool projection or report.
   This is not an atomic lock against ABA or in-place source mutation (#1450).
3. Produce a strict max-five `tool_definitions` list from those projected
   `CapabilityCandidate` fields. Under ANY data-scope rules, **discard all
   unstructured tool/endpoint/parameter descriptions, examples and nested
   schema metadata**. Include only recognized primitive parameter types
   and the already projected visible output semantic IDs. Unsupported nested
   schema parameter types fail closed; they are not silently widened. Bound
   final serialized model tool definitions to 128 KiB.
4. `project_observation` emits coarse status and ONLY approved **scalar**
   declared output field values. Raw error strings, unregistered output
   keys, nested/unstructured values or nonfinite floats cannot pass into the
   model view. Full nested schema-aware projection is **not implemented**.
5. `public_trace` is an explicit **allowlist** of integer/bool outcome
   metrics and visible candidate counts; it never copies query, source gold,
   raw arguments, raw executor observations, final natural-language answer,
   arbitrary errors or hidden route IDs. The internal frozen executor may
   retain complete fixture evidence for synthetic grading, but that object
   must never be directly exported as a public result.

Tests inject `SECRET_HIDDEN_CANARY_1749` into hidden output fields, publisher
description prose, parameter descriptions/JSON schema, structured observation,
raw call arguments, final answer text and attempts. They check literal absence
from serialized model tool definitions, visible observations and public
artifact. Additional negative tests prove denied route IDs, duplicate/forged
selection, over-K, field-scoped nested value, registry/policy/availability
changes, outsider views and no planning/provider execution. Passing these is
**E0 interface safety evidence on fake source fixtures**, not real tenant
security certification or independent multilingual retrieval.

## Actually wired into the existing synthetic agent loop

The existing `scripts/agent_utility_generated_common.py::run_generated_episode`
now accepts the optional `experimental_agent_tool_surface` **only** together
with the `EVAL-FIXED5-OPTIN` route selector. This does not alter frozen
FULL/SR-5/SR-10/ORACLE conditions.

- The selector is shown only this source-scoped view's route IDs, not all raw
  registered IDs. The source registry identity and authority witness are
  checked before and after the callback.
- The agent receives **only** `AuthorizedAgentToolSurface.tool_definitions`
  instead of the legacy `_visible_tools(raw_registry,...)` serializer.
- Every model turn and synthetic execution boundary rechecks the authority
  witness. After a synthetic tool call, the next agent turn receives only
  `project_observation`, not the original raw observation.
- The returned episode data comes solely from `public_trace`; raw arguments,
  gold, original observations and final model text never leave the function.
- An unexpected route in tool output or a policy/registry/availability swap
  fails closed; no historical frozen task/gold/scorer was modified.

**Remaining BLOCKER before real tenant execution:** `FrozenCorpusExecutor`
performs synthetic source fixture policies only and is **not** a trusted
provider invoker or full RBAC/ABAC execution boundary. A production adapter
must independently recheck host-allowed tool execution, current policy,
approval, source/version/ABA safety and all native input/output contracts;
nested output objects need a true schema projector rather than coarse
rejection. The source-identity witness is not an atomic concurrent
transaction. Never expose this experimental E0 route to customer data.

When this end-to-end E0 integration works, run one prospective paired
Lexical/Dense/Hybrid/Typed+No-fit comparison only with independently authored
source-native EN/KO/JA/unsupported gold (external #1346). No claim of such
gold or end-to-end E2 today. Preserve the historical frozen #432 conditions,
both conflicting native Open-Meteo/ServiceNow model DEV outcomes, and
v0.18 release #1356 HARD HOLD.

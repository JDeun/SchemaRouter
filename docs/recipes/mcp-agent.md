# MCP agent boundary

This pattern is useful when an application discovers capabilities from an MCP server but does not
want remote annotations to become authorization. The paper-first development package uses an
explicitly configured Algorithm 1 plan and the registered executor, not a catalog-wide lexical
ranking or a score-based execution bridge.

```python
from schemarouter import PaperPlanRequest, RunConfig, SchemaRouter

router = await SchemaRouter.from_url(
    "http://localhost:8000/mcp",
    kind="mcp",
)
```

Registration does not authorize invocation. Prepare a field-routing session using an owner-reviewed
concept catalog; configure `configure_field_routing` with the schema-independent Understand model,
the reviewed Intent/FieldGroup declarations and the paper Rank policy bound to that session's
snapshot. The offline `examples/quickstart.py` demonstrates this configuration without a real model.

## Production note

`allow_unclassified_remote=True` is broad and is not enabled in this example. A production
deployment with mixed read and write MCP tools should use trusted local classification or separate
servers by authority domain. The server's own annotations are not the final side-effect decision.
The application supplies a trusted principal and explicitly approved source-local parameters;
model proposals never become those parameters merely because the model suggested them.

## Optional no-match execution guard

The former calibrated `RetrievalAbstentionPolicy`, `ainvoke_selective`, and
`execute_selective_plan` APIs are retired from the development package. The original comparisons
and their fail-closed execution tests remain under `scripts/research_legacy_planning/` in a source
checkout, not as a fallback for Algorithm 1.

After configuring the field-routing session, use the same trusted principal for paper planning
and execution:

```python
request = PaperPlanRequest(
    query=user_request,
    host_source_arguments=trusted_source_arguments,
)
plan = await router.aplan_authorized(request, principal=trusted_principal)
if plan.planning_status == "ready":
    results = await router.execute(
        plan, config=RunConfig(principal=trusted_principal),
    )
else:
    results = []  # Incomplete or unsupported plan: no tool call.
```

A ready diagnostic is not execution authority by itself. The issued plan's local witness rechecks
the original source revision, principal, field coverage, unchanged calls and binding readiness.
The registered executor still enforces current policy and validates actual arguments and outputs.
No universal score threshold or independently calibrated open-set quality is claimed. Historical
score-based shortlist tests retain their original scope, provenance, fallback and no-call checks.

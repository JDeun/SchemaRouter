# MCP agent boundary

This pattern is useful when an application discovers capabilities from an MCP server but does not
want remote annotations to become authorization.

```python
from schemarouter import ExecutionPolicy, PlanRequest, SchemaRouter

router = await SchemaRouter.from_url(
    "http://localhost:8000/mcp",
    kind="mcp",
    policy=ExecutionPolicy(
        allow_unclassified_remote=True,
    ),
)

results = await router.ainvoke(
    PlanRequest(
        query="add result",
        arguments={"a": 2, "b": 3},
    )
)
```

## Production note

`allow_unclassified_remote=True` is broad. A production deployment with mixed read and
write MCP tools should prefer a future trusted local classification layer or separate servers by
authority domain.

The current design refuses to trust a remote server's own annotations as the final
side-effect decision.

## Optional no-match execution guard

For ordinary application calls, use the higher-level **`ainvoke_selective()`**
entrypoint so the host need not coordinate two separately authorized artifacts:

```python
from schemarouter import RetrievalAbstentionPolicy, ainvoke_selective

policy = RetrievalAbstentionPolicy(min_score=host_config.calibrated_min_score)
results = await ainvoke_selective(
    router, user_request, k=3, policy=policy, config=trusted_run_config,
)
```

The host must independently calibrate `calibrated_min_score` and may catch
`PolicyViolationError` to return a no-capability response without a call.
Both retrieval and planning use the **same RunConfig principal**. No tool
can execute through this API after abstention. Plain `ainvoke()` does not use
this optional gate.



`router.ainvoke(...)` above does **not** automatically reject an unsupported
user request merely because the best-ranked capability is a poor match.
To explicitly opt into an externally calibrated retrieval abstention check
**before actual execution**, use the same trusted request and authorization
context for retrieval and planning:

```python
from schemarouter import (
    PlanRequest, PolicyViolationError, RetrievalAbstentionPolicy,
    execute_selective_plan,
)

request = PlanRequest(query=user_request)
policy = RetrievalAbstentionPolicy(min_score=host_config.calibrated_min_score)
retrieval = router.retrieve_executable(request, k=3)
plan = router.plan_executable(request)
try:
    results = await execute_selective_plan(router, retrieval, plan, policy=policy)
except PolicyViolationError:
    results = []  # No tool call dispatched by this optional guard.
```

This refuses an abstained shortlist, unknown fallback tools, schema mismatch
and stale registry/query pairs. It does **not** certify an unsupported intent:
the score and cutoff still require *independent prospective calibration*.
The host must use this opt-in bridge consistently; plain `ainvoke` bypasses
it. It never replaces SchemaRouter's normal authorization or execution policy.

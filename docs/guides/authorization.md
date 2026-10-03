# Principal-aware authorization

SchemaRouter can apply trusted RBAC/ABAC claims before capability retrieval and revalidate them at
the execution boundary.

SchemaRouter is **not** an identity provider. Authentication, SSO, token verification, group
membership, and HR directory truth stay in the host application. The host supplies a verified
`PrincipalContext`.

## Employee, manager, executive

```python
from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
)

policy = AuthorizationPolicy(
    rules=(
        AuthorizationRule(
            name="employee-data",
            effect="allow",
            operation="employee_records.*",
            roles_any=("employee", "manager", "executive"),
        ),
        AuthorizationRule(
            name="manager-data",
            effect="allow",
            operation="management_metrics.*",
            roles_any=("manager", "executive"),
        ),
        AuthorizationRule(
            name="executive-data",
            effect="allow",
            operation="board_financials.*",
            roles_any=("executive",),
        ),
    )
)

router = SchemaRouter(authorization_policy=policy)

employee = PrincipalContext(subject="alice", roles=("employee",))
manager = PrincipalContext(subject="bob", roles=("manager",))
executive = PrincipalContext(subject="ceo", roles=("executive",))
```

When an authorization policy is configured, planning and retrieval without a principal fail closed.

```python
employee_candidates = router.retrieve(
    "quarterly finance",
    principal=employee,
    k=5,
)

executive_candidates = router.retrieve(
    "quarterly finance",
    principal=executive,
    k=5,
)
```

Unauthorized endpoints are removed before ranking. This prevents a downstream model from receiving a
forbidden tool merely to have execution reject it later.

Execution is checked again:

```python
result = await router.execute(
    plan,
    config=RunConfig(principal=executive),
)
```

A plan created for a broader principal cannot be replayed by a narrower principal.

## Department, team, and attributes

Rules can combine RBAC with ABAC:

```python
AuthorizationRule(
    name="sales-apac-enterprise",
    effect="allow",
    operation="sales_pipeline.*",
    departments_any=("sales",),
    teams_any=("enterprise",),
    attributes=(("region", "apac"),),
)
```

Selectors across categories are ANDed; values inside an `*_any` selector are ORed. Rules are
evaluated in declaration order and the first matching rule wins.

## Default behavior

`AuthorizationPolicy` is deny-by-default. If no rule matches, the route is invisible and cannot
execute.

A router created without `authorization_policy` preserves the existing no-principal behavior.

## Non-disclosure boundary

Authorization is applied as an additional local availability predicate during planning/retrieval.
Invisible endpoints are not returned as rejected candidates. The existing capability-eligibility API
similarly returns no explanation for host-invisible capabilities.

Authorization failures at the execution boundary use a generic denial message rather than exposing
which role, department, team, or attribute failed.

## Database authorization

Database onboarding builds on this principal boundary. Database adapters should expose only the
table/column schema permitted for the selected access scope and must enforce row predicates inside
the trusted database invoker. Model-supplied arguments must never be able to remove or weaken those
row predicates.

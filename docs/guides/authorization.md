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
employee_candidates = router.retrieve_authorized(
    "quarterly finance",
    principal=employee,
    k=5,
)

executive_candidates = router.retrieve_authorized(
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

## Field, row, tenant, and traversal scopes

Capability authorization answers **whether a principal may use an endpoint**. Data-scope rules narrow
what that already-authorized endpoint may expose or execute.

```python
from schemarouter import DataScopeRule, TrustedFilterBinding

policy = AuthorizationPolicy(
    rules=(
        AuthorizationRule(
            effect="allow",
            operation="company.employees.select",
            roles_any=("employee", "manager", "executive"),
        ),
    ),
    data_rules=(
        DataScopeRule(
            name="employee-row-scope",
            operation="company.employees.select",
            roles_any=("employee",),
            visible_fields=("id", "name"),
            trusted_filters=(
                TrustedFilterBinding(
                    field="department",
                    principal_value="attribute:department",
                ),
            ),
        ),
        DataScopeRule(
            name="manager-row-scope",
            operation="company.employees.select",
            roles_any=("manager",),
            visible_fields=("id", "name", "department", "salary"),
            trusted_filters=(
                TrustedFilterBinding(
                    field="department",
                    principal_value="attribute:department",
                ),
            ),
        ),
        DataScopeRule(
            name="executive-scope",
            operation="company.employees.select",
            roles_any=("executive",),
            visible_fields=("id", "name", "department", "salary"),
        ),
    ),
)
```

For the employee rule above:

- `salary` and `department` are removed from the model-visible retrieval schema before scoring;
- the trusted department predicate is resolved from the verified principal context;
- the predicate is injected inside the trusted database invoker and cannot be removed by model arguments;
- a forged/stale plan that explicitly asks for a hidden field fails closed at execution.

`TrustedFilterBinding` can source values from `subject`, `role`, `department`, `team`, or
`attribute:<name>`. Missing required attributes fail closed.

The same scope contract is reused across database families:

| Data family | Scope enforcement |
| --- | --- |
| SQLite / SQLAlchemy RDB | visible columns + trusted equality/IN row predicates |
| Vector stores | visible result/metadata fields + trusted filterable metadata predicates |
| Document/search/KV/time-series | visible fields + trusted exact-match predicates |
| Graph / RDF | visible result fields + allowed relationship/predicate set + maximum hop depth |

For vector stores, a backend must explicitly support a trusted `filters` argument before a
configured tenant filter can execute. If it cannot enforce the filter, SchemaRouter denies the call
rather than silently running an unscoped search.

For graph/RDF stores, omitting `relationship_types` does not widen access: the invoker defaults to
the principal's allowed relationship set. A configured `max_hops` also caps the implicit default.

### Security boundary

Data-scope rules only narrow the application-visible surface. They never grant database privileges.
Database-native roles, grants, row-level security, ACLs, tenant credentials, and network boundaries
remain authoritative and should be configured independently.

The first matching data-scope rule applies, mirroring capability-rule ordering. Keep broad rules
after specific employee/team/department rules.


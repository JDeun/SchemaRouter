# Principal 기반 권한 관리

SchemaRouter는 신뢰된 RBAC/ABAC claim을 capability 검색 전에 적용하고 실행 직전에 다시
검증할 수 있습니다.

SchemaRouter 자체가 identity provider가 되는 것은 아닙니다. 로그인, SSO, token 검증,
group membership, HR directory의 정본은 host application이 담당하고, 검증된 결과만
`PrincipalContext`로 전달합니다.

## 사원, 관리자, 임원

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

Authorization policy를 설정한 router에서 principal 없이 planning/retrieval을 호출하면
fail-closed합니다.

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

권한이 없는 endpoint는 ranking 전에 제외되므로 downstream model에게 금지된 tool을 보여 준 뒤
실행 단계에서만 막는 구조가 아닙니다.

실행 직전에도 다시 확인합니다.

```python
result = await router.execute(
    plan,
    config=RunConfig(principal=executive),
)
```

더 높은 권한의 principal로 만든 plan을 더 낮은 권한의 principal이 재사용할 수 없습니다.

## 부서, 팀, attribute

RBAC와 ABAC를 함께 사용할 수 있습니다.

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

서로 다른 selector category는 AND, 같은 `*_any` 안의 값은 OR로 평가합니다. Rule은 선언
순서대로 평가하며 첫 번째 match가 적용됩니다.

## 기본 정책

`AuthorizationPolicy`는 deny-by-default입니다. 어떤 rule에도 match하지 않으면 해당 route는
보이지 않고 실행할 수도 없습니다.

`authorization_policy`를 설정하지 않은 기존 router는 principal 없이도 이전 동작을 그대로
유지합니다.

## Non-disclosure 경계

권한 정책은 planning/retrieval의 추가 local availability predicate로 적용됩니다. 보이지 않는
endpoint는 "거절된 후보"로도 반환하지 않습니다. 기존 capability eligibility API 역시
host-invisible capability에는 설명을 반환하지 않습니다.

실행 단계의 authorization 오류도 어떤 role/department/team/attribute에서 실패했는지를
노출하지 않는 일반적인 denial 메시지를 사용합니다.

## Database 권한

Database onboarding은 이 principal boundary 위에 구성합니다. DB adapter는 선택된 access
scope에 허용된 table/column schema만 노출하고, row predicate는 trusted database invoker
내부에서 강제해야 합니다. Model이 전달하는 argument가 row predicate를 제거하거나 약화할 수
없어야 합니다.

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

## First-match 우선순위와 policy lint

Runtime 평가는 선언 순서를 유지하며 첫 번째로 match한 authorization/data-scope rule이
적용됩니다. 따라서 configuration loader는 뒤의 rule이 명백히 도달 불가능한 broad-before-
narrow 순서나 중복 matcher를 기본적으로 lint 오류로 처리합니다.

```python
from schemarouter import parse_authorization_policy

policy = parse_authorization_policy(policy_json)  # 기본 lint=True
```

Lint는 중복 rule name, 동일 match condition, 안전하게 증명할 수 있는 shadowing을
진단합니다. 임의 wildcard predicate의 의미를 과도하게 추론하지 않으며, rule 이름/위치는
trusted configuration surface에만 제공합니다. Runtime의 authorization denial message는 계속
의도적으로 일반적인 형태를 유지합니다. `lint=False`는 기존 ordered policy를 마이그레이션할
때 host가 순서를 별도로 검토한 경우에만 사용해야 합니다.

Compiled lookup partition은 성능을 위해 무관한 rule을 건너뛸 수 있지만 원래 선언 순서와
first-match 결과는 바꾸지 않습니다.

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

## Field, row, tenant, traversal 세부 scope

Capability authorization은 **해당 principal이 endpoint 자체를 사용할 수 있는가**를 결정합니다.
Data-scope rule은 이미 허용된 endpoint가 실제로 보여 주거나 실행할 수 있는 데이터 범위를 더
좁힙니다.

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

위 employee rule에서는 다음이 적용됩니다.

- `salary`와 `department`는 scoring 전에 model-visible retrieval schema에서 제거됩니다.
- trusted department predicate는 검증된 principal context에서 결정됩니다.
- predicate는 trusted DB invoker 내부에서 강제되며 model argument가 제거하거나 약화할 수 없습니다.
- 숨긴 field를 직접 요청하도록 위조한 stale plan도 실행 단계에서 fail-closed합니다.

`TrustedFilterBinding`은 `subject`, `role`, `department`, `team`,
`attribute:<name>`에서 값을 가져올 수 있습니다. 필요한 attribute가 없으면 fail-closed합니다.

동일한 scope contract를 DB 계열별로 다음처럼 적용합니다.

| 데이터 계열 | Scope 강제 방식 |
| --- | --- |
| SQLite / SQLAlchemy RDB | visible column + trusted equality/IN row predicate |
| Vector store | visible result/metadata field + trusted filterable metadata predicate |
| Document/search/KV/time-series | visible field + trusted exact-match predicate |
| Graph / RDF | visible result field + 허용 relationship/predicate + 최대 hop depth |

Vector backend가 trusted tenant filter를 실제로 강제하려면 명시적인 `filters` 인자를
지원해야 합니다. 지원하지 못하면 unscoped search를 실행하지 않고 호출을 거부합니다.

Graph/RDF에서 `relationship_types`를 생략해도 접근 범위가 넓어지지 않습니다. Invoker는
principal에 허용된 relationship 집합을 기본값으로 사용하고, `max_hops`도 정책 상한으로
제한합니다.

### 보안 경계

Data-scope rule은 application-visible 범위를 더 좁힐 뿐 DB 권한을 부여하지 않습니다.
DB-native role/grant/RLS/ACL, tenant credential, network boundary는 계속 최종 권한 경계이며
별도로 구성해야 합니다.

Data-scope rule도 선언 순서대로 첫 번째 match를 적용합니다. 넓은 rule은 사원/팀/부서별
구체적인 rule 뒤에 두는 것이 안전합니다.



## Authorization audit event

Enterprise host는 opt-in trusted callback을 통해 authorization 결정을 관측할 수 있습니다.
기본 이벤트에는 raw principal claim이나 trusted-filter 값이 저장되지 않습니다.

```python
from schemarouter import RunConfig, SchemaRouter

audit_events = []

router = SchemaRouter(
    authorization_policy=policy,
    authorization_audit_hook=audit_events.append,
)

result = await router.execute(
    plan,
    config=RunConfig(
        principal=employee,
        principal_audit_id="directory-user-7f3a",
    ),
)
```

`AuthorizationAuditEvent`에는 allow/deny 결과, rule/default 결정 출처, match한 rule 이름,
data-scope rule 이름, visible field 개수, trusted-filter의 **field 이름**, graph scope 요약,
tool/endpoint identity, phase, run ID가 포함됩니다. Host가 `principal_audit_id`를 제공하면
그 opaque identifier도 같은 이벤트에 포함됩니다.

Host가 run ID를 지정하지 않으면 runtime이 생성합니다. LangChain/LlamaIndex export는 export
결정과 실제 execution 결정에 같은 run ID를 재사용하므로, trusted audit sink에서 두 경계를
연결해 볼 수 있고 raw `PrincipalContext`를 넘길 필요는 없습니다.

기본값에서는 audit hook이 꺼져 있습니다. SchemaRouter는 subject, role, department, team,
principal attribute, resolved trusted-filter 값을 자동 저장하지 않습니다. Host가 별도 audit
sink에 추가 identity 정보를 기록한다면 그 sink 자체가 host의 trusted security boundary가
됩니다.

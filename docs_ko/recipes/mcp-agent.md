# MCP 에이전트 실행 경계

애플리케이션이 MCP 서버에서 기능을 탐색하되 원격 서버의 주석(annotation)을 실행 권한의 근거로 받아들이지 않으려는 경우에 사용하는 패턴입니다. 원 논문 중심의 개발 패키지는 카탈로그 전체에 대한 Lexical 랭킹이나 점수 기반 실행 연결 대신 명시적으로 설정한 Algorithm 1 계획과 등록된 Executor를 사용합니다.

```python
from schemarouter import PaperPlanRequest, RunConfig, SchemaRouter

router = await SchemaRouter.from_url(
    "http://localhost:8000/mcp",
    kind="mcp",
)
```

등록은 호출을 승인하지 않습니다. 소유자가 검토한 개념 카탈로그를 사용해 필드 라우팅 세션을 준비합니다. `configure_field_routing`에 스키마 독립적인 Understand 모델, 검토된 Intent/FieldGroup 선언, 해당 세션의 스냅샷에 결속된 원 논문 Rank 정책을 설정합니다. 오프라인 예제 `examples/quickstart.py`는 실제 모델 없이 이 설정을 보여 줍니다.

## 운영 환경에서의 주의사항

`allow_unclassified_remote=True`는 허용 범위가 넓은 설정으로, 이 예제에서는 활성화하지 않습니다. 읽기 도구와 쓰기 도구가 혼재하는 운영 환경에서는 신뢰 가능한 로컬 분류를 적용하거나 권한 도메인별로 MCP 서버를 분리해야 합니다. 원격 서버 자체의 주석을 부작용 발생 여부의 최종 판단 근거로 신뢰하지 않습니다. 애플리케이션이 신뢰된 Principal과 명시적으로 승인한 원천별 파라미터를 제공해야 하며, 모델이 제안했다는 이유만으로 제안값이 승인된 파라미터가 되지는 않습니다.

## 선택적 No-match 실행 차단

과거 보정 점수 기반 `RetrievalAbstentionPolicy`, `ainvoke_selective`, `execute_selective_plan` API는 개발 배포 패키지에서 제거되었습니다. 기존 비교 구현과 fail-closed 실행 테스트는 소스 체크아웃의 `scripts/research_legacy_planning/`에 보존되며 Algorithm 1의 fallback이 아닙니다.

필드 라우팅 세션을 설정한 뒤 원 논문의 계획과 실행에 동일한 신뢰된 Principal을 사용합니다.

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

준비된 진단 결과 자체가 실행 권한을 부여하지는 않습니다. 발급된 계획의 로컬 witness는 원래 원천의 리비전, Principal, 필드 커버리지, 호출 내용의 불변성 및 바인딩 준비 상태를 다시 검증합니다. 등록된 Executor는 계속 현재 정책을 적용하고 실제 인수 및 출력을 검증합니다. 보편적인 점수 임계값이나 독립적으로 보정된 open-set 성능을 주장하지 않습니다. 과거 점수 기반 후보 목록의 테스트는 기존 범위, 출처, fallback 및 호출 차단 검증을 보존합니다.

# LangChain

SchemaRouter는 LangChain 런타임의 대체제가 아니라 선택적으로 추가할 수 있는 실행 경계로 통합됩니다.

## 설치

배포 패키지를 사용하는 경우:

```bash
pip install "schemarouter[langchain]"
```

저장소에서 직접 개발하는 경우:

```bash
pip install -e ".[dev,langchain]"
```

핵심 패키지는 LangChain에 의존하지 않습니다.

## 기존 LangChain 도구 가져오기

기존 LangChain `BaseTool` 또는 `StructuredTool` 객체를 SchemaRouter의 정본 기능 모델로 컴파일하여 일반적인 실행 파이프라인에 연결할 수 있습니다.

```python
from langchain_community.tools import DuckDuckGoSearchRun
from schemarouter import SchemaRouter

router = SchemaRouter()
key = router.add_langchain_tool(
    DuckDuckGoSearchRun(),
    provider="duckduckgo",
    read_only=True,
    remote=True,
)
```

가져오기 기능은 도구가 선언한 입력 스키마를 읽고, 출력 스키마가 선언되어 있으면 그것도 사용합니다. 구조화된 결과 목록은 레코드 형태를 보존합니다. 예를 들어 `results: list[{title, url}]`의 항목이 선언되어 있으면 `results[].title`과 `results[].url` 필드를 서로 무관한 배열로 분리하지 않고 그대로 노출할 수 있습니다.

도구 설명을 근거로 읽기·쓰기 권한을 **추론하지 않습니다**. `read_only`, `destructive`, `remote`, `provider`, `access_mode`는 신뢰된 로컬 환경에서 분류해야 합니다.

이 방식은 공급자별로 SchemaRouter 전용 어댑터를 하나씩 작성하지 않아도 기존 LangChain 생태계의 도구를 SchemaRouter 기능으로 사용할 수 있게 합니다. 웹 검색, 학술 검색, 금융, 데이터베이스, SaaS 도구 등이 해당합니다.

## 등록된 엔드포인트 내보내기

```python
from schemarouter.integrations import to_langchain_tools

tools = to_langchain_tools(router)
```

등록된 각 엔드포인트는 SchemaRouter 입력 스키마를 유지하는 LangChain `StructuredTool`이 됩니다.

엔드포인트 하나만 내보내려면:

```python
from schemarouter.integrations import to_langchain_tool

tool = to_langchain_tool(
    router,
    "weather",
    "current",
)
```

`AuthorizationPolicy`를 구성했다면 호스트 애플리케이션에서 검증한 동일한 신뢰 실행 설정을 전달합니다.

```python
from schemarouter import PrincipalContext, RunConfig

employee = PrincipalContext(
    subject="alice",
    roles=("employee",),
    attributes={"department": "sales"},
)

tools = to_langchain_tools(
    router,
    run_config=RunConfig(principal=employee),
)
```

Principal에게 노출이 허가된 엔드포인트만 내보냅니다. LangChain에 도구 스키마를 제공하기 전에 DataScope에 따른 필드·파라미터 투영을 적용합니다. 호출은 `SchemaRouter.execute(..., config=...)`로 다시 들어오기 때문에 신뢰된 행·테넌트 필터와 실행 시점 권한 관리가 유지됩니다.

## 실시간 내보내기 계약

`StructuredTool`은 내보낸 시점에 해당 주체에게 허가된 엔드포인트 스키마를 캡처합니다. 호출할 때마다 SchemaRouter가 현재 엔드포인트를 다시 해석하고 권한 및 DataScope 보기를 재적용합니다. 스키마, 도구 지문 또는 허가된 투영 계약이 변경되었다면 실행 전에 `StaleExportedToolError`로 실패합니다.

스키마를 새로고침하거나 권한 정책이 변경된 경우에는 `to_langchain_tool(...)`을 통해 다시 내보내거나 `to_langchain_tools(...)`로 카탈로그를 재구성하십시오. 오래된 프레임워크 에이전트가 이전보다 권한이 넓거나 다른 라이브 계약을 조용히 실행하는 일을 막습니다.

## 실행 가능한 예제

저장소에 최소한의 실행 가능한 통합 예제가 있습니다.

```bash
python examples/langchain_quickstart.py
```

CI에서는 별도의 통합 테스트 외에도 이 예제를 실행해 문서의 연동 방법이 계속 동작하는지 확인합니다.

## 실행은 계속 SchemaRouter를 경유합니다

이 통합은 원래 전송 계층을 직접 호출하지 **않습니다**.

```text
LangChain StructuredTool
 -> SchemaRouter ToolCall
 -> current schema validation
 -> AuthorizationPolicy / DataScope
 -> ExecutionPolicy
 -> binding-drift check
 -> trusted invoker
 -> output validation
```

따라서 LangChain 에이전트도 SchemaRouter를 직접 사용하는 경우와 같은 안전하게 거부하는 실행 계약의 보호를 받습니다.

## 책임 분리

권장하는 책임 구성은 다음과 같습니다.

| 관심 영역 | 담당 주체 |
| --- | --- |
| 에이전트 그래프 및 대화 | LangChain 또는 LangGraph |
| 모델 호출 | 상위 프레임워크·애플리케이션 |
| 도구 카탈로그 스키마 | SchemaRouter |
| 엔드포인트·인자·필드 실행 계획 | SchemaRouter |
| 부작용 정책 | SchemaRouter 로컬 정책 |
| 도구 실행 검증 | SchemaRouter |
| 체크포인트 및 메모리 | 상위 프레임워크 |

통합을 위해 SchemaRouter가 그래프 런타임을 중복 구현해서는 안 됩니다.

직접적인 `StateGraph` 통합은 [LangGraph](langgraph.md) 문서를 참고하십시오.

## 패키징

현재 브리지는 기본 배포판의 `langchain` extra로 유지합니다. 별도의 `langchain-schemarouter` 패키지는 독립적인 릴리스 주기, 의존성 부담의 실질적 증가, 상위 생태계의 요구가 있을 때까지 보류합니다.

지원 범위와 유지보수 정책은 [호환성 테스트](../compatibility.md)를 참고하십시오.

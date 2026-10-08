# LlamaIndex 통합

SchemaRouter는 자체 스키마 검증과 실행 경계를 유지하면서 등록된 엔드포인트를 LlamaIndex 도구로 노출할 수 있습니다.

## 설치

배포된 패키지를 사용하는 경우 선택적 추가 의존성(extra)을 설치합니다.

```bash
pip install "schemarouter[llamaindex]"
```

이 연동 기능은 현재 SchemaRouter 배포판에 `llamaindex` 선택적 extra로 포함됩니다.

저장소에서 직접 개발하는 경우:

```bash
pip install -e ".[dev,llamaindex]"
```

## 기존 LlamaIndex 도구 가져오기

LlamaIndex `BaseTool` / `FunctionTool`과 유사한 객체도 직접 등록할 수 있습니다.

```python
router = SchemaRouter()
key = router.add_llamaindex_tool(
    llama_tool,
    provider="scholarly-search",
    read_only=True,
    remote=True,
)
```

SchemaRouter는 입력 계약을 얻기 위해 `ToolMetadata.get_parameters_dict()` 또는 선언된 `fn_schema`를 읽습니다. 타입이 있는 `FunctionTool` 객체라면 반환 타입 애너테이션도 안전하게 표현할 수 있는 범위에서 출력 JSON Schema로 보존합니다.

타입이 지정된 목록 반환값은 네이티브 어댑터와 동일한 **레코드 보존형 항목-필드 계약**을 사용합니다. 반환 스키마에 해당 항목 속성이 선언되어 있다면 `results: list[Hit]` 같은 반환값에서 `results[].title` 등의 필드를 노출할 수 있습니다.

가져온 도구에도 SchemaRouter 정책, 지문(fingerprint), 검증, 폴백, 상태(health), 관측 가능성 정책이 적용됩니다. 도구 메타데이터 자체에는 실행 권한이 없습니다.

## 등록된 엔드포인트 내보내기

단일 엔드포인트 또는 선택한 카탈로그를 변환할 수 있습니다.

```python
from schemarouter.integrations import to_llamaindex_tool, to_llamaindex_tools

tool = to_llamaindex_tool(router, "materials", "search")
tools = to_llamaindex_tools(router)
```

기업용 권한 관리가 켜져 있다면 신뢰할 수 있는 principal과 함께 내보냅니다.

```python
from schemarouter import PrincipalContext, RunConfig

employee = PrincipalContext(
    subject="alice",
    roles=("employee",),
    attributes={"department": "sales"},
)

tools = to_llamaindex_tools(
    router,
    run_config=RunConfig(principal=employee),
)
```

내보낸 카탈로그에는 해당 principal에게 허용된 엔드포인트만 포함됩니다. DataScope 투영은 LlamaIndex에 공개되는 스키마에서 숨겨진 필드와 파라미터를 제거합니다. 도구 호출은 `SchemaRouter.execute(..., config=...)`로 다시 들어오므로 실행 시점에도 권한 관리와 신뢰된 데이터 필터를 재적용합니다.

## 실시간 내보내기 계약

`FunctionTool`은 내보내기 시점에 허가된 엔드포인트 스키마를 캡처합니다. 각 호출 직전 SchemaRouter는 해당 엔드포인트를 다시 찾고 권한을 재확인합니다. 엔드포인트 스키마, 도구 지문 또는 허가된 DataScope 투영이 변경되었다면 실행 전에 `StaleExportedToolError`로 실패합니다.

스키마를 새로고침하거나 권한 정책이 변경된 경우에는 `to_llamaindex_tool(...)`을 다시 호출하거나 `to_llamaindex_tools(...)`로 카탈로그를 재생성해야 합니다. 이미 내보낸 LlamaIndex 스키마가 다른 라이브 기능에 조용히 재바인딩되는 일은 허용하지 않습니다.

## 실행 가능한 예제

저장소에는 실행 가능한 최소 통합 예제가 포함되어 있습니다.

```bash
python examples/llamaindex_quickstart.py
```

CI에서는 이 예제를 통합 계약 테스트와 함께 실행합니다.

## 실행 경계

어댑터의 역할은 최소한으로 제한됩니다. LlamaIndex는 에이전트 및 워크플로 오케스트레이션을 책임지고, SchemaRouter는 등록된 스키마 식별성, 정책, 검증, 바인딩 확인, 엔드포인트 실행을 책임집니다.

연동 기능이 LlamaIndex의 메타데이터에 SchemaRouter 실행 정책을 제어할 권한을 부여하지 않습니다.

## 패키징

현재 연동 기능은 기본 배포판의 `llamaindex` extra 안에 유지합니다. 별도 패키지 분리는 연동 기능만의 릴리스 주기가 필요하거나 의존성 부담이 실질적으로 커지거나 상위 프로젝트 유지보수 담당자가 독립 배포판을 요구할 때에만 고려합니다.

지원 범위와 유지보수 정책은 [호환성 테스트](../compatibility.md)를 참고하십시오.

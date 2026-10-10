# 도구와 엔드포인트 계약

스키마 모델은 구성 요소를 명시적으로 구분합니다.

```text
ToolSpec
  └─ EndpointSpec
       ├─ ParameterSpec
       ├─ FieldSpec
       ├─ input_schema
       └─ output_schema
```

## ToolSpec

`ToolSpec`은 관련 작업을 하나로 묶습니다. 네임스페이스를 사용하면 서로 다른 기능 제공원에서 온 도구를 구분할 수 있습니다.

```python
ToolSpec(
    name="materials",
    namespace="lab",
    endpoints=[...],
)
```

이 경우 레지스트리 키는 `lab.materials`가 됩니다.

## EndpointSpec

엔드포인트는 호출할 수 있는 하나의 작업을 나타냅니다. 어댑터에 따라 다음 중 하나에 대응할 수 있습니다.

- OpenAPI 작업
- MCP 도구
- Python callable
- 검토 후 승인한 문서 기반 엔드포인트

엔드포인트의 식별 정보에는 HTTP 메서드·경로 메타데이터, 부작용 분류, 파라미터 계약, 출력 계약, 스키마 지문이 포함됩니다.

## ParameterSpec

파라미터는 **논리적인 인자 키**와 실제 전송 형식을 구분합니다. 같은 전송 이름이 서로 다른 위치에 합법적으로 존재할 수 있는 OpenAPI 작업에서 중요한 구분입니다.

예를 들어 이름 충돌은 다음처럼 표현할 수 있습니다.

```text
path__id   -> path parameter "id"
query__id  -> query parameter "id"
header__id -> header parameter "id"
body__id   -> JSON body field "id"
```

플래너와 실행기는 논리적인 키를 사용하고, 전송 계층은 원래의 전송 이름을 사용합니다.

## FieldSpec

플래너는 최상위 출력 필드로 응답 필드 투영을 계획합니다. 중첩 구조와 로컬 참조를 포함하는 완전한 출력 JSON Schema는 원시 응답 검증을 위해 계속 유지합니다.

## 지문(Fingerprints)

엔드포인트와 도구 지문은 실행 가능한 스키마 계약의 정규 해시입니다. 설명용 메타데이터는 지문 계산에서 제외됩니다.

오래된 계획은 다른 엔드포인트 지문을 가진 계약에 대해 실행할 수 없고, 오래된 invoker 바인딩은 도구 계약이 교체된 뒤에 실행할 수 없습니다.

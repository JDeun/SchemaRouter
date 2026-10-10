# 필드 투영(Field projection)

SchemaRouter는 어떤 필드 투영을 적용하기 전에 **원시 도구 출력 전체를 검증**합니다. 따라서 투영을 통해 잘못된 응답을 숨길 수 없습니다.

## 최상위 필드

기본 필드 계약은 기존과 같습니다.

```python
from schemarouter import FieldSpec

FieldSpec(name="temperature")
```

명시적인 경로를 지정하지 않으면 해당 필드는 같은 이름의 최상위 키를 투영합니다.

## 중첩 객체 필드

논리적 필드 ID를 중첩된 JSON 객체 경로에 매핑할 때는 `FieldSpec.path`를 사용합니다.

```python
FieldSpec(
    name="display_name",
    path=["user", "profile", "name"],
    aliases=["name", "profile name"],
)
```

논리적 ID는 계속 `display_name`입니다. 계획에서는 임의의 JSONPath가 아니라 이 선언된 ID를 선택합니다.

```python
call.fields == ["display_name"]
```

다음과 같은 원시 응답을 받았다고 가정합니다.

```json
{
  "user": {
    "id": "42",
    "profile": {
      "name": "Ada",
      "address": {
        "city": "Seoul",
        "secret": "internal"
      }
    }
  }
}
```

투영된 결과는 선언된 객체 구조를 유지합니다.

```json
{
  "user": {
    "profile": {
      "name": "Ada"
    }
  }
}
```

## 보안 경계

`FieldSpec.path`는 신뢰할 수 있는 스키마 메타데이터입니다. 모델이 생성한 실행 권한이 아닙니다.

SchemaRouter는 다음을 보장합니다.

- `ToolCall.fields`에는 선언된 논리적 필드 ID만 허용합니다.
- 선언된 필드 ID가 아닌, 위조된 경로 문자열을 거부합니다.
- 선언된 경로 사이의 중복 또는 조상·자손 겹침을 거부합니다.
- 중첩값을 추출하기 전에 원시 출력 전체를 스키마로 검증합니다.
- 투영된 값을 복사하므로 소비자가 투영 결과를 수정해도 원래 invoker 결과는 변경되지 않습니다.
- 호출 인식 invoker가 전송 계층 필드 투영을 제공하더라도 명시적인 중첩 경로가 있으면 로컬 투영을 강제합니다.

## 플래너 동작

플래너의 매칭은 논리 필드 이름, 별칭(alias), 명시적인 경로 구간을 고려합니다. 그래도 출력되는 `ToolCall.fields`에는 논리적 필드 ID만 포함됩니다.

이렇게 전송·스키마 표현과 범위가 제한된 의사결정 표면을 분리합니다.

## 배열 항목 필드

배열 순회는 명시적으로 지정하며 레코드의 대응 관계를 보존합니다. 예약된 `"*"` 경로 구간은 신뢰할 수 있는 `FieldSpec.path` 및 `result_path` 메타데이터에서만 사용하십시오.

```python
FieldSpec(
    name="results[].title",
    path=["results", "*", "title"],
    result_path=["results", "*", "title"],
    json_schema={"type": "string"},
)
```

`results[].title`과 `results[].url`을 함께 선택해도 각 원천 레코드가 보존됩니다.

```json
{
  "results": [
    {"title": "A", "url": "https://a.example"},
    {"title": "B"}
  ]
}
```

SchemaRouter는 자식 필드들을 서로 독립된 배열로 평탄화하지 않습니다. 그렇게 하면 행이나 개체의 대응 관계가 깨질 수 있습니다. 선택적인 자식 필드가 없다면 해당 레코드에서만 누락된 상태를 유지합니다.

와일드카드 배열 경로에는 더 엄격한 불변 조건이 적용됩니다.

- 원천 경로에 명시적인 `result_path`가 있어야 합니다.
- 원천·결과 경로의 와일드카드 위치가 일치해야 합니다.
- 와일드카드는 JSON Schema에 선언된 배열만 순회합니다.
- 서버 측 투영 스키마는 배열의 `items`를 통해 축소됩니다.
- 단위 정규화 및 선택된 필드 검증은 보존된 각 레코드에 적용됩니다.
- 부모 배열을 선택하더라도 모든 하위 필드가 자동으로 선택되지는 않습니다.

`"*"` 구간은 내부의 타입 기반 경로 표시자이며, 모델이 제공한 임의의 JSONPath 문법이 아닙니다.

## 현재 지원 범위

명시적인 경로는 중첩 객체와 레코드 관계를 보존하는 배열 항목 순회를 지원합니다. 일반 JSONPath 표현식, 필터, 슬라이스, 추론된 와일드카드 순회는 지원하지 않습니다.

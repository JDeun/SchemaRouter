# Field projection

SchemaRouter는 projection을 적용하기 전에 전체 raw tool output을 검증합니다. 따라서 projection으로 invalid response를 숨길 수 없습니다.

## Top-level field

기본 field contract는 그대로 유지됩니다:

```python
from schemarouter import FieldSpec

FieldSpec(name="temperature")
```

명시적 path가 없으면 동일한 이름의 top-level key를 projection합니다.

## Nested object field

logical field ID를 nested JSON object path에 매핑하려면 `FieldSpec.path`를 사용합니다:

```python
FieldSpec(
    name="display_name",
    path=["user", "profile", "name"],
    aliases=["name", "profile name"],
)
```

logical ID는 `display_name`으로 유지됩니다. plan은 임의 JSONPath 대신 이 선언된 ID를 선택합니다:

```python
call.fields == ["display_name"]
```

다음 raw response가 주어지면:

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

projected result는 선언된 object shape를 보존합니다:

```json
{
  "user": {
    "profile": {
      "name": "Ada"
    }
  }
}
```

## Security boundary

`FieldSpec.path`는 trusted schema metadata이며 model이 생성하는 execution authority가 아닙니다.

SchemaRouter는 다음을 보장합니다:

- `ToolCall.fields`에는 선언된 logical field ID만 허용합니다;
- 선언된 field ID가 아닌 위조 path 문자열을 거부합니다;
- 중복되거나 조상·자손 관계로 겹치는 선언 path를 거부합니다;
- nested value 추출 전에 전체 raw output schema를 검증합니다;
- projection result를 통해 원래 invoker result가 변경되지 않도록 값을 복사합니다;
- call-aware invoker가 transport-level field projection을 제공하더라도 명시적 nested path가 있으면 local projection을 강제합니다.

## Planner 동작

planner matching은 logical field name, alias, explicit path segment를 고려합니다. 생성된 `ToolCall.fields`에는 여전히 logical field ID만 포함됩니다.

이를 통해 transport/schema representation과 bounded decision surface를 분리합니다.

## Array-item field

array traversal은 명시적이며 record를 보존합니다. 예약된 `"*"` path segment는 trusted `FieldSpec.path` / `result_path` metadata에서만 사용합니다:

```python
FieldSpec(
    name="results[].title",
    path=["results", "*", "title"],
    result_path=["results", "*", "title"],
    json_schema={"type": "string"},
)
```

`results[].title`과 `results[].url`을 함께 선택해도 각 source record를 보존합니다:

```json
{
  "results": [
    {"title": "A", "url": "https://a.example"},
    {"title": "B"}
  ]
}
```

SchemaRouter는 row/entity alignment를 훼손할 수 있으므로 child를 독립 array로 flatten하지 않습니다. 누락된 optional child는 해당 record에서도 누락 상태로 유지됩니다.

wildcard array path에는 더 엄격한 invariant가 적용됩니다:

- source path는 명시적인 `result_path`를 선언해야 합니다;
- source와 result path의 wildcard 위치가 같아야 합니다;
- wildcard는 선언된 JSON Schema array만 순회합니다;
- server-projected schema는 array `items`를 통해 좁혀집니다;
- unit normalization과 selected-field validation은 보존된 record별로 적용됩니다;
- 상위 array를 선택해도 모든 하위 field가 자동 선택되지는 않습니다.

`"*"` segment는 내부 typed path marker이며 model이 제공하는 임의 JSONPath syntax가 아닙니다.

## 현재 범위

explicit path는 nested object와 명시적인 record-preserving array-item traversal을 지원합니다. 일반 JSONPath expression, filter, slice, inferred wildcard traversal은 지원하지 않습니다.

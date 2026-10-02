# Field projection

SchemaRouter는 projection 전에 전체 raw tool output을 검증합니다. 따라서 projection으로 invalid response를 숨길 수 없습니다.

## 최상위 field

명시적 path가 없으면 `FieldSpec(name="temperature")`는 같은 이름의 top-level key를 projection합니다.

## Nested object field

logical field ID를 nested JSON path에 매핑하려면 `FieldSpec.path`를 사용합니다.

```python
FieldSpec(
    name="display_name",
    path=["user", "profile", "name"],
    aliases=["name", "profile name"],
)
```

logical ID는 `display_name`으로 유지되며 plan은 임의 JSONPath가 아니라 이 선언 ID를 선택합니다. projection 결과도 선언된 object shape를 보존합니다.

## 보안 경계

`FieldSpec.path`는 trusted schema metadata입니다. model이 만든 execution authority가 아닙니다. SchemaRouter는 `ToolCall.fields`에서 선언된 logical field ID만 허용하고, 선언되지 않은 forged path와 중복/ancestor-descendant overlap path를 거부합니다. nested value 추출 전 전체 raw output schema를 검증하고 projected value를 복사합니다.

## Array-item field

array traversal은 명시적이고 record-preserving입니다. trusted `FieldSpec.path`/`result_path` metadata에서만 reserved `"*"` segment를 사용합니다.

```python
FieldSpec(
    name="results[].title",
    path=["results", "*", "title"],
    result_path=["results", "*", "title"],
    json_schema={"type": "string"},
)
```

`results[].title`과 `results[].url`을 함께 선택하면 각 source record의 정렬을 유지합니다. child를 독립적인 parallel array로 평탄화하지 않습니다.

wildcard는 explicit `result_path`가 필요하고 source/result path의 같은 위치에 있어야 하며 선언된 JSON Schema array만 통과합니다. `"*"`는 model이 제공하는 임의 JSONPath syntax가 아니라 내부 typed path marker입니다.

## 현재 범위

nested object와 명시적 record-preserving array-item traversal을 지원합니다. 일반 JSONPath expression/filter/slice와 추론된 wildcard traversal은 지원하지 않습니다.

# Tool과 endpoint contract

스키마 모델은 명시적입니다.

```text
ToolSpec
  └─ EndpointSpec
       ├─ ParameterSpec
       ├─ FieldSpec
       ├─ input_schema
       └─ output_schema
```

## ToolSpec

`ToolSpec`은 관련 operation을 묶습니다. namespace를 사용하면 서로 다른 원본의 tool을 구분할 수 있습니다.

```python
ToolSpec(
    name="materials",
    namespace="lab",
    endpoints=[...],
)
```

registry key는 `lab.materials`가 됩니다.

## EndpointSpec

endpoint는 호출 가능한 하나의 operation입니다. adapter에 따라 OpenAPI operation, MCP tool, Python callable, 승인된 문서 기반 endpoint 등이 될 수 있습니다.

endpoint identity에는 method/path metadata, side-effect 분류, parameter contract, output contract, schema fingerprint가 포함됩니다.

## ParameterSpec

parameter는 **logical argument key**와 wire representation을 구분합니다. 같은 wire name이 여러 위치에 합법적으로 존재할 수 있는 OpenAPI operation에서 중요합니다.

```text
path__id   -> path parameter "id"
query__id  -> query parameter "id"
header__id -> header parameter "id"
body__id   -> JSON body field "id"
```

planner와 executor는 logical key를 사용하고 transport가 원래 wire name을 기록합니다.

## FieldSpec

최상위 output field는 planner의 response projection에 사용됩니다. 중첩 구조와 local ref를 포함한 전체 output JSON Schema는 raw response validation을 위해 그대로 유지됩니다.

## Fingerprint

endpoint/tool fingerprint는 실행 가능한 schema contract의 canonical hash입니다. descriptive metadata는 fingerprint에서 제외됩니다.

오래된 plan은 다른 endpoint fingerprint에 대해 실행될 수 없으며, tool contract가 교체된 뒤에는 오래된 invoker binding도 실행될 수 없습니다.

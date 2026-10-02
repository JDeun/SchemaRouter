# LlamaIndex 통합

SchemaRouter는 schema validation과 execution boundary를 유지하면서 등록 endpoint를 LlamaIndex tool로 노출할 수 있습니다.

## 설치

```bash
pip install "schemarouter[llamaindex]"
```

## 기존 LlamaIndex tool 가져오기

`BaseTool` / `FunctionTool` 계열 object를 `router.add_llamaindex_tool(...)`로 직접 등록할 수 있습니다. `ToolMetadata.get_parameters_dict()` 또는 declared `fn_schema`에서 input contract를 읽고 typed `FunctionTool`의 return annotation도 안전하게 표현 가능한 경우 output JSON Schema로 보존합니다.

typed list result는 native adapter와 같은 record-preserving item-field contract를 사용합니다. imported tool에도 SchemaRouter policy, fingerprint, validation, fallback, health, observability가 적용되며 metadata가 execution authority를 부여하지 않습니다.

## 등록 endpoint 내보내기

`to_llamaindex_tool(router, "materials", "search")`, `to_llamaindex_tools(router)`를 사용할 수 있습니다. repository의 `examples/llamaindex_quickstart.py`를 CI에서 integration contract test와 함께 실행합니다.

LlamaIndex는 agent/workflow orchestration을, SchemaRouter는 registered schema identity/policy/validation/binding/execution을 담당합니다. bridge는 현재 main distribution의 optional `llamaindex` extra로 유지합니다.

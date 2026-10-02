# OpenAPI 호환성 보고서

SchemaRouter는 제한된 OpenAPI subset을 가져옵니다. 지원하지 않는 semantics는 조용히 재해석하지 않고 명시적으로 보여야 합니다.

가져온 모든 OpenAPI `ToolSpec`에는 `tool.metadata["compatibility"]`에 machine-readable report가 있습니다. 등록 전 `analyze_openapi_compatibility(document)`로 검사할 수도 있습니다.

## 상태 값

- `supported`: 가져온 surface에서 알려진 호환성 제한을 찾지 못함
- `partial`: 일부 construct가 보존되거나 부분적으로만 해석됨
- `unsupported`: operation은 있지만 안전하게 가져올 수 있는 것이 없음

report에는 전체/importable operation 수와 issue 수도 포함됩니다.

## 명시적으로 보고하는 construct

unresolved cross-document `$ref`, `allOf`/`oneOf`/`anyOf`, recursive local component reference, OpenAPI 3.0 `nullable`, discriminator, cookie parameter, multiple content type, non-JSON body, non-object JSON request body, callback/webhook, server variable, operation security requirement 등을 보고합니다.

일부 construct는 전체 JSON Schema를 runtime validation에 보존하지만 planner-side 해석은 제한적이므로 `partial`입니다. `allOf`는 안전하게 도출할 수 있는 object property와 required field를 평탄화하지만 모든 JSON Schema composition 상호작용을 완전히 지원한다고 주장하지 않습니다.

## Parsing과 분리하는 이유

parser가 `ToolSpec` 생성에 성공했더라도 호출자에게 중요한 semantics를 잃을 수 있습니다. compatibility report는 “SchemaRouter가 무엇을 충실히 이해했고 무엇을 애플리케이션이 명시적으로 검토해야 하는가?”에 답합니다.

bounded external-ref resolution이 성공하면 report 생성 전에 local bundle pointer로 다시 쓰므로 더 이상 `external_ref` issue로 나타나지 않습니다. `partial`을 자동 오류로 취급하지 말고 실제 노출할 operation에 영향을 주는지 검토하세요.

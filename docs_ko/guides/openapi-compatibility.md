# OpenAPI compatibility report

SchemaRouter는 bounded OpenAPI subset을 import합니다. 지원하지 않는 semantic은 조용히 재해석하지 않고 명시적으로 보여야 합니다.

import된 모든 OpenAPI `ToolSpec`은 다음 위치에 machine-readable report를 포함합니다:

```python
tool.metadata["compatibility"]
```

등록 전에 document를 검사할 수도 있습니다:

```python
from schemarouter import analyze_openapi_compatibility

report = analyze_openapi_compatibility(document)

print(report.status)
for issue in report.issues:
    print(issue.support, issue.construct, issue.location, issue.message)
```

## Status 값

- `supported` — import된 surface에서 알려진 compatibility limitation이 감지되지 않음
- `partial` — 하나 이상의 construct가 보존되거나 일부만 해석됨
- `unsupported` — document에 operation은 있지만 안전하게 import할 수 있는 것이 없음

report에는 전체/importable operation 수와 issue 수도 포함됩니다.

## 명시적으로 보고하는 construct

현재 analyzer는 다음 사례 등을 보고합니다:

- unresolved cross-document `$ref` target (bounded same-origin resolution은 explicit URL-ingestion opt-in에서만 제공되며 same-document URI ref는 자동 normalize됨)
- `allOf`, `oneOf`, and `anyOf`;
- recursive local component references;
- OpenAPI 3.0 `nullable`;
- discriminators;
- cookie parameters;
- multiple request/response content types;
- non-JSON request or response bodies;
- non-object JSON request bodies;
- callbacks and webhooks;
- server variables;
- operation security requirements.

일부 construct는 planner-side interpretation이 bounded하더라도 runtime validation용 full JSON Schema를 유지하므로 `partial`로 표시됩니다. `allOf`의 경우 안전하게 도출할 수 있을 때 object property와 required field를 flatten하지만 모든 JSON Schema composition interaction을 완전히 지원한다고 주장하지 않습니다.

## Parsing과 분리하는 이유

parser가 `ToolSpec` 생성에 성공하더라도 caller에게 중요한 semantic을 잃을 수 있습니다. compatibility report는 다른 질문에 답합니다:

> "SchemaRouter가 정확히 이해한 것은 무엇이며, 어떤 부분에 명시적인 application review가 필요한가?"

bounded external-ref resolution이 성공하면 report 생성 전에 해당 reference를 local bundle pointer로 다시 쓰므로 더 이상 `external_ref` issue로 나타나지 않습니다.

`partial` report를 자동으로 error로 취급하지 않습니다. 보고된 construct를 검사하고 application이 노출하려는 operation에 영향을 주는지 판단합니다.

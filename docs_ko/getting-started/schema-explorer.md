# Capability Explorer

SchemaRouter의 **Capability Explorer**는 등록된 typed capability catalog를 위한 read-only 문서 화면입니다. 프로토콜에 종속되지 않으며 OpenAPI, MCP, GraphQL, OData, OpenRPC, OPTIMADE, Python, SDK-bound tool, 선언형 HTTP capability를 동일한 contract model로 보여줍니다.

## 영속 registry에서 정적 Explorer 생성

```bash
schemarouter explorer \
  --registry ./schemarouter-registry.sqlite3 \
  --output ./schema-explorer.html
```

생성되는 HTML은 self-contained이며 원격 JavaScript, CSS, font 또는 다른 asset을 불러오지 않습니다.

Explorer에는 다음 정보가 포함됩니다.

- tool/provider/adapter/source provenance
- schema와 endpoint fingerprint
- read-only / mutating / destructive 분류
- credential 값이 제외된 authentication requirement
- 매개변수·전송 형식의 이름·위치·직렬화 의미·JSON Schema
- 전체 input/output schema
- 출력 의미 ID·단위·정규화 계약·한정 조건·투영 경로
- tool, endpoint, provider, field, semantic ID, unit, method, mode 통합 검색

문서에 포함된 example credential이나 다른 sample secret이 우발적으로 공개되지 않도록 schema의 `default` / `example` / `examples` 값은 Explorer 문서에서 제외됩니다. 임의의 ToolSpec metadata도 복사하지 않습니다.

## Python API

```python
from schemarouter import (
    build_capability_explorer_document,
    render_schema_explorer,
)

document = build_capability_explorer_document(router.registry)
html = render_schema_explorer(document)
```

privacy-safe한 live binding, health, schema-watch 상태를 포함하려면 다음과 같이 사용합니다.

```python
document = build_capability_explorer_document(
    router.registry,
    live=router.inspect(),
)
```

Explorer는 canonical ToolSpec contract와 기존 privacy-safe `RouterInspection` snapshot만 사용합니다. live invoker, credential, HTTP client, subprocess handle 또는 임의의 trace payload 값을 읽지 않습니다.

## 보안 경계

Explorer는 문서 기능일 뿐입니다.

Swagger의 "Try it out"과 같은 실행 버튼을 제공하지 **않습니다**. Tool 실행에는 계속 SchemaRouter의 일반적인 planning, validation, policy, approval, binding 검사가 필요합니다.

기존 운영 dashboard와 Explorer는 별도 기능입니다.

- **dashboard**: runtime/registry/run 운영 현황
- **explorer**: 상세 capability contract 문서

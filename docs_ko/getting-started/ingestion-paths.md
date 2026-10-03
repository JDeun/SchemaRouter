# 입력 방식 선택

가능하면 가장 권위 있는 스키마 원본을 사용하세요. SchemaRouter는 모든 입력을 **동일하게 취급하지 않습니다**.

사용자가 protocol 세부사항보다 **provider 이름**을 알고 있다면 먼저 `router.add_provider(...)`를
사용하세요. `ProviderProfile`이 provider를 알려진 OpenAPI, OPTIMADE, HTTP/JSON, SDK access
method로 해석한 뒤 기존 protocol-neutral ingestion pipeline에 위임합니다. Provider-specific
planner가 아니라 onboarding 편의 계층입니다.

| 원본 | 등록 | 실행 바인딩 | 신뢰 수준 |
| --- | --- | --- | --- |
| 알려진 provider profile | provider identity를 선언된 access method로 해석 | method별 기존 binding 규칙 | profile metadata는 trusted local configuration, credential은 process-local |
| 타입이 지정된 Python callable | 자동 | 자동 | 로컬 코드 |
| OpenAPI 3.x | 일반적인 하위 집합 자동 지원 | 동일 origin은 자동, cross-origin은 명시적 승인 | 원격 스키마는 설명 정보 |
| OpenRPC / JSON-RPC | method/result 자동 탐색 | 동일 origin은 자동, cross-origin은 명시적 승인 | 인터페이스 스키마만으로 side effect 권한을 부여하지 않음 |
| OData v4 CSDL | entity set 자동 탐색 | read-only 자동 바인딩 | 메타데이터는 형태를 제한하지만 write 권한은 부여하지 않음 |
| GraphQL introspection | query/mutation 자동 탐색 | 동일 endpoint 자동 | query는 read-only, mutation은 정책으로 제한 |
| OPTIMADE | `/info` + `/info/<entry_type>` 탐색 | read-only HTTP 자동 바인딩 | 원격 스키마는 설명 정보 |
| MCP Streamable HTTP | 자동 탐색 | HTTP transport 자동, 정책 적용 | 원격 annotation은 신뢰하지 않음 |
| MCP stdio | 신뢰된 subprocess에서 자동 탐색 | 신뢰된 로컬 stdio lifecycle | command/argv/env는 로컬 설정 |
| MCP custom client factory | 호출자가 소유한 client를 통해 자동 탐색 | 호출자 소유 transport lifecycle | transport 상태는 ToolSpec 외부에 유지 |
| 선언형 HTTP/JSON | 신뢰된 로컬 ToolSpec | 고정 origin HTTP 자동 바인딩 | 로컬 manifest, secret은 runtime에만 유지 |
| Custom `SourceAdapter` | adapter 정의 | adapter 정의 | 로컬 정책 권한을 보존해야 함 |
| 사람이 읽는 문서 | 모델 보조 제안 | 명시적 승인 필요 | 근거를 가진 추론 결과 |

## 선택 기준

구현을 직접 소유하고 있고 가장 간단한 타입 기반 경로가 필요하면 **Python 도구**를 사용합니다.

서비스가 기계 판독 가능한 HTTP 계약을 이미 제공한다면 **OpenAPI**를 사용합니다. SchemaRouter는 스키마 조회 credential과 runtime credential을 분리하며, cross-origin `servers` 선언만으로 실행 권한이 생기지 않도록 합니다.

JSON-RPC 2.0 서비스가 기계 판독 가능한 OpenRPC 문서를 제공한다면 **OpenRPC**를 사용합니다. method, parameter, result schema와 로컬 reference를 동일한 canonical contract로 컴파일합니다. 원격 method의 side effect 여부는 신뢰된 로컬 정책이 분류하기 전까지 미분류 상태입니다.

서비스가 `$metadata`를 통해 CSDL을 제공한다면 **OData**를 사용합니다. entity set은 read capability가 되고 complex type은 중첩 field가 되며, planner가 선택한 field는 native `$select` selector로 변환됩니다.

introspection을 사용할 수 있고 native field selection 의미가 중요하다면 **GraphQL**을 사용합니다. SchemaRouter는 root field와 argument를 canonical contract로 매핑하고 선택된 output field를 GraphQL selection set으로 변환합니다. mutation은 신뢰된 로컬 정책이 허용하기 전까지 거부됩니다.

상호운용 가능한 재료 데이터베이스를 조회한다면 **OPTIMADE**를 사용합니다. 각 entry type과 사용 가능한 property를 탐색하고 read-only search/get endpoint를 만든 뒤, 계획된 output field를 OPTIMADE `response_fields`로 매핑합니다.

capability가 이미 MCP 생태계에 있다면 **MCP**를 사용합니다. URL 기반 경로는 Streamable HTTP이고, 로컬 서버는 `add_mcp_stdio(...)`, 호출자 소유/in-process 또는 enterprise transport는 `add_mcp_client_factory(...)`를 사용할 수 있습니다. command argument, 환경 secret, socket, credential, client state는 모델이 선택할 수 있는 schema field가 아니라 신뢰된 transport 설정으로 유지됩니다.

capability가 이미 해당 생태계의 tool로 패키징되어 있다면 **기존 LangChain/LlamaIndex tool**을 사용합니다. SchemaRouter는 서비스별 adapter를 새로 요구하지 않고 선언된 tool contract와 신뢰된 invocation path를 가져옵니다.

SDK/client를 안전하게 introspect할 수 없다면 **명시적 ToolSpec + trusted invoker**를 사용합니다. yfinance, mp-api helper, 사내 SDK, database client, CLI wrapper 등 신뢰된 transport를 연결하는 범용 탈출구입니다.

내장되지 않은 다른 구조화 프로토콜이라면 **custom adapter**를 사용합니다. STAC overlay, FHIR 전용 surface, gRPC descriptor plugin, WSDL/SOAP, 조직 전용 표준 등이 여기에 해당합니다. adapter는 provider별 분기를 planner에 추가하는 대신 프로토콜 의미를 SchemaRouter의 canonical contract로 컴파일합니다.

구조화 계약이 전혀 없을 때만 **사람이 읽는 문서**를 사용합니다. 모델 추론은 공개된 스키마보다 약한 근거이므로 먼저 실행 불가능한 proposal을 만듭니다.

## `kind="auto"`의 동작

`SchemaRouter.from_url(..., kind="auto")`는 기본적으로 의도적으로 **수동적(passive)** 입니다. 신뢰된 로컬 discovery profile이 제한된 GET/HEAD 방식 검사이며 프로토콜 session을 만들지 않는다고 선언한 adapter만 사용합니다.

내장 passive 순서는 다음과 같습니다.

```text
OpenAPI
  -> OpenRPC
  -> OPTIMADE
  -> OData
```

GraphQL과 MCP는 active discovery protocol입니다.

- GraphQL introspection은 POST를 전송합니다.
- MCP Streamable HTTP는 protocol client/session을 만듭니다.

따라서 기본 auto-detection에서는 건너뜁니다. 프로토콜을 알고 있다면 kind를 명시하세요.

```python
await router.add_url(url, kind="graphql")
await router.add_url(url, kind="mcp")
```

과거의 광범위한 probing 동작이 꼭 필요한 애플리케이션은 로컬에서 명시적으로 허용해야 합니다.

```python
await router.add_url(
    url,
    kind="auto",
    allow_active_probes=True,
)
```

같은 안전 경계가 `probe_url()`과 `from_url()`에도 적용됩니다. CLI에서는 `schemarouter source probe URL --allow-active-probes`에 해당합니다.

신뢰된 discovery profile이 없는 adapter는 auto-detection에서 active로 취급됩니다. 따라서 서드파티 plugin은 설치되었다는 이유만으로 예상하지 못한 probing 권한을 얻지 못합니다. 명시적인 `kind="plugin_kind"`는 계속 지원됩니다.

일반 HTML 문서는 자동으로 실행 가능한 tool로 변환되지 않습니다. passive detection이 실패하면 diagnostics에 건너뛴 active protocol이 표시됩니다. 사람이 읽는 문서는 `inspect_url()`을 사용하세요.

## 선언형 HTTP/JSON

API에 정확하고 신뢰할 수 있는 계약은 있지만 탐색 가능한 OpenAPI/MCP/OPTIMADE 스키마가 없다면 로컬 `ToolSpec`을 선언하고 `router.add_http_tool(...)`로 바인딩합니다. 별도의 REST 전용 스키마 언어를 만들지 않으면서 기존 parameter, field, validation, policy, provenance, secret 분리 경계를 유지할 수 있습니다.

이 입력 방식들을 여러 도메인과 실제 서비스 예제로 비교하려면 [범용 capability 입력](../guides/universal-ingestion.md)을 참고하세요.

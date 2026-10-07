# Provider 중심 등록

대부분의 사용자는 provider가 어떤 프로토콜이나 SDK를 제공하는지보다 **어떤 provider를 쓰고 싶은지**를 먼저 압니다.

SchemaRouter 내부의 protocol-neutral ingestion 구조는 그대로 유지하면서, 알려진 provider는 provider 이름만으로 등록을 시작할 수 있습니다.

```python
from schemarouter import SchemaRouter

router = SchemaRouter()
result = await router.add_provider("materials-project")
```

내장 profile은 provider를 알려진 access method로 해석하고, 현재 프로세스에서 안전하게 사용할 수 있는 방법만 등록합니다. 필요한 credential이나 optional dependency가 없으면 임의로 추측하거나 설치하지 않고 상태로 보고합니다.

기본 동작은 의도적으로 **best-effort**입니다. 어떤 method가 credential, optional dependency 또는 수동 binding을 필요로 하더라도 사용할 수 있는 다른 method는 등록합니다. 반환되는 `ProviderRegistrationResult.status`는 `complete`, `partial`, `failed` 중 하나이므로 caller가 method별 결과를 다시 집계할 필요가 없습니다.

여러 access method가 하나의 필수 fallback/topology 단위라면 all-or-nothing 등록을 사용할 수 있습니다.

```python
result = await router.add_provider(
    "my-provider",
    methods={"openapi", "mcp"},
    require_all=True,
    replace=True,
)
assert result.status == "complete"
```

`require_all=True`에서는 모든 요청 method를 먼저 실제 registry에 공개하지 않은 상태로 준비합니다. Credential 누락, 사용할 수 없는 dependency/source, manual-only method, collision 또는 준비 실패가 하나라도 있으면 요청한 provider topology는 변경되지 않습니다. 모든 준비가 성공한 뒤에만 contract를 하나의 version-guarded registry batch로 공개하고 trusted binding을 연결합니다. Binding 단계가 실패하면 이전 contract와 binding을 복구하며, 동시에 registry가 변경되었다면 다른 writer의 상태를 덮어쓰지 않고 fail-closed합니다.

## 알 수 없거나 모호한 provider 이름

등록된 profile은 계속 로컬에서 결정론적으로 해석합니다. 모르는 이름을 입력했다고 해서 네트워크 검색 결과를 곧바로 실행 권한으로 바꾸지는 않습니다.

먼저 `discover_provider()`로 검토 가능한 proposal을 얻습니다.

```python
proposal = router.discover_provider("google")

for candidate in proposal.candidates:
    print(candidate.candidate_id, candidate.display_name, candidate.registrable)
```

`google`처럼 조직 전체를 가리키는 이름은 의도적으로 ambiguous로 처리합니다. 현재 내장 service-family hint는 Google Drive, Calendar, Maps, Gemini, BigQuery처럼 구체적인 서비스 후보를 제시하고 하나를 임의로 선택하지 않습니다.

사내 service catalog, 문서 검색 또는 다른 신뢰된 소스를 쓰고 싶다면 host가 discovery backend를 명시적으로 연결할 수 있습니다.

```python
proposal = router.discover_provider("catalog", backend=my_discovery_backend)
candidate = proposal.candidates[0]

router.approve_provider_candidate(
    candidate,
    expected_digest=candidate.approval_digest,
)
```

Backend가 `ProviderProfile`을 제안하더라도 proposal 자체는 실행 권한이 없습니다. 정확한 profile digest를 사용한 명시적 approval 이후에만 profile이 등록되고, 그 뒤에도 기존 adapter/binding/credential 규칙을 그대로 적용합니다. 즉 흐름은 **discover → inspect → approve → register**이지 **search → execute**가 아닙니다.

## 등록 전 확인

Provider 해석 자체는 로컬에서 이루어지며 네트워크 요청을 하지 않습니다.

```python
resolution = router.resolve_provider("materials-project")

for method in resolution.methods:
    print(method.method_id, method.status, method.credential_names)
```

일반적인 환경에서는 다음과 같이 보일 수 있습니다.

```text
optimade    available
openapi     available    credential: X-API-KEY
python-sdk  dependency_missing
```

Credential requirement는 선언 정보일 뿐입니다. 실제 secret 값은 provider profile, ToolSpec, snapshot, inspection output에 저장되지 않습니다.

## 초기 내장 provider

내장 acceptance profile은 서로 다른 접근 형태를 검증하도록 구성합니다.

- **Materials Project** — 공개 OPTIMADE, 인증이 필요한 OpenAPI, optional `mp-api` SDK.
- **Crossref** — 공개 declarative HTTP/JSON REST.
- **Tavily** — 인증이 필요한 declarative HTTP/JSON search와 optional Python SDK.
- **APIs.guru** — 공개 OpenAPI discovery와 read-only metrics 실행.
- **OData.org V4 reference service** — 공개 OData metadata discovery와 read-only query 실행.

인증이 필요한 method는 process-local trusted header로 전달합니다.

```python
result = await router.add_provider(
    "tavily",
    methods={"rest"},
    trusted_headers_by_method={
        "rest": {"Authorization": f"Bearer {TAVILY_API_KEY}"}
    },
)
```

SchemaRouter는 SDK를 자동 설치하지 않습니다. SDK가 설치되어 있어도 provider plugin이 trusted binding을 제공하지 않는 한 명시적인 binding이 필요합니다.

## 여러 접근 방법은 계속 구분됩니다

Provider-first 등록은 기존 adapter 위의 편의 계층입니다.

```text
provider identity
    |
    v
ProviderProfile
    |
    +-- OpenAPI
    +-- OPTIMADE
    +-- GraphQL
    +-- OData
    +-- OpenRPC
    +-- MCP (URL-backed)
    +-- HTTP/JSON
    +-- Python / plugin binding
    |
    v
기존 ToolSpec / EndpointSpec / FieldSpec pipeline
```

각 method는 같은 `provider` identity를 공유하되 서로 다른 `access_mode`를 유지합니다. 같은 provider라는 이유만으로 method가 자동으로 호환되는 것은 아닙니다. 기존 semantic, datatype, unit, qualifier, health, policy, fallback 규칙이 그대로 적용됩니다.

## Provider catalog 확장

애플리케이션은 로컬 `ProviderProfile`을 등록할 수 있고, 설치된 패키지는 `schemarouter.providers` entry-point group으로 provider profile을 제공할 수 있습니다. Python entry point import는 trusted local code를 실행하므로 plugin loading은 명시적 allowlist 방식입니다.

## Method 지원 범위

Provider profile은 기본 registry의 모든 URL 기반 adapter를 대상으로 할 수 있습니다. Provider-first 계층이 프로토콜별 등록기를 다시 구현하는 것이 아니라, 선언된 method를 기존 adapter로 전달합니다.

| Profile method kind | Provider-first 동작 |
| --- | --- |
| `openapi` | URL 자동 등록 |
| `optimade` | URL 자동 등록 |
| `graphql` | URL 자동 등록 |
| `odata` | URL 자동 등록 |
| `openrpc` | URL 자동 등록 |
| `mcp` | URL 기반 MCP transport 자동 등록 |
| `http_json` | 명시적으로 신뢰된 declarative `ToolSpec`으로 자동 등록 |
| `python` / SDK | explicit trusted binding 필요. 패키지가 설치되어 있다는 이유만으로 실행 권한을 부여하지 않음 |

Caller-owned transport, Python client, framework object는 계속 explicit trust boundary입니다. Provider profile에 이런 방법을 기술할 수는 있지만, core SchemaRouter가 설치된 패키지나 import 가능한 객체에서 실행 권한을 추론하지는 않습니다.

Provider profile은 execution planner가 아닙니다. 이름이 있는 provider를 기존 ingestion 계층에 연결하는 방법만 기술하며, routing과 execution은 기존 SchemaRouter contract를 그대로 사용합니다.

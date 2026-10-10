# 범용 기능 등록

SchemaRouter는 특정 도메인에 종속되지 않습니다. 호환성의 기준은 브랜드 목록이 아니라, 외부 기능을 동일한 정본 계약으로 컴파일하는 소수의 등록 방식입니다.

~~~text
ToolSpec
  -> EndpointSpec
      -> ParameterSpec
      -> FieldSpec
~~~

등록된 기능은 플래너, 검증, 실행 정책, 지문, 대체 경로, 상태 확인, 스키마 변경, 투영, 증거 및 관측 경계를 공유합니다.

## 공급자 중심 등록

사용자가 원하는 서비스는 알지만 해당 서비스가 제공하는 프로토콜을 모두 알지는 못할 경우, 어댑터 선택보다 한 단계 위에서 시작합니다.

```python
result = await router.add_provider("materials-project")
```

`ProviderProfile`은 공급자 식별자를 선언된 접근 방법으로 해석한 다음 각 방법을 기존 OpenAPI, OPTIMADE, HTTP/JSON, Python, 플러그인 경로로 위임합니다. 공급자별 플래너를 새로 만들지 않으며, 공급자 식별자가 같다는 이유만으로 접근 방법 간 의미적 호환성을 가정하지 않습니다.

내장 검증 프로필은 Materials Project, Crossref, Tavily입니다.

## 지원하는 등록 방식

| 등록 방식 | 사용 조건 | 공개 진입점 |
| --- | --- | --- |
| Provider profile | 공급자는 알지만 모든 프로토콜·SDK를 알지 못할 때 | `await router.add_provider(...)` |
| 직접 ToolSpec | 애플리케이션이 이미 정본 계약을 소유할 때 | router.add_tool(...) |
| 타입이 있는 Python callable | SDK나 함수에 안정적인 타입 시그니처가 있을 때 | router.add_callable(...) |
| ToolSpec + SDK/클라이언트 | SDK·클라이언트를 안전하게 내부 검사할 수 없을 때 | router.add_bound_tool(...) |
| OpenAPI / Swagger | HTTP API가 OpenAPI를 게시할 때 | from_url(..., kind="openapi") |
| MCP Streamable HTTP | 원격 서버가 HTTP로 MCP 도구를 제공할 때 | from_url(..., kind="mcp") |
| MCP stdio | 로컬 MCP 서버를 신뢰된 하위 프로세스로 실행할 때 | router.add_mcp_stdio(...) |
| MCP 사용자 정의 전송 | 애플리케이션이 신뢰된 MCP 수명주기를 소유할 때 | router.add_mcp_client_factory(...) |
| OPTIMADE | 재료 데이터가 OPTIMADE로 노출될 때 | from_url(..., kind="optimade") |
| GraphQL | introspection과 네이티브 선택 집합을 사용할 수 있을 때 | from_url(..., kind="graphql") |
| OData | CSDL/$metadata와 $select를 사용할 수 있을 때 | from_url(..., kind="odata") |
| OpenRPC / JSON-RPC | JSON-RPC 서비스가 OpenRPC를 게시할 때 | from_url(..., kind="openrpc") |
| LangChain 도구 가져오기 | 기존 기능이 LangChain 도구일 때 | router.add_langchain_tool(...) |
| LlamaIndex 도구 가져오기 | 기존 기능이 LlamaIndex 도구일 때 | router.add_llamaindex_tool(...) |
| REST/JSON | REST는 안정적이지만 검색 가능한 스키마가 없을 때 | router.add_http_tool(...) |
| 사용자 정의 프로토콜 | 별도 탐색·전송 계층이 필요한 프로토콜일 때 | router.register_adapter(...) |
| 사람이 읽는 문서 | 문서만 존재할 때 | 검사 → 제안 → 명시적 승인 |

프로토콜에 특화된 코드는 일반 HTTP, Python 또는 플러그인 방식에서는 보존할 수 없는 유용한 기계 판독 의미를 제공하는 경우에만 핵심 패키지에 추가합니다.

## 네트워크 신뢰 경계

URL을 이용한 기능 탐색과 실행은 네트워크 신뢰 경계입니다. 기본 `NetworkPolicy.trusted_internal()`은 기존 로컬·인트라넷 배포와의 호환성을 유지하므로 모델이나 사용자가 제어하는 URL을 그 기본 설정에 전달해서는 안 됩니다.

신뢰도가 낮은 입력이 URL에 영향을 줄 수 있다면 공개 네트워크 전용 정책을 구성합니다.

```python
from schemarouter import NetworkPolicy, SchemaRouter

router = SchemaRouter(
    network_policy=NetworkPolicy.public_only(
        allowed_ports={80, 443},
    )
)
await router.add_url("https://api.example.com/openapi.json", kind="openapi")
```

공개 정책은 loopback, link-local, 사설, 멀티캐스트·예약 주소 및 일반적인 클라우드 메타데이터 목적지를 거부합니다. 호스트 이름을 IDNA로 정규화하고 네트워크 접근 직전에 해석하며, 모든 리다이렉트와 외부 OpenAPI 참조를 다시 검사합니다. 같은 정책은 OpenAPI/HTTP JSON, GraphQL, OData, OpenRPC, OPTIMADE, MCP HTTP 실행 바인딩에도 전달됩니다.

명시적으로 신뢰해야 하는 내부 서비스는 `allowed_hosts`에 등록할 수 있습니다. 신뢰된 헤더는 다른 출처로 향하는 스키마 리다이렉트에 전달하지 않습니다. 리다이렉트를 지원하지 않는 프로토콜 어댑터도 기존처럼 거부합니다.

DNS 검증과 HTTP 클라이언트의 실제 연결 주소 조회는 서로 다른 작업입니다. 따라서 내장 공개 정책은 DNS rebinding 위험을 줄이지만 연결 수준의 DNS 고정까지 보장하지 않습니다. 더 강한 보호가 필요하면 검증된 주소를 고정하는 전송·리졸버 조합을 사용하거나 네트워크 계층에서 동일한 송신 정책을 강제해야 합니다.

## 광범위한 도메인 적합성 매트릭스

기계가 읽을 수 있는 회귀 테스트 픽스처는 `tests/fixtures/domain_ingestion_matrix.json`입니다. 재료 과학과 무관한 도메인도 의도적으로 포함합니다.

| 서비스·예제 | 도메인 | 권장 등록 방식 | 추가로 지원되는 경로 |
| --- | --- | --- | --- |
| Materials Project | 재료 과학 | Provider profile | 공개 OPTIMADE, 인증 OpenAPI, Python/mp-api, 바인딩된 SDK |
| DuckDuckGo/DDGS | 웹 검색 | LangChain 도구 | Python 래퍼, 바인딩된 SDK |
| Tavily | 웹 검색 | Provider profile | 인증 HTTP/JSON, Python SDK, LangChain 도구, 바인딩된 SDK |
| Brave Search | 웹 검색 | HTTP/JSON | Python 래퍼, 바인딩된 SDK, 플러그인 |
| Yahoo Finance/yfinance | 금융 | 바인딩된 SDK | Python callable, LangChain 도구 |
| arXiv | 학술 검색 | LangChain 도구 | Python 래퍼, 바인딩된 SDK, 플러그인 |
| Crossref | 학술 메타데이터 | Provider profile | 공개 HTTP/JSON, 바인딩된 SDK |
| GitHub REST | 개발자 플랫폼 | OpenAPI | HTTP/JSON, 바인딩된 SDK, 플러그인 |
| GraphQL business API | 업무용 애플리케이션 | GraphQL | 바인딩된 SDK |
| OData enterprise API | 기업 데이터 | OData | 바인딩된 SDK |
| OpenRPC service | 범용 RPC | OpenRPC | HTTP/JSON, 바인딩된 SDK |
| 로컬 MCP stdio 서버 | 로컬 도구 | MCP stdio | 사용자 정의 MCP 클라이언트 팩토리 |

이 매트릭스는 CI에서 검증합니다. 대응하는 공개 API나 내장 어댑터 없이 새로운 등록 방식을 지원한다고 명시하면 적합성 테스트가 실패합니다.

## 같은 공급자의 여러 접근 경로

하나의 공급자가 동일한 논리적 데이터를 여러 접근 방식으로 제공할 수 있습니다.

~~~text
provider="materials-project"
  access_mode="openapi"
  access_mode="optimade"
  access_mode="python"
  access_mode="sdk"
~~~

또는 다음과 같을 수 있습니다.

~~~text
provider="tavily"
  access_mode="http_json"
  access_mode="langchain"
  access_mode="python"
~~~

이 경로들은 공존할 수 있지만 공급자 이름이 같다는 이유로 자동으로 동등해지는 것은 아닙니다. 동일 공급자의 대체 경로에도 일반적인 의미·타입·단위·한정자 및 실행 정책 호환성 검사를 적용합니다.

## 어댑터 간 필드 범위의 일관성

구조화 어댑터는 동일한 타입 기반 필드 계약을 사용합니다. 원본에서 선언했다면 SchemaRouter는 다음 정보를 보존합니다.

- JSON 데이터 타입과 형태
- 설명과 보수적인 별칭
- 원본 경로와 투영된 결과 경로
- 식별자
- 원본 단위
- 공급자와 접근 경로 식별자
- 중첩 객체 및 레코드 보존형 배열 항목 경로

배열 하위 필드는 다음처럼 레코드 관계가 유지되는 명시적인 경로를 사용합니다.

~~~text
results[].title
results[].url
~~~

서로 연관된 배열을 독립된 배열로 펼쳐서는 안 됩니다.

의미적 ID, 표준 단위 변환, 차원, 한정자, 라이선스, 출처는 신뢰된 계약입니다. 권위 있는 구조화 소스 또는 신뢰된 보강 과정에서 얻어야 하며, 임의의 자연어 설명만으로 추측하지 않습니다.

## 서비스에 여러 인터페이스가 있는 경우

가장 풍부하고 권위 있는 기계 판독 경로를 우선합니다. 다만 가용성과 폴백을 위해 여러 경로를 등록할 수 있습니다.

Materials Project가 대표적인 예입니다.

~~~text
Materials Project
  -> OpenAPI
  -> OPTIMADE
  -> mp-api / Python
  -> explicit ToolSpec + trusted SDK invoker
~~~

신뢰할 수 있는 공급자 프로필이 있다면 사용자가 이러한 경로를 수동으로 열거할 필요도 없습니다. `add_provider("materials-project")`가 공급자 식별자를 프로토콜에 중립적인 동일 기능 모델로 확장하고, 사용할 수 없거나 인증이 필요한 방법을 명시적으로 보고합니다.

이 원칙은 과학 외 분야에도 적용됩니다.

~~~text
web search
  -> existing LangChain/LlamaIndex tool
  -> direct REST/HTTP JSON
  -> typed Python SDK
  -> SourceAdapter plugin when protocol semantics require it
~~~

## 핵심 패키지 밖에 두는 프로토콜

STAC, gRPC/Protobuf, SOAP/WSDL, AsyncAPI는 현재 플러그인 또는 오버레이 경계를 사용합니다. 향후 구현이 탐색, 필드 투영, 수명주기 면에서 충분한 가치를 입증하는 경우에만 핵심 패키지로 승격합니다. 근거는 프로토콜 수용 결정 가이드를 참고하십시오.

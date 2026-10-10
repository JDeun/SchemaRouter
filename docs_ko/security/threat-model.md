# 보안 정책

SchemaRouter는 remote schema, model output, tool description을 신뢰하지 않는 데이터로 취급합니다. Credential, side effect, binding, policy의 authority는 신뢰된 local application code에 남습니다.

## 지원 버전

SchemaRouter는 현재 pre-1.0입니다. Security fix는 최신 non-prerelease release line과 현재 development line에 적용합니다. Release별 support window가 별도로 공지되지 않는 한 이전 0.x line에 대한 backport는 보장하지 않습니다.

## 취약점 보고

Public issue에 credential, token, private endpoint 또는 exploit detail을 포함하지 마십시오.

이 repository에서 GitHub private vulnerability reporting을 사용할 수 있으면 이를 이용하십시오. Private reporting을 사용할 수 없다면 technical detail을 공개하기 전에 GitHub를 통해 repository owner에게 비공개로 연락하십시오.

민감하지 않은 correctness bug는 일반 GitHub issue로 보고하면 됩니다.

## Threat model

### Remote schema와 model output

OpenAPI document, MCP metadata, 사람이 읽는 documentation, LLM이 생성한 analysis는 execution authority가 아닙니다.

SchemaRouter:

- model output을 registered schema로 다시 projection;
- undeclared tool, endpoint, parameter, field 거부;
- JSON Schema로 input과 raw output validation;
- stale schema fingerprint와 stale invoker binding 거부;
- mutation/destructive/unclassified remote operation에 trusted local policy 요구.

### Authorization audit 전달

Authorization decision과 audit delivery는 서로 다른 security plane입니다. Host가 제공한 `authorization_audit_hook`은 privacy-safe decision metadata만 받으며 principal claim과 trusted-filter value는 포함하지 않습니다.

Audit delivery 기본값은 `best_effort`입니다. Sink failure는 authorization decision과 격리되고 `router.authorization_audit_delivery_status()`에 기록되며 allow를 execution failure로 바꾸거나 deny를 sink exception으로 가리지 않습니다.

감사 로그의 반드시 저장해야 하는 배포 환경에서는 `authorization_audit_delivery_mode="strict"`를 명시적으로 활성화할 수 있습니다. 엄격 모드에는 감사 데이터를 기록할 수신 대상이 필요합니다. 승인된 호출이라도 실제 실행 전에 감사 전달에 실패하면 `AuthorizationAuditDeliveryError`로 안전하게 중단합니다. 원래의 권한 판정이 거부였다면 해당 판정과 최초의 `PolicyViolationError`를 별도로 유지합니다. 실행 추적에는 개인정보를 노출하지 않는 전달 실패 플래그 및 허용·거부 결과만 기록하며, 수신 대상의 예외 내용이나 사용자 권한 관련 데이터는 기록하지 않습니다.

### Credential

Runtime credential은 model-visible tool argument 밖에 유지해야 합니다.

OpenAPI 스키마를 가져올 때 사용하는 헤더와 런타임 API 호출 헤더는 별도 채널로 관리합니다. Authorization, Cookie, Host, 프록시 인증처럼 민감한 헤더는 모델이 선택한 인수를 통해 전달할 수 없습니다.

Schema, documentation 또는 API URL에 credential을 포함하지 마십시오.

Authenticated MCP에도 같은 원칙을 적용합니다. Bearer/custom header는 trusted transport layer에 두며 userinfo credential이 포함된 MCP URL은 거부합니다. Protocol-controlled `Mcp-*` header는 SchemaRouter의 trusted-header channel로 override할 수 없습니다. Custom OAuth, mTLS, proxy, gateway 동작은 application이 제공하는 `MCPClientFactory` 뒤에 둡니다.

Schema watch는 process-local credential과 transport factory를 정확한 registered tool fingerprint 및 credential-free structured-source identity에 고정합니다. Application code가 같은 logical tool key를 다른 source, transport, contract로 교체하면 기존 watch는 **refresh request/session을 열기 전에** `stale_source` 또는 `stale_contract`가 됩니다.
Watch 자체가 검증하고 적용한 compatible refresh는 fingerprint pin만 전진시킬 수 있으며 source/transport identity는 변경되지 않아야 합니다. 따라서 credential rotation에는 implicit carry-over가 아니라 명시적인 trusted-local watch re-registration이 필요합니다.

조건부 스키마 요청 검증자(ETag / Last-Modified)도 데이터 소스에 종속됩니다. SchemaRouter는 저장된 검증자 메타데이터와 함께 구조화된 소스 식별자의 불투명 다이제스트를 저장하고, 프로세스 내부 캐시는 논리적 도구 키와 소스 식별자를 함께 사용해 구분합니다. 같은 키를 유지한 도구 교체, 어댑터 변경 또는 소스 변경이 발생하면 캐시를 사용하지 않고 새로 요청합니다. 새 기능이 이전 레지스트리 키를 재사용했다는 이유만으로 기존 검증자를 전송하거나 신뢰하지 않습니다. 일치하는 소스 다이제스트가 없는 이전 형식 또는 잘못된 검증자 메타데이터는 무시하고 정상적인 전체 요청으로 복구합니다.

### Network destination과 SSRF

로컬 개발 도구가 주요 사용 사례이므로 SchemaRouter는 localhost 및 사설 네트워크의 MCP/OpenAPI 엔드포인트를 지원합니다. 따라서 사설 주소나 링크 로컬 주소를 전역적으로 차단하지 않습니다.

`SchemaRouter.from_url()`과 `inspect_url()`은 network-capable API로 취급해야 합니다.

Application이 untrusted end user의 URL을 받는다면 SchemaRouter에 전달하기 전에 자체 network policy를 적용해야 합니다. Hosted service는 일반적으로 다음을 수행해야 합니다:

- 승인된 host 또는 service registry를 allowlist;
- 명시적으로 필요한 경우를 제외하고 클라우드 메타데이터 주소, 루프백, 링크 로컬 및 사설 주소 범위를 해석한 뒤 차단;
- network layer에서 DNS rebinding을 고려;
- 가능한 경우 egress control 사용.

SchemaRouter는 schema/document redirect를 original origin으로 제한하고 OpenAPI runtime call도 명시적으로 승인된 origin으로 제한합니다. OpenAPI runtime response는 기본 16 MiB limit의 bounded reader를 통해 stream되며 이는 OPTIMADE adapter의 bounded-response posture와 같습니다.

Cross-document OpenAPI `$ref` fetching은 기본적으로 비활성화됩니다. Trusted application code가 opt-in하면 referenced document는 entry document의 origin 안에 있어야 하고 schema header는 그 origin 안에서만 재사용되며 redirect는 same-origin으로 유지되고 depth/document/aggregate-byte limit이 적용됩니다.
`$id` base-URI rebasing 또는 non-JSON-Pointer anchor를 사용하는 document는 현재 resolver가 추측하지 않고 fail-closed합니다.

이 검사들은 application의 initial URL admission policy를 대체하지 않습니다.

### Observability

Run-event argument와 result payload는 기본적으로 redaction됩니다.

`RunConfig(include_payloads=True)`는 user data, API response, identifier 또는 기타 sensitive information을 direct event consumer에 노출할 수 있습니다. Destination이 신뢰되고 적절한 retention control이 있을 때만 payload tracing을 활성화하십시오.

Optional OpenTelemetry exporter는 더 엄격합니다. Structural attribute는 export하지만 underlying event stream이 payload를 허용했더라도 argument value, result payload, RunConfig metadata, tag, exception message는 export하지 않습니다.

영구 실행 추적은 전달받은 `RunEvent` 메시지를 그대로 저장합니다. 기본 런타임 설정에서는 인수 값과 결과 본문이 가려진 상태로 유지됩니다. `RunConfig(include_payloads=True)`를 사용하면 해당 값이 디스크에 기록될 수 있으므로 애플리케이션의 접근 제어, 저장 시 암호화, 백업 및 보존 정책을 적용해야 합니다. SchemaRouter 자체는 SQLite 추적 데이터베이스를 암호화하지 않습니다.

### Approval, budget, retry

Local execution policy는 첫 번째 side-effect gate입니다. Application은 non-read-only 또는 모든 call에 대해 trusted sync/async approval callback을 추가로 요구할 수 있습니다. Callback 누락, negative decision, callback failure는 execution을 거부합니다.

Per-run budget은 logical call, total attempt, remote attempt, elapsed time, per-tool call, application-defined cost unit을 제한합니다. Retry attempt는 invoker 실행 전에 attempt/remote/cost budget을 소비하며 retry backoff는 남은 elapsed-time budget으로 제한됩니다. Async approval callback과 execution hook도 남은 시간으로 제한되고 synchronous trusted callback은 반환 직후 검사됩니다. Budget refusal과 schema contract violation은 retry하지 않습니다.

Automatic retry는 trusted local code가 non-read-only operation retry를 명시적으로 opt-in하지 않는 한 read-only로 분류된 endpoint로 제한됩니다. Built-in OpenAPI/OPTIMADE HTTP invoker는 보수적인 transient status만 retry하고 다른 HTTP error와 deterministic response-contract failure에는 즉시 실패합니다. Trusted custom invoker는 `NonRetryableInvocationError`를 발생시켜 안전하게 복구할 수 없는 failure의 retry를 막을 수 있습니다.

### 신뢰된 execution hook

Before/after execution hook은 trusted local executable code이며 redacted telemetry가 아닙니다.
Before hook은 validated argument value를, after hook은 final projected result payload를 볼 수 있습니다. 해당 data를 신뢰할 수 없는 remote/third-party callback에는 연결하지 마십시오.

훅은 분리된 모델 스냅샷을 받으며 실행할 호출이나 반환 결과를 변경할 수 없습니다. `None`이 아닌 훅 반환값은 거부됩니다. 훅에서 예외가 발생하면 안전하게 중단합니다. 특히 **실행 후 훅의 실패는 재시도 가능한 도구 실행 실패로 분류하지 않으므로**, 관측·미들웨어 장애 때문에 이미 성공한 호출을 반복 실행하지 않습니다.

### 신뢰된 contract amendment

`SchemaRouter.amend_capability()`는 invoker binding과 같은 등급의 trusted local code입니다. Remote content, model output, decision backend에서는 접근할 수 없습니다.

계약 수정은 결과의 의미를 선언하거나 주석으로 추가하는 용도로만 허용됩니다. 실행 대상 식별자와 검증 스키마의 변경은 거부하므로 호출을 다른 대상으로 돌리거나, 입력 범위를 넓히거나, 파괴적 작업을 읽기 전용으로 재분류하거나, 원본 소스가 선언한 응답 검증을 완화할 수 없습니다. 거부된 수정 사항은 아무것도 등록하지 않으며 기존 바인딩에도 영향을 주지 않습니다.

도구와 엔드포인트의 `metadata` 수정도 거부됩니다. 자유 형식 주석처럼 보여도 검증 과정에서 필수 조건을 도출할 수 있기 때문입니다. 예를 들어 소스에 `output_schema`가 없을 때 `endpoint.metadata["output_required"]`는 자동 생성된 출력 스키마를 결정합니다. 따라서 메타데이터만 수정해도 명시된 계약 요소나 지문을 변경하지 않은 채 응답에 반드시 포함해야 할 필드를 바꿀 수 있습니다. 이를 방지하기 위해 해당 수정도 허용하지 않습니다.

Amendment에서도 fingerprint는 변경되므로 stale-binding 및 stale-plan protection은 그대로 유지됩니다.

### Third-party adapter plugin

Installed entry point는 local executable code입니다. SchemaRouter는 import 없이 plugin metadata를 inspect할 수 있지만 발견된 plugin을 auto-load하지 않습니다. 실제 import에는 trusted application code가 제공한 명시적인 non-empty allowlist가 필요합니다. Remote content와 model output은 import할 installed plugin을 선택할 수 없습니다.

### Third-party decision-backend plugin

Decision-backend entry point 역시 trusted local executable code입니다. Discovery는 package metadata만 읽으며 trusted application code가 정확한 plugin name 하나를 요청하기 전에는 plugin module을 import하지 않습니다. 이름이 중복되면 모듈을 불러오기 전에 실패 처리하므로 패키지 설치 순서에 따라 구현체가 조용히 선택되는 일을 막습니다.

Loaded decision backend는 여전히 SchemaRouter가 만든 finite option set만 받습니다.
Unknown option ID, duplicate selection, malformed result, invalid score는 일반 `DecisionBackend` validation path에서 fail-closed합니다. Plugin code 자체는 trusted Python code이며 임의 local action을 수행할 수 있으므로 application은 plugin installation/loading을 model output이 아니라 code trust decision으로 취급해야 합니다.

Shared benchmark configuration은 선택된 environment variable에서 명시적으로 전달됩니다. Report는 plugin identity, distribution/version, configuration environment-variable name, configuration key만 기록하며 configuration value는 저장하지 않습니다.

### 사람이 읽는 documentation

Documentation-derived schema는 grounding과 explicit approval이 성공할 때까지 non-executable proposal로 유지됩니다. Documentation text is treated as untrusted and script/style content is removed before model
analysis.

## 보안에 민감한 contribution 규칙

다음 항목에 영향을 주는 변경에는 adversarial regression test가 필요합니다:

- authorization 또는 credential;
- URL/redirect/origin 처리;
- schema fingerprint 또는 registry mutation;
- execution policy;
- retry 또는 side effect;
- input/output validation;
- event payload redaction 및 telemetry export;
- adapter plugin loading;
- decision-backend plugin discovery/loading 및 benchmark secret 처리;
- MCP authenticated/custom transport;
- per-call approval 또는 execution budget;
- trusted execution hook;
- documentation grounding 또는 proposal approval.

함께 보기:

- [Architecture](../architecture.md)
- [Adapter authoring](../adapter-authoring.md)
- [Release checklist](../release-checklist.md)

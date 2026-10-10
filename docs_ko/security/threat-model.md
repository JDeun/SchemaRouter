# 보안 정책

SchemaRouter는 외부 스키마, 모델 출력, 도구 설명을 신뢰할 수 없는 데이터로 취급합니다. 자격 증명, 부작용이 있는 작업, 실행 바인딩 및 정책에 대한 최종 권한은 신뢰된 로컬 애플리케이션 코드에 있습니다.

## 지원 버전

SchemaRouter는 현재 1.0 이전 버전입니다. 보안 수정은 최신 정식 릴리스 계열과 현재 개발 계열에 적용합니다. 릴리스별 지원 기간이 별도로 공지되지 않은 경우, 이전 0.x 계열에 대한 수정 사항의 역이식(backport)은 보장하지 않습니다.

## 취약점 보고

공개 이슈에 자격 증명, 토큰, 비공개 엔드포인트 또는 취약점 악용의 구체적인 내용을 포함하지 마십시오.

이 저장소에서 GitHub의 비공개 취약점 신고 기능을 사용할 수 있다면 해당 기능을 이용하십시오. 사용할 수 없다면 기술적 세부 사항을 공개하기 전에 GitHub를 통해 저장소 소유자에게 비공개로 연락하십시오.

민감한 정보를 포함하지 않는 정확성 관련 버그는 일반 GitHub 이슈로 신고할 수 있습니다.

## 위협 모델

### 외부 스키마와 모델 출력

OpenAPI 문서, MCP 메타데이터, 사람이 읽는 문서 및 LLM이 생성한 분석 결과는 실행을 승인하는 권한의 근거가 아닙니다.

SchemaRouter는 다음 원칙을 적용합니다.

- 모델 출력을 등록된 스키마에 맞춰 다시 투영합니다.
- 선언되지 않은 도구, 엔드포인트, 매개변수 및 필드를 거부합니다.
- JSON Schema로 입력과 가공 전 출력을 검증합니다.
- 오래된 스키마 지문과 오래된 실행기 바인딩을 거부합니다.
- 변경·파괴적 작업 또는 유형이 분류되지 않은 원격 작업에는 신뢰된 로컬 정책을 요구합니다.

### 권한 감사 결과 전달

권한 판정과 감사 정보 전달은 서로 다른 보안 영역입니다. 호스트가 제공하는 `authorization_audit_hook`에는 개인정보를 노출하지 않는 판정 메타데이터만 전달하며, 주체의 권한 주장(principal claim)과 신뢰된 필터 값은 포함하지 않습니다.

감사 정보 전달의 기본값은 `best_effort`입니다. 수신 대상(sink)의 장애는 권한 판정과 분리되며 `router.authorization_audit_delivery_status()`에 기록합니다. 수신 대상의 예외 때문에 허용 판정을 실행 실패로 바꾸거나 거부 판정을 가리지 않습니다.

감사 로그를 반드시 저장해야 하는 배포 환경에서는 `authorization_audit_delivery_mode="strict"`를 명시적으로 활성화할 수 있습니다. 엄격 모드에는 감사 데이터를 기록할 수신 대상이 필요합니다. 승인된 호출이라도 실제 실행 전에 감사 전달에 실패하면 `AuthorizationAuditDeliveryError`로 안전하게 중단합니다. 원래의 권한 판정이 거부였다면 해당 판정과 최초의 `PolicyViolationError`를 별도로 유지합니다. 실행 추적에는 개인정보를 노출하지 않는 전달 실패 플래그 및 허용·거부 결과만 기록하며, 수신 대상의 예외 내용이나 사용자 권한 관련 데이터는 기록하지 않습니다.

### 자격 증명

런타임 자격 증명은 모델에 노출되는 도구 인수 밖에서 관리해야 합니다.

OpenAPI 스키마를 가져올 때 사용하는 헤더와 런타임 API 호출 헤더는 별도 채널로 관리합니다. Authorization, Cookie, Host, 프록시 인증처럼 민감한 헤더는 모델이 선택한 인수를 통해 전달할 수 없습니다.

스키마, 문서 또는 API URL에 자격 증명을 포함하지 마십시오.

인증된 MCP에도 같은 원칙을 적용합니다. Bearer 토큰 및 사용자 지정 헤더는 신뢰된 전송 계층에서 관리하고, 사용자 정보(userinfo)에 자격 증명이 포함된 MCP URL은 거부합니다. 프로토콜이 제어하는 `Mcp-*` 헤더는 SchemaRouter의 신뢰된 헤더 채널을 통해 덮어쓸 수 없습니다. 사용자 지정 OAuth, mTLS, 프록시 및 게이트웨이 동작은 애플리케이션에서 제공하는 `MCPClientFactory` 뒤에 배치합니다.

Schema watch는 process-local credential과 transport factory를 정확한 registered tool fingerprint 및 credential-free structured-source identity에 고정합니다. Application code가 같은 logical tool key를 다른 source, transport, contract로 교체하면 기존 watch는 **refresh request/session을 열기 전에** `stale_source` 또는 `stale_contract`가 됩니다.
Watch 자체가 검증하고 적용한 compatible refresh는 fingerprint pin만 전진시킬 수 있으며 source/transport identity는 변경되지 않아야 합니다. 따라서 credential rotation에는 implicit carry-over가 아니라 명시적인 trusted-local watch re-registration이 필요합니다.

조건부 스키마 요청 검증자(ETag / Last-Modified)도 데이터 소스에 종속됩니다. SchemaRouter는 저장된 검증자 메타데이터와 함께 구조화된 소스 식별자의 불투명 다이제스트를 저장하고, 프로세스 내부 캐시는 논리적 도구 키와 소스 식별자를 함께 사용해 구분합니다. 같은 키를 유지한 도구 교체, 어댑터 변경 또는 소스 변경이 발생하면 캐시를 사용하지 않고 새로 요청합니다. 새 기능이 이전 레지스트리 키를 재사용했다는 이유만으로 기존 검증자를 전송하거나 신뢰하지 않습니다. 일치하는 소스 다이제스트가 없는 이전 형식 또는 잘못된 검증자 메타데이터는 무시하고 정상적인 전체 요청으로 복구합니다.

### 네트워크 목적지와 SSRF

로컬 개발 도구가 주요 사용 사례이므로 SchemaRouter는 localhost 및 사설 네트워크의 MCP/OpenAPI 엔드포인트를 지원합니다. 따라서 사설 주소나 링크 로컬 주소를 전역적으로 차단하지 않습니다.

`SchemaRouter.from_url()`과 `inspect_url()`은 네트워크 요청을 수행할 수 있는 API로 취급해야 합니다.

애플리케이션이 신뢰할 수 없는 최종 사용자로부터 URL을 받는 경우, 해당 URL을 SchemaRouter에 전달하기 전에 애플리케이션 자체의 네트워크 정책을 적용해야 합니다. 호스팅 서비스는 일반적으로 다음 조치를 취해야 합니다.

- 승인된 호스트 또는 서비스 레지스트리만 허용 목록에 등록합니다.
- 명시적으로 필요한 경우를 제외하고 클라우드 메타데이터 주소, 루프백, 링크 로컬 및 사설 주소를 DNS 해석 결과까지 확인하여 차단합니다.
- 네트워크 계층에서 DNS 리바인딩 공격을 고려합니다.
- 가능한 경우 외부 송신(egress) 제어를 적용합니다.

SchemaRouter는 schema/document redirect를 original origin으로 제한하고 OpenAPI runtime call도 명시적으로 승인된 origin으로 제한합니다. OpenAPI runtime response는 기본 16 MiB limit의 bounded reader를 통해 stream되며 이는 OPTIMADE adapter의 bounded-response posture와 같습니다.

Cross-document OpenAPI `$ref` fetching은 기본적으로 비활성화됩니다. Trusted application code가 opt-in하면 referenced document는 entry document의 origin 안에 있어야 하고 schema header는 그 origin 안에서만 재사용되며 redirect는 same-origin으로 유지되고 depth/document/aggregate-byte limit이 적용됩니다.
`$id` base-URI rebasing 또는 non-JSON-Pointer anchor를 사용하는 document는 현재 resolver가 추측하지 않고 fail-closed합니다.

이 검사들은 application의 initial URL admission policy를 대체하지 않습니다.

### Observability

Run-event argument와 result payload는 기본적으로 redaction됩니다.

`RunConfig(include_payloads=True)`는 user data, API response, identifier 또는 기타 sensitive information을 direct event consumer에 노출할 수 있습니다. Destination이 신뢰되고 적절한 retention control이 있을 때만 payload tracing을 활성화하십시오.

Optional OpenTelemetry exporter는 더 엄격합니다. Structural attribute는 export하지만 underlying event stream이 payload를 허용했더라도 argument value, result payload, RunConfig metadata, tag, exception message는 export하지 않습니다.

영구 실행 추적은 전달받은 `RunEvent` 메시지를 그대로 저장합니다. 기본 런타임 설정에서는 인수 값과 결과 본문이 가려진 상태로 유지됩니다. `RunConfig(include_payloads=True)`를 사용하면 해당 값이 디스크에 기록될 수 있으므로 애플리케이션의 접근 제어, 저장 시 암호화, 백업 및 보존 정책을 적용해야 합니다. SchemaRouter 자체는 SQLite 추적 데이터베이스를 암호화하지 않습니다.

### 승인, 예산 및 재시도

Local execution policy는 첫 번째 side-effect gate입니다. Application은 non-read-only 또는 모든 call에 대해 trusted sync/async approval callback을 추가로 요구할 수 있습니다. Callback 누락, negative decision, callback failure는 execution을 거부합니다.

Per-run budget은 logical call, total attempt, remote attempt, elapsed time, per-tool call, application-defined cost unit을 제한합니다. Retry attempt는 invoker 실행 전에 attempt/remote/cost budget을 소비하며 retry backoff는 남은 elapsed-time budget으로 제한됩니다. Async approval callback과 execution hook도 남은 시간으로 제한되고 synchronous trusted callback은 반환 직후 검사됩니다. Budget refusal과 schema contract violation은 retry하지 않습니다.

Automatic retry는 trusted local code가 non-read-only operation retry를 명시적으로 opt-in하지 않는 한 read-only로 분류된 endpoint로 제한됩니다. Built-in OpenAPI/OPTIMADE HTTP invoker는 보수적인 transient status만 retry하고 다른 HTTP error와 deterministic response-contract failure에는 즉시 실패합니다. Trusted custom invoker는 `NonRetryableInvocationError`를 발생시켜 안전하게 복구할 수 없는 failure의 retry를 막을 수 있습니다.

### 신뢰된 실행 훅

Before/after execution hook은 trusted local executable code이며 redacted telemetry가 아닙니다.
Before hook은 validated argument value를, after hook은 final projected result payload를 볼 수 있습니다. 해당 data를 신뢰할 수 없는 remote/third-party callback에는 연결하지 마십시오.

훅은 분리된 모델 스냅샷을 받으며 실행할 호출이나 반환 결과를 변경할 수 없습니다. `None`이 아닌 훅 반환값은 거부됩니다. 훅에서 예외가 발생하면 안전하게 중단합니다. 특히 **실행 후 훅의 실패는 재시도 가능한 도구 실행 실패로 분류하지 않으므로**, 관측·미들웨어 장애 때문에 이미 성공한 호출을 반복 실행하지 않습니다.

### 신뢰된 계약 수정

`SchemaRouter.amend_capability()`는 invoker binding과 같은 등급의 trusted local code입니다. Remote content, model output, decision backend에서는 접근할 수 없습니다.

계약 수정은 결과의 의미를 선언하거나 주석으로 추가하는 용도로만 허용됩니다. 실행 대상 식별자와 검증 스키마의 변경은 거부하므로 호출을 다른 대상으로 돌리거나, 입력 범위를 넓히거나, 파괴적 작업을 읽기 전용으로 재분류하거나, 원본 소스가 선언한 응답 검증을 완화할 수 없습니다. 거부된 수정 사항은 아무것도 등록하지 않으며 기존 바인딩에도 영향을 주지 않습니다.

도구와 엔드포인트의 `metadata` 수정도 거부됩니다. 자유 형식 주석처럼 보여도 검증 과정에서 필수 조건을 도출할 수 있기 때문입니다. 예를 들어 소스에 `output_schema`가 없을 때 `endpoint.metadata["output_required"]`는 자동 생성된 출력 스키마를 결정합니다. 따라서 메타데이터만 수정해도 명시된 계약 요소나 지문을 변경하지 않은 채 응답에 반드시 포함해야 할 필드를 바꿀 수 있습니다. 이를 방지하기 위해 해당 수정도 허용하지 않습니다.

Amendment에서도 fingerprint는 변경되므로 stale-binding 및 stale-plan protection은 그대로 유지됩니다.

### 타사 어댑터 플러그인

Installed entry point는 local executable code입니다. SchemaRouter는 import 없이 plugin metadata를 inspect할 수 있지만 발견된 plugin을 auto-load하지 않습니다. 실제 import에는 trusted application code가 제공한 명시적인 non-empty allowlist가 필요합니다. Remote content와 model output은 import할 installed plugin을 선택할 수 없습니다.

### 타사 의사결정 백엔드 플러그인

Decision-backend entry point 역시 trusted local executable code입니다. Discovery는 package metadata만 읽으며 trusted application code가 정확한 plugin name 하나를 요청하기 전에는 plugin module을 import하지 않습니다. 이름이 중복되면 모듈을 불러오기 전에 실패 처리하므로 패키지 설치 순서에 따라 구현체가 조용히 선택되는 일을 막습니다.

Loaded decision backend는 여전히 SchemaRouter가 만든 finite option set만 받습니다.
Unknown option ID, duplicate selection, malformed result, invalid score는 일반 `DecisionBackend` validation path에서 fail-closed합니다. Plugin code 자체는 trusted Python code이며 임의 local action을 수행할 수 있으므로 application은 plugin installation/loading을 model output이 아니라 code trust decision으로 취급해야 합니다.

Shared benchmark configuration은 선택된 environment variable에서 명시적으로 전달됩니다. Report는 plugin identity, distribution/version, configuration environment-variable name, configuration key만 기록하며 configuration value는 저장하지 않습니다.

### 사람이 읽는 문서

문서에서 추출한 스키마는 근거 확인(grounding)과 명시적 승인 절차를 모두 통과하기 전까지 실행할 수 없는 제안으로만 취급합니다. 문서 텍스트는 신뢰할 수 없는 입력으로 취급하며, 모델이 분석하기 전에 스크립트와 스타일 콘텐츠를 제거합니다.

## 보안에 민감한 기여 규칙

다음 항목에 영향을 주는 변경에는 적대적 상황을 가정한 회귀 테스트가 필요합니다.

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

- [아키텍처](../architecture.md)
- [어댑터 작성](../adapter-authoring.md)
- [릴리스 체크리스트](../release-checklist.md)

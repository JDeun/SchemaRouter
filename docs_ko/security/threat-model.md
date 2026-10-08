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

Mandatory audit persistence가 필요한 deployment는 `authorization_audit_delivery_mode="strict"`를 opt-in할 수 있습니다. Strict mode는 configured sink를 요구하며 allowed invocation 진행 전에 `AuthorizationAuditDeliveryError`로 fail-closed합니다. If the
underlying authorization decision was deny, the error retains that decision and the original
`PolicyViolationError` separately. Run traces record only privacy-safe delivery-failure flags and
the allow/deny effect, not sink exception text or principal data.

### Credential

Runtime credential은 model-visible tool argument 밖에 유지해야 합니다.

OpenAPI schema-fetch header와 runtime API header는 별도 channel을 사용합니다. Authorization, Cookie, Host, proxy authorization 같은 민감한 header는 model이 선택한
arguments.

Schema, documentation 또는 API URL에 credential을 포함하지 마십시오.

Authenticated MCP에도 같은 원칙을 적용합니다. Bearer/custom header는 trusted transport layer에 두며 userinfo credential이 포함된 MCP URL은 거부합니다. Protocol-controlled `Mcp-*` header는 SchemaRouter의 trusted-header channel로 override할 수 없습니다. Custom OAuth, mTLS, proxy, gateway 동작은 application이 제공하는 `MCPClientFactory` 뒤에 둡니다.

Schema watch는 process-local credential과 transport factory를 정확한 registered tool fingerprint 및 credential-free structured-source identity에 고정합니다. Application code가 같은 logical tool key를 다른 source, transport, contract로 교체하면 기존 watch는 **refresh request/session을 열기 전에** `stale_source` 또는 `stale_contract`가 됩니다.
Watch 자체가 검증하고 적용한 compatible refresh는 fingerprint pin만 전진시킬 수 있으며 source/transport identity는 변경되지 않아야 합니다. 따라서 credential rotation에는 implicit carry-over가 아니라 명시적인 trusted-local watch re-registration이 필요합니다.

Conditional schema-fetch validator(ETag / Last-Modified)도 source-bound입니다. SchemaRouter는 persisted validator metadata와 함께 structured-source identity의 opaque digest를 저장하고 process-local cache를 logical tool key와 source identity 모두로 keying합니다. A same-key
따라서 replacement, adapter change, source change는 uncached 상태로 시작합니다. Replacement capability가 같은 registry key를 재사용했다는 이유만으로 validator를 전송하거나 신뢰하지 않습니다. Legacy or
malformed persisted validator metadata without a matching source digest is ignored and repaired by
a normal full fetch.

### Network destination과 SSRF

Local developer tool이 주요 use case이므로 SchemaRouter는 localhost 및 private-network MCP/OpenAPI endpoint를 지원하며 private 또는 link-local을 전역적으로 거부하지 않습니다.
addresses.

`SchemaRouter.from_url()`과 `inspect_url()`은 network-capable API로 취급해야 합니다.

Application이 untrusted end user의 URL을 받는다면 SchemaRouter에 전달하기 전에 자체 network policy를 적용해야 합니다. Hosted service는 일반적으로 다음을 수행해야 합니다:

- 승인된 host 또는 service registry를 allowlist;
- resolve and reject cloud metadata, loopback, link-local, and private ranges unless explicitly
  required;
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

Persistent run trace는 수신한 정확한 `RunEvent` envelope을 저장합니다. 기본 runtime configuration에서는 argument value와 result payload가 redacted 상태로 유지됩니다. If
`RunConfig(include_payloads=True)`를 사용하면 해당 value가 disk에 기록되어 application의 access-control, encryption-at-rest, backup, retention policy 적용 대상이 될 수 있습니다. SchemaRouter 자체는 SQLite trace database를 암호화하지 않습니다.

### Approval, budget, retry

Local execution policy는 첫 번째 side-effect gate입니다. Application은 non-read-only 또는 모든 call에 대해 trusted sync/async approval callback을 추가로 요구할 수 있습니다. Callback 누락, negative decision, callback failure는 execution을 거부합니다.

Per-run budget은 logical call, total attempt, remote attempt, elapsed time, per-tool call, application-defined cost unit을 제한합니다. Retry attempt는 invoker 실행 전에 attempt/remote/cost budget을 소비하며 retry backoff는 남은 elapsed-time budget으로 제한됩니다. Async approval callback과 execution hook도 남은 시간으로 제한되고 synchronous trusted callback은 반환 직후 검사됩니다. Budget refusal과 schema contract violation은 retry하지 않습니다.

Automatic retry는 trusted local code가 non-read-only operation retry를 명시적으로 opt-in하지 않는 한 read-only로 분류된 endpoint로 제한됩니다. Built-in OpenAPI/OPTIMADE HTTP invoker는 보수적인 transient status만 retry하고 다른 HTTP error와 deterministic response-contract failure에는 즉시 실패합니다. Trusted custom invoker는 `NonRetryableInvocationError`를 발생시켜 안전하게 복구할 수 없는 failure의 retry를 막을 수 있습니다.

### 신뢰된 execution hook

Before/after execution hook은 trusted local executable code이며 redacted telemetry가 아닙니다.
Before hook은 validated argument value를, after hook은 final projected result payload를 볼 수 있습니다. 해당 data를 신뢰할 수 없는 remote/third-party callback에는 연결하지 마십시오.

Hook은 detached model snapshot을 받으며 executable call이나 returned result를 변경할 수 없습니다.
Non-None hook return은 거부됩니다. Hook exception은 fail-closed하며 after-hook failure는
classified as retryable tool failures, preventing an observability/middleware outage from repeating
an already successful invocation.

### 신뢰된 contract amendment

`SchemaRouter.amend_capability()`는 invoker binding과 같은 등급의 trusted local code입니다. Remote content, model output, decision backend에서는 접근할 수 없습니다.

Amendment는 result semantic만 declare하거나 annotate할 수 있습니다. Execution identity와 validation shape는 거부되므로 call redirect, input surface 확대, destructive operation의 read-only 재분류, source가 선언한 response validation 완화가 불가능합니다. A refused amendment registers
nothing and leaves the binding untouched.

`metadata`도 tool과 endpoint 모두에서 거부됩니다. Free-form annotation처럼 보여도 validation이 여기서 requirement를 도출할 수 있기 때문입니다.
(`endpoint.metadata["output_required"]` shapes the synthesized output schema
when a source published no `output_schema`), so a metadata-only amendment
could otherwise change what a response must contain without touching a listed
aspect or the fingerprint.

Amendment에서도 fingerprint는 변경되므로 stale-binding 및 stale-plan protection은 그대로 유지됩니다.

### Third-party adapter plugin

Installed entry point는 local executable code입니다. SchemaRouter는 import 없이 plugin metadata를 inspect할 수 있지만 발견된 plugin을 auto-load하지 않습니다. 실제 import에는 trusted application code가 제공한 명시적인 non-empty allowlist가 필요합니다. Remote content와 model output은 import할 installed plugin을 선택할 수 없습니다.

### Third-party decision-backend plugin

Decision-backend entry point 역시 trusted local executable code입니다. Discovery는 package metadata만 읽으며 trusted application code가 정확한 plugin name 하나를 요청하기 전에는 plugin module을 import하지 않습니다. Duplicate names fail before import so package-install order cannot silently choose an
implementation.

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

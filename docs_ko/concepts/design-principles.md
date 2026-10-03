# 설계 원칙

SchemaRouter는 **schema fidelity, local authority, bounded choice, fail-closed execution**을 우선합니다. remote description이나 model output은 힌트일 수 있지만 permission, credential, transport origin, schema truth를 결정하지 않습니다.

protocol별 세부사항은 adapter에 두고 core에는 canonical typed contract만 노출합니다. retrieval과 execution을 분리하고, plan을 권한으로 취급하지 않으며, 실행 직전에 current registry/fingerprint/binding/policy/schema를 다시 검증합니다.

정확한 정보가 없으면 추론하지 않습니다. unit conversion, semantic alias, side-effect classification, cross-provider equivalence, dynamic schema semantics는 trusted contract가 있을 때만 사용합니다. observability는 기본적으로 payload를 redact하고 optional integration은 core dependency graph를 비대하게 만들지 않습니다.


Provider-first 등록은 provider와 access mode를 합치지 않습니다. `ProviderProfile`은 사용자가
알려진 protocol/SDK를 직접 열거하지 않아도 되게 할 뿐이며, 각 method는 자체 `access_mode`,
schema identity, health, policy 경계를 유지합니다.

State-aware retrieval도 host가 준 explicit typed state만 사용합니다. 기존 stateless
`retrieve`를 바꾸지 않으며 hidden route나 workflow state를 추론하지 않습니다.

Observability는 unified decision trace로 eligibility/state/health/drift/policy/constraint/
negotiation/fallback/lineage를 구조적으로 설명할 수 있지만 hidden capability, rank score,
credential, private header, payload를 노출하지 않습니다.

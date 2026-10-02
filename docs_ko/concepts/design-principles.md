# 설계 원칙

SchemaRouter는 **schema fidelity, local authority, bounded choice, fail-closed execution**을 우선합니다. remote description이나 model output은 힌트일 수 있지만 permission, credential, transport origin, schema truth를 결정하지 않습니다.

protocol별 세부사항은 adapter에 두고 core에는 canonical typed contract만 노출합니다. retrieval과 execution을 분리하고, plan을 권한으로 취급하지 않으며, 실행 직전에 current registry/fingerprint/binding/policy/schema를 다시 검증합니다.

정확한 정보가 없으면 추론하지 않습니다. unit conversion, semantic alias, side-effect classification, cross-provider equivalence, dynamic schema semantics는 trusted contract가 있을 때만 사용합니다. observability는 기본적으로 payload를 redact하고 optional integration은 core dependency graph를 비대하게 만들지 않습니다.

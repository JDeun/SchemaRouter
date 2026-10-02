# 호환성 정책

SchemaRouter는 pre-1.0이지만 공개 contract 변경을 의도적으로 관리합니다. core package는 optional integration 없이 동작해야 하며 LangChain/LangGraph/LlamaIndex/MCP/Jev/Laya/OpenTelemetry 등은 bounded optional dependency로 유지합니다.

지원 Python/version 범위, minimum dependency, Windows smoke, wheel/sdist clean install, public API export, docs build, security automation을 CI에서 검증합니다. protocol compatibility는 deterministic fixture와 scheduled/manual live evidence를 분리해 외부 provider outage를 core regression으로 오판하지 않습니다.

breaking minor change에는 changelog와 migration guidance가 필요하고 patch는 security/correctness fail-closed defect를 제외하면 backward-compatible해야 합니다. persisted SQLite format은 package version과 별도로 versioning하며 unknown/newer/corrupt format을 추측하지 않고 실패합니다.

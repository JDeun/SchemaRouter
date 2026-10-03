# 호환성 정책

SchemaRouter는 pre-1.0이지만 공개 contract 변경을 의도적으로 관리합니다. core package는 optional integration 없이 동작해야 하며 LangChain/LangGraph/LlamaIndex/MCP/Jev/Laya/OpenTelemetry 등은 bounded optional dependency로 유지합니다.

지원 Python/version 범위, minimum dependency, Windows smoke, wheel/sdist clean install, public API export, docs build, security automation을 CI에서 검증합니다. protocol compatibility는 deterministic fixture와 scheduled/manual live evidence를 분리해 외부 provider outage를 core regression으로 오판하지 않습니다.

breaking minor change에는 changelog와 migration guidance가 필요하고 patch는 security/correctness fail-closed defect를 제외하면 backward-compatible해야 합니다. persisted SQLite format은 package version과 별도로 versioning하며 unknown/newer/corrupt format을 추측하지 않고 실패합니다.


Current main의 compatibility coverage에는 provider-first 등록도 포함됩니다. Deterministic
test는 Materials Project/Crossref/Tavily profile resolution과 등록 경계를 검증하고,
scheduled/manual Compatibility Smoke는 Materials Project public OPTIMADE 실제 조회, Crossref
public REST 실제 조회, Tavily auth contract 및 key가 있을 때의 live search를 기록합니다.

또한 state-conditioned retrieval, indexed/incremental capability graph, atomic snapshot
publication, artifact/snapshot migration, decision-trace privacy/inspection integration을 일반
CI에서 검증합니다. 외부 provider outage는 계속 non-blocking compatibility evidence로
취급합니다.

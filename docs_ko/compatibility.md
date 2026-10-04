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


## Native database live acceptance

Native database 호환성은 **deterministic contract/SDK-shape 검증**과 **실제 runtime live
acceptance**를 구분합니다. 전자는 controlled fixture/client shape를 대상으로 bounded adapter
contract를 검증하고, 후자는 실제 local/container 또는 in-process runtime에 연결해 schema
discovery, bounded read/search/traversal, field projection, trusted Principal/DataScope filter,
raw-query authority 비노출을 확인합니다.

현재 Tier A 대표 live surface는 PostgreSQL+pgvector, Qdrant, FalkorDB, MongoDB, Chroma,
ClickHouse입니다. 각 job은 service tag와 실제 client version을 JSON artifact에 기록합니다.
이 결과가 Elasticsearch/OpenSearch, Neo4j, ArangoDB, InfluxDB, Milvus, Couchbase까지 live
검증됐다는 뜻은 아닙니다. 해당 adapter들은 별도 live acceptance가 추가되기 전까지
deterministic contract/SDK-shape evidence로만 표현합니다.

Pinecone, DynamoDB, Azure Cosmos DB, Amazon Neptune처럼 hosted credential이 필요한 대상은
Tier B로 둡니다. 일반 PR CI가 유료/외부 credential에 의존하지 않도록 manual 또는 scheduled
acceptance로 유지하며, credential이 없다는 사실을 live compatibility 증거로 해석하지
않습니다.

Native database adapter를 변경하는 release는 current `main`의 관련 Tier A compatibility
evidence가 최근 green인지 release checklist에서 확인합니다. 외부 public provider outage는
계속 package correctness blocker와 분리합니다.

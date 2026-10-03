# Live adapter 호환성 매트릭스

SchemaRouter는 필수 CI에서 deterministic fixture coverage를 유지하고, public-provider 근거는 별도의 scheduled/manual compatibility workflow로 수집합니다. 공개 서비스는 외부 dependency이므로 outage를 자동으로 SchemaRouter regression으로 분류하지 않고 compatibility evidence로 기록합니다.

## 매트릭스

| Adapter | Deterministic local conformance | Scheduled/manual evidence | 안전한 실행 | 근거 원본 | 알려진 한계 |
| --- | --- | --- | --- | --- | --- |
| OpenAPI | Yes | Live public provider | Read-only metrics request | APIs.guru | 공개 provider availability는 외부 상태 |
| OPTIMADE | Yes | Live public provider | Read-only structure search | COD OPTIMADE | availability와 dataset latency가 달라질 수 있음 |
| GraphQL | Yes | Live public provider | Read-only media query | AniList | introspection availability가 바뀔 수 있음 |
| OData | Yes | Live public provider | Read-only Products query with `$top=1` | OData.org V4 reference service | 제한된 read query만 검증 |
| OpenRPC | Yes | Pinned reference implementation | Harmless local echo method | in-repo local JSON-RPC server | 안정적인 unauthenticated public endpoint를 가정하지 않음 |
| MCP Streamable HTTP | Yes | Pinned reference implementation | Local `add` tool | in-repo MCP SDK fixture server | public MCP endpoint 대신 reference server 사용 |
| Provider profile: Materials Project | Yes | Live public provider | provider identity -> public OPTIMADE -> read-only structure query | Materials Project OPTIMADE | 인증 OpenAPI/SDK는 별도 gate |
| Provider profile: Crossref | Yes | Live public provider | provider identity -> public REST works query | Crossref REST API | public availability는 외부 상태 |
| Provider profile: Tavily | Yes | Auth-contract + optional live | provider identity -> auth-required REST, key가 있으면 live search | Tavily Search API | secret이 없으면 auth-required를 명시하고 실행 성공을 꾸미지 않음 |
| Provider profile: APIs.guru | Yes | Live public provider | provider identity -> OpenAPI -> read-only metrics request | APIs.guru | public availability는 외부 상태 |
| Provider profile: AniList | Yes | Live public provider | provider identity -> GraphQL -> read-only media query | AniList | introspection availability가 바뀔 수 있음 |
| Provider profile: OData V4 reference | Yes | Live public provider | provider identity -> OData -> read-only Products query | OData.org V4 reference service | reference service availability는 외부 상태 |

workflow는 timestamp, SchemaRouter version, source, discovery/execution success, endpoint count, binding state, returned-data shape, latency, auth state, provider-specific note를 machine-readable JSON으로 기록합니다.

## 매트릭스 실행

GitHub Actions **Compatibility Smoke** workflow는 매주 실행되며 수동 실행도 가능합니다. 각 adapter JSON, 통합 JSON/Markdown과 workflow step summary를 생성합니다.

public-provider job은 의도적으로 non-blocking입니다. pinned-reference failure는 repository가 통제하는 compatibility evidence이므로 aggregator에서 다르게 취급합니다.

개별 smoke도 로컬에서 실행할 수 있으며 MCP reference evidence에는 optional MCP dependency가 필요합니다.

## 근거 해석

green public-provider row는 report의 `generated_at` 시점에 provider가 reachable/compatible했다는 뜻이지 영구 availability 보장이 아닙니다. 실패하면 먼저 provider/network/infrastructure 상태인지 분류해야 합니다.

pinned OpenRPC/MCP row는 process-local `ProviderProfile`을 통해 등록한 뒤 기존 adapter로 연결하는 재현 가능한 provider-first compatibility evidence입니다. 실패 시 SchemaRouter 또는 dependency compatibility regression 가능성을 조사해야 합니다.


Provider-first smoke는 다음 스크립트로 개별 실행할 수 있습니다.

```bash
python scripts/live_materials_project_provider_smoke.py
python scripts/live_crossref_provider_smoke.py
python scripts/live_tavily_provider_smoke.py
python scripts/live_provider_first_protocol_smoke.py --provider apis-guru
python scripts/live_provider_first_protocol_smoke.py --provider anilist
python scripts/live_provider_first_protocol_smoke.py --provider odata-v4-reference
```

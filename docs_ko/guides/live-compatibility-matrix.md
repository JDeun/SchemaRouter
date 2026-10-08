# Live adapter compatibility matrix

SchemaRouter는 mandatory CI에서 deterministic fixture coverage를 유지하고 public-provider evidence에는 별도의 scheduled/manual compatibility workflow를 사용합니다. public service는 external dependency이므로 outage는 자동으로 SchemaRouter regression으로 분류하지 않고 compatibility evidence로 기록합니다.

## Matrix

| Adapter | deterministic local conformance | scheduled/manual evidence | safe execution | evidence source | 알려진 제한 |
| --- | --- | --- | --- | --- | --- |
| OpenAPI | 예 | live public provider | read-only metrics request | APIs.guru | public provider availability는 external state입니다. |
| OPTIMADE | 예 | live public provider | read-only structure search | COD OPTIMADE | public provider availability와 dataset latency는 변동될 수 있습니다. |
| GraphQL | 예 | live public provider + pinned reference | read-only media/reference query | AniList + in-repo GraphQL reference | public introspection은 변경될 수 있으며 pinned reference는 release-gated입니다. |
| OData | 예 | live public provider | `$top=1` read-only Products query | OData.org V4 reference service | `$top=1`의 read-only Products query만 검증합니다. |
| OpenRPC | 예 | pinned reference implementation | harmless local echo method | in-repo local JSON-RPC server | stable unauthenticated public execution endpoint를 가정하지 않습니다. |
| MCP Streamable HTTP | 예 | pinned reference implementation | local `add` tool | in-repo MCP SDK fixture server | stable public MCP endpoint를 가정하지 않고 reference server를 사용합니다. |
| Provider profile: Materials Project | 예 | live public provider | provider identity -> public OPTIMADE -> read-only structure query | Materials Project OPTIMADE | authenticated OpenAPI/SDK path는 별도 gate로 유지됩니다. |
| Provider profile: Crossref | 예 | live public provider | provider identity -> public REST -> works query | Crossref REST API | public provider availability는 external state입니다. |
| Provider profile: Tavily | 예 | auth-contract + optional live execution | provider identity -> auth-required REST; `TAVILY_API_KEY` 설정 시 live search | Tavily Search API | secret이 없으면 fabricated execution success가 아니라 explicit auth-required evidence로 기록합니다. |
| Provider profile: APIs.guru | 예 | live public provider | provider identity -> OpenAPI -> read-only metrics request | APIs.guru | public provider availability는 external state입니다. |
| Provider profile: OData V4 reference | 예 | live public provider | provider identity -> OData -> read-only Products query | OData.org V4 reference service | reference-service availability는 external state입니다. |

compatibility workflow는 timestamp, SchemaRouter version, source, discovery/execution success, endpoint count, binding state, returned-data shape, latency, auth state, provider-specific note를 machine-readable JSON으로 기록합니다.

## Matrix 실행

GitHub Actions **Compatibility Smoke** workflow는 매주 실행되며 수동 dispatch도 가능합니다. `adapter-compatibility-matrix` job은 다음을 생성합니다:

- adapter별 `*-compatibility.json` report 하나
- `adapter-compatibility-matrix.json`
- `adapter-compatibility-matrix.md`
- workflow step summary의 동일 Markdown table

public-provider job은 의도적으로 non-blocking입니다. pinned-reference failure는 locally controlled compatibility evidence를 나타내므로 aggregator가 다르게 처리합니다.

개별 smoke는 local에서도 실행할 수 있습니다:

```bash
python scripts/live_graphql_smoke.py --json-out /tmp/graphql-compatibility.json
python scripts/live_odata_smoke.py --json-out /tmp/odata-compatibility.json
python scripts/live_reference_openrpc_smoke.py --json-out /tmp/openrpc-compatibility.json
python scripts/live_reference_mcp_smoke.py --json-out /tmp/mcp-compatibility.json
python scripts/live_reference_graphql_smoke.py --json-out /tmp/graphql-reference-compatibility.json
python scripts/live_materials_project_provider_smoke.py
python scripts/live_crossref_provider_smoke.py
python scripts/live_tavily_provider_smoke.py
python scripts/live_provider_first_protocol_smoke.py --provider apis-guru
python scripts/live_provider_first_protocol_smoke.py --provider odata-v4-reference
```

MCP reference evidence에는 optional MCP dependency가 필요합니다:

```bash
pip install ".[mcp]"
```

## Evidence 해석

green public-provider row는 report의 `generated_at` 시점에 provider가 reachable/compatible했다는 뜻이며 영구 availability 보장은 아닙니다. public-provider failure는 먼저 provider/network/infrastructure state로 분류해야 합니다.

pinned GraphQL, OpenRPC, MCP row는 이 repository가 소유하는 reproducible provider-first compatibility evidence입니다. 각 reference source는 일반 protocol adapter에 도달하기 전에 process-local `ProviderProfile`을 통해 등록됩니다. 여기서의 failure는 SchemaRouter 또는 dependency compatibility regression 가능성이 있으므로 조치 대상입니다.

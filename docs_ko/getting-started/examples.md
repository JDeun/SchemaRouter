# 예제 및 데모 갤러리

이 페이지에서 현재 사용 중인 stack에 맞는 가장 짧은 실행 가능한 SchemaRouter 경로를 선택할 수 있습니다.
예제는 **offline deterministic**이거나 **live/pinned provider**로 명시적으로 표시됩니다.
evidence.

![SchemaRouter field-first, route-second scenario](../assets/real-world-scenario.svg)

## 기존 스택에서 시작하기

| 현재 환경 | 예제 | 확인할 수 있는 내용 |
| --- | --- | --- |
| Provider name | [provider-first guide](../guides/provider-first-registration.md) | provider identity → 안전하게 사용 가능한 access method |
| Python function | [typed callable](https://github.com/JDeun/SchemaRouter/blob/main/examples/quickstart.py) | typed local discovery + execution |
| SDK/client object | [SDK-bound demo](https://github.com/JDeun/SchemaRouter/blob/main/examples/sdk_bound_demo.py) | explicit contract around opaque trusted runtime state |
| Many tools | [context reduction](https://github.com/JDeun/SchemaRouter/blob/main/examples/context_reduction_demo.py) | full catalog과 bounded Top-K retrieval 비교 |
| Multiple providers | [mixed-provider demo](https://github.com/JDeun/SchemaRouter/blob/main/examples/mixed_provider_demo.py) | 상호 보완적인 semantic-field coverage |
| MCP stdio | [stdio quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/mcp_stdio_quickstart.py) | real MCP subprocess discovery and execution |
| MCP Streamable HTTP | [reference smoke](https://github.com/JDeun/SchemaRouter/blob/main/scripts/live_reference_mcp_smoke.py) | real SDK HTTP transport against a pinned server |
| OpenAPI URL | [live OpenAPI quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/live_openapi_quickstart.py) | public provider discovery and execution |
| LangChain | [LangChain quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/langchain_quickstart.py) | `StructuredTool` bridge |
| LangGraph | [LangGraph quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/langgraph_quickstart.py) | SchemaRouter as a graph node |
| LlamaIndex | [LlamaIndex quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/llamaindex_quickstart.py) | `FunctionTool` bridge |
| Persisted registry/traces | [inspection dashboard](https://github.com/JDeun/SchemaRouter/blob/main/examples/inspection_dashboard.py) | live inspection + static HTML dashboard |
| Changing provider schema | [schema drift demo](https://github.com/JDeun/SchemaRouter/blob/main/examples/schema_drift_demo.py) | conservative compatibility classification |
| Typed execution state | [state-aware retrieval](../guides/state-aware-retrieval.md) | fixed Top-K filtering vs eligible Top-K corrective backfill |
| Large capability registry | [graph scalability guide](../guides/capability-graph-scalability.md) | indexed/incremental graph construction + benchmark |
| Portable graph files | [artifacts and snapshots](../guides/capability-artifacts.md) | inspect, validate, migrate versioned capability files |
| Decision observability | [decision trace guide](../guides/capability-decision-traces.md) | privacy-safe candidate/exclusion/fallback 설명 |

The repository-level
[examples README](https://github.com/JDeun/SchemaRouter/tree/main/examples)
에는 정확한 명령, optional extra, 예상 출력 형태, 근거 분류가 정리되어 있습니다.

## 실제 provider 경로

사용자용 quickstart는 공개·read-only이며 key가 필요 없는 APIs.guru를 사용합니다:

```bash
python examples/live_openapi_quickstart.py
```

Provider-first acceptance에서는 Materials Project, Crossref, Tavily도 추가로 검증합니다:

```bash
python scripts/live_materials_project_provider_smoke.py
python scripts/live_crossref_provider_smoke.py
python scripts/live_tavily_provider_smoke.py
```

Materials Project와 Crossref 경로는 실제 read-only provider query를 실행합니다. Tavily는 secret 없이 auth contract를 검증하고 `TAVILY_API_KEY`가 설정되어 있으면 실제 search를 실행합니다.

추가 public compatibility 예제는 다른 protocol surface를 다룹니다:

```bash
python scripts/live_graphql_smoke.py
python scripts/live_odata_smoke.py
```

GraphQL 예제는 Rick and Morty API를 사용하고 OData 예제는 OData.org V4 reference service를 사용합니다. Materials-specific live evidence는 COD OPTIMADE를 통해 확인할 수 있습니다:

```bash
python scripts/live_optimade_smoke.py
```

Public provider uptime은 외부 상태이므로 이 경로들은 mandatory PR gate가 아니라 scheduled/manual compatibility evidence입니다.

## 고정된 protocol reference

안정적인 unauthenticated public provider가 적절하지 않은 경우 fixture를 live public evidence인 것처럼 취급하지 않고 local reference implementation을 사용합니다.

For MCP stdio:

```bash
pip install "schemarouter[mcp]"
python examples/mcp_stdio_quickstart.py
```

MCP Streamable HTTP의 경우:

```bash
python scripts/live_reference_mcp_smoke.py
```

OpenRPC / JSON-RPC의 경우:

```bash
python scripts/live_reference_openrpc_smoke.py
```

## 전후 비교: 모든 schema를 한꺼번에 노출하지 않기

Run:

```bash
python examples/context_reduction_demo.py
```

이 예제는 40-tool registry를 구성하고 다음 serialized size를 보고합니다:

- 전체 registered tool catalog;
- bounded Top-3 `CapabilityRetrieval` result.

Bounded payload는 더 작아야 하며 weather query에서는 weather route가 1위여야 합니다. 이는 token benchmark가 아니라 product demonstration이며 실제 model-token 측정은 research benchmark suite에서 다룹니다.

## Mixed-provider field-first planning

Run:

```bash
python examples/mixed_provider_demo.py
```

한 provider는 `band_gap`을, 다른 provider는 `document_abstract`를 선언합니다. Request는 두 field를 모두 요구하고 두 번의 call을 허용합니다. SchemaRouter는 먼저 semantic field need를 compile한 뒤 상호 보완적인 executable route를 선택합니다.

이는 하나의 logical answer에 heterogeneous source의 evidence가 필요할 때 사용하는 것과 같은 architecture입니다.
providers.

## Schema drift와 운영 검사

Offline drift classifier를 실행합니다:

```bash
python examples/schema_drift_demo.py
```

그 다음 [schema drift and compatibility](../guides/schema-drift.md)를 사용해 remote refresh/watch, pending review, 명시적 accept/reject, fingerprint 동작을 다룹니다.

Runtime observability에는 다음을 사용합니다:

```bash
python examples/inspection_dashboard.py
```

이 예제는 실제 registry와 trace store에서 static HTML dashboard를 생성합니다. [Capability Explorer](schema-explorer.md)는 registered capability에 대한 protocol-neutral Swagger-style view를 제공합니다.

## CI와 재현성

Mandatory CI는 설치된 wheel/sdist artifact로 deterministic example을 실행합니다. Optional integration job은 관련 extra와 함께 framework/MCP example을 실행합니다. Live public provider는 별도 compatibility workflow에 두어 외부 outage가 release를 막지 않게 합니다.


## 0.14 이후 infrastructure 검사

Provider-first acceptance, state-conditioned retrieval, graph scalability, versioned artifact/snapshot migration, decision trace는 stable execution boundary 주변의 additive infrastructure입니다.

유용한 명령:

```bash
python scripts/live_materials_project_provider_smoke.py
python scripts/live_crossref_provider_smoke.py
python scripts/live_tavily_provider_smoke.py
python scripts/benchmark_capability_graph.py --sizes 1000,10000,50000
```

지속 저장되는 portable file에는 다음 명령을 사용합니다:

```bash
schemarouter artifact inspect graph.json --json
schemarouter artifact migrate graph.json --json
schemarouter snapshot inspect snapshot.json --json
schemarouter snapshot migrate snapshot.json --json
```

Decision trace와 typed-state retrieval은 두 번째 workflow runtime이 아니라 각각의 focused guide에서 다룹니다:
[state-aware retrieval](../guides/state-aware-retrieval.md) ·
[decision traces](../guides/capability-decision-traces.md).

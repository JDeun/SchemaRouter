<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-dark.svg">
    <img alt="SchemaRouter" src="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-light.svg" width="680">
  </picture>
</p>

<p align="center"><strong>LLM 도구 생태계를 위한 스키마 인지형 계획·실행 레이어</strong></p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="https://jdeun.github.io/SchemaRouter/">Docs</a> ·
  <a href="https://github.com/JDeun/SchemaRouter/releases/latest">Latest release</a>
</p>

<p align="center">
  <a href="https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml"><img alt="Docs" src="https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml/badge.svg"></a>
  <a href="https://pypi.org/project/schemarouter/"><img alt="PyPI" src="https://img.shields.io/pypi/v/schemarouter"></a>
  <a href="https://github.com/JDeun/SchemaRouter/blob/main/LICENSE"><img alt="MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
</p>

SchemaRouter는 에이전트와 도구 사이에 위치합니다. 자연어 요청과 등록된 capability catalog를
작고 타입이 명확한 실행 계획으로 만들고, 실제 실행 직전에도 그 계획을 다시 검증합니다.

```text
Query
  -> Tool
  -> Endpoint
  -> Parameters
  -> Response fields
  -> Policy / evidence
  -> Schema validation
  -> Execute
```

범용 에이전트 프레임워크를 대체하려는 프로젝트가 아닙니다. LangChain, LangGraph,
LlamaIndex 또는 자체 orchestrator는 위에 두고, OpenAPI, MCP, OPTIMADE, Python callable,
adapter plugin은 아래에 연결하는 **tool-schema boundary**입니다.

### Field-first, route-second

SchemaRouter는 먼저 **사용자 질문에 실제로 필요한 선언된 데이터 필드가 무엇인지**를
결정한 뒤, 그 필드를 제공할 수 있는 provider/access path를 선택합니다. endpoint가
server-side projection을 명시적으로 지원하면 계획된 필드만 upstream에 요청하고, raw
schema 검증 후 final local projection을 다시 적용해 provider가 더 넓은 payload를 보내도
downstream LLM context에는 필요한 데이터만 남깁니다.

가용성 문제는 route를 바꿀 수 있지만 data need 자체를 넓히지는 않습니다. 미리 컴파일된
read-only fallback은 같은 provider의 다른 access mode로 우회하고, 명시적으로 허용한
경우에만 다른 provider로 넘어갑니다. runtime에서 agent식 자율 재탐색은 하지 않습니다.

```text
Agent / graph / application orchestrator
                 |
           SchemaRouter
      typed planning + validation
                 |
        capability sources
 OpenAPI / MCP / OPTIMADE / Python

Laya / Ollama / Jev는 SchemaRouter 내부의 제한된 선택 단계를 보조하는
optional decision backend일 뿐입니다.
에이전트가 되지 않으며, tool loop를 실행하지 않고, 실행 권한도 받지 않습니다.
```

> **현재 안정판: 0.6.0** · `pip install schemarouter` · pre-1.0

## 왜 필요한가

도구가 많아지면 단순한 tool selection만으로는 충분하지 않습니다. SchemaRouter는 실행
경계를 다음처럼 명시적으로 만듭니다.

- 선언된 tool/endpoint만 선택;
- 선언된 parameter/output field만 허용;
- 입력과 raw output을 JSON Schema로 검증;
- 오래된 schema fingerprint와 invoker binding 차단;
- mutation/destructive 권한을 로컬 정책에 유지;
- credential과 model-visible argument 분리;
- retry, elapsed time, remote call, response size 제한;
- OpenAPI 호환성 한계를 추측하지 않고 명시적으로 보고.

## 빠른 시작

```python
from pydantic import BaseModel
from schemarouter import PlanRequest, SchemaRouter, schema_tool


class Weather(BaseModel):
    city: str
    temperature: float


@schema_tool(read_only=True)
def current_weather(city: str) -> Weather:
    return Weather(city=city, temperature=20.5)


router = SchemaRouter()
router.add_callable(current_weather)

result = router.invoke(
    PlanRequest(query="city temperature", arguments={"city": "Seoul"})
)

print(result[0].data)
```

## capability 연결

| Source | 적합한 경우 | Entry point |
| --- | --- | --- |
| **Python** | 로컬 typed capability | `router.add_callable(...)` |
| **OpenAPI** | HTTP API가 machine-readable contract 제공 | `SchemaRouter.from_url(..., kind="openapi")` |
| **MCP** | MCP로 tool 제공 | `SchemaRouter.from_url(..., kind="mcp")` |
| **OPTIMADE** | materials data가 OPTIMADE 제공 | `SchemaRouter.from_url(..., kind="optimade")` |
| **사람이 읽는 문서** | machine-readable schema가 없음 | inspect → proposal → 명시적 승인 |

**LangChain, LangGraph, LlamaIndex**는 framework bridge이고, **OpenTelemetry**는 선택형
telemetry export입니다. **Jev / TypeSafe, Laya, Ollama는 optional decision backend**입니다.
기존 시스템이 사용하는 **GPT, Gemini, Claude 또는 다른 cloud model client**도
provider-neutral `ModelQueryAnalyzer` 또는 `CallableDecisionBackend`로 주입할 수 있습니다.
어떤 경로도 SchemaRouter의 policy/schema validation/execution 경계를 우회하지 않습니다.

## SchemaRouter가 구축한 구조 확인

저장된 registry와 run trace를 실제 도구 실행 없이 확인할 수 있습니다.

```bash
schemarouter inspect registry --db ./registry.sqlite3
schemarouter inspect tool materials --db ./registry.sqlite3
schemarouter inspect diff materials \
  --old-db ./registry-before.sqlite3 \
  --new-db ./registry-current.sqlite3
schemarouter inspect traces --db ./traces.sqlite3
schemarouter inspect trace <RUN_ID> --db ./traces.sqlite3
schemarouter dashboard \
  --registry ./registry.sqlite3 \
  --traces ./traces.sqlite3 \
  --output ./artifacts/schemarouter-dashboard.html
```

inspection 명령에 `--json`을 붙이면 자동화에 사용할 수 있는 구조화된 결과를 출력합니다.
dashboard는 같은 inspection contract를 사용하는 self-contained read-only HTML 파일입니다.
registry 화면에서는 tool/endpoint 구조, HTTP method/path, read-only/mutating 분류,
parameter/output field 수, schema fingerprint를 확인할 수 있고, trace 화면에서는 저장된
실행 이벤트와 오류/완료 상태를 확인할 수 있습니다.

[Operational inspection 가이드](https://jdeun.github.io/SchemaRouter/guides/inspection/)

## 0.6에서 달라진 점

0.6은 bounded decision, 운영 관측, OpenAPI fidelity를 확장한 릴리스입니다.

- CPU/CUDA/MPS를 지원하는 로컬 Laya decision backend;
- 기존 GPT, Gemini, Claude 등 cloud model client를 재사용하는 provider-neutral 경로;
- live/persistent inspection과 self-contained read-only HTML dashboard;
- response `oneOf`/`anyOf` field discovery와 static same-origin `$id`/`$anchor` resolution;
- typed JSON root request body, OpenAPI 3.0 nullable normalization, default parameter style 직렬화.

자세한 내용은 [0.6.0 릴리스 노트](https://jdeun.github.io/SchemaRouter/releases/0.6.0/)를 참고하세요.

## main의 0.7 개발 라인

현재 `0.7.0.dev0`은 agent orchestration을 확장하는 대신 기존 실행 경계를 더 단단하게
만드는 방향입니다.

- exact fingerprint 차단은 유지하면서 변경 원인을 설명하는 보수적 schema diff;
- operation 단위의 로컬 allow/deny/approval policy rule;
- SchemaRouter가 직접 관측 가능한 신호만 기록하는 구조화된 plan explanation;
- 모든 call이 현재 시점에서 명시적 read-only일 때만 허용되는 flat parallel fan-out;
- provider/access identity, bounded read-only fallback, server-side field projection contract,
  복구 가능한 access-path health state;
- 명시적 JSON datatype, optional unit metadata, canonical affine unit normalization, 그리고
  temperature/phase/orientation/method 같은 exact qualifier를 갖는 typed scientific result contract;
- 쿼리에 조건이 명시된 경우 동일한 scientific field를 qualifier로 구분하되 unit conversion이나
  과학적 추론은 수행하지 않는 qualifier-aware routing;
- 동일한 논리 인자를 provider별 로컬 parameter 이름으로 안전하게 연결하는 trusted
  parameter alias.

DAG/workflow, memory, prompt system, autonomous tool loop는 계속 범위 밖에 둡니다.

## 문서

README보다 framework manual을 기준 문서로 사용합니다.

- [설치와 빠른 시작](https://jdeun.github.io/SchemaRouter/getting-started/installation/)
- [실행 모델 이해](https://jdeun.github.io/SchemaRouter/concepts/schema-router/)
- [OpenAPI 가이드](https://jdeun.github.io/SchemaRouter/guides/openapi/)
- [Runtime policy와 retry](https://jdeun.github.io/SchemaRouter/guides/execution-policy/)
- [Framework integration](https://jdeun.github.io/SchemaRouter/integrations/langchain/)
- [API reference](https://jdeun.github.io/SchemaRouter/reference/api/)
- [Architecture와 maturity](https://jdeun.github.io/SchemaRouter/architecture/)
- [Security model](https://jdeun.github.io/SchemaRouter/security/threat-model/)

## 개발

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

ruff check .
pytest -q -m "not mcp_integration"
```

보호된 CI는 Python 3.10–3.14, Windows, minimum dependencies, package artifact, Pyright,
coverage, documentation, optional integration suite까지 검증합니다.

## 프로젝트 범위

SchemaRouter는 별도의 chat abstraction, model-provider layer, memory system, checkpoint store,
graph runtime을 다시 만들지 않습니다.

> **Natural-language request → typed tool execution plan → validated execution.**

## 연구와 라이선스

SchemaRouter는
[SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG](https://github.com/JDeun/paper_SchemaRouter)
연구에서 출발했습니다.

[MIT](LICENSE) © 2026 Yong-eun Cho

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

> **현재 안정판: 0.5.0** · `pip install schemarouter` · pre-1.0

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

**LangChain, LangGraph, LlamaIndex, Jev / TypeSafe, Laya, Ollama, OpenTelemetry**는 선택형 bridge로
연결할 수 있으며 SchemaRouter의 policy/validation 경계를 우회하지 않습니다.

## SchemaRouter가 구축한 구조 확인

0.6 개발 브랜치에서는 저장된 registry와 run trace를 실제 도구 실행 없이 확인할 수 있습니다.

```bash
schemarouter inspect registry --db ./registry.sqlite3
schemarouter inspect tool materials --db ./registry.sqlite3
schemarouter inspect traces --db ./traces.sqlite3
schemarouter inspect trace <RUN_ID> --db ./traces.sqlite3
```

`--json`을 붙이면 자동화나 대시보드에서 사용할 수 있는 구조화된 결과를 출력합니다.
registry 화면에서는 tool/endpoint 구조, HTTP method/path, read-only/mutating 분류,
parameter/output field 수, schema fingerprint를 확인할 수 있고, trace 화면에서는 저장된
실행 이벤트와 오류/완료 상태를 확인할 수 있습니다.

[Operational inspection 가이드](https://jdeun.github.io/SchemaRouter/guides/inspection/)

## 0.5에서 달라진 점

0.5는 범위 확장보다 runtime 안정화에 집중한 릴리스입니다.

- transient-aware HTTP retry와 명시적 non-retryable failure;
- wall-clock execution budget을 넘지 않는 retry backoff;
- approval callback/execution hook까지 elapsed-time budget 적용;
- OpenAPI parameter 우선순위와 자동 endpoint 이름 충돌 처리 개선;
- required JSON body는 보존하되 schema 없는 body는 임의 생성하지 않음;
- protocol-controlled header를 planner argument에서 제외;
- 여러 2xx JSON/no-content 응답 variant를 정확히 보존·검증.

자세한 내용은 [0.5.0 릴리스 노트](https://jdeun.github.io/SchemaRouter/releases/0.5.0/)를 참고하세요.

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

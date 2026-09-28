<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-dark.svg">
    <img alt="SchemaRouter" src="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-light.svg" width="680">
  </picture>
</p>

<p align="center"><strong>RAG와 LLM Agent를 위한 typed capability routing·execution layer</strong></p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="https://jdeun.github.io/SchemaRouter/">Docs</a> ·
  <a href="https://github.com/JDeun/SchemaRouter/releases/latest">Latest release</a>
</p>

<p align="center">
  <a href="https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml"><img alt="Docs" src="https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml/badge.svg"></a>
  <a href="https://pypi.org/project/schemarouter/"><img alt="PyPI" src="https://img.shields.io/pypi/v/schemarouter?label=PyPI&cacheSeconds=300&v=0.10.0"></a>
  <a href="https://github.com/JDeun/SchemaRouter/blob/main/LICENSE"><img alt="MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
</p>

> **현재 안정판: 0.10.0** · `pip install schemarouter` · Beta / pre-1.0

SchemaRouter는 RAG/Agent 애플리케이션과 외부의 구조화된 capability 사이에 위치합니다.
OpenAPI, MCP, OPTIMADE, Python, plugin tool을 하나의 typed capability catalog로 정규화하고,
질문에 필요한 데이터를 제공할 수 있는 제한된 실행 경로를 선택한 뒤 실행 전후에 계약을 다시
검증합니다.

SchemaRouter 자체가 범용 Agent framework나 LLM provider layer, 또는 최종 답변을 생성하는
RAG generator는 아닙니다.

## RAG에서 SchemaRouter의 위치

**RAG(Retrieval-Augmented Generation, 검색 증강 생성)**는 외부의 비파라메트릭 정보원을
retrieval하고, 그 결과를 이용해 generation을 증강하는 구조입니다.

SchemaRouter는 generation을 담당하지 않습니다. 대신 RAG/Agent가 API·MCP·도구에서 최신의
구조화된 외부 데이터를 가져올 때 사용할 수 있는 **retrieval + execution 계층**을 담당합니다.

```text
사용자 질문
    |
    v
RAG / Agent / Application
    |
    |  "탄성계수와 출처가 필요함"
    v
SchemaRouter
    |
    +--> 등록된 capability retrieval
    +--> endpoint + 필요한 field 선택
    +--> parameter / policy / health 검증
    +--> trusted transport 실행
    +--> raw output 검증
    +--> 선언된 unit normalization / field projection
    |
    v
Typed external data
    |
    v
RAG generation / agent reasoning
```

문서 중심 RAG의 retriever가 문서 chunk나 record를 검색한다면, SchemaRouter가 다루는 retrieval
surface는 **실행 가능한 capability와 그 capability가 반환할 수 있는 구조화 데이터**입니다.

[RAG에서의 위치와 capability model](https://jdeun.github.io/SchemaRouter/concepts/capability-catalog/)

## Field-first, route-second

SchemaRouter는 먼저 **무슨 데이터가 필요한지**를 결정한 뒤 그 데이터를 실제로 제공할 수 있는
등록된 경로를 선택합니다.

예를 들어:

```text
질문: "이 소재의 300 K 탄성계수는?"

필요 field
  semantic_id: mechanical.elastic_modulus
  datatype: number
  unit: 해당되는 경우에만 선언
  qualifiers:
    temperature: 300 K

가능한 경로
  provider A / REST endpoint
  provider A / OPTIMADE access
  provider B / MCP tool
```

availability 때문에 route가 바뀔 수는 있지만 요청한 데이터 계약 자체가 조용히 바뀌어서는
안 됩니다.

Field contract에는 다음을 담을 수 있습니다.

- JSON datatype / shape
- semantic ID와 alias
- optional source unit
- 명시적인 canonical unit normalization
- temperature, pressure, phase, orientation, method 등의 exact qualifier
- provenance, license, source-type evidence
- provider/access identity와 availability

단위는 항상 필요한 것이 아닙니다. 텍스트, 식별자, boolean, 구조화 객체, dimensionless 값은
정상적으로 unitless일 수 있습니다. 또한 SchemaRouter는 단위 문자열만 보고 과학적 동등성이나
변환식을 임의로 추론하지 않습니다.

## 실행 경계

```text
LangChain / LangGraph / LlamaIndex / 자체 애플리케이션
                         |
                    SchemaRouter
                         |
          OpenAPI / MCP / OPTIMADE / Python
```

상위 framework가 대화, decomposition, generation, memory, graph, agent loop를 담당하고,
SchemaRouter는 typed capability와 실제 실행 경계를 담당합니다.

Laya, Ollama, Jev/System-One, hosted model, embedding, pairwise decision backend는 이미 등록된
후보 선택을 보조할 수 있지만 실행 권한이 되지는 않습니다. 새로운 tool/field/credential/permission/
side effect를 만들어낼 수 없습니다.

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

## Capability 연결

| Source | 적합한 경우 | Entry point |
| --- | --- | --- |
| **Python** | 로컬 typed capability | `router.add_callable(...)` |
| **OpenAPI** | HTTP API가 machine-readable contract 제공 | `SchemaRouter.from_url(..., kind="openapi")` |
| **MCP** | MCP로 capability 제공 | `SchemaRouter.from_url(..., kind="mcp")` |
| **OPTIMADE** | materials data가 OPTIMADE 제공 | `SchemaRouter.from_url(..., kind="optimade")` |
| **사람이 읽는 문서** | machine-readable contract가 없음 | inspect → proposal → 명시적 승인 |

LangChain, LangGraph, LlamaIndex bridge와 선택형 OpenTelemetry export를 제공합니다.
비표준 decision runtime은 `schemarouter.decision_backends` entry-point plugin으로 연결할 수
있습니다.

## 0.10.0에서 실제로 작동하는 것

현재 배포 버전은 core architecture가 실제 동작하는 beta 구현입니다.

- typed Tool / Endpoint / Parameter / Field registry contract
- Python, OpenAPI, MCP, OPTIMADE ingestion
- field-first planning과 bounded multi-provider field coverage
- input/raw-output JSON Schema validation
- schema fingerprint와 binding drift 차단
- read/write/destructive local policy와 per-call approval
- 명시적 server-side projection + final local projection
- optional datatype/unit normalization과 scientific qualifier
- provider/access fallback, finite cooldown, trusted health recovery
- sync/async invocation, batch, streaming, typed events, trace, inspect/dashboard
- LangChain, LangGraph, LlamaIndex, Jev/System-One, Laya, Ollama, OpenTelemetry integration surface

따라서 **등록된 capability와 지원되는 routing case에 대해서는 지금 배포 버전이 실제로
작동합니다.**

## 현재 한계: open-set 자연어 routing

아직 해결되지 않은 연구 문제는 기본 실행이 아니라 다음 둘을 안정적으로 구분하는 것입니다.

> "이 질문은 등록된 도메인과 비슷하다."

> "이 질문에서 요구한 정확한 operation을 실제 등록 endpoint가 지원한다."

가장 강한 frozen DEV 후보는 목표를 통과했지만 independent zero-overlap fresh confirmation에서
실패했습니다. 따라서 0.10.0에서는 실험적 learned router를 unconditional production default로
승격하지 않았습니다.

첫 arbitrary-tool registry-compiled learned veto 역시 과도한 abstention 때문에 valid request를
대부분 거부하여 terminal reject됐습니다.

자세한 내용:

- [Routing research status](https://jdeun.github.io/SchemaRouter/research/routing-status/)
- [0.10.0 release notes](https://jdeun.github.io/SchemaRouter/releases/0.10.0/)
- [Changelog](CHANGELOG.md)

## Registry와 run 확인

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

## 문서

- [설치](https://jdeun.github.io/SchemaRouter/getting-started/installation/)
- [Quickstart](https://jdeun.github.io/SchemaRouter/getting-started/quickstart/)
- [SchemaRouter란](https://jdeun.github.io/SchemaRouter/concepts/schema-router/)
- [RAG에서의 위치와 capability model](https://jdeun.github.io/SchemaRouter/concepts/capability-catalog/)
- [Field-first execution](https://jdeun.github.io/SchemaRouter/concepts/field-first-execution/)
- [OpenAPI](https://jdeun.github.io/SchemaRouter/guides/openapi/)
- [MCP](https://jdeun.github.io/SchemaRouter/guides/mcp/)
- [Architecture and maturity](https://jdeun.github.io/SchemaRouter/architecture/)
- [Security model](https://jdeun.github.io/SchemaRouter/security/threat-model/)

## 범위

SchemaRouter는 별도의 chat abstraction, prompt framework, model-provider layer, conversation
memory, checkpoint store, graph runtime을 다시 만들지 않습니다.

> **Natural-language request → typed capability plan → validated external data → surrounding RAG/agent**

## 연구와 라이선스

SchemaRouter는
[SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG](https://github.com/JDeun/paper_SchemaRouter)
연구에서 출발했습니다.

[MIT](LICENSE) © 2026 Yong-eun Cho

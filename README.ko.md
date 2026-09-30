<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-dark.svg">
    <img alt="SchemaRouter" src="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-light.svg" width="680">
  </picture>
</p>

<p align="center"><strong>Agent에 연결된 도구는 너무 많고, 각 도구는 필요한 것보다 너무 많이 반환합니다. 그 사이에 typed boundary를 둡니다.</strong></p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="https://jdeun.github.io/SchemaRouter/">Docs</a> ·
  <a href="https://github.com/JDeun/SchemaRouter/releases/latest">Latest release</a>
</p>

<p align="center">
  <a href="https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml"><img alt="Docs" src="https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml/badge.svg"></a>
  <a href="https://pypi.org/project/schemarouter/"><img alt="PyPI" src="https://img.shields.io/pypi/v/schemarouter?label=PyPI&cacheSeconds=300&v=0.12.0"></a>
  <a href="https://github.com/JDeun/SchemaRouter/blob/main/LICENSE"><img alt="MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
</p>

> **현재 안정판: 0.12.0** · `pip install schemarouter` · Beta / pre-1.0

Agent가 사용할 수 있는 도구가 많아질수록 선택은 어려워지고, 도구의 응답에는 질문에 필요하지
않은 데이터까지 함께 들어오는 경우가 많습니다. SchemaRouter는 요청에 **어떤 선언된 data field가
필요한지** 먼저 정하고, 그 데이터를 제공할 수 있는 등록 도구만 제한적으로 노출하며, 모델에
전달되기 전에는 선언된 output field만 남깁니다. Typed contract에는 unit, qualifier, provenance,
validation rule을 담을 수 있어 서로 다른 의미의 값이 조용히 대체되는 것을 막습니다.

`pip install schemarouter`

SchemaRouter 자체가 범용 Agent framework나 LLM provider layer, 또는 최종 답변을 생성하는
RAG generator는 아닙니다.

[outputSchema를 제공하지 않는 MCP server에 result contract 선언하기 →](docs/guides/mcp.md) ·
[실측 agent-utility 결과 보기 →](docs/research/agent-utility-b1-result.md)

## RAG에서 SchemaRouter의 위치

SchemaRouter는 최종 generation을 담당하지 않습니다. 대신 RAG/Agent가 API·MCP·도구에서
구조화된 외부 데이터를 가져올 때 사용할 수 있는 **retrieval + execution boundary**를 제공합니다.

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

## Agent에 compact tool 후보만 제공하기

SchemaRouter는 planning이나 execution 없이 등록된 capability의 **Top-K 후보만** 반환할 수 있습니다.

```python
candidates = router.retrieve(
    "MAT-7의 현재 Young's modulus",
    k=5,
)

for candidate in candidates.candidates:
    print(candidate.route_id, candidate.output_fields)
```

현재 로컬 실행 binding까지 준비된 route만 필요하면 `retrieve_executable(..., k=5)`을 사용합니다.
비동기 API는 `aretrieve`, `aretrieve_executable`입니다.

현재 `main`에는 **experimental·default-off** structural retrieval profile도 포함되어 있습니다.

```python
router = SchemaRouter(structural_retrieval=True)
candidates = router.retrieve("등록된 job을 취소해줘", k=3)
```

이 profile은 보수적인 tool-identifier/operation-family evidence와 schema-specificity tie-break를
추가합니다. 실행 권한은 바뀌지 않으며 product default도 아닙니다. Fixed Top-3 retrieval
confirmation은 통과했지만, 이후 preregistered strong-agent K3-vs-K5 downstream gate에서
task-pass 비열등성 기준(-2pp)을 통과하지 못했습니다. 따라서 Top-3는 held-out benchmark에
승격되지 않았습니다. 다음 release에서 상태가 명시적으로 바뀌기 전까지 structural retrieval은
opt-in research surface로 취급해야 합니다.

후보에는 full effective input/output JSON Schema와 등록된 parameter/output field,
semantic ID, optional unit·qualifier, provider/access identity, read/write/destructive metadata,
schema fingerprint가 유지됩니다.
Retrieval 자체는 side effect가 없고 실행 권한을 부여하지 않습니다. 최종 후보 선택은 상위 Agent가
담당하며 실제 실행은 계속 SchemaRouter의 validation과 policy를 통과해야 합니다.

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

## 0.12.0에서 실제로 작동하는 것

현재 배포 버전은 core architecture가 실제 동작하는 beta 구현입니다.

- typed Tool / Endpoint / Parameter / Field registry contract
- `retrieve` / `aretrieve`와 executable-ready variant를 통한 first-class bounded Top-K capability retrieval
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

## 현재 연구 방향: Agent를 위한 compact capability retrieval

안정판 0.12.0의 실행 경계는 그대로입니다. 다만 현재 연구 질문은 SchemaRouter 자체가 최종
open-set classifier가 되는 것에서, downstream LLM Agent를 위한 **typed capability retrieval
substrate**로 평가하는 방향으로 바뀌었습니다.

역할 분리는 다음과 같습니다.

```text
등록된 capability catalog
  -> SchemaRouter Top-K typed candidate
  -> downstream agent가 후보 안에서 선택
  -> local schema / argument / permission / destructive policy
  -> execution
```

이 구분이 중요한 이유는 보정된 0.14 Phase-A frozen benchmark에서 Top-1 required-route recall은
**68.97%**였지만 Top-5에서는 필요한 capability를 **100%** 보존했기 때문입니다. 등록 endpoint가
250개일 때 Top-5가 노출하는 serialized schema context는 FULL의 평균 **2.38%**에 불과했습니다.

Canonical B1 Qwen3-0.6B agent benchmark도 이제 종료됐습니다. SR-5는 FULL의 **68.48%** 대비
**91.30%** task pass를 기록했고, tool-schema token은 FULL의 **5.42%**만 사용했으며
unauthorized destructive execution은 **0**이었습니다. 다만 이는 controlled mechanism
evidence이며 넓은 production claim은 아닙니다. 더 강한 SmolLM3-3B B2 replication (#423)도 terminal success입니다. 별도의 structural
K3-vs-K5 최적화는 preregistered task-pass promotion gate를 통과하지 못해 K3가 held-out
benchmark에 승격되지 않았습니다. 현재는 execution-state-aware corrective retrieval (#431)이
진행 중이며, 이후 780-task held-out benchmark (#432)와 final-answer quality (#424)가 자동
conveyor의 후속 confirmation stage로 남아 있습니다.

기존 0.11–0.13 open-set classifier/veto 실험은 실패한 기록이 아니라 중요한 negative evidence로
보존합니다. 0.11.0에서 실험적 learned router를 unconditional production default로 승격하지
않는다는 점도 변하지 않으며 structural retrieval도 0.12.0의 unconditional default가 아닙니다.

자세한 내용:

- [Routing research status](https://jdeun.github.io/SchemaRouter/research/routing-status/)
- [선행연구 로드맵](https://jdeun.github.io/SchemaRouter/research/prior-art-roadmap/)
- [전체 실험 인덱스](https://jdeun.github.io/SchemaRouter/research/experiment-index/)
- [0.14 논문 evidence checkpoint](https://jdeun.github.io/SchemaRouter/research/0.14-paper-evidence-checkpoint/)
- [0.12.0 release notes](https://jdeun.github.io/SchemaRouter/releases/0.12.0/)
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
- [선행연구 로드맵](https://jdeun.github.io/SchemaRouter/research/prior-art-roadmap/)
- [Routing research status](https://jdeun.github.io/SchemaRouter/research/routing-status/)
- [전체 실험 인덱스](https://jdeun.github.io/SchemaRouter/research/experiment-index/)

## 범위

SchemaRouter는 별도의 chat abstraction, prompt framework, model-provider layer, conversation
memory, checkpoint store, graph runtime을 다시 만들지 않습니다.

> **Natural-language request → typed capability plan → validated external data → surrounding RAG/agent**

## 연구와 라이선스

SchemaRouter는
[SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG](https://github.com/JDeun/paper_SchemaRouter)
연구에서 출발했습니다.

[MIT](LICENSE) © 2026 Yong-eun Cho

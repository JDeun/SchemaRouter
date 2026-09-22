<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-dark.svg">
    <img alt="SchemaRouter" src="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-light.svg" width="760">
  </picture>
</p>

# SchemaRouter

**LLM 도구 생태계를 위한 스키마 인지형 계획 및 실행 레이어입니다.**

[English](README.md) · [한국어](README.ko.md)

[![CI](https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml/badge.svg)](https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml)
[![Docs](https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml/badge.svg)](https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/JDeun/SchemaRouter/blob/main/LICENSE)

SchemaRouter는 자연어 요청과 등록된 capability catalog를 입력받아 작고, 타입이 명확하며,
감사 가능한 실행 계획으로 컴파일합니다.

단순한 `Query -> Tool` 라우팅보다 더 깊은 수준을 다룹니다.

```text
Query
  -> Tool
  -> Endpoint
  -> Parameters
  -> Response fields
  -> Evidence / policy
  -> Schema validation
  -> Execute
```

SchemaRouter는 LangChain이나 LangGraph를 대체하는 범용 에이전트 프레임워크가 아닙니다.
OpenAPI, MCP, OPTIMADE, Python callable 및 제3자 어댑터와 에이전트 사이의
**tool-schema boundary**를 담당하도록 설계되었습니다.

> 현재 공개 non-prerelease 릴리스는 **0.3.0**입니다. PyPI에서
> `pip install schemarouter`로 설치할 수 있습니다. SchemaRouter는 아직 pre-1.0이므로
> 이후 0.x minor 릴리스에서는 문서화된 버전 정책에 따라 의도적인 호환성 변경이 있을 수 있습니다.

## 왜 필요한가

에이전트가 사용하는 도구가 많아질수록 단순히 “어떤 도구를 호출할지”만 결정해서는
충분하지 않습니다. 런타임은 다음 사항도 알아야 합니다.

- 도구 안에서 어떤 operation/endpoint가 필요한지;
- 어떤 parameter가 실제 스키마에 선언되어 있고 유효한지;
- 응답에서 어떤 field만 유지해야 하는지;
- 해당 operation이 read-only, mutating, destructive, unclassified 중 무엇인지;
- 계획 이후 스키마가 변경되었는지;
- 실제 도구 응답이 선언된 계약을 만족하는지.

SchemaRouter는 이런 결정을 명시적인 타입 계약과 검증 단계로 만듭니다.

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

results = router.invoke(
    PlanRequest(
        query="city temperature",
        arguments={"city": "Seoul"},
    )
)

print(results[0].data)
```

capability source가 달라도 동일한 실행 인터페이스를 사용합니다.

```python
router.invoke(request)
await router.ainvoke(request)

router.batch(requests)
await router.abatch(requests)

router.stream(request)
router.astream(request)
router.astream_events(request)
```

## 스키마 연결

### OpenAPI

```python
router = await SchemaRouter.from_url(
    "https://api.example.com/openapi.json",
    kind="openapi",
)
```

### OPTIMADE

```python
router = await SchemaRouter.from_url(
    "https://www.crystallography.net/cod/optimade",
    kind="optimade",
)
```

OPTIMADE entry schema는 `/info/<entry_type>`에서 탐색하며, 계획된 field는 실행 전에
프로토콜의 `response_fields` query parameter로 변환됩니다.

### MCP

```bash
pip install "schemarouter[mcp]"
```

```python
router = await SchemaRouter.from_url(
    "http://localhost:8000/mcp",
    kind="mcp",
)
```

### Python

```python
router.add_callable(my_typed_function)
```

### 사람이 읽는 API 문서

```python
proposal = await router.inspect_url(
    "https://docs.example.com/api",
    model=documentation_model,
)

router.approve_proposal(
    proposal,
    base_url="https://api.example.com",
)
```

HTML 등 사람이 읽는 문서는 자동으로 executable tool이 되지 않습니다. 먼저 근거가 포함된
proposal로 변환한 뒤 명시적인 승인을 받아야 합니다.

## 핵심 보장

- **Schema-constrained planning** — 등록되지 않은 tool, endpoint, parameter, field는 실행
  가능한 호출이 될 수 없습니다.
- **Runtime JSON Schema validation** — 호출 전 argument와 projection 전 raw output을
  검증합니다.
- **Bounded nested projection** — 선언된 logical field만 명시적 nested object path에
  매핑할 수 있으며 모델이 임의 JSONPath나 미선언 경로를 만들 수 없습니다.
- **Schema / binding drift detection** — 오래된 plan이나 transport binding은 fail closed로
  차단합니다.
- **Local execution authority** — 원격 metadata나 모델 출력이 mutation/destructive 권한을
  부여할 수 없습니다.
- **Credential separation** — schema fetch credential과 runtime credential을 분리하며,
  인증 MCP secret은 trusted transport 경계 안에만 둡니다.
- **Read-only retry by default** — 계약 위반이나 위험한 호출을 자동 재시도하지 않습니다.
- **호출별 승인 및 실행 budget** — trusted local callback과 call/attempt/remote/time/quota/
  cost-unit 제한을 fail-closed로 적용합니다.
- **OpenAPI compatibility report** — partial/unsupported construct를 숨기지 않고
  machine-readable report로 노출합니다.
- **Redacted runtime event by default** — payload trace는 명시적으로 opt-in해야 합니다.
- **Persistent/pluggable registry** — built-in transactional `SQLiteRegistry`를 사용하거나
  공개 `ToolRegistry` protocol 기반 커스텀 구현을 주입할 수 있습니다. persistent catalog에는
  trusted invoker나 credential을 직렬화하지 않습니다.
- **Pluggable adapter** — `AdapterRegistry`를 통해 다양한 structured protocol을 동일한
  `ToolSpec` / `EndpointSpec` 실행 모델로 변환할 수 있으며, 설치된 entry-point plugin은
  명시적 allowlist가 있어야 import됩니다.
- **선택형 OpenTelemetry export** — payload 값 없이 redacted runtime event를 run/tool span으로
  변환할 수 있습니다.

## LangChain과 사용

```bash
pip install "schemarouter[langchain]"
```

```python
from schemarouter.integrations import to_langchain_tools

tools = to_langchain_tools(router)
```

LangChain 도구로 노출해도 실행은 SchemaRouter의 policy, fingerprint, input/output validation
경계를 그대로 통과합니다.

## LangGraph와 사용

```bash
pip install "schemarouter[langgraph]"
```

```python
from schemarouter.integrations import to_langgraph_node

builder.add_node("schema_router", to_langgraph_node(router))
```

이 노드는 sync/async `StateGraph` 실행을 지원하고 checkpoint에 적합한 partial state update를
반환합니다. planning, policy, 검증된 execution authority는 SchemaRouter가 계속 유지합니다.

## LlamaIndex와 사용

LlamaIndex bridge는 패키지 extra로 설치할 수 있습니다.

```bash
pip install "schemarouter[llamaindex]"
```

```python
from schemarouter.integrations import to_llamaindex_tools

tools = to_llamaindex_tools(router)
```

LlamaIndex는 agent/workflow orchestration을 담당하고, SchemaRouter는 schema identity,
validation 및 endpoint execution 경계를 유지합니다.

## 실험적 bounded decision

SchemaRouter는 tool/endpoint와 output field 선택을 보조하는 opt-in `DecisionBackend`를
제공합니다. 기본값은 **OFF**이며 모델이 임의의 실행 가능한 스키마 멤버를 만들 수 없습니다.

```python
from schemarouter import DecisionPolicy, SchemaPlanner
from schemarouter.integrations import JevDecisionBackend

planner = SchemaPlanner(
    registry,
    decision_backend=JevDecisionBackend(min_confidence=0.65),
    decision_policy=DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
        fallback="deterministic",
    ),
)
```

특정 provider에 종속되지 않는 local embedding backend도 core dependency 추가 없이 사용할 수
있습니다.

```python
from schemarouter import EmbeddingDecisionBackend

backend = EmbeddingDecisionBackend(
    embed_batch,
    min_similarity=0.35,
    min_margin=0.05,
)
```

callable에는 local SentenceTransformers/FastEmbed 계열 encoder나 애플리케이션 소유 embedding
service를 연결할 수 있습니다. cosine ranking은 SchemaRouter가 로컬에서 수행하며 약하거나
모호한 선택은 abstain할 수 있습니다.

Jev / TypeSafe System One은 선택형 기능입니다.

```bash
pip install "schemarouter[jev]"
export TYPESAFE_API_KEY="..."
```

Jev는 SchemaRouter가 미리 허용한 유한한 option 중 하나만 선택합니다. 존재하지 않는 option
ID는 confidence와 무관하게 fail closed 처리되고, 유효하지만 confidence가 낮은 선택은
abstain한 뒤 deterministic fallback으로 돌아갈 수 있습니다.

패키지를 설치했거나 API key가 존재한다는 이유만으로 Jev가 자동 활성화되지는 않습니다.

로컬 Ollama 모델도 별도 Python SDK 없이 bounded decision backend로 사용할 수 있습니다.

```python
from schemarouter.integrations import OllamaDecisionBackend

backend = OllamaDecisionBackend("your-installed-model")
```

Ollama structured output으로 유한한 option ID를 제한하고, SchemaRouter가 결과를 다시 로컬
검증합니다. 로컬 모델이 존재한다는 이유만으로 자동 활성화되지는 않습니다.

bounded field selection도 별도로 opt-in할 수 있습니다.

```python
policy = DecisionPolicy(
    enabled=True,
    field_selection=True,
    fallback="deterministic",
)
```

backend에는 선언된 non-identifier field만 제공되고 identifier field는 항상 로컬에서
보존됩니다. invalid output이나 abstain은 deterministic projection으로 fallback됩니다.

Evidence sufficiency도 별도로 opt-in할 수 있는 보수적 gate입니다.

```python
policy = DecisionPolicy(
    enabled=True,
    evidence_sufficiency=True,
    fallback="deterministic",
)
```

요청된 provenance/license/unit/source-type은 먼저 로컬 schema metadata로 충족되어야 합니다.
그 뒤 backend는 `evidence:sufficient` / `evidence:insufficient` 두 선택지만 받으며,
로컬에서 충분한 call을 veto할 수 있을 뿐 없는 evidence를 만들어내거나 실행 권한을 높일 수
없습니다.

## Decision benchmark

기본 deterministic routing을 측정합니다.

```bash
python scripts/benchmark_decision_routing.py
```

local embedding callable도 같은 corpus에서 비교할 수 있습니다.

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --embedding-callable my_embeddings:embed_batch
```

API key가 있다면 같은 케이스로 Jev도 비교할 수 있습니다.

```bash
TYPESAFE_API_KEY="..." python scripts/benchmark_decision_routing.py --jev
```

설치된 로컬 Ollama 모델도 같은 corpus로 비교할 수 있습니다.

```bash
python scripts/benchmark_decision_routing.py --ollama-model your-installed-model
```

benchmark에는 144개 multilingual/adversarial 고정 corpus가 포함되며 routing accuracy,
invalid-plan rate, abstention/fallback, category accuracy, p50/p95 latency, token usage, error와
선택적인 비용 추정치를 기록합니다. `--model-callable module:function`을 이용하면
provider-neutral `ModelQueryAnalyzer`도 같은 harness에서 비교할 수 있고, embedding
encoder는 `--embedding-callable module:function`으로 연결할 수 있습니다.

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --json-out artifacts/decision-benchmark.json \
  --csv-out artifacts/decision-benchmark.csv
```

## 문서

전체 문서는 framework manual 형태로 구성되어 있습니다.

- [Getting started](https://jdeun.github.io/SchemaRouter/getting-started/installation/)
- [Core concepts](https://jdeun.github.io/SchemaRouter/concepts/schema-router/)
- [OpenAPI guide](https://jdeun.github.io/SchemaRouter/guides/openapi/)
- [OpenAPI compatibility](https://jdeun.github.io/SchemaRouter/guides/openapi-compatibility/)
- [OPTIMADE guide](https://jdeun.github.io/SchemaRouter/guides/optimade/)
- [MCP guide](https://jdeun.github.io/SchemaRouter/guides/mcp/)
- [LangChain integration](https://jdeun.github.io/SchemaRouter/integrations/langchain/)
- [LlamaIndex integration](https://jdeun.github.io/SchemaRouter/integrations/llamaindex/)
- [Jev / TypeSafe integration](https://jdeun.github.io/SchemaRouter/integrations/jev/)
- [Ollama decision backend](https://jdeun.github.io/SchemaRouter/integrations/ollama/)
- [OpenTelemetry integration](https://jdeun.github.io/SchemaRouter/integrations/opentelemetry/)
- [Third-party adapter plugins](https://jdeun.github.io/SchemaRouter/guides/adapter-plugins/)
- [Decision backends](https://jdeun.github.io/SchemaRouter/concepts/decision-backends/)
- [Decision benchmark](https://jdeun.github.io/SchemaRouter/guides/decision-benchmark/)
- [Persistent run traces](https://jdeun.github.io/SchemaRouter/guides/run-traces/)
- [Field projection](https://jdeun.github.io/SchemaRouter/guides/field-projection/)
- [Candidate indexing](https://jdeun.github.io/SchemaRouter/guides/candidate-indexing/)
- [API reference](https://jdeun.github.io/SchemaRouter/reference/api/)
- [Architecture](https://jdeun.github.io/SchemaRouter/architecture/)
- [Security](https://github.com/JDeun/SchemaRouter/blob/main/SECURITY.md)

로컬 문서 서버:

```bash
pip install -e ".[docs]"
mkdocs serve
```

## 개발

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

ruff check .
pytest -q -m "not mcp_integration"
python examples/quickstart.py
python scripts/benchmark_decision_routing.py

# 선택형 통합을 포함한 전체 패키지 surface 타입 검사
pip install -e ".[dev,mcp,langchain,langgraph,llamaindex,jev,otel]"
pyright
pytest -q --cov=schemarouter --cov-branch --cov-report=term-missing
```

선택형 통합은 코어 의존성과 분리되어 있습니다.

```bash
pip install -e ".[dev,mcp]"
pytest -q tests/test_mcp_integration.py

pip install -e ".[dev,langchain]"
pytest -q tests/test_langchain_integration.py

pip install -e ".[dev,llamaindex]"
pytest -q tests/test_llamaindex_integration.py

pip install -e ".[dev,jev]"
pytest -q tests/test_jev_integration.py

pip install -e ".[dev,otel]"
pytest -q tests/test_opentelemetry_integration.py
```

## 프로젝트 범위

SchemaRouter는 별도의 chat abstraction, graph runtime, model-provider framework, memory system,
checkpoint store를 다시 만들지 않습니다. 이런 역할은 상위 orchestration framework가 담당하는
것이 적절합니다.

SchemaRouter가 집중하는 범위는 다음과 같습니다.

> **Natural-language request -> typed tool execution plan -> validated execution.**

## 연구 배경

SchemaRouter는
[SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG](https://github.com/JDeun/paper_SchemaRouter)
연구에서 출발했습니다.

프레임워크 버전은 연구 아이디어를 유지하면서 “도구당 endpoint 하나”나 fixture-only 실행과
같은 연구 harness의 가정을 제거하고 실제 애플리케이션에서 사용할 수 있는 실행 경계로
확장했습니다.

## 라이선스

[MIT](LICENSE) © 2026 Yong-eun Cho

# Developer launch playbook

이 playbook은 SchemaRouter의 기존 runnable example과 public evidence를 재사용 가능한 developer-facing launch material로 구성합니다. 하루짜리 star 급증이 아니라 **qualified technical exposure**를 목표로 합니다.

## Launch 목표

Developer가 2분 안에 다음 내용을 이해할 수 있어야 합니다:

> SchemaRouter는 LLM/RAG 에이전트를 위한 타입 기반 기능 검색 및 스키마 인식 실행 계층입니다.
> 방대한 도구 카탈로그에서 현재 요청에 필요한 기능과 필드만 좁혀 검색하고,
> 실제 실행은 등록된 스키마, 로컬 정책, 신뢰할 수 있는 바인딩의 통제를 받도록 합니다.

The primary call to action is:

```bash
pip install "schemarouter==0.14.0"
```

일반 설치에서는 `pip install schemarouter`가 최신 안정 버전을 설치합니다. 공개 데모의 재현성을 위해 출시 안내 예제는 `0.14.0`으로 버전을 고정합니다.

Repository: <https://github.com/JDeun/SchemaRouter>

Docs: <https://jdeun.github.io/SchemaRouter/>

Runnable examples: <https://github.com/JDeun/SchemaRouter/tree/main/examples>

## 공개적으로 주장할 수 있는 내용

공개할 기술적 주장은 재현 가능한 산출물에 연결해야 합니다.

### Stable product

- 안정화된 릴리스: `0.14.0`, 베타 / 1.0 이전 버전;
- Python 3.10~3.14는 릴리스 차단 조건에 해당하는 CI 검증 대상;
- MCP, OpenAPI, OPTIMADE, GraphQL, OData, OpenRPC/JSON-RPC, Python/SDK 바인딩,
  LangChain/LangGraph, LlamaIndex에서 타입 기반 수집·실행 경로를 지원;
- 검색 점수나 모델 판단은 실행 권한을 부여하지 않음;
- 릴리스 산출물에는 wheel, sdist 및 SPDX SBOM이 포함되고 출처·검증 절차는
  공개 신뢰 문서에 기록됨.

### Controlled research evidence

과제 23개를 동결한 Qwen3-0.6B B1 실험에서 확인된 내용:

- SR-5 task pass: **91.30%**;
- FULL task pass: **68.48%**;
- SR-5 schema-token ratio: **5.42%**;
- required-route recall: **100%**.

이는 해당 워크로드의 통제된 메커니즘 근거입니다. SchemaRouter가 모든 에이전트·모델·워크로드·최종 답변에서 성능을 향상시킨다는 모집단 수준의 주장은 **아닙니다**.

구조적 K3 대 K5 승격 검증도 부정적 결과를 내어 승격되지 않았습니다. 연구를 소개할 때 이 결과도 숨기지 않고 제시해야 합니다.

검증 자료 색인:
<https://jdeun.github.io/SchemaRouter/project/trust-and-evidence/>

## What not to claim

Do not say:

- "SchemaRouter를 쓰면 모든 에이전트의 정확도가 높아진다";
- "SchemaRouter는 운영 환경에서 토큰 사용량을 94.58% 줄인다";
- "SchemaRouter는 다른 모든 라우터보다 안전하다";
- "Jev/Laya/Ollama가 최고의 결정 백엔드다";
- 외부 채택 사례나 사례 연구 없이 "운영 환경에서 검증됐다"고 주장;
- 명시적 허락 없이 어떤 조직이 "사용 중"이라고 주장.

이슈 #15는 실시간 결정 백엔드의 검증 자료를 추적하며, 이슈 #584는 외부 도입과 독립 검증을 관리합니다.

## Core launch narrative

### Problem

에이전트 시스템은 종종 전체 도구 카탈로그를 모델의 문맥에 넣습니다. 카탈로그가 커지면 서로 다른 두 문제가 뒤섞입니다:

1. **검색** — 현재 요청과 관련된 기능·출력 필드는 무엇인가?
2. **실행 권한** — 실제로 실행해도 되는 등록 작업은 무엇인가?

모든 스키마를 모델에 전달해도 두 경계가 제대로 구분되는 것은 아닙니다. 문맥이 불필요하게 커지고 관련 없는 필드가 노출되며, 모델이 선택했거나 원격에서 설명된 작업을 실행 권한으로 잘못 취급하도록 구현이 유도될 수 있습니다.

### Approach

SchemaRouter inserts a typed boundary:

```text
user request
   -> required declared fields
   -> bounded registered capability candidates
   -> local validation/policy/binding checks
   -> trusted invocation
   -> raw output validation
   -> declared-field projection
   -> agent / RAG context
```

SchemaRouter는 별도의 에이전트 런타임이 되려는 것이 아닙니다. LangChain, LangGraph, LlamaIndex 또는 사용자 애플리케이션이 기존 오케스트레이션 제어권을 유지합니다.

### Why it matters

이 설계는 **검색 결과를 곧 실행 권한으로 바꾸지 않으면서** 문맥 오염을 줄이는 것이 목표입니다. 제공자 메타데이터는 기능을 설명할 수 있지만 실제 실행 권한은 신뢰된 로컬 애플리케이션 상태가 결정합니다.

## 30-second demo

첫 시연은 네트워크 연결이나 API 키에 의존하지 않도록 결정론적인 문맥 축소 데모로 진행합니다.

### Recording flow

Terminal:

```bash
git clone https://github.com/JDeun/SchemaRouter
cd SchemaRouter
python -m venv .venv
source .venv/bin/activate
pip install -e .
python examples/context_reduction_demo.py
```

Show, in order:

1. 도구 40개로 구성된 카탈로그
2. 자연어 요청 1개
3. 타입 기반 Top-3 기능 검색 결과
4. 전체 카탈로그와 제한된 검색 결과의 직렬화 바이트 수 비교
5. 1순위로 선택된 날씨 관련 경로

Overlay/caption:

> "모델에 모든 도구 스키마를 전달하지 마세요. 요청에 필요한 타입 기반 기능만 검색하고, 로컬 계약을 통해서만 실행하세요."

직렬화된 바이트 수를 모델 토큰 수로 표기해서는 안 됩니다.

## Five-minute technical walkthrough

### 0:00-0:40 — The failure mode

큰 도구 카탈로그를 보여주고 '모든 스키마를 그냥 전달하는 방식'이 불필요한 문맥을 늘리고 관련성과 권한을 혼동하게 하는 이유를 설명합니다.

### 0:40-1:30 — Capability retrieval

Run:

```bash
python examples/context_reduction_demo.py
```

`retrieve(..., k=3)`와 `retrieve_executable(..., k=3)`의 차이 및 검색된 후보가 타입 기반 입력·출력 계약을 유지한다는 점을 설명합니다.

### 1:30-2:40 — Real provider ingestion

별도 인증이 필요 없는 공개 OpenAPI 예제를 실행합니다:

```bash
python examples/live_openapi_quickstart.py
```

Explain:

```text
external schema -> registered typed capability -> bounded plan -> validated execution -> typed result
```

### 2:40-3:30 — Framework fit

LangChain·LangGraph·LlamaIndex 예제를 보여주면서 SchemaRouter가 에이전트 그래프나 대화 런타임을 소유하지 않는다는 점을 강조합니다.

### 3:30-4:20 — Execution boundary

Show the trust model:

- 스키마 지문 및 바인딩
- 입력·출력 JSON Schema 검증
- 로컬 부작용 정책
- 파괴적 작업 오류 시 안전하게 거부
- 스키마 변경 시 기존에 승인된 실행 권한이 조용히 대체되지 않음

### 4:20-5:00 — Evidence and invitation

신뢰·근거 페이지와 예제 모음을 열어 보여줍니다. B1 통제 실험의 정확한 범위를 설명하고 K3의 부정적인 결과도 언급한 다음, 실제 통합 과정의 불편 사항에 대한 의견을 구합니다.

## "모든 도구 스키마를 LLM에 전달하면 안 되나요?"

이 질문을 받으면 다음과 같이 설명합니다:

> 규모가 작고 도구 구성이 고정돼 있다면 모든 스키마를 전달하는 방법도 충분히 합리적일 수 있습니다. SchemaRouter는 카탈로그가 크거나 이질적이거나 운영상 민감한 상황을 대상으로 합니다. 필요한 타입 기반 기능 집합과 출력 필드만 제한적으로 검색하고 실행 권한은 등록된 로컬 계약에 둡니다. 목표는 "모델에 스키마를 절대 보여주지 말자"가 아니라 "전체 카탈로그를 전달하지 않아도 되도록 하고, 스키마의 관련성이 실행 허가로 바뀌지 않게 하자"입니다.

Key distinctions:

| Concern | Sending all schemas | SchemaRouter boundary |
| --- | --- | --- |
| catalog context | whole selected catalog | bounded capability retrieval |
| output context | often full provider response | declared field projection |
| authority | easy to conflate with model choice | local policy + trusted binding |
| drift | application-specific | fingerprinted schema lifecycle |
| framework | tied to prompting pattern | sits beneath/alongside agent frameworks |

## Integration snippets

### OpenAPI

```python
router = await SchemaRouter.from_url(
    "https://api.apis.guru/v2/openapi.yaml",
    kind="openapi",
)
```

### MCP stdio

See the runnable pair:

```bash
python examples/mcp_stdio_quickstart.py
```

### LangChain

```bash
pip install "schemarouter[langchain]"
python examples/langchain_quickstart.py
```

### LangGraph

```bash
pip install "schemarouter[langgraph]"
python examples/langgraph_quickstart.py
```

### LlamaIndex

```bash
pip install "schemarouter[llamaindex]"
python examples/llamaindex_quickstart.py
```

## Channel playbooks

### Hacker News / Show HN

> **2026년 게시 유의 사항:** Hacker News는 제출자가 HN 게시글과 댓글을 직접 작성하도록 요구하며 LLM이 생성하거나 수정한 문구를 그대로 게시하지 않도록 안내하고 있습니다. 일반적인 커뮤니티 참여 이력이 부족한 계정에는 Show HN 게시가 일시적으로 제한될 수도 있습니다. 제출 전 공식 Show HN 및 사이트 지침을 다시 읽고 관리자의 계정이 게시 가능한지 확인하세요. 아래 초안은 내부 검토용 항목으로만 취급하고 Hacker News에 복사해 게시하지 마세요.

Show HN은 가입 없이도 직접 실행하고 코드를 검토할 수 있는 프로젝트에 적합하므로 이 조건에서만 사용합니다.

Proposed title:

> **Show HN: SchemaRouter – typed capability retrieval for agents with too many tools**

Suggested first comment:

> SchemaRouter는 에이전트 개발 과정에서 같은 문제를 반복해서 겪은 끝에 만들었습니다. 도구 카탈로그가 커질수록 "어떤 스키마가 관련되는가?"와 "실제로 실행을 허용해도 되는가?"라는 질문이 뒤섞이기 시작했습니다.
>
> SchemaRouter는 에이전트/RAG 스택 아래에서 사용하는 Python 라이브러리입니다. 제한된 타입 기반 기능 집합을 검색하고 필드 단위 계약을 유지하며 등록된 로컬 바인딩과 정책으로만 실행합니다. MCP, OpenAPI, Python/SDK 도구, LangChain/LangGraph, LlamaIndex 및 여러 구조화 프로토콜을 지원합니다.
>
> 저장소에는 가입 없이 실행할 수 있는 예제가 있습니다. 도구 40개를 사용하는 문맥 축소 데모와 공개 OpenAPI 빠른 시작 안내 등이 포함됩니다. 벤치마크 수치 하나만 제시하는 대신 릴리스·SBOM·실증 근거의 경계도 공개했습니다.
>
> 특히 대규모 도구 카탈로그를 운영하는 분들의 기술적 비판을 듣고 싶습니다. 여러분의 스택에서는 기능 검색이 어느 시점부터 유용해지며, 어떤 연동 장벽이 별도의 타입 기반 경계를 도입하는 것을 가로막을까요?

실제 게시 시 지켜야 할 규칙:

- 가입이나 마케팅 페이지가 아닌 실행 가능한 저장소에 직접 연결합니다;
- 기술적인 질문이 올라오면 답변할 수 있도록 참여합니다;
- 추천이나 댓글을 요청하지 않습니다;
- 다른 커뮤니티를 통해 투표를 조직하지 않습니다;
- 사소한 릴리스 변경을 반복적인 Show HN 게시글로 올리지 않습니다.

공식 안내:
<https://news.ycombinator.com/showhn.html>

### Reddit

동일한 홍보 글을 여러 커뮤니티에 그대로 반복 게시하지 **않습니다**.

게시할 당일에 각 커뮤니티의 최신 규칙을 확인하고, 해당 기술적 문제가 직접적으로 관련되는 곳을 우선합니다.

Reusable technical post:

**Title**

> I built an OSS typed tool-schema boundary for agents — looking for feedback on large tool catalogs

**Body**

> 에이전트/RAG 시스템에서 계속 발견한 문제는 검색과 실행 권한의 분리였습니다. 도구 검색은 관련된 기능을 찾는 것이지 해당 기능의 실행을 자동으로 허가하는 일이 아닙니다.
>
> SchemaRouter는 구조화된 기능을 파싱·등록하고 제한된 타입 기반 후보 집합을 검색하며 로컬 계약을 통해 실행을 검증하는 MIT 라이선스 Python 라이브러리입니다. 결과가 모델로 돌아가기 전에 선언된 출력 필드만 투영합니다.
>
> LangChain/LangGraph/LlamaIndex를 대체하지 않고 함께 동작합니다. MCP, OpenAPI, Python/SDK 도구와 여러 구조화 프로토콜을 지원합니다.
>
> 가장 간단한 결정적 데모는 40개 도구 카탈로그를 구성하고 전체 카탈로그 직렬화와 타입 기반 Top-3 검색을 비교합니다.
>
> `python examples/context_reduction_demo.py`
>
> 저장소: https://github.com/JDeun/SchemaRouter
>
> 별점보다는 기술적 비판을 원합니다. 대규모 도구 카탈로그를 운영한다면, 에이전트 앞단에서 기능 라우터를 신뢰하기 위해 어떤 정보를 반드시 보존해야 한다고 생각하시나요?

Before posting:

- 해당 커뮤니티의 자기 홍보 및 외부 링크 규칙 확인
- 프로젝트 관리자라는 사실 명시
- 반복 노출보다 커뮤니티 주제에 맞는 실질적인 글 한 편 작성
- 요청받지 않은 개인 메시지 금지
- 투표 요청 금지

Reddit의 전체 사이트 스팸 지침은 반복적이거나 원치 않는 대량 참여 요청을 스팸으로 취급하며, 개별 커뮤니티의 규칙이 더 엄격할 수도 있다고 설명합니다.

### LinkedIn

일반적인 제품 발표문보다 개발 과정에서 얻은 실제 기술적 경험을 중심으로 작성합니다.

Draft:

> 도구 라우팅은 카탈로그가 작을 때만 단순해 보였습니다.
>
> 에이전트 시스템에서 "어떤 도구가 관련 있는가?"와 "어떤 작업의 실행을 실제로 허용하는가?"는 다른 질문입니다.
>
> SchemaRouter는 바로 이 차이를 바탕으로 만들었습니다.
>
> MCP, OpenAPI, Python/SDK 도구, LangChain/LangGraph, LlamaIndex 및 기타 구조화된 출처의 타입 기반 기능 검색과 스키마 인식 실행을 담당하는 오픈소스 Python 계층입니다.
>
> 설계는 필드 우선 방식입니다. 요청에 필요한 데이터를 식별하고, 제한된 기능 집합을 검색한 다음, 로컬 권한·바인딩을 검증하고 실행합니다. 이어서 원시 출력을 검증하고 선언된 필드만 에이전트 문맥으로 돌려보냅니다.
>
> 연구 주장은 의도적으로 제한했습니다. 23개 작업을 대상으로 한 Qwen3-0.6B 통제 실험에서는 제한된 SchemaRouter 조건이 강한 결과를 보였지만, 별도의 구조적 K3 대 K5 승격 검증은 실패했으며 부정적인 결과도 공개하고 있습니다.
>
> 안정화된 릴리스: 0.14.0
> GitHub: https://github.com/JDeun/SchemaRouter
> 검증·근거: https://jdeun.github.io/SchemaRouter/project/trust-and-evidence/
>
> 특히 규모가 크거나 이질적인 도구 카탈로그를 이용해 에이전트를 개발하는 분들의 의견을 듣고 싶습니다.

홍보 주장을 더 늘리기보다는 30초 분량의 터미널 데모 또는 아키텍처 이미지 한 장을 첨부합니다.

### Technical article

Working title:

> **Why I stopped treating tool retrieval as execution authority**

Outline:

1. 모든 도구를 프롬프트에 제공하는 접근이 여전히 적절한 경우.
2. 카탈로그가 크거나 이질적일 때 발생하는 문제.
3. 기능 검색과 실행 권한의 차이.
4. 필드 우선 검색과 결과 투영.
5. MCP/OpenAPI/Python/프레임워크 연동의 경계.
6. 스키마 변경, 바인딩, 파괴적 작업과 안전한 거부 동작.
7. 통제된 실증 자료와 부정적 결과.
8. 아직 필요한 독립 검증.
9. 실행 가능한 예제와 설치 방법.

글에 인용한 저장소 링크와 예제가 정상 동작하는 것을 확인한 뒤 게시합니다.

### Discord / Slack / community channels

프로젝트 공유가 명시적으로 허용되는 곳에만 게시합니다. 질문을 중심으로 짧은 글과 링크 하나를 사용하며, 요청받지 않은 단체 개인 메시지는 보내지 않습니다.

Suggested format:

> SchemaRouter는 에이전트 도구 카탈로그를 위한 오픈소스 타입 기반 기능 검색·실행 계층입니다. 결정적인 40개 도구 데모와 MCP/OpenAPI 연동을 제공하고 있습니다. 이 채널이 짧은 기술 피드백을 요청하기에 적절할까요? 그렇다면 실행 가능한 예제를 공유하겠습니다.

### 학회·밋업의 짧은 기술 발표

발표 제목:

> **Tool retrieval is not execution authority**

슬라이드 5장 구성:

1. 대규모 도구 카탈로그의 문제
2. 필드 우선 타입 기반 검색
3. 신뢰된 실행 경계
4. 통제된 긍정·부정 결과
5. 실행 가능한 오픈소스 데모와 토론 질문

## 대외 공개 진행 순서

모든 채널에 동시에 게시하지 않습니다.

### 0단계 — 기본 준비

이미 준비한 자료:

- 공개 도입 현황 점검표
- 안정화된 0.13.0 릴리스
- 실행 가능한 예제
- 신뢰성·검증 근거 안내 페이지
- 기여자 로드맵과 이슈 템플릿

첫 공개 게시 직전에 기존 주간 기록이 오래됐다면 최신 점검표 산출물을 저장합니다.

### 1단계 — 구체적인 기술 피드백 확보

1. Show HN 게시
2. 기술적 피드백에 응답
3. 실제 문제를 이슈·문서 수정으로 전환
4. 게시 URL·날짜 및 다음 점검표 기록

반응이 적다는 이유만으로 여러 곳에 재게시하지 않습니다.

### 2단계 — 직접 관리하는 네트워크에서 설명

1단계에서 받은 유용한 의견을 반영한 뒤 LinkedIn 기술 게시글 또는 기술 아티클을 공개합니다.

### Phase 3 — community-specific posts

관련성이 높은 Reddit 또는 다른 커뮤니티 한두 곳에 각각의 문제에 맞춰 새로 작성한 글을 게시합니다. 게시 직전에 규칙을 다시 확인합니다.

### Phase 4 — evidence follow-up

실질적인 통합 사례, 벤치마크 재현 또는 외부 도입 사례가 확보되면 같은 출시 안내를 반복하지 말고 새로운 근거를 바탕으로 후속 글을 작성합니다.

## Measurement

모든 외부 게시 기록은 [출시 및 외부 홍보 기록](launch-log.md)에 남깁니다.

For each entry record:

- UTC/KST 날짜;
- 게시 채널;
- 게시물의 정식 URL;
- 사용한 정확한 이미지·메시지 버전;
- 게시 전후의 점수표 스냅샷 및 실행 기록;
- 별점·포크·다운로드 집계 기간 변화;
- 이슈·PR·기여자 활동;
- 구체적인 연동 문의와 채택 문의;
- 저장소 변경을 촉발한 정성적 피드백.

근거 없이 모든 지표 변화를 특정 게시글 하나의 효과로 돌리지 않습니다.

## Stop conditions

Pause a channel if:

- 운영자나 사용자가 주제와 맞지 않거나 홍보성이라고 지적하는 경우;
- 새로운 근거 없이 같은 질문을 반복하는 경우;
- 프로젝트가 들어오는 이슈에 대응하지 못하는 경우;
- 공개 문구가 실증 근거의 범위를 넘어서는 경우;
- 방문자가 증가하지만 첫 사용 실패로 온보딩 결함이 드러나는 경우.

먼저 저장소의 공개 자료를 수정한 뒤 작업을 재개합니다.

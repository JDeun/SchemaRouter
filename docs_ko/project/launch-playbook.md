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

For normal installs, `pip install schemarouter` resolves the latest stable release. The launch demo pins `0.14.0` so the public walkthrough remains reproducible.

Repository: <https://github.com/JDeun/SchemaRouter>

Docs: <https://jdeun.github.io/SchemaRouter/>

Runnable examples: <https://github.com/JDeun/SchemaRouter/tree/main/examples>

## 공개적으로 주장할 수 있는 내용

Safe public claims should map to a reproducible artifact.

### Stable product

- 안정화된 릴리스: `0.14.0`, 베타 / 1.0 이전 버전;
- Python 3.10~3.14는 릴리스 차단 조건에 해당하는 CI 검증 대상;
- MCP, OpenAPI, OPTIMADE, GraphQL, OData, OpenRPC/JSON-RPC, Python/SDK 바인딩,
  LangChain/LangGraph, LlamaIndex에서 타입 기반 수집·실행 경로를 지원;
- 검색 점수나 모델 판단은 실행 권한을 부여하지 않음;
- 릴리스 산출물에는 wheel, sdist 및 SPDX SBOM이 포함되고 출처·검증 절차는
  공개 신뢰 문서에 기록됨.

### Controlled research evidence

One frozen 23-task Qwen3-0.6B B1 experiment recorded:

- SR-5 task pass: **91.30%**;
- FULL task pass: **68.48%**;
- SR-5 schema-token ratio: **5.42%**;
- required-route recall: **100%**.

This is controlled mechanism evidence on that workload. It is **not** a population-level claim that
SchemaRouter improves every agent, model, workload, or final answer.

The structural K3-vs-K5 promotion gate also produced a negative result and was not promoted. Keep
that result visible when discussing the research.

Verification index:
<https://jdeun.github.io/SchemaRouter/project/trust-and-evidence/>

## What not to claim

Do not say:

- "SchemaRouter를 쓰면 모든 에이전트의 정확도가 높아진다";
- "SchemaRouter는 운영 환경에서 토큰 사용량을 94.58% 줄인다";
- "SchemaRouter는 다른 모든 라우터보다 안전하다";
- "Jev/Laya/Ollama가 최고의 결정 백엔드다";
- 외부 채택 사례나 사례 연구 없이 "운영 환경에서 검증됐다"고 주장;
- 명시적 허락 없이 어떤 조직이 "사용 중"이라고 주장.

Issue #15 remains the live decision-backend evidence track. Issue #584 tracks external adoption and
independent validation.

## Core launch narrative

### Problem

Agent stacks often push an entire tool catalog into model context. As the catalog grows, two
different problems get mixed together:

1. **retrieval** — which capabilities and output fields are relevant now?
2. **authority** — which registered operation is actually allowed to execute?

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

It is deliberately not another agent runtime. LangChain, LangGraph, LlamaIndex, or custom
applications can stay in control of orchestration.

### Why it matters

The design aims to reduce context pollution **without turning retrieval into permission**. Provider
metadata can describe a capability, but trusted local application state grants execution authority.

## 30-second demo

Use the deterministic context-reduction demo so the first impression does not depend on network
availability or API keys.

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

1. a 40-tool catalog;
2. one natural-language request;
3. the Top-3 typed capability retrieval;
4. the serialized full-catalog bytes versus bounded retrieval bytes;
5. the selected weather route at rank 1.

Overlay/caption:

> "Don't give the model every tool schema. Retrieve the typed capability surface needed for this
> request, then execute only through local contracts."

Do not label serialized bytes as model token counts.

## Five-minute technical walkthrough

### 0:00-0:40 — The failure mode

Show a large tool catalog and explain why "just send all schemas" creates unnecessary context and
mixes relevance with authority.

### 0:40-1:30 — Capability retrieval

Run:

```bash
python examples/context_reduction_demo.py
```

Explain `retrieve(..., k=3)` / `retrieve_executable(..., k=3)` and that candidates retain typed
input/output contracts.

### 1:30-2:40 — Real provider ingestion

Run the public no-auth OpenAPI example:

```bash
python examples/live_openapi_quickstart.py
```

Explain:

```text
external schema -> registered typed capability -> bounded plan -> validated execution -> typed result
```

### 2:40-3:30 — Framework fit

Show the LangChain/LangGraph/LlamaIndex examples and emphasize that SchemaRouter does not own the
agent graph or conversation runtime.

### 3:30-4:20 — Execution boundary

Show the trust model:

- fingerprints/bindings;
- input/output JSON Schema validation;
- local side-effect policy;
- destructive operations fail closed;
- schema drift does not silently replace accepted authority.

### 4:20-5:00 — Evidence and invitation

Open the trust/evidence page and example gallery. State the controlled B1 evidence with its exact
scope, mention the negative K3 result, and ask for feedback on real integration friction.

## "Why not just send all tool schemas to the LLM?"

Use this explanation when the question comes up:

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

Use Show HN only because the project is directly runnable and inspectable without a signup gate.

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

Rules for the actual submission:

- 가입이나 마케팅 페이지가 아닌 실행 가능한 저장소에 직접 연결합니다;
- 기술적인 질문이 올라오면 답변할 수 있도록 참여합니다;
- 추천이나 댓글을 요청하지 않습니다;
- 다른 커뮤니티를 통해 투표를 조직하지 않습니다;
- 사소한 릴리스 변경을 반복적인 Show HN 게시글로 올리지 않습니다.

Official guidance:
<https://news.ycombinator.com/showhn.html>

### Reddit

Do **not** copy the same promotional post across many communities.

Candidate communities should be evaluated on the day of posting for their current rules. Prefer a
community only where the technical problem is directly on-topic.

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

- check the specific community's self-promotion and link rules;
- disclose that you are the maintainer;
- prefer one substantive community-specific post over repeated exposure;
- no unsolicited DMs;
- no vote requests.

Reddit's sitewide spam guidance explicitly treats repeated/unwanted/unsolicited mass engagement as
spam and notes that individual communities may be stricter.

### LinkedIn

Use the personal engineering story rather than a generic product announcement.

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

Attach the 30-second terminal demo or one architecture image rather than adding more promotional
claims.

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

Publish the article only after the repository links/examples it references are stable.

### Discord / Slack / community channels

Only post where project sharing is explicitly permitted. Use a short question-led message and one
link. Never use unsolicited bulk DMs.

Suggested format:

> SchemaRouter는 에이전트 도구 카탈로그를 위한 오픈소스 타입 기반 기능 검색·실행 계층입니다. 결정적인 40개 도구 데모와 MCP/OpenAPI 연동을 제공하고 있습니다. 이 채널이 짧은 기술 피드백을 요청하기에 적절할까요? 그렇다면 실행 가능한 예제를 공유하겠습니다.

### Conference / meetup lightning talk

Title:

> **Tool retrieval is not execution authority**

Five-slide structure:

1. large tool catalog problem;
2. field-first typed retrieval;
3. trusted execution boundary;
4. controlled positive + negative evidence;
5. runnable OSS demo / open questions.

## Campaign sequence

Do not publish everywhere at once.

### Phase 0 — baseline

Already available:

- public adoption scorecard;
- stable 0.13.0 release;
- runnable examples;
- trust/evidence page;
- contributor roadmap and issue templates.

Capture the scorecard artifact immediately before the first public launch post if the current
weekly snapshot is stale.

### Phase 1 — high-signal technical feedback

1. Show HN;
2. respond to technical feedback;
3. convert valid friction into issues/docs fixes;
4. record post URL/date and the next scorecard snapshot.

Do not proceed to broad reposting merely because the post is quiet.

### Phase 2 — owned-network explanation

Publish the LinkedIn technical post and/or technical article after incorporating useful Phase 1
feedback.

### Phase 3 — community-specific posts

Use one or two relevant Reddit/community posts, each rewritten around that community's problem.
Check current rules immediately before posting.

### Phase 4 — evidence follow-up

After a meaningful integration, benchmark reproduction, or external adopter exists, publish a
follow-up based on new evidence rather than repeating the launch announcement.

## Measurement

Record every external publication in
[Launch and outreach log](launch-log.md).

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

Do not attribute all metric movement to one post without evidence.

## Stop conditions

Pause a channel if:

- 운영자나 사용자가 주제와 맞지 않거나 홍보성이라고 지적하는 경우;
- 새로운 근거 없이 같은 질문을 반복하는 경우;
- 프로젝트가 들어오는 이슈에 대응하지 못하는 경우;
- 공개 문구가 실증 근거의 범위를 넘어서는 경우;
- 방문자가 증가하지만 첫 사용 실패로 온보딩 결함이 드러나는 경우.

Fix the repository surface first, then resume.

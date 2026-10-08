# Decision backend

SchemaRouter can optionally use a bounded decision model to refine choices that were already
derived from the local schema catalog. This feature is **off by default**.

Decision backend는 plan generator가 아닙니다. locally authorized된 유한 option ID 집합만 받고 그 안에서만 선택할 수 있습니다. typed execution plan은 계속 SchemaRouter가 구성하며 policy, schema validation, fingerprint, execution authority도 SchemaRouter에 남습니다.

provider layer는 교체 가능합니다. Laya와 Ollama 같은 direct backend 외에도 `SystemOneDecisionBackend`는 설정을 통해 Jev-compatible hosted/self-hosted System One endpoint를 사용할 수 있습니다. 새로운 compatible model family를 위해 별도의 SchemaRouter planner를 만들 필요는 없지만 동일한 local option validation과 workload-specific quality evaluation을 통과해야 합니다.

또한 이들은 **agent나 orchestrator가 아닙니다**. decision backend는 conversation loop를 소유하지 않고 tool 호출 시점을 결정하지 않으며 tool을 실행하거나 memory를 관리하거나 임의의 multi-step plan을 만들지 않습니다. SchemaRouter 내부의 bounded decision point 뒤에 위치하는 교체 가능한 classifier/ranker에 가깝습니다.

```mermaid
flowchart TD
    O["orchestrator"] --> P["SchemaRouter planner"]
    P --> C["finite candidate set"]
    C --> DB["optional DecisionBackend"]
    DB --> V["validated candidate ID(s)"]
    V --> E["SchemaRouter plan + policy + execution"]
```

## 활성화

```python
from schemarouter import CallableDecisionBackend, DecisionPolicy, SchemaPlanner

backend = CallableDecisionBackend(my_decision_model)
planner = SchemaPlanner(
    registry,
    decision_backend=backend,
    decision_policy=DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
        fallback="deterministic",
    ),
)
```

The master `enabled` switch must be true. Individual surfaces are separately configurable:

- `tool_selection`
- `endpoint_selection`
- `field_selection`
- `evidence_sufficiency`
- `recall_on_empty`

도구 또는 엔드포인트 선택 기능을 활성화하면 제한된 후보 선택 기능도 동작합니다. `field_selection`은 식별자 필드를 로컬에 보존하면서, 백엔드가 선언된 비식별자 출력 필드에서만 선택하도록 합니다. `evidence_sufficiency` 역시 보수적인 이진 게이트로 구현되어 있습니다. SchemaRouter가 먼저 로컬 스키마 메타데이터에서 요구된 출처·라이선스·단위·원본 유형의 근거를 확인한 다음, 백엔드는 로컬에서 충분하다고 판정된 호출을 유지하거나 불충분하다는 이유로 거부할 수만 있습니다. 제공자는 로컬에 없는 근거를 새로 만들어 충분한 상태로 바꿀 수 없습니다.

### 제한된 semantic candidate recall

다국어 질의나 바꿔 쓴 질의에서는 등록된 스키마에 적절한 기능이 기술되어 있어도 어휘 기반 검색이 올바른 엔드포인트를 놓칠 수 있습니다. `SchemaPlanner`는 최종 후보 선택 전에 별도의 **후보 재현율 개선 백엔드**를 선택적으로 추가할 수 있습니다.

```python
from schemarouter import EmbeddingDecisionBackend, SchemaPlanner

recall = EmbeddingDecisionBackend(multilingual_embed_batch)

planner = SchemaPlanner(
    registry,
    candidate_recall_backend=recall,
    candidate_recall_limit=4,
    decision_backend=final_decider,
    decision_policy=policy,
)
```

이 단계는 후보를 찾아내는 역할만 합니다. 유한한 등록 엔드포인트 카탈로그를 입력받아 최대 `candidate_recall_limit`개의 선택지 ID를 반환할 수 있습니다. SchemaRouter는 의미 기반 top-k 후보를 일반 어휘 검색 후보와 합친 후, 기존의 제한된 결정·정책·스키마·근거·런타임 파이프라인을 통해 실제 실행 가능 여부를 판단합니다.

의미 기반 재현율 백엔드는 도구, 호출, 인수, 필드 또는 실행 권한을 새로 만들지 **않습니다**. 백엔드가 실패하거나 선택을 포기하면 SchemaRouter는 어휘 기반 후보를 유지하고 경고를 남깁니다. 어휘 검색 결과가 없더라도 의미 기반 검색 백엔드가 설정된 경우 `recall_on_empty`를 통해 전체 카탈로그를 추가 노출하지 않습니다. 의미 기반 top-k 범위가 그대로 적용됩니다.

다국어 임베딩 모델은 자연스러운 선택이지만 SchemaRouter가 특정 모델에 종속되지는 않습니다. 기존 `EmbeddingDecisionBackend`는 애플리케이션이 소유한 SentenceTransformers, FastEmbed, 원격 임베딩 API 또는 도메인 전용 인코더를 감쌀 수 있습니다.

### 제한된 capability-fit / no-route gate

의미 기반 후보 검색은 재현율을 높이지만 이것만으로는 도메인 밖 질의에도 카탈로그 내 후보를 억지로 선택할 수 있습니다. `SchemaPlanner`는 어휘·의미 검색 이후 최종 후보 선택 이전에 선택적 `candidate_fit_backend`도 지원합니다.

```python
fit = EmbeddingDecisionBackend(
    multilingual_embed_batch,
    min_similarity=0.45,
)

planner = SchemaPlanner(
    registry,
    candidate_recall_backend=recall,
    candidate_recall_limit=2,
    candidate_fit_backend=fit,
)
```

적합성 백엔드는 이미 허용 범위로 제한된 후보 집합만 전달받습니다. 구체적인 선택을 반환해도 그 의미는 ‘제시된 기능 중 하나 이상이 질의에 그럴듯하게 맞는다’는 것뿐입니다. SchemaRouter는 일반 후속 순위 결정기를 위해 전체 후보 집합을 유지합니다. 적합성 백엔드는 최종 경로를 선택하거나 실행 권한을 만들 수 없습니다.

명시적으로 선택을 포기하면 모든 후보 경로를 억제하고 경로 없는 계획을 생성합니다. 반대로 백엔드 예외가 발생했다고 해서 이미 허용된 경로를 차단하지는 않습니다. SchemaRouter는 후보 집합을 유지하고 경고를 남깁니다. 따라서 이 게이트는 새로운 보안 권한이 아니라 품질·선택 포기 판단의 경계입니다.

For embedding-based fit gates, calibrate `min_similarity` and `min_margin` on development or
calibration data. Do not tune these thresholds against a held-out test split.

### 제한된 operation-capability fit

광범위한 `candidate_fit_backend`는 검색된 기능 중 하나라도 질의의 도메인에 해당하는지 판단합니다. 그러나 유사 도메인에서 지원되지 않는 작업을 가려내기에는 부족합니다. 예를 들어 레지스트리에는 `lookup`, `update`만 등록돼 있는데 사용자가 계정 `delete`를 요청하더라도 질의가 `users` 도메인에 속한다는 사실 자체는 명확할 수 있습니다.

For that case, `SchemaPlanner` supports an optional `operation_fit_backend` between broad capability
fit and same-tool endpoint disambiguation:

```python
operation_fit = EmbeddingDecisionBackend(
    multilingual_embed_batch,
    min_similarity=0.25,
)

planner = SchemaPlanner(
    registry,
    candidate_recall_backend=recall,
    candidate_recall_limit=2,
    candidate_fit_backend=fit,
    operation_fit_backend=operation_fit,
    endpoint_disambiguation_backend=disambiguator,
)
```

작업 적합성 판단 범위는 일반 기능 적합성보다 좁습니다. 현재 가장 앞선 도구 도메인에 속하는 형제 엔드포인트만 살펴보고, 엔드포인트 작업 이름, 신뢰할 수 있는 `EndpointSpec.operation_aliases`, 엔드포인트 설명, 작업 분류 및 선택적인 HTTP 메서드를 입력받습니다. 단순히 도메인이나 필드가 유사하다는 이유로 미지원 작업을 지원 대상으로 바꾸지 않도록 임베딩 텍스트에는 도구 설명, 도구 이름 레이블, 답변 필드 레이블을 넣지 않습니다. 최상위 도구의 식별자는 로컬 요청 메타데이터로만 제공하며 기본 임베딩 선택지 텍스트에는 포함하지 않습니다.

작업 별칭은 애플리케이션에서 명시적으로 관리하는 라우팅 어휘입니다. 예를 들어 `["current conditions", "live conditions"]`나 `["create support ticket", "open support case"]`가 있습니다. SchemaRouter는 사용자 입력이나 모델 출력에서 별칭을 추론하지 않고 수집 어댑터도 임의로 만들지 않습니다. 별칭은 계획 단계의 힌트일 뿐이며 엔드포인트 생성, 인수 수정, 부작용 분류·정책 변경 또는 실행 권한 부여에 사용할 수 없습니다. 별칭의 변경은 지문으로 기록되며 검사·대시보드 출력에서 확인할 수 있습니다.

긍정적인 판단은 제시된 작업 중 하나가 요청과 그럴듯하게 일치한다는 뜻일 뿐입니다. 이 단계는 후보의 순서를 바꾸지 않으므로 최종 경로를 결정할 수 없습니다. 명시적으로 선택을 포기하면 후보 집합을 억제하고, 백엔드 실패 시에는 이미 허용된 후보를 경고와 함께 유지합니다. `max_calls > 1`에서는 이 단계를 건너뜁니다.

As with all model-assisted routing stages, operation-fit thresholds are workload/model specific.
Calibrate them on development/calibration data and evaluate any claimed improvement on a fresh
untouched holdout.

### 제한된 same-tool endpoint disambiguation

의미 기반 검색과 기능 적합성 게이트를 통과해도 선두 도구의 형제 엔드포인트 여러 개가 여전히 적합해 보일 수 있습니다. `SchemaPlanner`는 이 형제 엔드포인트의 순서만 바꾸기 위해 `endpoint_disambiguation_backend`를 선택적으로 사용할 수 있습니다.

```python
disambiguator = EmbeddingDecisionBackend(multilingual_embed_batch)

planner = SchemaPlanner(
    registry,
    candidate_recall_backend=recall,
    candidate_recall_limit=2,
    candidate_fit_backend=fit,
    endpoint_disambiguation_backend=disambiguator,
)
```

이 단계는 일반 후보 선택보다 범위가 좁습니다. 이미 선두에 있는 도구 도메인의 엔드포인트만 받고, 그중 한 형제 엔드포인트를 맨 앞으로 이동할 수 있습니다. 다른 도구로 바꾸거나 후보를 추가·삭제하거나 인수·필드를 만들거나 실행 권한을 부여할 수 없습니다. 백엔드가 실패하거나 선택을 포기하면 기존 후보 순서가 유지됩니다.

이 단계는 `max_calls > 1`일 때 건너뜁니다. 이 경우 단일 경로의 순서보다 의미적으로 필요한 필드의 포괄 범위가 선택을 좌우해야 하기 때문입니다. 엔드포인트 설명에는 신뢰할 수 있는 읽기 전용·데이터 변경 작업 분류와 선언된 답변 필드 레이블이 포함돼 있어 일반 의미 기반 백엔드도 `search/update`, `lookup/update`, `list/create`, `current/forecast` 같은 조합을 구별할 수 있습니다.

As with the recall and fit stages, evaluate disambiguation on development/calibration data and use a
fresh untouched holdout for any claimed improvement.
### 빈 lexical recall

`recall_on_empty=True`는 후보 선택에 추가로 설정할 수 있는 선택 사항입니다. 한국어 질의를 영어 전용 스키마 카탈로그로 라우팅해야 하는 경우처럼 결정적인 어휘 검색 단계가 엔드포인트를 전혀 찾지 못할 때 의미가 있습니다.

`tool_selection` 또는 `endpoint_selection`과 함께 활성화하면 모든 결정적 스키마 점수가 0이더라도 SchemaRouter가 유한한 등록 엔드포인트 카탈로그를 제한된 결정 백엔드에 보여줄 수 있습니다. 백엔드는 여전히 로컬 선택지 ID만 받으며 도구나 엔드포인트를 임의로 만들어낼 수 없습니다.

기본값은 `False`입니다. 카탈로그를 확장한 뒤 백엔드가 오류를 내거나 선택을 포기하면 SchemaRouter는 임의의 엔드포인트를 고르지 않고 호출 없는 결과를 반환합니다. 대체할 결정적 후보가 없기 때문입니다. 구체적인 선택지를 반환한 경우에는 등록된 경로를 선택하므로, 도메인 밖 요청을 억제하려면 필요에 따라 보정된 신뢰도와 `candidate_abstention="no_route"`를 함께 사용해야 합니다. 특히 다국어, 도메인 밖 또는 적대적 요청에서는 운영 환경에 이 정책을 켜기 전에 해당 작업 부하를 벤치마크하세요.

후보 선택 포기 동작은 `candidate_abstention="inherit" | "deterministic" | "no_route" | "error"`로 별도 설정할 수 있습니다. 기본값 `"inherit"`는 `fallback`을 따르는 기존 동작을 보존하므로 이미 설정된 `fallback="deterministic"`, `fallback="error"`의 의미가 유지됩니다. `"no_route"`는 제한된 백엔드가 명시적으로 선택을 포기할 때 후보 경로를 억제하며, 신뢰도 기준으로 도메인 밖 요청을 처리할 때 유용합니다. 제공자 예외나 잘못된 출력은 여전히 `fallback`이 처리하므로 `"no_route"`를 택했다고 해서 제공자 장애가 조용히 경로 없음으로 바뀌지는 않습니다.

## 제한된 field selection

Enable field selection explicitly:

```python
policy = DecisionPolicy(
    enabled=True,
    field_selection=True,
    fallback="deterministic",
)
```

For each already-selected endpoint, SchemaRouter offers only declared non-identifier output fields
as finite `field:N` options. Identifier fields never enter the provider's choice set and are
always retained locally.

결정 요청의 `max_selections`는 결정적 투영 단계에서 결정한 답변 필드 개수를 넘지 않습니다. 결정적 투영이 재현율 우선 모드에서 모든 필드를 유지하는 경우, 백엔드는 이렇게 선언된 필드 중 제한된 부분집합을 선택할 수 있습니다.

제공자 장애, 잘못되거나 알려지지 않은 필드 ID, 중복 ID, 선택 개수 초과 또는 선택 포기는 후보 라우팅과 동일한 폴백 정책을 따릅니다. 근거 요구 사항은 최종적으로 로컬 검증을 거친 필드 집합을 기준으로 다시 계산합니다.

## 제한된 evidence sufficiency

Enable the surface explicitly and request evidence on the plan request:

```python
policy = DecisionPolicy(
    enabled=True,
    evidence_sufficiency=True,
    fallback="deterministic",
)

request = PlanRequest(
    query="band gap",
    evidence=EvidenceRequirements(
        provenance=True,
        license=True,
        units=True,
        source_type="calculated",
    ),
)
```

SchemaRouter는 백엔드에 연락하기 전에 결정적인 로컬 사전 검증을 수행합니다. 이 단계에서 근거가 될 수 있는 것은 도구 수준의 `source_type`·`license` 메타데이터와 선택된 답변 필드의 `source_type`, `license`, `unit` 메타데이터뿐입니다.

요청된 요건 중 하나라도 로컬에서 확인되지 않으면 제공자에게 묻지 않고 호출을 거부합니다. 로컬 근거가 충분하면 제공자에게 `evidence:sufficient`와 `evidence:insufficient`라는 유한한 선택지 두 개만 전달합니다. `insufficient`를 선택하면 보수적인 거부권으로만 작용합니다. `sufficient`를 선택해도 출처, 라이선스, 단위, 필드, 도구 또는 실행 권한을 추가할 수 없습니다.

Provider failure or abstention can fall back to the local evidence assessment when
`fallback="deterministic"`; `fallback="error"` fails planning instead.

## Fallback

`fallback="deterministic"` is the default. Invalid output, provider failure, unknown option IDs,
or abstention falls back to SchemaRouter's deterministic ranking and adds a warning to the plan.

Use `fallback="error"` when a decision failure must stop planning.

## Contract invariant

A decision provider:

- 유한하고 불투명한 선택지 ID만 전달받습니다;
- `ToolCall`을 생성할 수 없습니다;
- 도구, 엔드포인트, 필드, 매개변수, 인증정보 또는 실행 권한을 추가할 수 없습니다;
- 알 수 없는 선택지를 실행 가능하게 만들 수 없습니다;
- 로컬에 없는 근거를 충분한 것으로 승격시킬 수 없습니다;
- 로컬 근거 사전 검증을 이미 통과한 호출을 거부할 수만 있습니다;
- 제한된 범위의 유한한 점수를 반환해야 합니다;
- 선택을 포기할 수 있습니다;
- 반환한 메타데이터는 어떤 경우에도 권한의 근거가 되지 않습니다.

The planner, execution policy, schema fingerprint checks, argument validation, and output validation
remain unchanged.

## Decision backend 선택

The optional backends serve different deployment goals:

| Backend | Best fit | Trade-off |
| --- | --- | --- |
| Deterministic / embedding | Zero provider dependency and predictable local behavior | Lower semantic flexibility on ambiguous language |\n| Pairwise scorer / reranker | Direct query-option relevance scoring with bounded local authority | Application owns model/runtime and score calibration |
| Hosted general LLM via `CallableDecisionBackend` | Reuse an existing GPT, Gemini, Claude, or other cloud-model client | Provider latency/cost; application owns structured-output prompting and credentials |
| Laya | Fast local finite decisions, including Apple Silicon through PyTorch MPS/Metal | Single-selection adapter today; quality is checkpoint/domain dependent |
| Ollama | Reuse a general local LLM that is already deployed for other application tasks | Autoregressive generation is heavier and slower than a purpose-built decision model |
| Jev / TypeSafe | Hosted purpose-built bounded decisions without local model operations | External service/network dependency |

Laya 또는 결정적 백엔드로 작업 요구 사항을 충족한다면 Ollama는 **필수가 아닙니다**. 하지만 이미 로컬 지시 모델을 운영하는 팀의 폭넓은 호환성 경로로, 나란히 비교하는 벤치마크 근거로, 그리고 특화된 System-One 결정 모델보다 범용 언어 모델이 적합한 작업의 폴백으로 유용할 수 있습니다.

## 기존 cloud LLM client

애플리케이션이 이미 호스팅 모델 API를 사용한다면 SchemaRouter는 Ollama나 Laya를 요구하지 않습니다. 제공자 중립적인 `CallableDecisionBackend`로 애플리케이션이 소유한 GPT, Gemini, Claude 또는 기타 구조화 출력 클라이언트를 감쌀 수 있습니다.

```python
from schemarouter import CallableDecisionBackend, DecisionPolicy, SchemaPlanner

async def cloud_decider(request):
    # Use the application's existing cloud-model client here.
    # Return only finite option IDs that came from request.options.
    payload = {
        "query": request.query,
        "options": [
            {
                "id": option.id,
                "label": option.label,
                "description": option.description,
            }
            for option in request.options
        ],
        "max_selections": request.max_selections,
    }
    raw = await existing_cloud_model_json_call(payload)
    return raw

backend = CallableDecisionBackend(cloud_decider)

planner = SchemaPlanner(
    registry,
    decision_backend=backend,
    decision_policy=DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
        fallback="deterministic",
    ),
)
```

해당 호출 함수는 내부적으로 OpenAI, Google, Anthropic 또는 다른 제공자를 사용할 수 있습니다. SchemaRouter는 애플리케이션의 제공자 클라이언트나 API 키를 자동으로 상속하지 않으며, 애플리케이션이 신뢰할 수 있는 클라이언트를 명시적으로 주입합니다. 따라서 벤더 SDK와 인증정보는 SchemaRouter 코어 밖에 유지됩니다.

The same fail-closed contract still applies: unknown IDs, duplicate IDs, or selections beyond
`max_selections` are rejected before they can affect planning.

There are no first-class OpenAI/Gemini/Anthropic SDK dependencies in core. The stable
integration surface is the provider-neutral callable contract.

## Local embedding similarity

`EmbeddingDecisionBackend`는 로컬·호스팅 임베딩 모델에 대해 특정 제공자 의존성을 추가하지 않는 경로를 제공합니다. 임베더에는 사용자 질의와 허용된 선택지 각각의 텍스트 표현을 순서대로 전달합니다. SchemaRouter는 코사인 유사도를 로컬에서 계산하고 순위가 매겨진 벡터 위치를 원래의 불투명한 선택지 ID로 되돌립니다.

```python
from schemarouter import EmbeddingDecisionBackend

backend = EmbeddingDecisionBackend(
    embed_batch,
    min_similarity=0.35,
    min_margin=0.05,
)
```

백엔드는 입력 텍스트마다 유한하고 차원이 동일한 벡터 하나를 반환하는 동기·비동기 호출 함수를 모두 사용할 수 있습니다. 따라서 SchemaRouter의 핵심 의존성에 패키지를 추가하지 않고도 애플리케이션이 소유한 SentenceTransformers, FastEmbed, semantic-router 인코더, 원격 임베딩 API 또는 맞춤 도메인 인코더를 사용할 수 있습니다.

기본 선택지 텍스트 포맷터는 `DecisionOption.metadata`를 임베더에 전달하지 않습니다. 사용자 정의 `option_text` 콜백은 신뢰할 수 있는 애플리케이션 코드이며 다른 데이터 경계를 선택할 수도 있습니다. 노름이 0인 벡터, NaN/Infinity, 차원 불일치, 잘못된 배치 크기 또는 잘못된 벡터 형태는 안전하게 거부합니다. `min_similarity`는 일치도가 낮을 때, `min_margin`은 선택 경계가 모호할 때 선택 포기를 허용합니다.

For asymmetric retrieval encoders, wrap the callable so the first input (the query) uses the
encoder's query path and option texts use its passage/document path.

## Pairwise query-option scoring

`PairwiseDecisionBackend` is a provider-neutral path for cross-encoders, rerankers, or any
application-owned model that directly scores a query against each authorized option.

```python
from schemarouter import PairwiseDecisionBackend

backend = PairwiseDecisionBackend(
    score_pairs,
    min_score=0.20,
    min_margin=0.05,
)
```

점수 계산기는 `(query, option_text)` 쌍의 배치를 받아 각 쌍마다 `[0, 1]` 범위의 신뢰도 점수 하나를 정확히 반환합니다. SchemaRouter는 이 점수를 로컬에서 정렬하고 각 위치를 원래 불투명한 선택지 ID로 연결합니다. 따라서 점수 계산기에 새로운 경로를 만들어낼 권한을 주지 않고도 `operation_fit_backend`, `candidate_fit_backend`, 엔드포인트 구분 또는 최종 제한 결정 단계에 사용할 수 있습니다.

기본 포맷터는 선택지 레이블과 설명만 전달하며 `DecisionOption.metadata`는 전달하지 않습니다. 배치 크기 불일치, 잘못된 값, NaN/Infinity 또는 `[0, 1]` 밖의 점수는 안전하게 거부됩니다. 비동기 점수 계산기는 일반 비동기 계획 경로를 통해 지원됩니다.

SchemaRouter는 Transformers, Torch, 특정 재순위화 모델 또는 호스팅 순위 API에 종속되지 않습니다. 점수 계산 모델과 점수 보정은 애플리케이션이 소유합니다. 모델이 범위 제한 없는 로짓을 출력한다면 백엔드에 반환하기 전에 보정되었거나 별도로 명시적으로 정의된 `[0, 1]` 신뢰도로 바꿔야 합니다. 임계값은 모델과 작업 부하에 따라 달라지며 홀드아웃 평가 데이터가 아닌 개발·보정 데이터에서 결정해야 합니다.

## Jev / TypeSafe System One

SchemaRouter includes an optional `JevDecisionBackend` on current unreleased `main`:

```bash
pip install -e ".[jev]"
```

The normal packaged extra name will be `schemarouter[jev]` in the next release.

```python
from schemarouter.integrations import JevDecisionBackend

backend = JevDecisionBackend(
    min_confidence=0.65,
)
```

제공자는 제시된 선택지 ID에 대해 TypeSafe `choice` 기본 연산을 사용합니다. 알 수 없는 ID는 신뢰도에 따른 선택 포기를 평가하기 전에 안전하게 거부합니다. 신뢰도가 낮은 유효 선택은 포기하고 결정적 라우팅으로 폴백할 수 있습니다.

The adapter does not forward `DecisionOption.metadata`, and API credentials are client
configuration rather than model state.

See [Jev / TypeSafe System One](../integrations/jev.md) for sync/async usage and security details.

## Local Laya decision model

SchemaRouter includes an optional `LayaDecisionBackend` for local non-autoregressive bounded
decisions:

```bash
pip install -e ".[laya]"
```

The packaged extra is `schemarouter[laya]`.

```python
from schemarouter.integrations import LayaDecisionBackend

backend = LayaDecisionBackend(
    min_confidence=0.65,
)
```

By default, Laya may route between its English and multilingual checkpoints from the bounded request
state. Applications may pin a checkpoint with `model=` and may preload checkpoints for a
long-running process.

어댑터는 Laya의 유한한 `choice` 기본 연산을 기존 SchemaRouter `DecisionBackend` 계약에 연결합니다. 알 수 없는 선택지 ID는 신뢰도 게이트보다 먼저 거부하고, `DecisionOption.metadata`는 전달하지 않으며, Hugging Face 인증정보는 신뢰할 수 있는 로컬 설정에 남겨둡니다.

See [Laya](../integrations/laya.md) for checkpoint, device, preload, confidence, and benchmark
guidance.

## Local Ollama model

SchemaRouter also includes an `OllamaDecisionBackend` that uses Ollama structured outputs over the
native HTTP API. No Ollama Python SDK is required.

```python
from schemarouter.integrations import OllamaDecisionBackend

backend = OllamaDecisionBackend(
    "your-installed-model",
    async_mode=True,
)
```

백엔드는 JSON Schema enum으로 `option_id`를 제한하고, 모델이 판단할 근거로 활용하도록 그 스키마를 프롬프트에 포함합니다. 이후 반환된 `DecisionResult`를 로컬에서 다시 검증합니다. `DecisionOption.metadata`는 어떤 경우에도 전달되지 않습니다. 모델이 보고하는 점수는 보정된 확률이 아닌 자체 평가값으로 취급합니다.

See [Ollama](../integrations/ollama.md) for configuration and benchmark usage.

## Experimental provider

그 밖의 System-One 방식 또는 결정 모델 제공자는 SchemaRouter 코어에 직접 가져오기보다 `DecisionBackend`를 구현해야 합니다. 제공자 연동은 선택적이며 명시적으로 활성화합니다. 임베딩 라이브러리 역시 안정적인 제공자별 계약이 전용 어댑터를 정당화하지 않는 한 애플리케이션이 소유하는 편이 적절합니다.

This separation lets applications change, disable, or compare a decision provider without changing
registered tools, execution policy, or the deterministic planner.

## Benchmarking

Use `scripts/benchmark_decision_routing.py` to compare the deterministic baseline,
`ModelQueryAnalyzer`, local embedding backends, Jev, Laya, and explicitly selected local Ollama models
on the same cases.

See [Decision routing benchmark](../guides/decision-benchmark.md).

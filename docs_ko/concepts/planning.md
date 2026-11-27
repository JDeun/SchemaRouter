# Planning과 field projection

이 페이지의 Lexical 검색 및 계획 예시는 이전 릴리스 계약을 설명하는 과거 자료입니다. 개발 중인 원 논문 중심 패키지에서는 해당 API가 제거되었습니다. 현재의 계획 입력은 `PaperPlanRequest`이며 `configure_field_routing`으로 설정합니다. 상태 적격성 비교는 [연구용 상태 검색 가이드](../guides/state-aware-retrieval.md)를 참고하세요.

Planning은 요청을 schema 제약을 따르는 하나 이상의 `ToolCall` 객체로 변환합니다.

## 입력

Planner는 문자열 또는 `PlanRequest`를 입력으로 받습니다.

```python
from schemarouter import PlanRequest

request = PlanRequest(
    query="LiFePO4 band gap",
    arguments={"formula": "LiFePO4"},
    max_calls=1,
)
```

`PlanRequest`에는 선호 tool, 명시적 concept, evidence requirement도 지정할 수 있습니다.

## 분석

기본 `KeywordAnalyzer`는 결정론적이며 offline으로 동작합니다. Query의 용어를 선언된 tool,
endpoint, parameter, field에 대응시킵니다.

기존 카탈로그 기반 `ModelQueryAnalyzer`는 소스 체크아웃의 연구 아카이브로 이전되었습니다. 원 논문의 스키마 독립적 Understand는 별도 경로입니다. 모든 모델 출력은 실행 권한이 없는 제안이며, 로컬 검증 및 실행 정책은 계속 적용됩니다.

## Candidate scoring

Planner는 다음 순서의 요소를 우선합니다.

1. 명시적으로 선호된 endpoint
2. 명시적으로 선호된 tool
3. 추론된 concept과 일치하는 schema name 및 alias
4. 필요한 parameter를 충족할 수 있는 endpoint

Score는 선택을 위한 heuristic일 뿐 execution authority가 아닙니다.

## Semantic field coverage

선언된 semantic field와 일치하는 요청의 경우 `ExecutionPlan.coverage`가 planner의 제한된
coverage 상태를 구조화된 데이터로 노출합니다.

```python
plan = router.plan(
    PlanRequest(
        query="band gap and paper abstract",
        max_calls=2,
    )
)

print(plan.coverage.required)
print(plan.coverage.covered)
print(plan.coverage.uncovered)
print(plan.coverage.complete)
```

`required`는 bounded decision assistance가 candidate를 좁히거나 우선순위를 조정하기 전의 전체
schema-recalled candidate 집합에서 계산됩니다. `covered`는 compile된 primary call에 실제로
남은 field를 나타냅니다. `max_calls`, policy, 누락된 binding 또는 다른 local constraint 때문에
완전한 coverage가 불가능하면 `uncovered`가 명시적으로 남고 plan에는
`uncovered semantic field requirements` warning이 포함됩니다.

명시적인 multi-call plan에서 bounded decision backend는 candidate의 우선순위를 조정할 수 있지만
결정론적으로 schema recall된 pool을 삭제하지 않습니다. 최종 call 선택은 상호 보완적인 semantic
field coverage와 기존 `max_calls` authority boundary의 제약을 받습니다. 따라서 같은 field에 대한
중복 access path 두 개가 모든 call slot을 차지하여, 다른 required field에 사용 가능한 route가
있는데도 선택되지 못하는 상황을 방지합니다.

Single-call decision 동작과 lexical recall이 비어 있을 때의 fail-closed 동작은 그대로 유지됩니다.

## 구조화된 plan 설명

제품의 `ToolCall`은 더 이상 Lexical `score` 또는 `explanation`을 포함하지 않습니다. 과거의 `PlanExplanation`, 점수 성분, 필드 선택 이유, 무시된 인수 및 bounded decision 선택 출처는 소스 체크아웃의 `scripts.research_legacy_planning.plan_models`와 연구용 계획 직렬화에서만 유지합니다.

현재 Algorithm 1의 계획 상태, 필드 커버리지, 원천에 결속된 Typed Tool Plan 및 원 논문 Rank 결과를 확인합니다. 계획 자체의 진단 정보는 실행 권한이 아니며, 등록된 Executor와 로컬 원천 witness가 실행 경계를 검증합니다.

```python
plan = router.plan(paper_request)
print(plan.planning_status, plan.coverage)
for call in plan.calls:
    print(call.tool, call.endpoint, call.fields, call.schema_fingerprint)
```

이 예제는 이미 설정한 원 논문 중심 라우터와 `PaperPlanRequest`를 전제로 합니다. 모델의 숨겨진 추론을 노출하거나 재구성하지 않습니다. 이전 Lexical JSON은 현재 제품 계획이 아닌 연구용 스키마에서 검증합니다.

## Field projection

Endpoint가 projection 가능한 output field를 선언하면 planner는 recall-first 전략으로 field를
선택합니다.

```text
clear field match
 -> selected fields + identifiers

ambiguous or no useful match
 -> retain declared fields rather than aggressively pruning
```

이는 지나치게 공격적인 projection이 field-level precision을 높이더라도 downstream answer
quality를 낮출 수 있다는 연구 결과를 반영한 설계입니다.

## 필수 argument 누락

누락된 값은 임의로 생성하지 않고 plan에 명시합니다.

```python
plan = router.plan("get a user")
print(plan.executable)  # required user_id가 없으면 False
```

Executor는 invocation 직전에 required argument를 다시 계산하므로 위조되었거나 오래된
`missing_required_arguments` 목록으로 contract를 우회할 수 없습니다.

## 사전 compile된 provider/access fallback

`PlanRequest`에서 제한된 read-only fallback planning을 명시적으로 활성화할 수 있습니다.

```python
request = PlanRequest(
    query="Si band gap",
    preferred_tools=["mp_api"],
    fallback_scope="cross_provider",
    max_fallbacks=3,
)
```

각 fallback은 자체 schema와 tool fingerprint를 기준으로 compile된 완전한 `ToolCall`입니다.
동일 provider의 access path가 다른 provider의 candidate보다 먼저 배치됩니다. 서로 다른 field
name을 노출하는 access path 사이의 semantic compatibility는 field alias로 증명합니다.

Fallback과 provider 간 교차 검증은 타입·정규화된 단위뿐 아니라 필요한 JSON Schema
조건도 비교합니다. enum/const, 범위, 패턴, 배열 조건의 차이가 충족 관계를 입증하지
못하면 필드 호환성의 근거로 삼지 않으며, 일반적인 스키마 포함 관계를 판정하지는 않습니다.
참조가 있는 스키마는 상위 타입 변경으로 중첩 참조의 의미가 달라질 수 있어 전체 스키마
동등성을 요구합니다. 명시적인 JSON Schema 입력·출력 검증은 NaN·무한대·복소수를 각각 호출 전·결과
반환 전에 거절하며 큰 정수와 nullable 값은 선언된 동작을 유지합니다.

Fallback은 model-driven replanning이 아니며 기본값은 비활성입니다.
[Provider-aware fallback](../guides/provider-fallback.md)을 참고하십시오.

## Evidence requirement는 local constraint

Model-backed decision backend가 없어도 `PlanRequest.evidence`는 신뢰된 local contract를
기준으로 강제됩니다.

예:

```python
PlanRequest(
    query="elastic modulus",
    evidence=EvidenceRequirements(units=True),
)
```

이 요청에서는 선택된 answer field가 unit을 선언해야 합니다. Unit이 없는 arXiv abstract나 web
snippet도 일반 planning에서는 유효한 field이며, 요청이 unit evidence를 명시적으로 요구할 때만
제외됩니다.

요청된 provenance, license, source type에도 같은 규칙이 적용됩니다. Global evidence
requirement는 **선택된 전체 answer surface**에 적용됩니다. 특히 provenance는 tool-level
`source_type`이 route 전체를 cover합니다. 그렇지 않으면 선택된 모든 answer field가 각자의
`source_type`을 선언해야 합니다. 여러 field 중 하나에만 evidence가 있어서는 global provenance
requirement를 충족하지 못합니다.

Optional decision backend는 local에서 충분한 evidence를 거부할 수는 있지만 registry에 선언되지
않은 evidence를 만들어낼 수는 없습니다.

### Field별 evidence requirement

Global `PlanRequest.evidence`는 선택된 전체 answer surface에 적용됩니다. 서로 이질적인 요청은
관련 없는 field에까지 requirement를 강제하는 대신 특정 semantic field에만 evidence를 지정할 수
있습니다.

```python
from schemarouter import EvidenceRequirements, PlanRequest

request = PlanRequest(
    query="band gap and paper abstract",
    max_calls=2,
    field_evidence={
        "band_gap": EvidenceRequirements(units=True),
    },
)
```

여기서는 `band_gap` route가 unit metadata를 노출해야 하지만 unit이 없는
`document_abstract` route는 여전히 유효합니다. `field_evidence` key는 alias나 model이 만든
remapping이 아니라 신뢰된 canonical `FieldSpec.semantic_id`와 일치해야 하며, semantic ID가
없으면 field name을 사용합니다.

Contract는 additive입니다. Global evidence는 계속 모든 selected answer field에 적용되고,
일치하는 field-specific evidence는 해당 semantic field에 더 엄격한 requirement를 추가합니다.
Global source-type과 field-specific source-type constraint가 충돌하면 거부됩니다. Compile된
`ToolCall.field_evidence` map에는 명시적 field-specific requirement가 어떤 local provider
field에 적용되었는지 기록됩니다.

Field별 evidence는 caller가 통제합니다. 연구용으로 보존된 `ModelQueryAnalyzer`는 이를 보존하지만 model에
노출하지 않으며, model output이 신뢰된 constraint를 추가·제거·확장하도록 허용하지 않습니다.
활성 `field_evidence` key는 등록된 canonical semantic field ID 또는 semantic ID가 없을 때
field name으로 해석되어야 합니다. 알 수 없는 활성 key는 조용히 무시하지 않고 fail-closed됩니다.

### Required evidence와 available evidence

Compile된 call은 requirement와 capability 상태를 분리해 유지합니다.

- `ToolCall.required_evidence`: 해당 call에 대한 caller의 global requirement
- `ToolCall.field_evidence`: selected local field에 매핑된 caller requirement
- `ToolCall.evidence`: 선택된 route가 실제 사용 가능하다고 선언한 evidence

이 구분은 요청된 속성을 provider capability로 오인하지 않도록 합니다. Executor는 실행 직전에
현재의 신뢰된 `ToolSpec` / `FieldSpec` contract에서 evidence를 다시 계산합니다. 위조된
evidence overclaim, 충족되지 않은 global/field별 requirement, 선택되지 않은 field에 연결된
requirement, 충돌하는 global/field별 source type을 거부합니다. Schema/tool fingerprint는
계속 drift를 방어하며, 수동으로 만든 call도 evidence를 다시 검증합니다.

## Parameter alias는 제한된 argument routing

Planner의 argument compilation은 먼저 정확한 endpoint parameter name을 binding합니다. 남은
argument는 신뢰된 `ParameterSpec.aliases`의 일대일 관계를 통해 binding될 수 있습니다.

이는 provider fallback에서 중요합니다. 하나의 요청이 동일한 semantic value를 유지하면서도
사전 compile된 각 route에는 자체 contract가 요구하는 key를 전달할 수 있습니다.

```text
request arguments: {"formula": "Si"}

provider A -> {"formula": "Si"}
provider B -> {"chemical_formula": "Si"}
```

값 `"Si"` 자체는 변환하지 않습니다. 모호한 alias 관계는 binding하지 않고 required parameter는
누락 상태로 유지하며, planning warning에 모호한 input key를 표시합니다.

## 명시적 host state를 사용하는 retrieval은 workflow planning과 별개

안정된 `retrieve(...)` / `aretrieve(...)` surface는 stateless 상태를 유지합니다.

Host runtime이 이미 typed execution state를 소유하고 있다면 명시적 eligibility filtering을
요청할 수 있습니다.

```python
eligible = router.retrieve_state_aware(
    query,
    execution_state=state,
    k=5,
    state_requirements=requirements,
)
```

필터링은 기존 Top-K를 보충하지 않습니다. 이후 워크플로 결정은 호출자가 담당하며,
상태 조건부 backfill은 과거 연구 비교 구현으로만 보존합니다.

이 기능은 capability retrieval이지 workflow planning이 아닙니다. SchemaRouter는 state
transition을 추론하거나 retry를 schedule하거나 transaction을 실행하거나 multi-step orchestration
path를 선택하지 않습니다.

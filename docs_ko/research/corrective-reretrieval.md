# 0.14 실행 상태 인식 교정 재검색

추적 이슈: #431

이 실험은 multi-step agent가 원래 query에서 생성된 candidate list를 단순히 넓히는 대신, **관측 가능한 typed execution state**를 바탕으로 재검색하여 누락된 다음 단계 capability를 복구할 수 있는지 검증합니다.

#423 B2가 terminal 상태이므로 이 실험은 이제 자동화된 #500 conveyor를 통해 수행할 수 있습니다.

2026-10-02 기준 recovery run `36897645512`는 변경되지 않은 frozen scientific source `30663de8f618bc88a893d9bf6214035a70e8e894`를 실행 중입니다. 이전 wrapper/cache 실패는 infrastructure evidence일 뿐입니다. Terminal aggregate와 사전 등록된 gate가 확보되기 전에는 partial shard outcome을 해석하거나, 이를 기준으로 tuning하거나, promotion해서는 안 됩니다.

## 선행 연구

이 protocol은 2026년의 두 연구에서 독립적으로 동기를 얻었습니다.

- Patel et al., *Dynamic Tool Dependency Retrieval for Lightweight Function Calling* (Findings ACL 2026): 초기 query에 더해 변화하는 tool-calling state/dependency를 retrieval 조건으로 사용합니다.
- Fang and Glass, *Beyond Single-Shot: Multi-step Tool Retrieval via Query Planning* (Findings ACL 2026): compositional tool use를 위해 one-shot matching을 iterative retrieval query로 대체합니다.

SchemaRouter의 실험 범위는 더 좁습니다. 관측 가능한 typed execution state만 허용하며, hidden future route, oracle task graph, retrieval-derived execution authority는 절대 허용하지 않습니다.

## 고정된 state contract

Research retriever가 조건으로 사용할 수 있는 항목:

- 원래 user query
- 이미 실행된 registered route ID
- 관측된 field name
- 관측된 semantic ID
- 관측된 value type
- unit, dimension, qualifier
- 완료된 tool이 생성한 stable identifier
- 마지막 execution status
- 마지막 error class
- deterministic task-incomplete boolean

State는 canonical sorted-key JSON으로 직렬화하고 research retrieval call에서만 원래 query 뒤에 추가합니다.

금지 항목:

- future required route ID
- gold next-route ID
- oracle task graph
- hidden expected answer
- hidden reference fact
- condition name
- SchemaRouter rank score 또는 rank position

Free-text tool output은 retrieval context에 주입하지 않습니다.

## 고정된 조건

다음을 비교합니다.

1. SR-5-STATIC
2. SR-PROGRESSIVE-STATIC
3. SR-5-STATE-AWARE
4. FULL
5. ORACLE

State-aware 조건은 Top-5로 시작하며 완료되거나 실패한 tool turn 이후 최대 한 번 refresh할 수 있습니다. Episode당 retrieval refresh는 최대 5회이고 각 refresh는 최대 5개 capability를 노출합니다.

## 평가 surface

고정된 evaluation surface는 **180개의 독립 semantic task**를 포함합니다.

- 5개 multi-step/state strata
- 6개 언어
- stratum × language cell당 6개 task

Strata:

1. two-step state dependency
2. three-step state dependency
3. recoverable execution failure
4. identifier/provenance propagation
5. typed unit state transition

Catalog size는 100, 250, 500 endpoint입니다.

## Primary metric

다음을 각각 별도로 보고합니다.

- deterministic task pass
- 각 observable state transition 이후 next-required-tool Recall@5
- initial miss 이후 recovery rate
- multi-step state completion
- 노출된 total unique candidate
- tool-schema 및 total input token
- retrieval call
- model turn 및 tool call
- wall latency
- failed execution
- unauthorized destructive execution

## Success gate

State-aware corrective retrieval은 다음 조건을 모두 만족할 때만 유용한 것으로 봅니다.

- task pass가 static progressive보다 2pp를 초과해 낮지 않을 것
- next-required-tool Recall@5가 최소 97%일 것
- initial-miss recovery가 static progressive보다 높을 것
- mean tool-schema token이 static progressive보다 낮을 것
- unauthorized destructive execution이 0을 유지할 것
- execution-policy integrity가 100%를 유지할 것

Primary interval은 task-stratum × language를 기준으로 한 stratified task-cluster bootstrap이며 10,000 iteration, seed 20260929를 사용합니다.

## 경계

Dynamic retrieval은 candidate exposure만 변경합니다. Execution을 authorize할 수 없습니다.

B2 failure를 기준으로 어떤 rule도 tuning해서는 안 되며 scoring이 시작된 뒤에는 state field를 추가할 수 없습니다.

# 0.14 execution-state-aware corrective re-retrieval

Tracking issue: #431

이 실험은 multi-step agent가 original query에서 생성된 candidate list를 단순히 넓히는 대신 **observable typed execution state**로 다시 retrieval하여 누락된 next-step capability를 복구할 수 있는지 묻습니다.

이슈 #423 B2는 terminal이므로 automated #500 conveyor를 통해 실험이 허용됐습니다.

2026-10-02 기준 recovery run `36897645512`는 변경되지 않은 frozen scientific source `30663de8f618bc88a893d9bf6214035a70e8e894`를 실행 중입니다. 이전 wrapper/cache failure는 infrastructure evidence일 뿐입니다. Terminal aggregate와 preregistered gate가 나오기 전에 partial shard outcome을 해석·tuning·promotion해서는 안 됩니다.

## Prior art

Protocol은 두 2026 연구에서 독립적으로 동기를 얻습니다.

- Patel et al., *Dynamic Tool Dependency Retrieval for Lightweight Function Calling* (Findings ACL 2026): initial query와 evolving tool-calling state/dependency를 함께 사용해 retrieval
- Fang and Glass, *Beyond Single-Shot: Multi-step Tool Retrieval via Query Planning* (Findings ACL 2026): compositional tool use를 위해 one-shot matching을 iterative retrieval query로 대체

SchemaRouter 실험은 더 좁습니다. Observable typed execution state만 허용하며 hidden future route, oracle task graph, retrieval-derived execution authority는 허용하지 않습니다.

## Frozen state contract

Research retriever는 다음을 condition으로 사용할 수 있습니다.

- original user query
- 이미 실행된 registered route ID
- observed field name
- observed semantic ID
- observed value type
- unit, dimension, qualifier
- completed tool이 생성한 stable identifier
- last execution status
- last error class
- deterministic task-incomplete boolean

State는 canonical sorted-key JSON으로 serialize되어 research retrieval call에서만 original query에 추가됩니다.

금지 항목:

- future required route ID
- gold next-route ID
- oracle task graph
- hidden expected answer
- hidden reference fact
- condition name
- SchemaRouter rank score 또는 rank position

Free-text tool output은 retrieval context에 주입하지 않습니다.

## Frozen conditions

다음을 비교합니다.

1. SR-5-STATIC
2. SR-PROGRESSIVE-STATIC
3. SR-5-STATE-AWARE
4. FULL
5. ORACLE

State-aware condition은 Top-5에서 시작하며 completed/failed tool turn 뒤 최대 한 번 refresh할 수 있고 episode당 최대 5회의 retrieval refresh를 허용합니다. 각 refresh는 최대 5개 capability를 노출합니다.

## Surface

Frozen evaluation surface는 **180개의 독립 semantic task**를 포함합니다.

- 5 multi-step/state strata
- 6 languages
- stratum × language cell당 6 tasks

Strata:

1. two-step state dependency
2. three-step state dependency
3. recoverable execution failure
4. identifier/provenance propagation
5. typed unit state transition

Catalog size는 100, 250, 500 endpoints입니다.

## Primary metrics

다음을 각각 보고합니다.

- deterministic task pass
- 각 observable state transition 이후 next-required-tool Recall@5
- initial miss 이후 recovery rate
- multi-step state completion
- total unique candidates exposed
- tool-schema 및 total input tokens
- retrieval calls
- model turns와 tool calls
- wall latency
- failed executions
- unauthorized destructive executions

## Success gate

State-aware corrective retrieval이 유용하려면:

- task pass가 static progressive보다 2pp를 초과해 나쁘지 않아야 함
- next-required-tool Recall@5 최소 97%
- initial-miss recovery가 static progressive보다 좋아야 함
- mean tool-schema token이 static progressive보다 낮아야 함
- unauthorized destructive execution 0
- execution-policy integrity 100%

Primary interval은 task-stratum × language에 대한 stratified task-cluster bootstrap이며 10,000 iterations, seed 20260929를 사용합니다.

## Boundary

Dynamic retrieval은 candidate exposure만 변경합니다. Execution을 authorize할 수 없습니다.

B2 failure에서 rule을 tune할 수 없으며 scoring 시작 이후 state field를 추가할 수 없습니다.

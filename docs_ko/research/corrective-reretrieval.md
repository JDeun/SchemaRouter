# 0.14 execution-state-aware corrective re-retrieval

추적 issue: #431

이 experiment는 multi-step agent가 original query에서 생성된 candidate list를 단순히 넓히는 대신 **observable typed execution state**를 이용해 re-retrieval함으로써 누락된 next-step capability를 복구할 수 있는지 검증합니다.

#423 B2가 terminal 상태이므로 이 experiment는 automated #500 conveyor를 통해 실행할 수 있습니다.

As of 2026-10-02, recovery run `36897645512` is executing the unchanged frozen scientific source
`30663de8f618bc88a893d9bf6214035a70e8e894`. Earlier wrapper/cache failures are infrastructure
evidence only. No partial shard outcome may be interpreted, tuned against, or promoted before the
terminal aggregate and preregistered gate are available.

## 선행 연구

This protocol is independently motivated by two 2026 results:

- Patel et al., *Dynamic Tool Dependency Retrieval for Lightweight Function Calling*
  (Findings ACL 2026), which conditions retrieval on the initial query plus evolving tool-calling
  state/dependencies.
- Fang and Glass, *Beyond Single-Shot: Multi-step Tool Retrieval via Query Planning*
  (Findings ACL 2026), which replaces one-shot matching with iterative retrieval queries for
  compositional tool use.

SchemaRouter's experiment is narrower: it permits only observable typed execution
state, never hidden future routes, oracle task graphs, or retrieval-derived execution authority.

## Frozen state contract

Research retriever는 다음 정보를 조건으로 사용할 수 있습니다:

- the original user query;
- already executed registered route IDs;
- observed field names;
- observed semantic IDs;
- observed value types;
- units, dimensions, and qualifiers;
- stable identifiers produced by completed tools;
- the last execution status;
- the last error class;
- a deterministic task-incomplete boolean.

The state is serialized as canonical sorted-key JSON and appended to the original query only for the
research retrieval call.

다음 정보는 사용할 수 없습니다:

- future required route IDs;
- gold next-route IDs;
- oracle task graphs;
- hidden expected answers;
- hidden reference facts;
- condition names;
- SchemaRouter rank scores or rank positions.

Free-text tool output is not injected into retrieval context.

## Frozen condition

Compare:

1. SR-5-STATIC;
2. SR-PROGRESSIVE-STATIC;
3. SR-5-STATE-AWARE;
4. FULL;
5. ORACLE.

The state-aware condition starts with Top-5 and may refresh at most once after each completed or
failed tool turn, with at most five retrieval refreshes per episode. Each refresh exposes at most
five capabilities.

## 평가 surface

The frozen evaluation surface contains **180 independent semantic tasks**:

- 5 multi-step/state strata;
- 6 languages;
- 6 tasks per stratum × language cell.

Strata:

1. two-step state dependency;
2. three-step state dependency;
3. recoverable execution failure;
4. identifier/provenance propagation;
5. typed unit state transition.

Catalog sizes are 100, 250, and 500 endpoints.

## 주요 metric

Report separately:

- deterministic task pass;
- next-required-tool Recall@5 after each observable state transition;
- recovery rate after an initial miss;
- multi-step state completion;
- total unique candidates exposed;
- tool-schema and total input tokens;
- retrieval calls;
- model turns and tool calls;
- wall latency;
- failed executions;
- unauthorized destructive executions.

## 성공 gate

State-aware corrective retrieval is useful only if:

- task pass is no worse than static progressive by more than 2pp;
- next-required-tool Recall@5 is at least 97%;
- initial-miss recovery is better than static progressive;
- mean tool-schema tokens are lower than static progressive;
- unauthorized destructive executions remain zero;
- execution-policy integrity remains 100%.

The primary interval is a stratified task-cluster bootstrap over task-stratum × language with
10,000 iterations and seed 20260929.

## Boundary

Dynamic retrieval은 candidate exposure만 변경합니다. Execution을 승인할 수 없습니다.

어떤 rule도 B2 failure를 이용해 tuning할 수 없으며 scoring 시작 후에는 state field를 추가할 수 없습니다.

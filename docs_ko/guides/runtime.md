# Batch, streaming, event

SchemaRouter는 capability source와 관계없이 일관된 실행 vocabulary를 사용합니다.

## Invoke

```python
result = router.invoke(request)
result = await router.ainvoke(request)
```

두 경로 모두 planning과 execution을 수행합니다.

## Batch

```python
results = router.batch(requests)
results = await router.abatch(requests, config={"max_concurrency": 8})
```

`abatch()`는 input 순서를 유지합니다. 완료 순서대로 소비하려면 `router.abatch_as_completed(requests)`를 사용하며 반환 index는 항상 원래 input을 가리킵니다.

## Result streaming

```python
async for result in router.astream(request):
    print(result.tool, result.endpoint)
```

기본 실행은 plan 순서를 유지하는 sequential mode입니다. 독립적인 read-only fan-out은 `RunConfig(execution_mode="parallel_read_only", max_parallel_calls=4)`로 명시적으로 활성화합니다.

parallel task를 시작하기 전에 모든 planned call을 현재 schema, binding, execution policy로 preflight하고 모든 call에서 `endpoint.read_only is True`인지 확인합니다. mutating/unclassified call이 하나라도 있으면 invocation 전에 parallel run 전체가 실패합니다.

`ainvoke()`는 plan 순서로 결과를 반환하지만 `astream()`, `astream_events()`는 completion order를 노출할 수 있습니다. 모든 parallel call은 동일한 per-run execution budget을 공유합니다. 이는 flat fan-out이며 DAG/workflow runtime이 아닙니다. dependency, branching, checkpoint, multi-step orchestration은 LangGraph 같은 상위 framework가 담당합니다.

### Bound registration의 원자성

`add_bound_tool()`, 실행 가능한 adapter를 포함한 URL ingestion, Python/LangChain/LlamaIndex/HTTP
등록, MCP 등록처럼 capability contract와 trusted invoker를 하나의 논리적 작업으로 등록하는
public API는 registry contract와 binding을 failure-atomic transition으로 publish합니다.

binding이 실패하면 SchemaRouter는 자신이 방금 publish한 정확한 registry version/fingerprint를
여전히 소유하고 있을 때만 이전 contract와 binding을 복원합니다. 신규 capability라면 방금
등록한 contract를 제거합니다. 다른 writer가 동시에 registry를 변경해 rollback이 안전하지
않아진 경우에는 그 변경을 덮어쓰지 않고 fail-closed로 종료하며, 해당 binding은 ready 상태로
남기지 않습니다. Schema HTTP validator 같은 post-publication 상태도 registry + binding 전환이
완전히 성공한 뒤에만 갱신됩니다.

### Async 실행 안의 동기 I/O

trusted sync invoker는 기본적으로 현재 thread에서 실행됩니다. 해당 invoker가 worker thread에서 안전하게 실행될 수 있다는 것을 caller가 알고 있다면 `offload_sync=True`로 bind할 수 있습니다. 이 경우 SchemaRouter는 event loop를 막지 않고, worker를 기다리는 동안 남은 elapsed execution budget도 적용합니다.

provider-neutral vector/graph/record-store backend는 `remote` 분류를 기준으로 같은 정책을 자동 적용합니다. `remote=True` backend의 동기 메서드는 worker thread로 offload하고, `remote=False`인 local/thread-affine backend는 inline으로 유지합니다. SQLite는 inline으로 유지됩니다.

Python은 이미 시작된 worker thread를 강제로 중단할 수 없습니다. 명시적으로 read-only인 endpoint는 elapsed budget을 넘으면 기존처럼 `ExecutionBudgetExceededError`를 발생시키지만, backend 호출이 반환될 때까지 worker가 리소스를 계속 사용할 수 있음을 caller가 고려해야 합니다. 반대로 non-read-only 또는 effect가 불명확한 endpoint는 worker가 시작된 뒤 timeout이나 task cancellation이 발생하면 `IndeterminateInvocationError`를 발생시킵니다. 이 오류는 non-retryable이며 mutation이 뒤늦게 완료될 수 있으므로 SchemaRouter가 같은 호출을 자동 재시도하지 않습니다. 더 강한 완료 보장이 필요하면 vendor-level timeout, transaction, idempotency key, 또는 cancellation-safe async client를 사용해야 합니다.

## Typed lifecycle event

```text
run.start
plan.end
tool.start
tool.end | tool.error
tool.fallback
run.end  | run.error
```

한 invocation의 모든 event는 같은 `run_id`와 단조 증가하는 `sequence`를 공유합니다. provider/access fallback도 같은 event stream을 사용하며 open-ended replanning을 수행하지 않습니다.

## Access health와 복구

`InvocationUnavailableError`로 retry를 모두 소진한 transport route는 유한한 process-local cooldown에 들어가고 만료 후 자동으로 다시 후보가 됩니다. 명시적 read-only path에는 trusted health probe를 등록할 수 있습니다. probe 성공은 즉시 route를 다시 열고 실패는 bounded cooldown만 연장합니다.

SchemaRouter는 remote metadata에서 probe를 만들어내거나 model output으로 health state를 수정하지 않습니다. 외부 service-health system이 있다면 `mark_access_unavailable()` / `mark_access_available()`을 직접 사용할 수 있습니다.

## Payload redaction

argument와 result payload는 기본 event에 포함하지 않습니다. `RunConfig(include_payloads=True)`는 적절한 retention control을 가진 trusted trace sink에서만 사용하세요.

## Bound configuration

`router.with_config(RunConfig(...))`는 underlying router를 변경하지 않고 가벼운 configured facade를 만듭니다.

## OpenTelemetry와 영속 trace

optional OpenTelemetry integration은 같은 typed event stream을 사용하며 payload, metadata, tag, exception message를 제외합니다. `SQLiteRunTraceStore`를 사용하면 process restart 후에도 event stream을 보존할 수 있습니다. replay는 historical event만 읽고 tool을 재실행하지 않습니다.

## Schema planning과 execution-ready planning

`plan()`/`aplan()`은 schema-oriented이며 그 순간 trusted invoker가 바인딩되어 있을 필요가 없습니다. 반면 `plan_executable()`/`aplan_executable()`은 현재 tool fingerprint에 trusted invoker가 바인딩되어 있어야 합니다. `invoke`, `ainvoke`, stream/batch/event API는 자동으로 이 stricter path를 사용합니다.

명시적인 `execute(plan)`은 replan하지 않습니다. 전달된 plan을 일반 fail-closed binding/schema/policy 규칙과 precompiled fallback route 아래에서 검증하고 실행합니다.

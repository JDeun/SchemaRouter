# Execution policy

`ExecutionPolicy`는 신뢰된 로컬 side-effect gate입니다.

planning이 관련 mutation을 찾아냈다고 해서 그 mutation이 허가된 것은 아닙니다.

## 기본 동작

기본 policy는 remote capability에 대해 보수적으로 동작합니다:

- 일반 local/manual contract는 실행할 수 있습니다.
- 알려진 OpenAPI mutation은 명시적으로 활성화하지 않으면 차단됩니다.
- destructive operation은 명시적으로 활성화하지 않으면 차단됩니다.
- 분류되지 않은 remote MCP operation은 명시적으로 활성화하지 않으면 차단됩니다.

## 로컬 authority 설정

```python
from schemarouter import ExecutionPolicy, SchemaRouter

router = SchemaRouter(
    policy=ExecutionPolicy(
        allow_mutations=True,
        allow_destructive=False,
        allow_unclassified_remote=False,
    )
)
```

이 policy는 신뢰된 application code만 구성해야 합니다.

## Operation-scoped rule

category-wide switch가 애플리케이션에 필요한 것보다 넓은 authority를 부여한다면 `PolicyRule`을 사용합니다. rule은 선언 순서대로 평가되며 첫 번째 match가 적용됩니다.

```python
from schemarouter import ExecutionPolicy, PolicyRule, SchemaRouter

router = SchemaRouter(
    policy=ExecutionPolicy(
        rules=(
            PolicyRule(
                name="allow-job-create",
                operation="jobs.create",
                effect="allow",
            ),
            PolicyRule(
                name="protect-delete",
                operation="jobs.delete*",
                effect="deny",
            ),
            PolicyRule(
                name="review-refunds",
                operation="payments.refund",
                effect="require_approval",
            ),
        ),
    ),
    approval_callback=approve,
)
```

operation string은 shell-style wildcard로 `tool.endpoint`와 match합니다. optional `remote`, `read_only`, `destructive`, `unclassified` predicate로 rule 범위를 더 좁힐 수 있습니다. `unclassified=True`는 side-effect classification이 unknown인 endpoint를 명시적으로 match하며 `read_only=None`은 그 의미를 겸하지 않고 기본 wildcard로 유지됩니다.

scoped `allow` rule은 해당 operation에만 적용되는 trusted local authority입니다. scoped `deny` rule은 globally enabled category의 범위를 좁힐 수 있습니다. `require_approval`은 authority grant가 아니라 추가 gate입니다. 호출은 먼저 해당 `allow_mutations`, `allow_destructive`, `allow_unclassified_remote` category guard 또는 명시적 scoped `allow` rule을 만족해야 하며, 그 다음 trusted approval callback이 이미 authorize된 호출의 진행 여부를 결정합니다.

어떤 rule도 match하지 않으면 기존 `allow_mutations`, `allow_destructive`, `allow_unclassified_remote` 동작을 그대로 유지합니다.

## 호출별 approval

policy permission과 human/application approval은 서로 별도의 gate입니다.

```python
from schemarouter import ExecutionPolicy, SchemaRouter

async def approve(tool, endpoint, call) -> bool:
    return await my_approval_service.check(
        tool=tool.key,
        endpoint=endpoint.name,
    )

router = SchemaRouter(
    policy=ExecutionPolicy(
        allow_mutations=True,
        approval_mode="non_read_only",
    ),
    approval_callback=approve,
)
```

`approval_mode`는 다음 값을 받습니다:

- `never` — 호출별 callback 없음, 기본값
- `non_read_only` — mutating/unclassified operation에 approval 적용
- `all` — 모든 호출 전에 approval 적용

approval이 필요한데 callback이 없으면 호출은 fail-closed됩니다. callback exception도 fail-closed되며 literal boolean `True`만 호출을 승인합니다. async approval은 run의 남은 elapsed-time budget으로 제한됩니다.

callback은 trusted local code에만 존재합니다. serializable planner input이 아니며 remote metadata나 model이 만들 수 없습니다.

## Run별 execution budget

```python
from schemarouter import ExecutionBudget, RunConfig

config = RunConfig(
    budget=ExecutionBudget(
        max_tool_calls=4,
        max_attempts=6,
        max_remote_attempts=4,
        max_elapsed_seconds=15,
        max_cost_units=3.0,
        per_tool_calls={"materials": 2},
        cost_units={
            "materials.search": 0.5,
            "papers.search": 1.0,
            "*": 0.25,
        },
    )
)

results = await router.ainvoke(request, config=config)
```

semantic은 deterministic합니다:

- logical tool call은 planned call마다 한 번 계산
- retry를 포함한 모든 실제 invoker attempt를 계산
- remote attempt는 별도로 계산
- cost unit은 attempt마다 부과
- operation-specific cost가 tool-specific cost보다 우선하며, tool-specific cost는 `"*"`보다 우선
- 하나의 plan에 포함된 모든 call이 동일 budget state를 공유
- wall-clock budget이 만료되면 async approval callback, execution hook, invocation, retry backoff를 중단하거나 제한
- synchronous approval/hook은 preempt할 수 없지만 반환 직후 elapsed time을 검사

batch API는 각 input invocation을 자체 budget을 가진 별도 run으로 취급합니다.

budget은 billing이 아니라 local enforcement입니다. cost unit은 애플리케이션이 정의하는 weight입니다.

## Retry 상호작용

read-only retry가 기본값입니다. 호출을 retry하면 각 retry는 network/tool invocation 전에 attempt, remote, cost budget을 소비합니다.

budget 거부는 retry하지 않습니다.

## Remote metadata가 권한을 부여할 수 없는 이유

remote server는 자신의 description과 annotation을 제어합니다. 이 field가 local execution authority를 설정하도록 허용하면 capability provider가 자기 자신에게 권한을 부여할 수 있습니다.

SchemaRouter는 일반 remote metadata는 descriptive하게 유지하고 local policy를 authority로 유지합니다.
policy가 사용하는 local/remote classification은 model-visible metadata flag가 아니라 fingerprinted `ToolSpec.remote` contract입니다. built-in remote adapter가 import 중 해당 field를 local에서 설정합니다.

## Runtime approval과 documentation proposal approval

documentation-derived tool에는 서로 분리된 gate가 있습니다:

```text
grounded proposal
 -> explicit approve_proposal()
 -> registered/bound tool
 -> ExecutionPolicy
 -> optional per-call approval
 -> execution budget
 -> execute
```

proposal approval은 추론된 contract가 registry에 들어갈 수 있는지를 결정합니다. runtime approval은 현재 이 특정 호출을 실행할 수 있는지를 결정합니다.

## Destructive operation

adapter가 분류할 수 있는 DELETE 계열 operation은 destructive로 표시됩니다. 주변 application에 적절한 authorization, audit, confirmation, rollback semantic이 있을 때만 `allow_destructive=True`를 설정합니다.

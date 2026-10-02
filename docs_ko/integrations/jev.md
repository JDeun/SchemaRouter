# Jev / TypeSafe System One

SchemaRouter는 Jev 같은 TypeSafe System One model용 optional bounded-decision adapter를 제공합니다. core dependency graph 밖에 있으며 기본값은 **off**입니다.

Jev는 execution plan을 작성하거나 agent/orchestrator로 동작하지 않습니다. finite option ID 중 하나를 반환할 뿐이며 tool execution/memory/agent loop를 소유하지 않습니다.

## 설치

```bash
pip install "schemarouter[jev]"
export TYPESAFE_API_KEY="..."
```

현재 `typesafe-sdk>=0.7,<1`을 지원하며 SDK 기본 model은 `jev-latest`입니다.

## 사용

`JevDecisionBackend(min_confidence=0.65)`를 `SchemaPlanner`의 decision backend로 전달합니다. confidence가 threshold보다 낮으면 abstain하며 기본 `fallback="deterministic"`에서는 deterministic ranking으로 돌아가 warning을 기록합니다. `async_mode=True`도 지원합니다.

## Data boundary

provider는 user query, 허용 시 bounded context, locally generated option ID, option label/description만 받습니다. `DecisionOption.metadata`, runtime/transport credential, invoker, execution policy는 model state에 넣지 않습니다. context도 로컬에 남겨야 한다면 `include_context=False`를 사용합니다.

## Fail-closed

제공하지 않은 option ID, non-finite/out-of-range confidence, malformed response, sync mode의 async client는 거부합니다. provider error 처리 방식은 `DecisionPolicy`가 결정합니다.

현재 adapter는 TypeSafe `choice` 한 번으로 최대 한 candidate만 반환합니다. multi-selection은 free-form output으로 합성하지 않고 별도 bounded contract가 필요합니다.

provider-neutral benchmark harness로 Jev를 같은 corpus에서 비교할 수 있으며 API key가 있을 때만 실행합니다.

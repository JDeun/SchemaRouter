# 런타임 수명주기

`SchemaRouter`는 health monitoring과 schema watching을 위해 자신이 시작한 background task를 직접 관리합니다. 애플리케이션 종료 시 `aclose()`를 호출하거나 router를 async context manager로 사용하세요.

```python
from schemarouter import SchemaRouter

async with SchemaRouter() as router:
    await router.start_health_monitor()
    await router.start_schema_watcher()
    # router 사용
```

context를 벗어나면 `await router.aclose()`가 호출됩니다. 종료 처리는 idempotent하며, 한쪽 종료 경로에서 오류가 발생하더라도 두 background manager를 모두 중지하려고 시도합니다.

## 리소스 소유권

`aclose()`는 router lifecycle이 소유한 다음 리소스만 중지합니다.

- `AccessHealthMonitor` background task
- `SchemaWatchManager` background task
- 명시적으로 offload된 invoker와 sync health probe가 사용하는 bounded synchronous worker pool

반대로 호출자가 소유한 다음 리소스는 **종료하지 않습니다**.

- 주입된 `httpx.AsyncClient`
- `SQLiteRegistry` 같은 주입된 registry
- SDK client, MCP factory/transport, subprocess handle 또는 기타 trusted invoker
- 호출자 소유 trace store

이러한 리소스는 애플리케이션이 자체 ownership model에 따라 종료해야 합니다. SchemaRouter adapter가 내부에서 만드는 단기 HTTP client는 해당 client를 만든 개별 operation 안에서 이미 종료됩니다. router를 닫으면 새로운 sync offload는 더 이상 받지 않지만, 이미 실행을 시작한 Python thread는 강제로 중단할 수 없으므로 `aclose()`가 반환된 뒤에도 자연스럽게 완료될 수 있습니다.

## 동기 및 비동기 루프 소유권

동기식 SchemaRouter wrapper는 호출할 때마다 새로운 `asyncio.run()` 루프를 만들지 않고 하나의 장기 실행 내부 event loop를 사용합니다. 따라서 내부 schema watcher 또는 health monitor의 lock에 경합이 발생한 뒤에도 동일한 router를 동기 API로 안전하게 재사용할 수 있으며, 여러 애플리케이션 thread에서 들어오는 동기 호출도 동일한 loop-affine runtime에서 직렬화됩니다.

loop-affine lifecycle state의 소유자는 하나뿐입니다. health monitor 또는 schema watcher를 애플리케이션의 async event loop에서 처음 사용한 경우, 이후 동일한 lifecycle state를 동기 wrapper를 통해 실행하는 방식은 지원되지 않으며 명확한 `RuntimeError`가 발생합니다. 반대 방향의 mixed-mode 전환도 같은 이유로 거부됩니다. async 애플리케이션에서는 async API를 일관되게 사용하고, 동기 애플리케이션에서는 동기 wrapper를 일관되게 사용하세요. 두 소유권 모델이 모두 필요하면 별도의 `SchemaRouter` 인스턴스를 사용해야 합니다.

schema watcher가 실행 중일 때도 동기식 schema-watch 등록과 제거는 안전합니다. wake-up은 다른 thread에서 `asyncio.Event`를 직접 변경하지 않고, 해당 event loop로 전달되어 처리됩니다.


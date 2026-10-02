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

반대로 호출자가 소유한 다음 리소스는 **종료하지 않습니다**.

- 주입된 `httpx.AsyncClient`
- `SQLiteRegistry` 같은 주입된 registry
- SDK client, MCP factory/transport, subprocess handle 또는 기타 trusted invoker
- 호출자 소유 trace store

이러한 리소스는 애플리케이션이 자체 ownership model에 따라 종료해야 합니다. SchemaRouter adapter가 내부에서 만드는 단기 HTTP client는 해당 client를 만든 개별 operation 안에서 이미 종료됩니다.

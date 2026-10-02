# Consumer acceptance 검증

SchemaRouter는 `scripts/consumer_acceptance.py`에 작은 end-to-end acceptance suite를 유지합니다. unit/adapter contract test와 달리 public package surface만 사용하며 installed wheel/sdist를 downstream application처럼 검증합니다.

검증 범위에는 Python-tool planning/execution, mutation denial/approval gate, schema/binding drift fail-closed, runtime output validation, read-only retry/budget, SQLite registry, redacted run trace, read-only inspection/dashboard, 설치된 CLI의 SQLite artifact 처리가 포함됩니다.

```bash
python scripts/consumer_acceptance.py
python scripts/consumer_acceptance.py --json-out artifacts/consumer-acceptance.json
```

## CI coverage

같은 script를 지원 Linux Python matrix, Windows smoke, minimum-dependency job, clean wheel/sdist venv에서 실행합니다.

package job은 built wheel에 lightweight optional extra `mcp`, `langchain`, `langgraph`, `llamaindex`, `jev`, `otel`도 설치합니다. MCP/Jev/OpenTelemetry no-network SDK/import smoke와 LangChain/LangGraph/LlamaIndex runnable example을 실행하고 installed inspection CLI/dashboard도 검증합니다. Laya는 PyTorch dependency 때문에 별도 CPU integration job에서 처리합니다.

public OpenAPI/OPTIMADE compatibility smoke는 외부 서비스에 의존하므로 deterministic package acceptance gate와 분리합니다.

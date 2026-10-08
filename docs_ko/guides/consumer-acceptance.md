# Consumer acceptance validation

SchemaRouter는 `scripts/consumer_acceptance.py`에 소규모 end-to-end acceptance suite를 유지합니다. unit/adapter contract test와 별개이며 public package surface만 사용하고 downstream application처럼 설치된 wheel 또는 sdist를 대상으로 실행하도록 설계되어 있습니다.

suite는 다음 production boundary를 검증합니다:

- 일반 Python-tool planning과 execution
- default mutation denial과 trusted approval gating
- schema-drift 및 invoker-binding-drift fail-closed 동작
- runtime output JSON Schema validation
- read-only retry 동작과 elapsed-time execution budget
- SQLite registry persistence
- redacted run-trace persistence
- read-only inspection/dashboard 생성
- persisted SQLite artifact를 대상으로 한 installed `schemarouter inspect` 및 `schemarouter dashboard` CLI 실행

로컬 실행:

```bash
python scripts/consumer_acceptance.py
```

machine-readable report를 보존하려면:

```bash
python scripts/consumer_acceptance.py --json-out artifacts/consumer-acceptance.json
```

## CI coverage

동일 script를 지원 Linux Python matrix, Windows smoke job, minimum-dependency job, clean wheel/sdist virtual environment에서 각각 실행합니다.

package job은 built wheel을 lightweight optional extra를 통해서도 install합니다:
`mcp`, `langchain`, `langgraph`, `llamaindex`, `jev`, `otel`입니다. MCP, Jev, OpenTelemetry에는 no-network SDK/import smoke를 실행하고 LangChain, LangGraph, LlamaIndex runnable example을 실행합니다. 이어 end-to-end example이 생성한 SQLite registry/trace artifact를 대상으로 installed inspection CLI를 검증하고 emitted JSON을 validate한 뒤 installed console script로 dashboard를 export합니다. 이를 통해 editable install로는 잡을 수 없는 packaging-metadata, optional-dependency, CLI-entry-point regression을 탐지합니다. Laya는 PyTorch dependency를 별도로 처리하므로 dedicated CPU integration job에 유지합니다.

public OpenAPI/OPTIMADE compatibility smoke는 external service에 의존하므로 분리합니다. 이 check는 현재 source tree를 non-editable로 설치하고 `pip check` 후 public service를 호출해 machine-readable artifact를 보존합니다. deterministic package acceptance gate로 취급하지 않습니다.

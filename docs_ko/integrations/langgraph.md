# LangGraph

SchemaRouter는 planning, policy, schema validation, execution authority를 내부에 유지하면서 native LangGraph `StateGraph` node로 실행할 수 있습니다.

## 설치

```bash
pip install "schemarouter[langgraph]"
```

core package는 LangGraph에 의존하지 않습니다.

## Graph node 추가

`to_langgraph_node(router)`를 `StateGraph` node로 등록할 수 있으며 sync/async graph execution을 모두 지원합니다.

기본 node는 `state["schemarouter_request"]`의 string/`PlanRequest`/compatible mapping 또는 `state["query"]` + optional `state["arguments"]`를 받습니다. 결과는 `schemarouter_results` partial state update로 반환되고 checkpoint/persistence 친화성을 위해 기본적으로 JSON serialize됩니다.

application-specific state는 `request_factory`와 `result_key`로 변환할 수 있습니다.

## 신뢰 경계

LangGraph → SchemaRouter node → planning → current schema validation → policy/approval/budget → binding-drift check → trusted invoker → output validation → partial graph-state update 순입니다.

LangGraph는 graph control flow, checkpoint, memory, runtime context, HITL orchestration을 담당하고 SchemaRouter는 schema-aware tool planning과 validated execution을 담당합니다. LangGraph `RunnableConfig`와 SchemaRouter `RunConfig`는 의도적으로 합치지 않습니다.

repository의 `examples/langgraph_quickstart.py`를 CI에서 실제 `StateGraph` sync/async mode로 실행합니다.

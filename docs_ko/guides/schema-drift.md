# Schema drift

SchemaRouter는 plan이 만들어진 뒤 schema나 transport contract가 바뀌면 조용히 실행하지 않습니다. endpoint/tool fingerprint가 current registry와 다르면 `SchemaDriftError`, binding이 이전 tool fingerprint에 묶여 있으면 `BindingDriftError`입니다.

`compare_endpoint_specs()`, `compare_tool_specs()`는 변경 이유를 보수적으로 설명하지만 compatible report도 fingerprint gate를 우회하지 않습니다. caller는 current contract로 replan/rebind해야 합니다.

schema watch/refresh는 trusted local capability이며 source adapter가 refresh profile을 명시한 경우에만 사용합니다. 변경을 자동 승인하지 않고 pending drift를 inspect한 뒤 accept/reject할 수 있습니다. credential/authority는 refresh metadata에서 추론하지 않습니다.


## 네이티브 데이터베이스 스키마 갱신

네이티브 onboarding API로 등록한 caller-owned relational, vector, graph, record-store backend는 process-local re-introspection callback을 유지합니다. backend client, credential, connection pool은 ToolSpec에 저장하지 않습니다.

`arefresh_native_schema(tool_key)`는 동일 contract는 유지하고, 호환성이 입증된 drift만 적용한 뒤 trusted binding을 새 fingerprint에 맞춰 다시 연결합니다. breaking drift는 현재 실행 contract를 유지한 채 `pending_review`로 격리하며 `aaccept_native_schema_pending(...)`으로 명시적으로 승인할 수 있습니다.

장기 실행에서는 `start_native_schema_watcher(interval_seconds=300)` / `stop_native_schema_watcher()`를 사용하고, 일회성 점검은 `check_native_schema_watches_once()`를 사용합니다. watcher 상태와 backend 객체는 process-local이며 credential을 persistence layer에 저장하지 않습니다.

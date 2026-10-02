# Schema drift

SchemaRouter는 plan이 만들어진 뒤 schema나 transport contract가 바뀌면 조용히 실행하지 않습니다. endpoint/tool fingerprint가 current registry와 다르면 `SchemaDriftError`, binding이 이전 tool fingerprint에 묶여 있으면 `BindingDriftError`입니다.

`compare_endpoint_specs()`, `compare_tool_specs()`는 변경 이유를 보수적으로 설명하지만 compatible report도 fingerprint gate를 우회하지 않습니다. caller는 current contract로 replan/rebind해야 합니다.

schema watch/refresh는 trusted local capability이며 source adapter가 refresh profile을 명시한 경우에만 사용합니다. 변경을 자동 승인하지 않고 pending drift를 inspect한 뒤 accept/reject할 수 있습니다. credential/authority는 refresh metadata에서 추론하지 않습니다.

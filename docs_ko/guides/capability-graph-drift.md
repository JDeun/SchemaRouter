# 기능 그래프 변경 감지

SchemaRouter는 이전에 컴파일한 기능 계약 스냅샷과 새로고침한 스냅샷을 비교하여 어떤 기능 그래프 노드를 다시 컴파일해야 하는지 식별할 수 있습니다.

```python
from schemarouter import compare_capability_graph_snapshot

report = compare_capability_graph_snapshot(graph, previous_contracts, refreshed_contracts)
if report.changed:
    print(report.compatibility)
    print(report.invalidated_capability_ids)
```

비교 결과는 결정론적입니다. 기능 계약 지문은 정규화된 JSON의 SHA-256 해시이므로 매핑에 키를 삽입한 순서가 달라도 지문은 바뀌지 않습니다.

## 무효화 경계

변경되거나 제거된 계약은 호환성을 깨는 변경입니다. 해당 기능과 기존 그래프에서 바로 연결된 선행·후행 노드를 무효화합니다. 그 노드에 연결된 간선의 호환성 판단은 더 이상 유효하지 않을 수 있기 때문입니다. 새로 추가된 기능은 호환 가능한 추가 변경이며, 호스트 또는 컴파일러가 새로운 간선을 계산할 수 있도록 새 노드만 무효화합니다.

이 API는 **무효화 메타데이터만 생성합니다**. 기능을 실행하거나, 호출을 다른 곳으로 이전하거나, 권한을 확대하거나, 호스트의 실행 정책을 교체하지 않습니다. 공급자 스키마를 새로고침할 시점, 영향받는 노드를 재구성할 시점, 새 그래프를 배포할 시점은 호스트가 결정합니다.

공급자 수준의 OpenAPI, MCP 또는 과학 데이터 공급자 스키마 변경은 먼저 기존 `ToolSpec` 및 스키마 차이 분석 계층으로 정규화해야 합니다. 그 후 기능 그래프 변경 감지가 갱신된 스키마에서 생성한 공급자 중립적인 기능 계약을 비교합니다. 런타임 상태는 별도의 오버레이로 유지되며 결정론적 계약 지문에 포함하지 않습니다.

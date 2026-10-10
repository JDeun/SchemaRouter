# 기능의 출처와 대체 경로 이력

기능 실행 경로의 이력(lineage)은 특정 경로를 선택한 이유와 대체 경로가 적용됐을 때 실제로 사용한 경로를 기록합니다.

```python
from schemarouter import CapabilityLineageHop, build_capability_lineage

selected = CapabilityLineageHop(
    provider="materials-project",
    access_method="rest",
    route_id="mp.summary",
    capability_id="material.summary",
    schema_fingerprint="...",
    semantic_ids=("band_gap",),
)
lineage = build_capability_lineage(selected=selected)
```

각 이력 문서는 정규화된 기계 판독 표현에 대해 계산한 결정론적 SHA-256 식별자를 부여받습니다. 개별 경로 기록에는 공급자, 접근 방식, 경로·기능 ID, 스키마 리비전·지문, 관련 의미적 ID, 구조화된 상태·대체 사유 등이 포함될 수 있습니다.

이 모델에는 **페이로드, 인자 값, 자격 증명, 헤더 필드를 의도적으로 포함하지 않습니다**. 호스트는 권한 또는 가시성 정책으로 숨겨진 기능의 이력도 생성해서는 안 됩니다. `inspect_capability_lineage()`는 로깅, 대시보드, 어댑터별 관측에 사용할 수 있는 분리된 안전 복사본을 반환합니다.

이력 기능은 분산 추적 시스템이 아니며 실행이나 권한 부여를 수행하지 않습니다. 실행, 정책, 민감 정보 가림, 추적 연결에 대한 책임은 계속 호스트에 있습니다.

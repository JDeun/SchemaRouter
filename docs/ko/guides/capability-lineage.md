# Capability provenance 및 fallback lineage

Capability lineage는 어떤 route가 선택되었는지와 fallback 발생 시 실제로 어떤 route가 사용되었는지를 기록합니다.

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

각 lineage 문서는 canonical machine-readable 표현의 SHA-256 digest를 결정적 ID로 사용합니다. Hop에는 provider, access method, route/capability ID, schema revision/fingerprint, 관련 semantic ID와 구조화된 health/fallback reason을 담을 수 있습니다.

모델에는 payload, argument value, credential, header 필드가 의도적으로 없습니다. Host는 authorization 또는 visibility policy로 숨겨진 capability의 lineage도 생성하지 않아야 합니다. `inspect_capability_lineage()`는 logging, dashboard, adapter observability에 사용할 수 있는 분리된 안전 복사본을 반환합니다.

Lineage는 distributed tracing이 아니며 실행이나 권한 부여를 수행하지 않습니다. 실행, policy, redaction, trace correlation의 책임은 host에 남습니다.

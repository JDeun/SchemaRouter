# Capability decision trace

SchemaRouter에는 state, health, drift, host policy, operational constraint, negotiation, fallback eligibility, routing lineage를 위한 여러 typed decision primitive가 있습니다. Capability decision trace는 이 **이미 계산된 결과**를 하나의 privacy-safe explanation으로 묶습니다.

이 기능은 observability layer이며 두 번째 policy engine이 아닙니다.

## Trace 만들기

```python
from schemarouter import (
    CapabilityDecisionCandidateInput,
    build_capability_decision_trace,
)

trace = build_capability_decision_trace(
    [
        CapabilityDecisionCandidateInput(
            capability_id="materials.optimade.summary",
            visible=True,
            final_disposition="selected",
            retrieval="retrieved",
            health="healthy",
            drift="current",
            policy="allowed",
            state=state_eligibility,
            operational=operational_result,
            negotiation=negotiation_candidate,
            fallback=fallback_eligibility,
        )
    ],
    snapshot_id=snapshot.snapshot_id,
    registry_version=router.registry.version,
)
```

Trace는 기존 component result object를 보존하면서 decision stage가 붙은 normalized reason list도 제공합니다.

## Privacy 경계

Host-visible candidate만 trace에 포함될 수 있습니다. `visible=False` 를 전달하면 capability identifier와 rejection reason까지 포함해 candidate 전체가 결과에서 제외됩니다.

Decision trace에는 다음을 넣지 않습니다.

- request payload value;
- credential과 private header;
- hidden capability inventory;
- rank score;
- execution binding 또는 invocation authority.

Trace ID는 visible structured trace content를 기준으로 deterministic하게 생성됩니다.

## Compact / detailed rendering

```python
from schemarouter import render_capability_decision_trace

compact = render_capability_decision_trace(trace)
detailed = render_capability_decision_trace(trace, detailed=True)
```

Compact rendering은 final disposition, health/drift/policy 상태와 normalized reason code를 보여줍니다. Detailed rendering은 이미 계산된 state, constraint, negotiation, fallback result object도 함께 제공합니다.

## Router inspection과 dashboard

Trace 저장은 host 책임으로 남습니다. SchemaRouter는 memory system이나 숨겨진 trace database를 추가하지 않습니다.

Live router를 inspect할 때 trace를 명시적으로 전달합니다.

```python
inspection = router.inspect(decision_traces=[trace])
```

HTML dashboard는 visible capability ID, final disposition, reason code만 포함하는 compact decision-trace table을 표시합니다.

## CLI

직렬화된 `CapabilityDecisionTrace` 는 어떤 tool도 실행하지 않고 inspect할 수 있습니다.

```bash
schemarouter inspect decision-trace decision-trace.json --json
schemarouter inspect decision-trace decision-trace.json --detailed --json
```

## Tracing 비활성화

Trace 생성은 opt-in입니다. `build_capability_decision_trace(..., enabled=False)` 를 사용하면 `None` 을 반환하며 candidate trace object를 만들지 않습니다.

Decision trace는 plan, authorize, rank, retry, execute, compensate를 수행하지 않으며 host visibility를 넓히지 않습니다.

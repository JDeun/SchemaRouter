# Decision backend plugin

SchemaRouter core에 model-specific integration을 추가하지 않고 설치된 Python package에서 서드파티 bounded decision backend를 로드할 수 있습니다.

## Entry-point contract

```toml
[project.entry-points."schemarouter.decision_backends"]
anyjev = "schemarouter_anyjev:create_backend"
```

entry point는 backend class, factory callable, 또는 `decide(request)`를 가진 preconstructed object가 될 수 있습니다.

## Discovery와 명시적 로드

`discover_decision_backend_plugins()`는 metadata만 읽고 plugin code를 import/execute하지 않습니다. `load_decision_backend_plugin("anyjev", config={...})`로 정확히 지정한 plugin만 import합니다. plugin loading은 trusted installed Python code 실행입니다.

반환 backend도 일반 bounded-decision contract를 따르며 selected option ID는 planning에 영향을 주기 전에 SchemaRouter가 finite offered ID와 대조합니다.

repository에는 실제 entry point를 선언한 deterministic demo package가 있으며 plugin이 execution authority를 받지 않고 finite option만 선택/abstain하는 경계를 검증합니다.

## Benchmark와 확장 경로

shared decision benchmark는 설치된 plugin을 `--decision-plugin anyjev`로 로드할 수 있습니다. report에는 plugin/distribution/version/config key와 config env 이름만 기록하고 값은 기록하지 않습니다.

새 모델은 가장 좁은 안정 interface를 사용합니다.

1. System One wire-compatible → `SystemOneDecisionBackend`
2. 일회성 연구 callable → `CallableDecisionBackend`
3. 재사용 서드파티 integration → `schemarouter.decision_backends` plugin

호환성은 추천 품질과 별개이며 production 교체 전 frozen workload에서 routing/rejection/false-route/latency/error/authority violation을 비교해야 합니다.

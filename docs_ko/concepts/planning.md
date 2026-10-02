# Planning

planner는 registry의 typed capability를 query와 caller-supplied argument/evidence constraint에 맞춰 bounded `ExecutionPlan`으로 컴파일합니다. deterministic lexical/indexed recall이 기본이며 optional semantic recall/decision backend는 등록된 candidate 안에서만 작동합니다.

multi-field request에서는 semantic requirement coverage를 추적해 `required`, `covered`, `uncovered`를 명시합니다. `max_calls`나 policy 때문에 완전한 coverage가 불가능하면 이를 숨기지 않고 warning으로 남깁니다.

field projection은 recall-first입니다. 명확한 field match가 있으면 identifier와 필요한 field를 선택하고, 모호하면 지나치게 잘라 downstream answer quality를 해치지 않도록 declared field를 유지합니다. missing required argument는 만들어내지 않고 plan을 non-executable로 표시하며 executor가 invocation 직전 다시 계산합니다.

fallback은 model-driven replanning이 아니라 각 provider/access schema에 대해 미리 컴파일된 finite read-only route입니다. evidence requirement와 parameter alias도 trusted local contract로 처리하며 executor가 현재 schema에서 다시 검증합니다.

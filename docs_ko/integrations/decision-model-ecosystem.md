# Decision-model 생태계 수용 기준

이 문서는 **integration 형태**를 추적하며 model quality를 평가하거나 추천하지 않습니다. 마지막 검토일은 **2026-09-28**입니다.

machine-readable discovery/benchmark 상태는 `benchmarks/system-one-candidate-registry.json`, promotion target은 `benchmarks/operation-routing-production-targets.json`에서 관리합니다.

## 수용 규칙

| Integration 형태 | SchemaRouter 경로 | 일반적으로 core 변경 필요? |
|---|---|---:|
| Jev/System One-compatible HTTP API | `SystemOneDecisionBackend` | No |
| 공식 Laya Python runtime | `LayaDecisionBackend` | No |
| 일회성 Python experiment | `CallableDecisionBackend` / `--decision-callable` | No |
| 재사용 non-System-One Python runtime | decision backend plugin | No |
| `DecisionBackend`에 맞지 않는 새 semantic primitive | research-only adapter 우선 | 근거 확보 후 검토 |

## 현재 discovery matrix

Jev/TypeSafe는 hosted reference System One API이며 generic compatible path도 지원합니다. Laya는 direct Python backend와 compatible HTTP runtime 경로가 있습니다. Kev, Mapika decider, Decis, LiteVar System One, laya-serve는 compatible wire contract일 때 `SystemOneDecisionBackend`를 사용합니다.

OpenJev 계열은 서로 다른 repository/runtime을 별도 provider로 취급하고 정확한 revision/license를 고정해야 합니다. AnyJev, Bespoke Nimble, System One Open처럼 wire contract가 다르거나 연구 단계인 runtime은 plugin 또는 research callable을 우선합니다.

integration compatibility와 model promotion은 분리합니다. 새 모델은 repository/runtime/model revision 고정 → 기존 authority를 바꾸지 않는 연결 → frozen benchmark → routing/rejection/false-route/latency/error/authority violation 기록 → fresh-surface confirmation 순으로 검증합니다.

## Authority invariant

> 모델은 로컬에서 허가된 finite choice를 score/select/veto할 수 있지만 tool, endpoint, field, argument, policy 또는 execution authority를 만들 수 없습니다.

이 규칙은 hosted Jev, Laya, Kev, OpenJev, AnyJev와 향후 model에 동일하게 적용됩니다.

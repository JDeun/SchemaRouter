# Decision-model ecosystem intake

이 페이지는 model quality가 아니라 **integration shape**를 추적합니다. 목록에 있다는 이유만으로 project를 endorse/promote하지 않습니다.

마지막 검토: **2026-09-28**.

Machine-readable discovery/benchmark intake state는 `benchmarks/system-one-candidate-registry.json`에 있습니다. Candidate name을 planner logic에 hard-code하지 말고 model discovery를 registry에 유지합니다. Promotion target은 `benchmarks/operation-routing-production-targets.json`에 별도로 중앙화하며 registry는 discovery UX를 위해 이를 mirror하고 test가 두 파일의 drift를 거부합니다.

## Intake rule

새 model/runtime에 맞는 가장 좁은 stable boundary를 선택합니다.

| Integration shape | SchemaRouter path | Core change 필요? |
|---|---|---:|
| Jev/System One-compatible HTTP API | `SystemOneDecisionBackend` | No |
| Direct official Laya Python runtime | `LayaDecisionBackend` | No |
| One-off Python experiment | `CallableDecisionBackend` / `--decision-callable` | No |
| Reusable non-System-One Python runtime | `schemarouter.decision_backends` plugin | No |
| `DecisionBackend`에 맞지 않는 새 semantic primitive | research-only adapter 우선 | Evidence 이후 maybe |

## 현재 discovery matrix

Ecosystem은 빠르게 바뀌므로 benchmark 전 exact repository/model/runtime revision을 pin합니다.

### Jev / TypeSafe

Hosted reference System One API이며 기존 `JevDecisionBackend`, generic compatible `SystemOneDecisionBackend` path가 있습니다. Credentialed comparison 전용이며 CI requirement가 아닙니다.

### Laya

Open typed-decision model family입니다. Direct Python path는 `LayaDecisionBackend`이며 native runtime은 typed `choice`, `score`, `noul` primitive를 지원합니다. Compatible contract를 보존하는 community HTTP/ONNX runtime은 generic System One path를 사용할 수 있습니다.

Current v4 evidence는 tested direct full-catalog Laya choice와 pinned winner-only native `noul` veto를 reject하지만 모든 Laya checkpoint/runtime/primitive가 동일하다는 뜻은 아닙니다.

### Kev

Repository family: `jaredpalmer/kev`.

Jev/System One-compatible `/v1/systemone` server이며 0.8B/4B/9B/27B class의 open model size와 `choice`/`noul`/`score`를 지원합니다. SchemaRouter path는 `SystemOneDecisionBackend`입니다. Model size/revision은 integration-code가 아니라 benchmark variable입니다. Pinned Kev-0.8B `choice+noul` #299/PR #300은 active 1,800-row v4 screen입니다.

### Mapika decider

`Mapika/decider`는 Jev/System One-compatible runtime family이며 `SystemOneDecisionBackend`를 사용합니다. Benchmark 전 candidate model/runtime revision을 독립적으로 pin해야 하며 아직 SchemaRouter quality result는 없습니다.

### Decis

`chaitin/Decis`는 self-hosted Jev-compatible server로 하나의 `/v1/systemone` endpoint 뒤에 Laya/Kev 등 여러 engine을 제공합니다. SchemaRouter는 underlying model마다 class를 추가하지 않고 wire contract를 target해야 한다는 예입니다.

### LiteVar System One

`LiteVar/system-one`은 local-first cross-platform System One runtime이며 Jev-compatible API와 Laya를 초기 backend로 하는 model-independent runtime abstraction을 제공합니다. `SystemOneDecisionBackend`를 사용합니다.

### laya-serve

`stiermid/laya-serve`는 Laya용 Jev-compatible HTTP serving layer입니다. In-process Python runtime을 원하면 대신 direct `LayaDecisionBackend`를 사용합니다.

### OpenJev variants

서로 관련 없는 여러 project가 OpenJev 이름을 사용하므로 repository/runtime별 distinct provider로 취급하고 명시적으로 pin합니다. 현재 tracked entry는 `SiliconLabAI/OpenJev`입니다.

Observed discovery revision의 source repository는 MIT이지만 selected runtime의 backend/model license는 별도로 확인해야 합니다. 실제 compatible wire contract를 보존할 때만 `SystemOneDecisionBackend`를 사용하고 그렇지 않으면 plugin/callable을 사용합니다.

### AnyJev

`nokia-applied-research/AnyJev`는 causal LLM을 typed-decision/readout variant로 변환합니다. Runtime/readout support는 level/model마다 다릅니다. Stable System One-compatible server contract가 pin되기 전에는 third-party plugin 또는 research callable을 사용합니다.

#311/PR #313은 immutable BGE winner 뒤에 zero-label L0 content-free `noul` veto를 staging합니다. Research workflow는 guarded marker/manual activation 전에는 dormant이며 모든 preregistered Kev-based candidate가 non-promotable이 되기 전 marker 사용은 금지됩니다.

### Bespoke Nimble

`bespokelabsai/nimble`은 Jev-wire-compatible server가 아니라 typed candidate-scoring model/runtime입니다. Model/checkpoint calibration은 release-specific이며 runtime과 함께 pin해야 합니다. Current Bespoke-Nimble-9B model card는 Apache-2.0을 보고하지만 observed GitHub code repo에는 root LICENSE가 없으므로 code/model license를 각각 검증해야 합니다.

Plugin/research callable path를 사용하며 더 큰 memory/GPU 요구는 drop-in CPU comparison이 아니라 별도 runtime experiment로 다룹니다. 아직 quality result는 없습니다.

### System One Open

`mithalouni/system-one-open`은 distinct serving/runtime contract를 가진 open Jev-style typed-decision implementation입니다. Compatible wire endpoint가 검증되기 전에는 plugin/research callable을 사용하고 hosted demo를 reproducible evidence로 보기 전에 weight/runtime을 독립적으로 pin합니다.

### 기타 model/runtime

Alternative Laya ONNX/TypeScript runtime, decision head, distilled decision model, future typed-decision engine도 기본적으로 permanent core class를 받지 않고 같은 intake rule을 따릅니다.

## 새 model promotion workflow

1. repository/runtime/model revision pin
2. planning authority 변경 없이 System One/plugin/callable로 연결
3. frozen benchmark protocol 실행
4. exact-route, unsupported rejection, false-route rate, latency, error, authority violation 기록
5. fresh-surface confirmation 전 semantics freeze
6. independent evidence가 active quality gate를 통과할 때만 default/recommended profile 승격

Observed registry revision은 discovery provenance일 뿐입니다.

## Authority invariant

> Model은 finite locally authorized choice를 score/select/veto할 수 있지만 tool, endpoint, field, argument, policy, execution authority를 만들 수 없습니다.

Hosted Jev, Laya, Kev, OpenJev, AnyJev 및 future model 모두에 동일하게 적용됩니다.

# 연구 실험 인덱스

SchemaRouter 연구의 canonical experiment ledger와 주요 evidence를 찾기 위한 인덱스입니다. machine-readable ledger가 experiment count/status/source revision/run/artifact의 source of truth이며 문서의 숫자는 repository-facts automation으로 동기화합니다.

실험은 development/calibration, frozen holdout, fresh confirmation, diagnostic을 구분합니다. consumed holdout은 이후 model/threshold/rule 선택에 재사용하지 않으며 infrastructure-invalid run은 scientific negative result로 세지 않습니다.

0.14 주요 track은 B1/B2 agent utility, K3-vs-K5 structural gate, corrective re-retrieval #431, independent held-out #432, final-answer #424, output-field projection #506, successor runtime qualification #510입니다.

## 어떤 근거 문서를 봐야 하나

이 페이지는 특정 실험 결정의 provenance를 확인할 때 사용합니다. 일반적인 연구 현황 파악에는 아래의 더 작은 문서부터 보는 것이 좋습니다.

| 질문 | 시작 문서 |
| --- | --- |
| 현재 방어 가능한 연구 주장은 무엇인가? | [연구 현황](routing-status.md) |
| 논문에 사용할 수 있는 근거는 무엇인가? | [논문 근거 패키지](paper-evidence-package.md) |
| 현재 진행 중이거나 막힌 작업은 무엇인가? | [선행연구 로드맵](prior-art-roadmap.md)과 active research issue |
| 실패를 포함해 실제로 무엇을 시도했는가? | 이 전체 ledger |
| 아키텍처가 어떻게 변했는가? | [설계와 실험 이력](design-and-experiment-history.md) |

아래의 장기 실험 목록은 의도적으로 보존한 archive입니다. 과거 실패 후보는 재현성을 위해 남겨 두지만 제품 권장 설정을 의미하지 않습니다.


## Evidence-to-Action contract regression

Issue #1203 / PR #1204에서 별도의 deterministic execution-boundary 실험을 추가했습니다. 고정된 8개 case에서 vanilla, routing-only, typed evidence gate를 비교합니다. 이 baseline은 regression artifact이며 위 routing experiment count에 포함하지 않고 SafeActBench 재현으로도 취급하지 않습니다. 정본 설명과 한계는 [Evidence-to-Action 경계](evidence-to-action.md)와 `benchmarks/evidence-to-action-v1/`에 기록합니다.

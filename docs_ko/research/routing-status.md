# Routing 연구 상태

stable product는 이미 typed capability retrieval/execution boundary로 동작하며 routing research는 그 위의 독립 최적화 track입니다. 과거 operation-routing cycle은 fresh confirmation에서 promotion gate를 통과하지 못해 target candidate 없이 종료되었습니다.

0.14에서는 router 자체 exact accuracy만이 아니라 **agent utility**를 중심으로 봅니다. B1은 compact SR-5가 FULL보다 훨씬 작은 schema context에서 높은 task pass를 보였고, B2/held-out/corrective/final-answer 연구로 일반화를 확인 중입니다.

연구가 진행 중이라는 이유로 stable package를 experimental이라고 취급하지 않으며, 반대로 partial benchmark를 stable 성능 보장으로 홍보하지 않습니다.

## 외부 검증 현황

외부 비교는 maintainer-owned 제품 검증과 분리해서 관리합니다. 개발 fixture와 protocol 준비 자체는 **외부 검증 근거가 아닙니다**.

| Track | 현재 상태 | 근거 경계 |
| --- | --- | --- |
| SmartMCP (#1114) | native 개발 fixture/smoke 준비 완료, maintainer protocol 확인 대기 | upstream 합의 전 held-out freeze 금지 |
| Clear Your Tools (#839) | v2.17.6 native BM25 개발 smoke 통합 중 | 공개 개발 fixture만 사용, held-out 주장 없음 |
| Jev (#796) | 82-tool / 16-query frozen package를 upstream에 전달 | upstream 실행/검토 대기, post-freeze tuning 금지 |
| HYSET (#795) | 공개 코드 기반 fresh-retraining protocol 준비 | independently retrained HYSET으로만 표기, paper checkpoint 재현 주장 금지 |

부정적 결과나 무효과 결과도 그대로 공개 가능한 근거로 취급하며, held-out row를 보고 후보를 수정하지 않습니다.

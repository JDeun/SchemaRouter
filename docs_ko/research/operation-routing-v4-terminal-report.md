# Operation routing v4 최종 보고서

해당 routing cycle은 production-target candidate를 승격하지 않고 종료되었습니다. 가장 강한 executable DEV candidate는 85.07 / 99.31 / 100 / 0.62와 p95 176.94ms를 기록했지만, unchanged zero-overlap fresh confirmation에서는 84.81 / 90.45 / 100 / 8.49, p95 278.37ms로 promotion gate를 통과하지 못했습니다.

따라서 calibration/blind-final을 추가 소비하지 않았고 DEV 성능을 production guarantee로 재라벨하지 않았습니다. conservative #259 profile의 83.77% supported exact, 98.96% near-domain rejection, 0.93% false-route, 약 134.95ms p95도 참고 evidence일 뿐 target pass가 아닙니다.

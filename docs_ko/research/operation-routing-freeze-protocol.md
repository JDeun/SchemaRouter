# Operation routing freeze protocol

operation-routing 연구는 corpus, split, model/revision, threshold search 범위, metric, promotion gate를 결과 확인 전에 고정합니다. exact-route, near-domain unsupported rejection, OOD rejection, false-route, latency, authority/error를 함께 기록합니다.

standing target은 supported exact ≥85%, near-domain unsupported rejection ≥97%, OOD 100%, false route ≤1%, authority/execution error 0, executable p95 ≤250ms입니다. 단일 metric 개선으로 다른 중요한 축의 악화를 숨기지 않습니다.

fresh holdout은 한 번 소비하면 tuning에 재사용하지 않고 diagnostic rerun은 명확히 구분합니다.

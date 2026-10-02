# 연구 거버넌스

SchemaRouter 연구는 preregistration, frozen workload/split, immutable evidence, negative-result 보존을 기본 원칙으로 합니다. 결과를 본 뒤 promotion gate, threshold, corpus, metric definition을 바꾸지 않습니다.

DEV/calibration은 선택에 사용할 수 있지만 holdout/fresh confirmation은 한 번 소비되면 이후 tuning에 재사용하지 않습니다. infrastructure failure와 scientific failure를 분리하고 exact source SHA, workflow run, artifact digest를 가능한 한 기록합니다.

stable product claim과 experimental result를 분리합니다. 연구 성능이 좋아도 execution authority/security/public API boundary를 자동으로 바꾸지 않으며 product correctness/security defect가 발견된 경우에만 stable-core 재검토 근거가 됩니다.

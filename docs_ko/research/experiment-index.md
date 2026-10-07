# 연구 실험 인덱스

SchemaRouter 연구의 canonical experiment ledger와 주요 evidence를 찾기 위한 인덱스입니다. machine-readable ledger가 experiment count/status/source revision/run/artifact의 source of truth이며 문서의 숫자는 repository-facts automation으로 동기화합니다.

실험은 development/calibration, frozen holdout, fresh confirmation, diagnostic을 구분합니다. consumed holdout은 이후 model/threshold/rule 선택에 재사용하지 않으며 infrastructure-invalid run은 scientific negative result로 세지 않습니다.

0.14 주요 track은 B1/B2 agent utility, K3-vs-K5 structural gate, corrective re-retrieval #431, independent held-out #432, final-answer #424, output-field projection #506, successor runtime qualification #510입니다.

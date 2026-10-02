# 설계와 실험 이력

이 문서는 SchemaRouter 초기 설계부터 stable product와 research track이 분리되기까지의 의사결정과 실험을 보존합니다. 결과가 좋지 않았던 candidate와 consumed holdout도 삭제하거나 재해석하지 않습니다.

연구 방향은 단순 router accuracy에서 실제 agent utility로 확장되었습니다. 핵심 질문은 compact typed capability retrieval이 full catalog 대비 context/schema token을 줄이면서 required tool recall, task completion, unsupported rejection, final-answer fact/value/unit/provenance quality를 유지하는가입니다.

새 hypothesis는 새 versioned experiment로 관리하고 frozen corpus/split/gate는 결과 확인 후 수정하지 않습니다. product architecture는 stable-core boundary 뒤에 고정하고 research는 ranking/index/shortlist/corrective retrieval 같은 compatible 내부 선택을 평가합니다.

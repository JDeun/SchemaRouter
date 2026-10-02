# 선행 연구와 연구 로드맵

SchemaRouter 연구는 tool routing, semantic routing, retrieval-augmented tool selection, open-set/OOD rejection, corrective retrieval, reranking, agent tool-use evaluation을 선행 연구 축으로 봅니다.

차별점은 단순 classifier 정확도만이 아니라 provider/endpoint/field 수준 typed capability contract, compact model-visible context, unsupported rejection, local execution authority, downstream task/final-answer utility를 함께 평가하는 데 있습니다.

새 방법은 기존 open-source/router 연구에서 검증된 아이디어를 참고하되 SchemaRouter의 frozen benchmark와 authority invariant 안에서 비교합니다. prior art를 이유로 결과가 없는 method를 default로 넣지 않습니다.

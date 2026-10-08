# 선행 연구와 연구 로드맵

SchemaRouter 연구는 tool routing, semantic routing, retrieval-augmented tool selection, open-set/OOD rejection, corrective retrieval, reranking, agent tool-use evaluation을 선행 연구 축으로 봅니다.

차별점은 단순 classifier 정확도만이 아니라 provider/endpoint/field 수준 typed capability contract, compact model-visible context, unsupported rejection, local execution authority, downstream task/final-answer utility를 함께 평가하는 데 있습니다.

새 방법은 기존 open-source/router 연구에서 검증된 아이디어를 참고하되 SchemaRouter의 frozen benchmark와 authority invariant 안에서 비교합니다. prior art를 이유로 결과가 없는 method를 default로 넣지 않습니다.

## Evidence-to-Action / SafeActBench

Issue #1203과 PR #1204는 Lin et al., *From Evidence to Action: How Tool-Using Agents Fail* (arXiv:2610.07753)에서 직접 동기를 얻은 별도 execution-boundary 연구 track입니다. SafeActBench는 6개 operational domain, 656개 case, 5개 protocol을 provenance-bound Evidence Ledger와 deterministic trajectory evaluator로 평가합니다. SchemaRouter의 현재 8-case corpus는 deterministic contract regression일 뿐 SafeActBench 재현으로 계산하지 않습니다. 자세한 내용은 [Evidence-to-Action 경계](evidence-to-action.md)를 참고합니다.

다음 연구 단계는 공개 benchmark/evaluator를 사용한 외부 평가입니다. Multi-action dependency 평가를 이유로 SchemaRouter core에 일반 DAG orchestration을 넣지 않습니다.

# 최종 답변 품질 연구

#424는 routing 성공만으로 충분하지 않다는 가정에서 final answer의 fact, numeric value, unit, provenance 품질을 직접 평가합니다. 144 task로 구성되며 corrective re-retrieval #431과 independent held-out #432의 downstream evidence track입니다.

비교 조건은 retrieval/context 차이 외의 agent/model/runtime 조건을 가능한 한 고정해야 합니다. answer quality와 schema-token/context cost를 함께 보고, tool selection이 맞았더라도 최종 답이 틀리면 성공으로 세지 않습니다.

terminal artifact가 완성되기 전 partial result는 결론으로 사용하지 않습니다.

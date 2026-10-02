# Field projection과 답변 품질

output field를 더 공격적으로 줄이면 context는 작아지지만 downstream answer에 필요한 보조 field를 제거할 수 있습니다. 이 연구는 projection precision이 아니라 final answer fact/value/unit/provenance quality와 context cost의 trade-off를 측정합니다.

#506의 최초 DEV screen은 agent가 tool을 호출하지 않아 projection 조건 자체를 비교하지 못했으므로 **instrument failure**로 처리했습니다. 이를 scientific result로 해석하지 않고 successor runtime qualification #510을 통해 tool-use envelope를 먼저 검증합니다.

product default는 이 evidence가 충분해질 때까지 recall-first projection을 유지합니다.

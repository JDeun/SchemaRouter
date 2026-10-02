# Agent utility B1 결과

B1은 compact typed retrieval이 full tool-schema exposure보다 downstream agent utility를 보존하거나 개선하는지 확인한 canonical experiment입니다.

Qwen3-0.6B, 23 semantic task에서 FULL task pass는 **68.48%**, SR-5는 **91.30%**였습니다. SR-5/FULL schema-token ratio는 **5.42%**, required-route recall은 **100%**, unauthorized destructive execution은 **0**이었습니다.

이 결과는 해당 frozen workload/model 조건의 evidence이며 모든 model/catalog에 일반화된 production guarantee가 아닙니다. 이후 stronger-agent B2와 independent held-out/final-answer 연구로 일반화 여부를 별도로 검증합니다.

# Adaptive shortlist depth 연구

고정 Top-K 대신 query/capability 상태에 따라 shortlist 깊이를 조정해 context cost를 줄이면서 required-route recall과 downstream task utility를 보존할 수 있는지 평가합니다.

비교는 frozen workload에서 fixed K baseline과 adaptive rule을 같은 agent/runtime 조건으로 실행해야 합니다. shortlist가 작아져 token이 줄었다는 사실만으로 성공으로 보지 않고 task completion, required-route recall, unsupported handling, latency를 함께 봅니다. promotion rule은 결과를 보기 전에 고정하며 consumed holdout으로 threshold를 다시 조정하지 않습니다.

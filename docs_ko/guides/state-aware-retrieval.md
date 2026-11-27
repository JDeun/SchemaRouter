# 상태 인식 capability retrieval

개발 배포 패키지에서는 과거 Lexical Top-K 결과의 상태 적격성 필터링 API를 제거했습니다. 원 논문 Algorithm 1에 따른 계획은 호스트의 워크플로 상태를 근거로 재랭킹하거나 후보를 보충하지 않습니다.

호스트는 공통 타입 계약인 `TypedExecutionState`와 `evaluate_state_eligibility(requirements, state)`, `evaluate_preconditions(preconditions, state)`를 사용하여 명시적으로 선언된 상태 요구사항과 사전조건을 검사할 수 있습니다. 이 함수들은 후보를 선택하거나 실행 권한을 부여하지 않습니다.

## 고정 Top-K 적격성 검사

과거 고정 Top-K 비교 구현은 소스 체크아웃의 `scripts/research_legacy_planning/state_retrieval.py`에, 상태 조건부 backfill 비교 구현은 `scripts/research_legacy_state_backfill.py`에 보존합니다. 두 구현은 배포 패키지의 API나 원 논문 계획 경로의 fallback이 아닙니다.

기존 비교 구현은 이미 허용된 후보만 검사하며 숨겨진 경로를 노출하거나 워크플로 상태를 추론하지 않습니다. 누락되거나 호환되지 않는 명시적 요구사항은 fail-closed로 처리합니다. 워크플로 선택, 실행 승인, 상태 변경, 재시도 및 보상 결정은 호스트의 책임입니다. 제품의 등록된 실행 경계와 권한 검증은 그대로 유지됩니다.

## 과거 adaptive context 비교 실험

성공 이력 재랭킹과 세션별 스키마 노출 필터는 배포 패키지의 라우팅 API에서 제거되었습니다. 기존 비교 실험 구현과 회귀 테스트는 `scripts/research_legacy_adaptive_context.py` 및 `tests/test_adaptive_context.py`에 보존됩니다. 호스트의 컨텍스트 관리는 원 논문 기반 계획을 변경하지 않는 별도 기능입니다.

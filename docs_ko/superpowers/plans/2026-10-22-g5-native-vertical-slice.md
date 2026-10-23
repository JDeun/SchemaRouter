# G5 원본 소스 기반 수직 통합 구현 계획

> **에이전트 작업자 안내:** `superpowers:subagent-driven-development`(권장) 또는 `superpowers:executing-plans`를 사용하여 작업을 순서대로 구현합니다. 아래 체크박스는 실행 절차의 기록용입니다.

**목표:** 기존 호스트 선언 개념과 타입 기반 G5 검색을 연결해, 권한이 검증된 고정 K 에이전트에 원본 경로 집합을 제공하고 기존 평가기로 실제 과제 완료 여부를 측정합니다.

**구조:** `resolve_native_concepts`, 현재 요청자 범위의 직접 FieldGroup 검색, 같은 버전의 `NativeSchemaGraphIndex.lookup`을 조합합니다. 두 번째 그래프·에이전트 루프·실행기를 만들지 않습니다. 기존 고정 5개 도구 평가기에 명시적 opt-in 어댑터를 추가하고 제한된 Open-Meteo E1 비교 부문 하나를 만듭니다. 실제 소스나 로컬 모델을 사용할 수 없을 때는 성공이라고 처리하지 않고 명시적으로 차단합니다.

**기술:** Python 3.10 이상, Pydantic v2, pytest, Ruff, Pyright, 기존 SchemaRouter 레지스트리·정책·원본 OpenAPI/MCP 어댑터, 기존 Open-Meteo `httpx` 및 로컬 Qwen E1 기능.

**설계:** `docs/superpowers/specs/2026-10-22-g5-native-vertical-slice-design.md`

## 전체 제약 사항

- 안정적인 `SchemaRouter.retrieve_authorized` 및 동결된 #432/FULL/SR-5 모델 경로의 동작은 변경하지 않습니다. 제품 기본값, 릴리스·태그, PR #1356을 변경하지 않습니다.
- 명시적 `PrincipalContext`, 원본 소유자가 검토한 `NativeConceptCatalog`, 원본 소스·엔드포인트 fingerprint, 같은 버전의 `NativeSchemaGraphIndex`를 요구합니다. **노출되는 고유 경로 개수의 K는 정확히 5**입니다.
- 별칭·출력 필드·연결 인자·입력값·권한·실행 권한을 추론하여 만들지 않습니다. 등록된 소스와 로컬 호스트가 최종 권한을 가집니다.
- 완전한 직접 단일 엔드포인트를 완전한 한 홉보다 우선할 수 있습니다. 불완전한 필드 집합이나 K 초과 후보의 임의 절단을 허용하지 않습니다.
- 후보 계산 전후와 에이전트에 공개하기 직전에 정책·데이터 범위·가용성·원본 ID를 재확인합니다. 숨겨진 경로·필드 이름이나 개수를 노출하지 않습니다.
- 원본 소스에서 실제 실행한 최종 과제 성공 점수와 E0 고정 fixture를 분리합니다. 개발자가 작성한 공개 E1은 독립 E2가 아닙니다. #1346은 `BLOCKED_EXTERNAL`을 유지합니다.
- **원본 소스 선행 조건:** 현재 Open-Meteo E1의 `ToolSpec`에는 `license`, 타입이 선언된 출력 `semantic_id`, 입증된 위도·경도 생산자→날씨 입력 G5 엣지가 없습니다. 원본 빌더에는 G5에 필요한 명시적 `AuthorizationPolicy`도 없습니다. `NativeSchemaGraphIndex`는 이를 의도적으로 거부합니다. 점수를 높이기 위해 소스 모델이나 권한을 임의 채우지 말고, 소유자가 검토한 정확한 버전의 메타데이터·정책·사용 허가를 먼저 확보합니다. 그렇지 않으면 `BLOCKED_SOURCE_SEMANTICS`를 기록합니다.
- 새 에이전트 실행기·라우팅 DB·독립적인 미세 벤치마크·모델 프롬프트는 추가하지 않고 기존 읽기 전용 유틸리티를 재사용합니다.
- 수직 통합 전체를 하나의 기능 브랜치/PR로 취급하고 관련 없는 최적화보다 사용자 기능 및 대응 과제 결과를 먼저 기록합니다.

## 리뷰 중점: 높은 위험의 다섯 입력

1. 타입 입력 두 개가 필요한 **불완전한 한 홉 연결**을 실행 가능 경로로 노출하지 않습니다(작업 1 `test_reject_partial_native_join`).
2. 중첩/ref 출력의 숨긴 레이블이 도구 스키마를 거쳐 모델에 전달되지 않습니다(작업 2 `test_graph_view_redacts_nested_hidden_metadata`).
3. 기존 뷰를 받은 후 정책이 제자리 변경되면 다음 모델 턴 전에 실패합니다(작업 2 `test_graph_selector_rejects_policy_content_drift`).
4. FULL과 G5 비교 사이에 실시간 소스가 바뀌면 성능 향상 대신 비교 불가/차단으로 분류합니다(작업 3 `test_paired_native_graph_source_drift_is_not_scored`).
5. 예전 일회성 마일스톤 초기화 Blob SHA를 재지정하거나 새로운 자동 Issues 쓰기 작업을 만들지 않습니다(작업 4 `test_live_assignment_addendum_preserves_initialization_blob_guard`).

---

## 파일 및 인터페이스

| 책임 | 파일 | 처리 |
| --- | --- | --- |
| 권한 범위 안에서 실행하지 않는 개념→직접/한 홉 구성 | `src/schemarouter/concept_graph_retrieval.py` | 새 파일; 기존 정규 그래프 로직은 변경하지 않음 |
| 명시적 opt-in 공개 import | `src/schemarouter/__init__.py` | 새 결과·구성 함수만 내보냄 |
| 구성 함수와 권한 경계 검증 | `tests/test_native_concept_graph_vertical_slice.py` | 새 파일 |
| 기존 평가기 연결 | `scripts/research_authorized_concept_fixed5_agent_bridge.py` | 이전 선택기와 평가 부문 유지 |
| 고정 K 어댑터 검증 | `tests/test_research_authorized_concept_graph_fixed5_bridge.py` | 새 파일 |
| 실제 원본 Open-Meteo E1 | `scripts/research_real_qwen_open_meteo_two_hop_e1.py` | 명시적 `concept_graph_optin`만 추가하고 기본값 유지 |
| E1 비교와 안전한 결과 | `tests/test_research_real_qwen_concept_graph_e1.py` | 새 파일 |
| 문서와 실시간 마일스톤 | `docs/research/research-program-2026.md`, `.github/RESEARCH_MILESTONES.md`, `tests/test_research_milestones.py` | 실제 차단·진척을 기술하며 초기화 매니페스트는 재지정하지 않음 |

### 작업 1: 소스 버전이 고정된 직접/한 홉 개념 그래프 결과

**파일:** `src/schemarouter/concept_graph_retrieval.py` 신규, `src/schemarouter/__init__.py` 수정, `tests/test_native_concept_graph_vertical_slice.py` 신규.

**소비 인터페이스:** `resolve_native_concepts(query, catalog=...)`, `retrieve_authorized_field_group(router, query, principal=..., group=..., k=5)`, `NativeSchemaGraphIndex.lookup(router, query, principal=..., group=..., k=5)` 및 기존 소스·권한 증거 검증.

**제공 인터페이스:**

- `NativeConceptRouteSet(route_ids: tuple[str, ...], route_fingerprints: tuple[tuple[str, str, str], ...], required_semantic_ids: tuple[str, ...], parameter_bindings: tuple[tuple[str, str], ...] = ())` 불변 데이터 클래스. fingerprint 삼중항은 `(route_id, tool_fp, endpoint_fp)`입니다.
- `NativeConceptGraphSelection(status: Literal["complete", "no_proven_hit", "over_k_unranked", "budget_unsatisfied"], snapshot_id: str, registry_version: int, requested_k: int, route_sets: tuple[NativeConceptRouteSet, ...], route_ids: tuple[str, ...], independent_quality_evidence: bool = False, calibrated_no_fit: bool = False, executable_authority: bool = False)` 불변 데이터 클래스.
- `retrieve_authorized_concept_graph(router: SchemaRouter, query: str, *, principal: PrincipalContext, catalog: NativeConceptCatalog, index: NativeSchemaGraphIndex, k: int = 5) -> NativeConceptGraphSelection`.

- [ ] **1. RED:** `tests/test_native_field_group_retrieval.py`와 `tests/test_native_graph_multi_input.py`의 fixture를 재사용해 `test_direct_complete_fieldgroup_precedes_partial_siblings`, `test_authorized_one_hop_preserves_route_ids_and_join_bindings`, `test_reject_partial_native_join` 작성. 직접 A+B의 `route_ids == ("complete.read",)` 및 한 홉의 모든 원본 경로·필수 바인딩·`executable_authority is False`를 검증. A 전용/B 전용 형제, 타입·단위·출처·라이선스 불일치, 두 번째 입력 누락은 실패해야 합니다.
- [ ] **2. RED 실행:** `python -m pytest tests/test_native_concept_graph_vertical_slice.py -k 'direct_complete or authorized_one_hop or reject_partial' -q`. 예상: fixture·import 환경 오류가 아니라 구성 함수가 없어 실패.
- [ ] **3. 최소 구성 구현:** 현재 호스트 카탈로그에서만 개념 해석; 같은 요청자·정책·레지스트리 스냅샷에서 기존 완전한 직접/한 홉 검색 호출. 원본의 범위 밖 도구를 탐색하거나 연결을 만들지 않음. 완전한 직접 경로 우선; 고유 노출 경로 ≤5만 `complete`. 독립 검증된 순위가 없이 K 초과 시 빈 경로의 `over_k_unranked`, 권한 있는 결과가 없으면 빈 경로의 `no_proven_hit`. `budget_unsatisfied`는 후속 모델 공개 예산 검사용으로 남김. 카탈로그 버전, 인덱스 출처, 권한 증거를 재검증.
- [ ] **4. GREEN:** 2단계 명령을 다시 실행하고 모두 통과 확인.
- [ ] **5. 부정 테스트 작성:** `test_graph_over_k_shared_root_is_not_arbitrary_top5`, `test_graph_denied_and_hidden_routes_leave_no_public_metadata`, `test_graph_changed_registry_or_policy_fails_closed`, `test_graph_owner_catalog_mutation_refused`, `test_graph_ko_ja_en_aliases_produce_same_typed_paths`, `test_graph_k_must_equal_five`.
- [ ] **6. RED:** `python -m pytest tests/test_native_concept_graph_vertical_slice.py -q`. 새로 추가한 보호 동작 테스트는 올바른 이유로 실패하고 기존 양성 테스트는 통과해야 함.
- [ ] **7. 최소 가드:** 후보 선택 전 P0에서 보이는 도구·필드만 투영, 정확한 K와 현재 소스·권한 확인, 숨긴 데이터를 직렬화하거나 미검증 순위를 사용하지 않음.
- [ ] **8. 회귀 검증:** `python -m pytest tests/test_native_field_group_retrieval.py tests/test_native_graph_index.py tests/test_native_graph_multi_input.py tests/test_native_concept_graph_vertical_slice.py -q` — 실패 0개.
- [ ] **9. 커밋:** 관련 세 파일을 추가하고 `feat: compose authorized native concepts with G5 routes` 메시지 사용.

### 작업 2: 기존 요청자별 에이전트 공개 인터페이스에 연결

**파일:** `scripts/research_authorized_concept_fixed5_agent_bridge.py` 수정, `tests/test_research_authorized_concept_graph_fixed5_bridge.py` 신규.

**소비 인터페이스:** 작업 1 결과, `AuthorizedAgentToolSurface`, `_visible_fingerprints`, `EXPERIMENTAL_FIXED5_CONDITION`, 기존 `(query: str, visible_route_ids: tuple[str, ...]) -> list[str]` 콜백.

**제공 인터페이스:** `AuthorizedConceptGraphFixed5Selector(view: AuthorizedAgentToolSurface, catalog: NativeConceptCatalog, index: NativeSchemaGraphIndex)`, `last_status: str | None` 및 세 품질·권한 플래그 모두 `False`.

- [ ] **1. RED 통합 테스트:** `test_graph_selector_passes_two_routes_to_existing_agent`, `test_graph_view_redacts_nested_hidden_metadata`, `test_graph_selector_rejects_policy_content_drift`, `test_graph_selector_rejects_schema_fingerprint_drift`, `test_graph_selector_rejects_over_k_or_byte_budget`, `test_graph_selector_no_gold_or_execution_access`. 기존 테스트의 스냅샷과 `run_generated_episode` 패턴을 사용. 모델에는 선언·권한·출처 가시성이 검증된 경로만 노출, 숨긴 이름 없음, 선택 단계 호스트 호출 없음, 미지원/초과 상태는 `[]`.
- [ ] **2. RED 실행:** `python -m pytest tests/test_research_authorized_concept_graph_fixed5_bridge.py -q` — fixture 준비 후 새 선택기 import 실패 예상.
- [ ] **3. 선택기 최소 구현:** 기존 `AuthorizedConceptFixed5Selector`와 과거 동작을 보존. 카탈로그 digest, 질의·뷰 일치, HMAC 범위의 receipt, 경로 fingerprint·후보 제한을 재사용. 두 경로의 완전성, `view.visible_route_ids` 포함 여부, K5, `view.tool_definitions(route_ids)` 직렬화 바이트 예산을 검증. 예산 실패는 `budget_unsatisfied`와 `[]`; 정책·fingerprint·뷰 변경은 `PolicyViolationError`. gold·fixture·모델 출력·invoker를 전달하지 않음.
- [ ] **4. GREEN 및 회귀:** `python -m pytest tests/test_research_authorized_concept_graph_fixed5_bridge.py tests/test_research_authorized_concept_fixed5_agent_bridge.py tests/test_integrated_fixed5_agent_selector.py tests/test_research_authorized_agent_tool_surface.py -q` — 실패 0개.
- [ ] **5. 커밋:** 두 파일을 추가하고 `feat: expose source-checked G5 route sets to existing fixed5 agent` 사용.

### 작업 3: 명시적 부정 결과를 포함하는 실제 소스 에이전트 실험

**파일:** `scripts/research_real_qwen_open_meteo_two_hop_e1.py` 수정, `tests/test_research_real_qwen_concept_graph_e1.py` 신규.

**소비 인터페이스:** 작업 2의 범위가 고정된 그래프 선택, 기존 `evaluate_one(agent, client, *, language, city, country, menu_mode="all_visible", transport_retry_budget=0, evidence_reprompt_budget=0)`, 원본 Open-Meteo 호스트, 엄격한 두 호출 인자 바인딩, `_matches_weather_final`.

**제공 인터페이스:** `evaluate_one`의 opt-in `menu_mode="concept_graph_optin"`, 동일 모듈의 `compare_graph_native_e1(agent: Any, client: httpx.AsyncClient) -> dict[str, Any]`. 비교 부문은 `all_visible`(원본 FULL), `lexical_k5`(현재 `router.retrieve_authorized`), `concept_graph_optin`(작업 2 선택기). 기존 `evaluate`/`real_cpu_run` 기본값과 출력은 유지합니다. 두 작업만 노출하는 Open-Meteo에서 K5 자체의 FULL 대비 컨텍스트 비용 절감은 입증할 수 없으므로, 이 E1은 **실제 두 단계 정답성·실패 원인**을 평가합니다.

- [ ] **1. RED 제어 호스트 테스트:** `test_graph_e1_requires_verified_geocoding_before_weather`, `test_graph_e1_scoped_selection_never_calls_host`, `test_paired_native_graph_source_drift_is_not_scored`, `test_graph_e1_false_final_not_scored_as_pass`, `test_graph_e1_en_ko_ja_same_source_and_k`, `test_legacy_e1_output_unchanged`, `test_unattested_live_open_meteo_g5_never_fabricates_join`. 기존 `httpx` 가짜 전송과 에이전트 fixture를 재사용하며 단위 테스트에서 실시간 네트워크·모델 다운로드를 허용하지 않음. 현 빌더는 라이선스·타입 필드·정책·승인 시작 경로 없이는 `BLOCKED_SOURCE_SEMANTICS`여야 함. 부문 사이 소스·정책 변경은 비교 불가, 호출 시도·검증 성공을 별도 집계, 실제 두 호출과 최종 사실 검증 후에만 성공 부여.
- [ ] **2. RED:** `python -m pytest tests/test_research_real_qwen_concept_graph_e1.py -q` — 기존 테스트 import는 성공하고 새 부문이 없어 실패해야 함.
- [ ] **3. opt-in E1 최소 구현:** 라이선스, semantic ID, 생산자 좌표→날씨 입력, 명시적 G5 권한 정책, 승인된 geocoding 시작 경로가 현재 원본 소스에 없는 상황을 먼저 검사합니다. Open-Meteo의 [사용 조건](https://open-meteo.com/en/terms)과 실제 스키마를 별도로 검증하고 공개 엔드포인트라는 이유만으로 상업적 사용권을 추론하지 않습니다. 소유자 승인 보강은 원본 이름·값·fingerprint와 `HostSemanticAttestation`을 지켜야 하며 과제 정답과 분리합니다. 적격한 소스일 때만 신뢰된 도시·국가·언어 입력과 위도·경도 바인딩을 사용합니다. 현재 버전의 그래프 검색과 모델 턴별 범위 가시성을 교차 검증합니다. 부적격하면 모델을 호출하거나 성능 백분율을 생성하지 않고 차단합니다. 기존 호출·범위 투영·파싱·재시도·최종 사실 점수를 유지합니다. 부문 순서 교대, 소스 변경 비교 불가, 정답을 통한 K 보충 금지. 외부 공개 지표는 언어, 조건, 소스 버전, 검증된 호출 수, 과제 통과, 안전한 실패 단계, 측정된 토큰·CPU·시간만 사용하며 비밀·질의·도구 응답은 보관하지 않음.
- [ ] **4. GREEN:** `python -m pytest tests/test_research_real_qwen_concept_graph_e1.py tests/test_research_real_qwen_open_meteo_two_hop_e1.py tests/test_research_paired_agent_fixed5_e0.py -q` — 기존 동작 포함 실패 0개.
- [ ] **5. E1 실행 조건:** 버전 고정 모델·독립 승인 소스 의미 계약·사용 허가가 모두 있을 때만 `python -m scripts.research_real_qwen_open_meteo_two_hop_e1 --out /tmp/schemarouter-native-g5-e1.json` 및 새로운 opt-in 비교 플래그 사용. 원본 과제·모델/소스 SHA와 민감 정보 제거된 결과를 보존. 성공/실패 기록 또는 `BLOCKED_SOURCE_SEMANTICS`·`BLOCKED_MODEL_RUNTIME`·`SOURCE_FAILURE` 중 실제 이유를 남김. E0 fixture를 E1로 부르거나 0토큰을 조작하거나 차단을 0% 성공률로 해석하지 않음.
- [ ] **6. 커밋:** 관련 파일을 추가하고 `test: measure opt-in G5 against real native agent task completion` 사용.

### 작업 4: 문서·마일스톤·적격성 결정

**파일:** `docs/research/research-program-2026.md`, `.github/RESEARCH_MILESTONES.md` 수정, `tests/test_research_milestones.py` 확인.

**소비 인터페이스:** 작업 1~3의 opt-in API, 실제 E1 결과 또는 차단 상태, 검증된 GitHub 배정 #1700→M1/#1711→M5.

**결과:** 실제 사용법·부정 결과를 문서화하고 릴리스 게이트나 Issues 워크플로 동작은 변경하지 않음.

- [ ] **1. RED 문서·마일스톤 테스트:** `test_live_assignment_addendum_preserves_initialization_blob_guard`로 최신 배정과 기존 30건의 **역사적인 일회성 초기화 스냅샷** 설명을 확인. `test_exact_source_blob_gates_one_time_main_push_initialization`의 원래 Blob·자동 쓰기 보호 유지.
- [ ] **2. RED:** `python -m pytest tests/test_research_milestones.py -k 'live_assignment_addendum' -q` — 새 주석이 없어 실패 예상.
- [ ] **3. 실제 기능 문서화:** 한/영/일 개념→FieldGroup→fixed5 읽기 전용 예시, 직접/한 홉, 거부·K 초과, 소스·호스트 책임, 정확한 E1 차단/측정, 상위 이슈 링크를 `docs/research/research-program-2026.md`에 작성. `.github/RESEARCH_MILESTONES.md`에 배정 추가. **`.github/research-milestones.json` 및 고정된 `3df25049...` 초기화/자동 동기화 정책은 변경 금지.** 미래의 기계 판독형 초기화 수정은 별도 검토와 버전 이관이 필요합니다.
- [ ] **4. 검증:** `python -m pytest tests/test_research_milestones.py -q`, `python .github/scripts/sync_research_milestones.py`(읽기 전용 미리 보기) — 실패·네트워크·Issues 쓰기 0개.
- [ ] **5. 저장소 검사:** `python -m pytest tests/test_native_concept_graph_vertical_slice.py tests/test_research_authorized_concept_graph_fixed5_bridge.py tests/test_research_real_qwen_concept_graph_e1.py tests/test_research_milestones.py -q`; 주요 수정 파일의 `ruff check`, `pyright`, `git diff --check`. 환경상 없는 검사 도구는 성공이라고 주장하지 않고 제한을 명시합니다.
- [ ] **6. 커밋:** 관련 세 파일과 `docs: record G5 end-to-end evidence and live milestone state` 사용.

## 최종 판단 및 브랜치 인계

1. PR 전에 설계의 보안·원본 ID·완전한 필드 집합·최종 과제 지표와 브랜치 전체를 검토합니다. 채택한 구현 절차의 코드 리뷰를 수행합니다.
2. 완성된 코드 PR에는 테스트 명령과 실제 출력, 과제별 E1 결과 또는 정확한 차단 조건, 미지원·숨김 범위 부정 사례, 측정된 경우 CPU 비용을 적습니다. E0 통과만으로 E2·기본값 적용·#1535/#1560/#1477 종료를 선언하지 않습니다.
3. 실행이 차단되어도 유효한 opt-in 기능과 정확한 부정·차단 증거를 보존합니다. 승인받지 않은 새로운 E0 최적화 작업을 시작하지 않습니다.
4. **E2 상태:** #1346 독립 E2는 차단 유지, #1356 릴리스 HARD HOLD 유지, CodeGraph #1711은 M5 유지. 릴리스·태그·이슈 종료·보호된 CI 우회는 이 계획에 포함되지 않습니다.

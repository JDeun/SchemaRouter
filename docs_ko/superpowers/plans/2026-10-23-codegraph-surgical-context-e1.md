# CodeGraph 방식 선택적 G5 E1 구현 계획

> **에이전트 작업자 필수 지침:** 작업별 구현에는 `superpowers:subagent-driven-development`(권장) 또는 `superpowers:executing-plans`를 사용합니다. 진행 단계는 체크박스(`- [ ]`)로 추적합니다.

**목표:** 출처가 검증된 G5의 참조 전용 E0 결과를 연구 전용 E1에서 **모델이 원본 스키마 공개를 요청하고, 호스트가 권한을 다시 검증한 뒤, 기존 읽기 전용 실행기로 호출하는** 흐름으로 완성합니다. 실제 작업 성공률과 모든 모델 비용을 FULL, lexical SR-5, typed G5 조건과 비교합니다.

**아키텍처:** 선택에는 기존 `retrieve_authorized_concept_graph`, 주체별 공개 권한에는 `capture_authorized_agent_tool_surface`, 원본 실행에는 `execute_scoped_host_call`만 사용합니다. 연구 전용 지연 스키마 실체화와 에이전트 프로토콜 어댑터를 추가하고, 원본 Open-Meteo 및 10개 이상 경로를 가진 로컬 원본 출처 집단에서 네 조건을 분리 비교합니다. 별도 레지스트리·실행 권한·제품 기본값은 만들지 않습니다.

**기술:** Python >=3.10, 현재 `schemarouter`의 Pydantic v2 레지스트리·정책·원본 G5 인덱스·`RegistryExecutor`, 기존 Qwen 모델 에이전트, `httpx` Open-Meteo E1 실험기, pytest, Ruff, Pyright, 영문/국문 MkDocs.

**설계 원문:** `docs/superpowers/specs/2026-10-23-codegraph-surgical-context-e1-design.md`

**추적:** [#1711](https://github.com/JDeun/SchemaRouter/issues/1711), M5. 선행 [#1714](https://github.com/JDeun/SchemaRouter/pull/1714), [#1715](https://github.com/JDeun/SchemaRouter/pull/1715). 설계 검토와 본 구현 계획의 검토는 별개입니다. 계획 검토 후 기존 **A안(직접 순차 구현)**으로 작업하며 하위 에이전트에 위임하지 않습니다.

## 전체 제약조건

- 명시적으로 선택하는 연구 전용 기능이며 `SchemaRouter.retrieve_authorized`, 표준 에이전트 도구 목록, 제품 정책 기본값, 실행 API를 변경하지 않습니다. #432의 기존 FULL/SR-5 결과도 수정하지 않습니다.
- 서로 다른 원본 경로에 엄격히 `k=5`를 적용하고 G5 `complete` 경로만 사용합니다. 임의 축소·K 확대·추측한 형식 바인딩·가공 스키마·대체 실행기를 금지합니다.
- 경로 참조, 도구 정의, 스키마 실체화 결과는 **실행 허가가 아닙니다**. 선택·공개·모델 응답 처리·원본 실행마다 등록 출처 증거, 정책 **내용** 해시, 정규화된 주체 정보, 경로·도구·엔드포인트 지문, 공개 가능한 필드, 모든 생산자 출력→소비자 입력 바인딩을 재검사합니다. 실패 시 원본 목록을 누설하지 않는 동일한 차단 응답을 사용합니다.
- 처음 모델에 제공하는 도구는 고정된 `research__request_scoped_source_schema` 호스트 작업 하나뿐입니다. 검증된 요청 전에는 **실행 가능한 원본 도구 스키마를 하나도 공개하지 않습니다**. 이 예약 작업은 연구 실험기에서만 처리하고 제공자 경로로 등록하거나 `execute_scoped_host_call`에 전달하지 않습니다.
- 원본 스키마는 `AuthorizedAgentToolSurface.tool_definitions`로만 공개합니다. 관측치는 기존 공개 스칼라 투영기, 원본 호출은 `execute_scoped_host_call`을 재사용합니다. 비공개 모델 대화, 개인 인수, 인증정보, 원시 제공자 응답, 숨겨진 정책·HMAC 비밀은 저장하지 않습니다.
- 네 조건의 작업·모델/리비전·출처 계약·언어·주체·K·시도/턴 예산을 동일하게 유지합니다. 모델 생성의 모든 턴과 스키마 요청을 측정하고 실제 토큰 정보가 없으면 `0`이 아닌 `null`로 표시합니다. E0의 UTF-8 바이트에서 금전적 절감 효과를 추정하지 않습니다.
- Open-Meteo 무료 API는 비상업 연구에 한정하며, 오픈소스의 상업 사용자가 자동으로 사용권을 얻는다고 설명하지 않습니다. 집단 B는 `E1_LOCAL_SOURCE_CONTROL`로 표시하며 원격 원본 제공자 성과나 독립 E2라고 주장하지 않습니다.
- 모델 런타임, 출처 이용권, 의미 계약, 원본 HTTP 연결이 준비되지 않으면 정확한 차단/비교 불가 결과와 **`null` 성공률 분모**를 남깁니다. #1346 E2는 별도 차단 상태, #1356 출시는 HARD HOLD입니다. 자동 병합·출시·이슈 종료는 하지 않습니다.

## 검토 집중 항목

실수하기 쉬운 다섯 입력 사례와 이를 검증할 소유 테스트입니다.

1. **조작·중복·미선택·와일드카드 경로 ID**로 요청해도 원본 스키마나 실행 권한이 노출되지 않아야 합니다(작업 1: `test_materializer_rejects_unselected_duplicate_and_wildcard_ids`).
2. 레지스트리 버전은 같지만 선택 이후 정책의 **중첩 규칙 내용이 제자리에서 변경**되면 공개와 호출을 모두 차단해야 합니다(작업 1: `test_materializer_rejects_in_place_policy_drift`).
3. 두 번째 경로 호출 전 **생산자의 식별자 출력이 숨겨지거나 주체 정보가 바뀐 경우** 소비자 스키마 및 호출이 중단되어야 합니다(작업 2: `test_agent_aborts_hidden_binding_or_principal_swap_before_consumer`).
4. **불완전·잘못된 메타 작업 JSON 또는 반복 스키마 요청**을 원본 호출로 오해하거나 무제한 공개해서는 안 됩니다(작업 2: `test_agent_rejects_malformed_or_repeated_schema_requests_without_source_call`).
5. 비교 조건 사이 **제공자 버전·전송 장애**가 발생한 경우 출처 실패를 성공·0원 성과로 계산해서는 안 됩니다(작업 3: `test_four_arm_source_failure_has_null_denominator_and_tokens`).

---

## 파일·인터페이스 대응표

| 역할 | 정확한 경로 | 작업 범위 |
| --- | --- | --- |
| 출처 검증 G5 선택 및 E0 비교 | `scripts/research_codegraph_surgical_context_e0.py` | 재사용, 발표한 E0 수치 미변경 |
| 연구 전용 선택 경로 스키마 실체화 | `scripts/research_codegraph_scoped_materializer.py` | `capture_surgical_episode`, `request_scoped_source_schema` 추가 |
| 권한·변경·K5 보안 테스트 | `tests/test_research_codegraph_scoped_materializer.py` | 신규 |
| 모델/호스트 프로토콜 | `scripts/research_codegraph_surgical_agent_e1.py` | `run_surgical_model_episode` 신규, 예약 메타 작업만 처리 |
| 에이전트 프로토콜·호스트 콜백 테스트 | `tests/test_research_codegraph_surgical_agent_e1.py` | 신규 |
| 원본 출처 네 조건 평가기 | `scripts/research_real_qwen_open_meteo_two_hop_e1.py` | 선택적 비교 추가, 기존 `evaluate_one` 기본값 유지 |
| 실제 모델 비교 테스트 | `tests/test_research_real_qwen_codegraph_surgical_e1.py` | 신규 |
| 원본으로 등록한 결정적 10개 이상 경로 | `scripts/research_codegraph_local_multiroute_e1.py` | 출처와 통합 비교 실행기 추가 |
| 로컬 실행·경로·비용 검증 | `tests/test_research_codegraph_local_multiroute_e1.py` | 신규 |
| E1 결과·출처·상업 이용 조건 | `docs/research/codegraph-surgical-context-e1.md`, `docs_ko/research/codegraph-surgical-context-e1.md` | 실제 시도 후 결과 또는 정확한 차단 사유 기록 |
| 양국어 탐색·메타데이터·직접 검토 | `mkdocs.yml`, `mkdocs.ko.yml`, `docs_ko/translation-manifest.json`, `audits/ko-direct-semantic-spotcheck-2026-10-12.json` | 마지막 문서 작업에서 갱신 |

### 작업 1: 실패 시 차단하는 선택 경로 전용 원본 스키마 실체화

**인터페이스:** `capture_surgical_episode(router, query, *, principal: PrincipalContext, catalog: NativeConceptCatalog, index: NativeSchemaGraphIndex, k: int = 5) -> SurgicalEpisode`는 호스트 내부에서 출처·정책·주체 증거와 G5 선택을 고정합니다. `request_scoped_source_schema(episode: SurgicalEpisode, selected_route_ids: list[str]) -> list[dict[str, Any]]`는 긍정적으로 선택된 경로의 **중복 없는 비어 있지 않은 부분집합**에 대해서만 현재 원본 스키마를 반환합니다. 모델에 전달할 참조는 비민감하고, 실체화 전 `tool_call_ready=False`입니다. 저장된 참조나 스키마는 호출 허가가 아니며, 호출자는 새로 검증된 원본 뷰를 기존 실행기에 제공해야 합니다.

- [ ] **1단계 — 실패 테스트 작성:** `test_valid_two_route_subset_returns_only_current_original_definitions`, `test_materializer_rejects_unselected_duplicate_and_wildcard_ids`, `test_materializer_rejects_in_place_policy_drift`, `test_materializer_rejects_registry_source_and_principal_drift`, `test_no_fit_denied_and_six_route_over_k_have_no_schema_disclosure`, `test_hidden_required_producer_field_prevents_disclosure`를 추가합니다. 기존 `tests/test_research_codegraph_surgical_context_e0.py`의 출처·정책·`DataScopeRule` 테스트 패턴을 재사용하고 원본 콜백 호출이 0임을 확인합니다.
- [ ] **2단계 — RED 실행:** `python -m pytest tests/test_research_codegraph_scoped_materializer.py -q` — 누락 기능 때문에 실패해야 하며 환경 오류가 아니어야 합니다.
- [ ] **3단계 — 최소 구현:** `retrieve_authorized_concept_graph(..., k=5)`와 새 `AuthorizedAgentToolSurface`를 이용해 `_retrieval_authority_witness`, `_authorization_policy_receipt`, `_principal_claims_canonical`, 경로 지문·보이는 필드·바인딩을 확인하고 `tool_definitions(subset, k=5)` 호출 전후에 다시 검증합니다. 낡거나 불완전하거나 K 초과·미선택인 참조는 동일하게 차단합니다. 숨겨진 경로 수나 HMAC 내용을 노출하지 않습니다.
- [ ] **4단계 — GREEN 실행:** `python -m pytest tests/test_research_codegraph_scoped_materializer.py tests/test_research_codegraph_surgical_context_e0.py tests/test_research_authorized_agent_tool_surface.py -q` — E0 결과를 유지하며 통과해야 합니다.
- [ ] **5단계 — 커밋:** 실체화 코드와 테스트만 스테이징하고 `git commit -m "feat(research): guard on-demand G5 original schema materialization"`.

### 작업 2: 모델의 스키마 요청에서 기존 권한 검증 원본 호출까지

**인터페이스:** `run_surgical_model_episode(agent, *, episode, host_context, max_turns=...) -> SanitizedEpisodeResult`. 기존 `LocalQwenAgent.generate(messages, tools)` 및 `parse_one_model_action` 형식을 사용합니다. 모델 도구명 `research__request_scoped_source_schema`만 호스트 `request_scoped_source_schema`로 별도 연결하고, 실제 원본 작업명은 `tool__endpoint`를 유지합니다. 스키마 응답을 **측정 대상 모델 대화**에 넣되 자동 실행하지 않습니다. 소비자 인수는 호스트가 신뢰하는 입력과 이전에 검증한 공개 관측치만으로 충족해야 합니다.

- [ ] **1단계 — 실패 테스트 작성:** `test_model_requests_schema_then_calls_two_registered_read_only_routes`, `test_initial_menu_has_only_schema_request_and_no_provider_tool`, `test_agent_aborts_hidden_binding_or_principal_swap_before_consumer`, `test_agent_rejects_malformed_or_repeated_schema_requests_without_source_call`, `test_unmaterialized_route_is_refused_without_original_invocation`, `test_premature_final_and_unbound_arguments_are_task_failures`, `test_schema_request_does_not_change_source_call_count`. 스크립트 모델 응답·실제 등록한 로컬 호스트 실행기·기존 `execute_scoped_host_call`을 사용해 실행 순서와 부정 입력의 호출 금지를 확인합니다.
- [ ] **2단계 — RED 실행:** `python -m pytest tests/test_research_codegraph_surgical_agent_e1.py -q`.
- [ ] **3단계 — 최소 구현:** 기존 턴 제한 Qwen 응답과 엄격한 JSON 작업 파서를 유지하면서 메타 작업→원본 스키마 공개→원본 경로 선택 루프를 구현합니다. 반복 공개, 불완전·복수 작업, 미공개 경로, 검증되지 않은 필수 인수를 거절합니다. 생성 응답 후와 매 원본 호출 전에 출처·권한을 재검증합니다. **모델이 직접** 원본 작업을 선택해야 하며, 관측치는 기존 투영기, 실행은 `RegistryExecutor`를 사용합니다.
- [ ] **4단계 — GREEN 실행:** `python -m pytest tests/test_research_codegraph_surgical_agent_e1.py tests/test_research_authorized_agent_tool_surface.py tests/test_research_real_qwen_bound_two_step_e0.py -q` — 기존 기능 포함 통과해야 합니다.
- [ ] **5단계 — 커밋:** `git commit -m "feat(research): execute surgical G5 schema-request protocol through scoped host"`.

### 작업 3: 원본 Open-Meteo에서 실제 모델 네 조건 비교

**인터페이스:** 기존 `compare_graph_native_e1`은 그대로 두고 `compare_codegraph_surgical_e1(agent, client, *, documented_noncommercial_e1: bool = False, ...) -> dict[str, Any]`를 추가합니다. 조건은 `all_visible`, `lexical_k5`, `concept_graph_optin`, `surgical_g5_e1`입니다. 동일 `USER_REQUESTS`·`CASES`, 원본 위치 검색→날씨 조회, `_matches_weather_final`, 출처 검증, 모델 리비전을 사용합니다. 메타 스키마 요청과 그 응답을 포함한 **모든 턴**의 실제 토큰을 각각 기록합니다.

- [ ] **1단계 — 실패 테스트 작성:** `test_four_arm_requires_same_tasks_principal_source_and_k`, `test_surgical_arm_never_preinvokes_provider_or_fabricates_geo_coordinates`, `test_four_arm_source_failure_has_null_denominator_and_tokens`, `test_model_runtime_unavailable_is_blocked_not_zero_success`, `test_each_meta_request_and_followup_turn_counts_actual_tool_tokens`, `test_original_three_arm_comparison_remains_unchanged`. `httpx.MockTransport` 및 스크립트 모델로 검증하며, 정상 출처에서 틀린 최종 답변은 모델 실패로 계산합니다.
- [ ] **2단계 — RED 실행:** `python -m pytest tests/test_research_real_qwen_codegraph_surgical_e1.py -q`.
- [ ] **3단계 — 최소 구현:** 작업 2의 연구 프로토콜을 네 번째 비교 조건으로만 추가합니다. 원본 제공자 클라이언트와 G5의 의미 계약 자격검사를 유지하고 조건 실행 순서를 교차합니다. 정책·출처 변경 시 중단하고 `INCOMPARABLE_SOURCE_FAILURE`, `INCOMPARABLE_SOURCE_DRIFT`, `BLOCKED_SOURCE_SEMANTICS`, `BLOCKED_MODEL_RUNTIME`과 `null` 분모를 보존합니다. 모델 입력·도구 스키마·출력 토큰을 모든 생성 결과에서 합산하되 불완전한 영수증은 `null`로 남깁니다. Open-Meteo의 **2개 경로만으로 큰 도구 목록의 비용 효율을 주장하지 않습니다**.
- [ ] **4단계 — GREEN 실행:** `python -m pytest tests/test_research_real_qwen_codegraph_surgical_e1.py tests/test_research_real_qwen_concept_graph_e1.py tests/test_research_real_qwen_open_meteo_two_hop_e1.py -q`.
- [ ] **5단계 — 조건부 실제 실행:** 고정 Qwen CPU 환경과 비상업 이용이 허용된 원본 출처가 준비된 경우에만 명시적 surgical 비교 플래그로 실행해 `/tmp/schemarouter-codegraph-surgical-e1-open-meteo.json`에 정제된 결과를 남깁니다. 준비되지 않으면 실제 모델 점수·사용량을 꾸미지 않고 차단 사유를 기록합니다.
- [ ] **6단계 — 커밋:** 비교기·테스트·비민감 실험 증거가 있는 경우에 한해 스테이징하고 `git commit -m "test(research): compare surgical G5 with original four-arm task outcomes"`.

### 작업 4: 실제 실행 가능한 10개 이상 원본 경로의 로컬 규모 실험

**인터페이스:** `run_local_multiroute_codegraph_e1(agent, *, language, condition) -> dict[str, Any]`. 결정적인 출력과 실제 호스트 등록을 가진 **읽기 전용 엔드포인트 최소 10개**를 `SchemaRouter`에 등록합니다. 출처가 선언한 형식 있는 원본 스키마, 사전 고정 EN/KO/JA 작업, 허가된 2단계 경로·권한 거절·부적합·6개 경로 K 초과를 포함합니다. 네 조건 모두 동일 출처와 신뢰 가능한 정답 검증을 사용하며 증거 등급은 항상 `E1_LOCAL_SOURCE_CONTROL`입니다.

- [ ] **1단계 — 실패 테스트 작성:** `test_fixture_registers_at_least_ten_real_read_only_host_routes`, `test_en_ko_ja_two_step_calls_are_actual_registered_callbacks`, `test_local_full_lexical_g5_surgical_share_exact_source_witness`, `test_denied_no_fit_over_k_stop_before_source_access`, `test_fixture_cost_includes_schema_round_trip_and_all_model_turns`, `test_no_claim_of_independent_or_remote_provider_evidence`. 형식 바인딩·K5·정확한 호스트 콜백 횟수를 확인합니다.
- [ ] **2단계 — RED 실행:** `python -m pytest tests/test_research_codegraph_local_multiroute_e1.py -q`.
- [ ] **3단계 — 최소 구현:** 실제로 등록한 결정적 콜백과 검토된 원본 스키마를 사용해 작업 3의 네 조건 실행기를 적용합니다. 로컬 관측치를 가짜 원격 API 응답으로 표시하지 않습니다. 모든 권한·출처·필드 검사, K5, 모델/턴 제한 및 최종 정답 검사를 유지합니다. 실제 모델이 없으면 `BLOCKED_MODEL_RUNTIME`으로 두며 모의 모델 테스트는 계약 검증으로만 기록합니다.
- [ ] **4단계 — GREEN 실행:** `python -m pytest tests/test_research_codegraph_local_multiroute_e1.py tests/test_research_codegraph_surgical_agent_e1.py tests/test_research_codegraph_scoped_materializer.py -q`.
- [ ] **5단계 — 실제 Qwen 조건부 실행:** 고정 모델이 준비되면 `--cohort local-source`로 실행하고 `/tmp/schemarouter-codegraph-surgical-e1-local.json`에 정제된 결과를 저장합니다. 모델이 없으면 모의 결과로 대체하지 않습니다. 실제 토큰 정보가 없으면 `null`입니다. Open-Meteo 결과와 별도로 보고합니다.
- [ ] **6단계 — 커밋:** `git commit -m "test(research): measure surgical G5 on source-registered multiroute control"`.

### 작업 5: 영문·국문 E1 결과와 브랜치 검토

**인터페이스:** `docs/research/codegraph-surgical-context-e1.md`와 이에 대응하는 직접 한국어 번역을 작성합니다. 계획·설계·집단별 증거·정확한 실행 명령을 연결하고 문서 출처 Blob 검토 및 두 MkDocs 탐색 목록을 유지합니다.

- [ ] **1단계 — 실패 테스트 작성:** `tests/test_bilingual_docs_integrity.py`, `tests/test_translation_semantic_sections.py` 또는 범위가 맞는 문서 증거 테스트에 두 집단, 네 조건, 원본 차단, 실제 토큰, `null` 분모 검증을 추가합니다. E0 바이트 감소를 모델 절감률로 설명하거나 E2·출시 완료를 주장하지 않는지 검증합니다.
- [ ] **2단계 — RED 실행:** `python -m pytest tests/test_bilingual_docs_integrity.py tests/test_translation_semantic_sections.py -q` — 새 증거 문서 검사만 실패해야 합니다.
- [ ] **3단계 — 최소 구현:** 영문·국문 결과 문서에 실제 생성한 집단 A/B 증거만 포함하고, 미실행 부분은 정확한 차단·부정 결과로 기록합니다. 출처 자격, 바이트와 토큰의 차이, 모델·코드·출처 리비전, CI 실행 ID, 재현 명령, 보안 부정 사례, 상업적 이용 권한 조건을 명시합니다. MkDocs 탐색, 번역 매니페스트 Blob, AI 보조 영문/국문 검토 감사 기록을 갱신합니다. #1711은 E1 실제 판정 전까지 열어두고 #1346/#1356은 변경하지 않습니다.
- [ ] **4단계 — 문서 검증:** `python -m pytest tests/test_bilingual_docs_integrity.py tests/test_korean_translation_coverage.py tests/test_translation_review_units.py tests/test_translation_semantic_sections.py tests/test_bilingual_coverage_report.py -q` 및 `python scripts/prepare_korean_docs.py --output /tmp/schemarouter-codegraph-e1-site-docs` — 번역 대체 페이지가 없어야 합니다.
- [ ] **5단계 — 전체 검증:** `python -m pytest -q`(환경 제한이 있다면 정확히 기록), `ruff check src scripts tests`, `pyright`, `git diff --check`를 실행하고 GitHub Actions·출처 증거·비공개 입력의 저장 여부를 검사합니다. 실제 실행하지 못한 검사를 통과했다고 보고하지 않습니다.
- [ ] **6단계 — 커밋·검토:** `git commit -m "docs(research): publish bilingual surgical G5 E1 verdict and evidence"` 후 구현 브랜치 전반을 검토하고 증거 및 CI 확인 전에는 PR을 Draft로 유지합니다. 병합과 출시는 별도 승인이 필요합니다.

## 최종 확인 및 인계

1. 최소 완료 기준은 **모델이 요청하는 스키마를 검증해 공개하고, 실제 등록된 원본 읽기 콜백을 기존 권한 실행기로 호출하는 기능**입니다. 추가 토큰 비용으로 효과가 음수이더라도 정확히 기록하며 추가 미세 최적화로 목표를 바꾸지 않습니다.
2. 원본 출처가 정상인데 모델이 실패한 경우, 출처 전송 실패, 모델 가동 불가, 합성 E0 실험을 구별합니다. 조건별 실제 모델 입력·도구 스키마·출력 토큰을 보고하거나 정확한 측정 불가 사유를 남깁니다.
3. 출처 SHA, 모델 리비전, 영문·국문 계획과 결과, 실행 명령, CI ID, 로컬 원본 실행 및 가능한 경우 원본 Open-Meteo 증거, 미해결 출시 제약을 보존합니다.
4. **계획 검토 지점:** 본 계획 승인을 받은 뒤 사용자 선택 **A안(직접 순차 구현)**으로 작업 1을 시작합니다. 승인 단계를 생략하거나 병렬 하위 에이전트 구현으로 전환하지 않습니다.

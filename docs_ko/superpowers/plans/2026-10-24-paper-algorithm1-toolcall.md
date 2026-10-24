# 원 논문 Algorithm 1 ToolCall 투영 구현 계획

> **에이전트 작업자를 위한 지침:** 이 계획을 단계별로 구현할 때는 `superpowers:subagent-driven-development`(권장) 또는 `superpowers:executing-plans` 지침을 적용합니다. 진행 상태는 체크박스(`- [ ]`)로 기록합니다.

**목표:** 출처 검증을 통과하고 필요한 필드가 모두 충족된 원 논문 경로들을 기존 `ToolCall`의 순서와 인자 의존성으로 투영합니다. 실행 권한을 새로 부여하거나 인자 값을 만들어 내지 않습니다.

**구조:** 선택형 `retrieve_paper_field_coverage`, 원본 레지스트리 및 동일한 주체 범위의 출처 가시성을 사용합니다. 기존 `ToolCall`과 근거 계약을 재사용해 비실행 호출 기록을 만들고, 반환 전에 원본 증명을 다시 검증합니다. 제품 기본 라우팅은 변경하지 않습니다.

**기술:** Python 3.10 이상, Pydantic v2, SchemaRouter 네이티브 그래프 인덱스, pytest, Ruff.

**설계서:** `docs/superpowers/specs/2026-10-24-paper-algorithm1-toolcall-design.md`

## 전체 제약 조건

- K5 고정. 명시적 주체, 출처 소유자가 검토한 콘셉트 카탈로그, 현행 인덱스 및 권한 정책을 요구합니다. 새 플래너, 인덱스, 에이전트, 실행기는 만들지 않습니다.
- 자연어 질의나 구조적 그래프만으로 후속 입력값을 만들어서는 안 됩니다. 의존 `ToolCall.arguments`는 비워 두고 원본 연결 요구 사항을 `missing_required_arguments`에 표시합니다. 승인된 입력 필요 G5 루트 역시 원본 호스트 입력명을 **미충족** 상태로 유지해야 합니다.
- 허용된 원본 출력 필드의 정확한 투영, 스키마·도구 지문, 제공 가능한 근거만 사용합니다. 비공개·숨김·변경된 출처 이름은 거부합니다.
- 결과는 명시적으로 선택하는 비실행·비권한 기록입니다. 운영 기본값, 배포, 독립 E2 승인에 영향을 주지 않습니다.

## 리뷰 중점 항목

1. 생산자 응답이 없는데도 소비자 인자가 실행 가능하게 표시되는 경우 — `test_compiled_fork_unbound_arguments_remain_nonexecutable`.
2. 동일한 이름의 비공개 필드가 `ToolCall.fields`에 노출되는 경우 — `test_compiled_direct_reuses_exact_scoped_field_projection`.
3. 잘못된 미래 단계 의존성이나 중복 바인딩을 실행 가능한 계획으로 투영하는 경우 — `test_compiler_rejects_unproved_or_changed_dependency`.
4. 증명과 반환 사이에 출처 가시성·가용성이 변경되는 경우 — `test_compiler_rejects_mid_projection_source_revocation`.
5. 불완전한 K5 결과에 호출이 표시되는 경우 — `test_compiler_preserves_no_proven_hit_or_over_k`.

---

## 작업 1: P1 증명 기록을 기존 ToolCall 계약으로 변환

**파일:** `src/schemarouter/paper_field_plan.py`, `tests/test_paper_field_plan.py` 신규 작성. `src/schemarouter/__init__.py`, `tests/test_public_api.py` 수정.

**인터페이스:** `compile_paper_field_toolcalls(router, query, *, principal, catalog, index, k=5) -> PaperFieldToolCallPlan`; `PaperFieldArgumentDependency(consumer_call_index, parameter, producer_call_index, producer_field)`; `PaperFieldCallAlternative(calls, dependencies, required_semantic_ids)`; `PaperFieldToolCallPlan(status, snapshot_id, registry_version, requested_k, alternatives, executable_authority=False, independent_quality_evidence=False)`.

- [x] 정확한 직접 필드 투영, 미연결 인자가 있는 원본 루트→두 소비자 분기, 미완전 결과 상태 보존에 대한 실패(RED) 테스트 작성.
- [x] 새 API가 없기 때문에 예상대로 실패하는지 확인.
- [x] 최소한의 플래너 모델 조립과 출처 권한·근거 검사를 구현하고, 첫 증명과 마지막 증명을 수행.
- [x] 성공(GREEN)을 확인한 뒤 잘못된 의존성, 뒤늦은 출처 철회, 기존 기본 동작 불변성 회귀 테스트를 추가해 차단.
- [x] 원 논문·네이티브 테스트와 저장소 린트를 실행하고 전체 테스트 결과의 한계를 기록.
- [x] 기존 PR #1746 기반의 별도 [Draft PR #1747](https://github.com/JDeun/SchemaRouter/pull/1747)에 커밋해 게시. 병합이나 상위 이슈 종료는 진행하지 않음.

## 작업 2: 이후 단계의 출처 소유자 승인 인자 및 실제 어댑터 검증 (이 구현 범위 밖)

- [ ] 인자가 있는 출처·루트에서 명시적인 호스트 승인 원본 입력 계약을 요구합니다. OPTIMADE 단위 변환을 추측하지 않습니다.
- [ ] 구체적인 루트 인자 검증과 실제 출처 어댑터에 대한 기존 실행기 동작을 증명합니다. #1346에서 독립 출처 자료가 마련되기 전에는 E2를 승인하지 않습니다.

## 구현 기록

- P1 #1746 원 논문 전용 CI가 성공한 뒤 계획을 시작했습니다. 당시는 전체 `CI`가 진행 중이었으며, 운영 기본값이나 독립 E2 승인은 요청하지 않았습니다.
- **RED:** 새 컴파일 API를 가져올 수 없어 테스트 수집이 실패했습니다. **GREEN:** 초기 계획 및 공개 API 테스트 10개, 이어서 관련 테스트 76개가 통과했고 Ruff 오류가 없었습니다. 5,000개 원본 경로 인덱스, 여섯 대안의 `over_k_unranked`, 미연결 인자, 원본 출력 투영, 기본 라우팅 불변성을 검증했습니다.
- 실제 발견한 추가 결함: 첫 P1 증명 직후 소유자 카탈로그 별칭 또는 권한 정책을 바꾸되 선택 필드를 그대로 유지하면 기존 컴파일러가 변경을 감지하지 못했습니다. 두 테스트의 실패를 확인한 뒤 첫 증명 **이전**에 주체·카탈로그·정책·출처 정보를 고정하고 두 번째 증명 이후 비교해 통과시켰습니다.
- 네이티브 그래프 의존성은 구조적 관계만 의미하며 컴파일러는 구체적 인자 값을 만들지 않습니다. 호스트가 승인한 입력 필요 G5 루트는 필요한 입력명만 미충족으로 표시합니다. 실제 호스트 값 바인딩 및 OPTIMADE 선택·필수 파라미터 적용은 이 단계에서 제외했습니다.
- 코드 리뷰에서 직접 호출 테스트에 실제 `DataScopeRule`이 없다는 점을 발견했습니다. 숨김 필드·생산자 식별자 테스트와 EN/KO/JA의 실제 OpenAPI/MCP 범위 테스트를 추가했습니다. 범위 적용된 엔드포인트는 비어 있는 입력 스키마의 표현을 바꿀 수 있으므로, 무입력 증명은 원본 지문으로 고정된 엔드포인트에서 수행하도록 수정했습니다.
- 리뷰에서 P1이 검증한 입력 필요 G5 루트를 P2가 일반적인 정책 오류로 거부하는 문제도 확인했습니다. 원본 게시물 ID→사용자 ID→사용자 이름 테스트를 먼저 실패시킨 뒤 `approved_host_roots`와 `_host_source_input_names`로 승인된 루트의 필수 입력명을 미충족 상태로 보존하도록 수정했습니다. 실제 값은 연결하지 않습니다.
- 리뷰 후 직접 확인한 관련 테스트는 **101개 통과**, `ruff check .` 성공, `pyright src/schemarouter/paper_field_plan.py` 오류·경고 0건입니다. 저장소 전체 pytest는 약 13% 지점의 장시간 무진행으로 중단했으므로 전체 통과라고 주장하지 않습니다.
- 별도 리뷰 결과 Critical 0건. Important 두 건(실제 데이터 스코프 검증 부족, 입력 필요 루트 구분)을 테스트와 함께 수정했고, 변경 가능한 내부 `ToolCall`이라는 Minor 한계는 설계서에 명시했습니다. 독립 E2는 수행하지 않았습니다.
- 게시 커밋 `965234e066e87ab1aa0a9399224567dd187f491a`의 트리 `76cadecd35695e6c93ede9965abaa5b92a3909bb`는 로컬 검증 결과와 동일하며 P1 원격 커밋 `5a530e6`을 부모로 둡니다. PR #1747은 P1 기능 브랜치 대상으로 Draft 상태입니다. #1560에 해당 체크포인트를 기록했습니다. P1 전체 CI #40040143730은 최종 성공했습니다.
- 전용 CI 회귀도 실패→수정→통과로 확인했습니다. 기존 워크플로는 P2 소스·테스트 변경에 반응하지 않았으므로 `test_dedicated_paper_ci_watches_and_runs_p2_recipe`를 추가하고, P2 및 호스트 입력 G5 테스트와 Ruff 검사를 실행하도록 연결했습니다. 관련 테스트 **102개 통과**, Ruff 및 P2 Pyright 검사도 성공했습니다. 이후 결과는 항상 최신 P2 커밋의 GitHub Actions에서 확인해야 합니다.

## 작업 3: 기존 인덱스 기반 직접 선택기를 P1/P2에 연결 (승인된 이어쓰기)

**파일:** `src/schemarouter/paper_field_retrieval.py`, `src/schemarouter/paper_field_plan.py`, `tests/test_paper_field_retrieval.py`, `tests/test_paper_field_plan.py`를 수정하고, E0 측정 결과를 `research/autoresearch/paper-field-union-implementation-e0.md`에 기록합니다.

**인터페이스:** `retrieve_paper_field_coverage`, `compile_paper_field_toolcalls`, `bind_paper_field_host_inputs`, `bind_paper_field_producer_result`에 키워드 전용 `experimental_indexed_direct: bool = False`를 추가합니다. 이미 제공되는 `retrieve_authorized_concept_graph(..., experimental_indexed_direct=...)`만 재사용합니다.

- [x] 기존 승인된 직접 경로·G5 분기 fixture에서 `experimental_indexed_direct=True`로 P1/P2를 호출하는 RED 테스트를 작성합니다. 결과 상태·원본 경로 ID·가시 필드·필수 그룹 범위를 비교하되 임의의 순서 일치는 요구하지 않습니다. 미지원 인자로 실패하는지 확인합니다.
- [x] 엄격한 불리언 검사와 기존 인덱스 기반 직접 선택기 전달을 구현하고, 모든 내부 재검증 및 호스트/생산자 바인더에도 같은 모드를 전달합니다. 기본 False의 출처 선택·권한 검사는 같지만 P2 결과 데이터클래스에 모드 필드가 추가되므로 직렬화 구조 자체는 확장됩니다.
- [x] 접근 거부·숨김·K 초과·오래된 출처·잘못된 인자 자료형을 RED→GREEN으로 검증합니다. 승인된 입력 필요 루트와 실제 관찰 결과의 바인딩도 인덱스 모드에서 검증하며 자동 호출은 추가하지 않습니다.
- [x] 500/5000 경로의 결정적 E0 직접·분기 비용을 측정합니다. 초기 인덱스 구성과 웜 검색을 분리하고 Python/Linux 및 p50/p95를 기록합니다. 독립 E2나 운영 기본 순위 품질을 주장하지 않습니다.
- [ ] 관련 출처 어댑터·공개 API 테스트, 전체 Ruff, Pyright를 검증하고 프로젝트 전체 pytest를 시도해 실패나 시간 제한을 기록합니다. 커밋·독립 리뷰·기존 Draft PR #1747 게시 후 실제 GitHub SHA와 CI를 기록합니다.

**작업 3 검증 한계:** 출처 기반·공개 API·번역 관련 집중 테스트 **180개**가 로컬 Python 3.12.14에서 통과했고 저장소 Ruff와 한국어 문서 준비(번역 158개, 대체 0개)도 통과했습니다. 다만 설정 없는 로컬 Pyright는 Python 실행 시 의존성 import가 정상임에도 `.venv/lib/python3.12/site-packages`를 검색 경로에 포함하지 않아 저장소 전역에서 진단 84건을 보고했습니다. 설치된 패키지 경로를 명시한 임시(미커밋) 설정으로 **변경된 구현·벤치마크 파일 3개**를 분리 검사한 결과, fixture의 Optional 타입 오류 2건을 발견·수정해 **오류/경고 0건**으로 통과했습니다. 이는 전체 저장소의 타입 검사 성공을 의미하지 않으며 정확한 PR 헤드의 원격 CI에서 별도 확인해야 합니다. 저장소 전체 pytest는 `timeout 120s`에서 종료 코드 124로 중단됐습니다(일부 진행 출력에서 실패 단언은 보이지 않았지만 약 13%만 수행). 따라서 전체 통과라고 주장할 수 없습니다. 실제 GitHub 게시 및 최신 SHA의 CI도 별도 증거가 필요합니다. 직접 조회와 타입 검증 분기의 E0 p50/p95는 연구 기록에 정리했으며, 분기 비교는 **기존 동일 분기 알고리즘 앞의 직접 검색 단계만** 바꾼 실험입니다.

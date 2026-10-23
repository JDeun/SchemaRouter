# CodeGraph 방식 선택적 G5 E1: 원본 스키마 실행과 검증 근거

**2026-10-23 · [#1711](https://github.com/JDeun/SchemaRouter/issues/1711) · M5 · 연구 전용 명시적 활성화 · 기본 동작 및 릴리스 변경 없음**

## 결론과 측정 가능 범위

**등록된 로컬 읽기 전용 콜백에서는 구현이 동작했지만, 실제 Qwen으로 수행한 네 비교군의 비용·정확도 비교는 아직 성립하지 않았습니다.** E1은 모델이 직접 `research__request_scoped_source_schema`를 요청하도록 하고, 현재 권한을 재검증한 후 선택된 **원본** 도구 정의만 공개합니다. 다음 원본 호출의 선택과 인수 제시는 여전히 모델의 몫입니다. 실제 실행에는 기존 `SchemaRouter` 계획기, 인증·권한 경계와 `RegistryExecutor`만 사용합니다. 별도의 실행기를 도입하거나 그래프 참조를 실행 허가증으로 취급하지 않습니다.

원본 Open-Meteo 비교와 로컬 도구 실험의 명시적 CPU 실행 모두 고정된 Qwen 모델 런타임 또는 가중치가 준비되지 않아 `BLOCKED_MODEL_RUNTIME`으로 종료됐습니다. 이 실행에서는 실제 모델 응답도, Open-Meteo 외부 HTTP 요청도 발생하지 않았습니다. 따라서 `task_success_rate: null`, `qualified_task_denominator: null`이며 실제 모델 토큰 절감률을 제시할 수 없습니다. **E0 bytes는 모델 토큰이나 달러 비용을 뜻하지 않습니다.** 이전 E0 합성 실험의 UTF-8 직렬화 크기 차이는 이번 E1의 프롬프트 비용·처리량·작업 성공률 우위를 입증하지 않습니다.

## 프로토콜과 권한 검증

1. 호스트는 strict `K=5`에 따라 `complete`로 확인된 원본 G5 경로, 원본 필드 결합, 도구·엔드포인트 지문, 주체 클레임, 권한 정책의 **내용** 영수증, 호스트 전용 무결성 영수증을 고정합니다. 불완전·거부·오래된 결과 또는 `over_k_unranked`는 스키마를 공개할 수 없습니다.
2. 모델이 처음 볼 수 있는 도구는 고정된 `research__request_scoped_source_schema` 하나뿐입니다. 그래프 참조의 `tool_call_ready=false`는 실제 호출이 불가능하다는 뜻이며, 검증된 모델 요청 이전에는 원본 도구 스키마를 노출하지 않습니다.
3. 모델은 실제 선택된 고유 경로 ID만 요청할 수 있습니다. 위조·중복·선택 외·와일드카드·상한 초과 요청은 차단합니다. 호스트는 원본 레지스트리를 다시 조회하고 주체, 정책 내용, 생산자 가시 필드, 경로 지문을 재확인합니다. 스키마 반환에는 모델 실행 회차 비용이 들지만 **공급자 호출이나 새로운 실행 권한이 아닙니다.**
4. 후속 원본 호출은 완전한 소스 경로를 따라야 하며, 입력값은 검증된 호스트 입력 또는 앞선 실제 공개 관측값에서만 가져옵니다. 기존 `execute_scoped_host_call`이 원본 실행 계획을 컴파일·검증합니다. 생산자 필드 숨김, 주체 변경, 원본 변경, 불일치 소비자 인수는 추가 실행 전에 차단합니다.
5. 스키마 요청 왕복까지 포함해 매 모델 실행의 `model_input_tokens`, `tool_schema_tokens`, `model_output_tokens`와 지연 시간을 계측합니다. 실제 토큰 영수증 하나라도 없으면 합계는 0이 아니라 `null`입니다. HTTP 시도, 검증된 원본 응답, 호스트 실행 시도, 스키마 요청 횟수는 따로 기록합니다. 원본 응답 본문, 비공개 인수·정책 및 HMAC 재료는 보고서에 남기지 않습니다.

검증 과정에서 기존 경계의 호환성 문제도 확인했습니다. 공급자 출력 필드 `status`가 호스트의 호출 성공 표시 `status`와 겹치면 기존 투영 단계에서 실제 결과값이 덮일 수 있습니다. 따라서 E1 로컬 실험은 원본 의미 ID `crm.status`를 유지하면서 실제 결과 필드명을 `case_state`로 선언합니다. 이전 E0 합성 소스나 호스트 인터페이스는 임의로 변경하지 않았으며, 예약 필드 충돌의 제품 API 수정은 별도 검토가 필요합니다.

## 코호트 A — 원본 Open-Meteo HTTPS 공급자

| 항목 | 결과 |
| --- | --- |
| 데이터 원본 | 실제 등록된 지명 검색 → 현재 날씨 어댑터, 검토된 원본 계약 |
| 과제 | 동일 주체와 원본 조건에서 작성한 EN/KO/JA 요청 |
| 비교군 | `all_visible`, `lexical_k5`, `concept_graph_optin`, `surgical_g5_e1` |
| 고정 모델 | `Qwen/Qwen3-0.6B`, 리비전 `c1899de289a04d12100db370d81485cdf75e47ca` |
| 공통 예산 | `K=5`, 모델 최대 5회, 기본 재질문 0회·HTTP 재시도 0회 |
| 2026-10-23 실제 CPU 시도 | `BLOCKED_MODEL_RUNTIME` — 오프라인 고정 모델 이용 불가 |
| 작업 성공 분자/분모 | `null` / `null` — 유효 비교 없음 |
| `model_input_tokens` / `tool_schema_tokens` / `model_output_tokens` | 차단 실행이므로 `null` / `null` / `null` |
| 실제 외부 HTTP 시도 | 0회 — 모델 사전검사를 통과하지 못해 원본 요청 없음 |
| 보안·계약 테스트 | MockTransport와 스크립트 모델로 경로 순서, 공급자 실패, 가짜 좌표, 최종값 검증 통과. **실제 공급자 성공 증거는 아님** |

검토되지 않은 카탈로그 또는 소스 루트는 `BLOCKED_SOURCE_SEMANTICS`로 분류하며 원본 API를 호출하지 않습니다. 비교군 사이 원본 영수증이나 검증된 날씨 결과가 달라지면 `INCOMPARABLE_SOURCE_DRIFT`, 실제 지명·날씨 HTTP 전송 장애는 `INCOMPARABLE_SOURCE_FAILURE`로 기록하고 분모는 `null`로 둡니다. 이는 모델 경로 선택 오류로 간주하지 않습니다. 모델 부재도 인위적인 성공률 0%가 아닌 `BLOCKED_MODEL_RUNTIME`입니다. 기존 세 비교군용 `compare_graph_native_e1`의 반환 형식과 기본값은 유지했습니다.

**Open-Meteo의 상업 이용 경계:** [공식 무료 API 이용약관](https://open-meteo.com/en/terms)에 따라 무료 API는 **non-commercial(비상업적)** 용도에 한정됩니다. [상업용 API](https://open-meteo.com/en/pricing)는 별도 구독·이용권이 필요합니다. SchemaRouter가 오픈소스라는 이유만으로 최종 사용자가 무료 Open-Meteo 엔드포인트를 유료 서비스에 사용할 권리를 얻지는 않습니다. 실제 운영자가 적절한 공급자 이용권과 데이터 출처 표기를 확인해야 합니다. 이번 명시적 연구 옵션은 상업용 배포 허가가 아닙니다.

## 코호트 B — 원본 등록형 로컬 12개 경로 실험

이 코호트는 **서로 독립적으로 등록된 읽기 전용 도구 12개**를 사용합니다. 두 필드가 같은 레코드에 속하는 `contacts.read` 생산자, 입력의 의미와 타입을 모두 검증하는 `cases.read` 소비자, 관련 없는 재고 조회 엔드포인트 10개입니다. EN/KO/JA 모두 동일 레지스트리·정책·원본 계약을 사용합니다. 기존 `SchemaRouter.execute`를 통해 실제로 등록된 로컬 콜백을 호출하며 평가기가 정답을 생성하거나 외부 공급자처럼 꾸미지 않습니다. 추가로 소비자가 6개인 over-K, 거부된 주체, 생산자 ID 누락 조건도 실험했습니다.

| 로컬 조건 | 결과 | 해석 |
| --- | --- | --- |
| EN/KO/JA 정상 결합 테스트 | 등록된 두 원본 콜백을 순서대로 실행하고 최종값 검증 | 스크립트 모델 **테스트**로서, Qwen 작업 품질 증거는 아님 |
| `lexical_k5`·`concept_graph_optin` EN 스크립트 테스트 | 각 원본 호출 2회, 모델 회차 3회, 고정 스텁 입력+출력 207토큰 | 제어 흐름 검증용이며 **실제 모델 토큰이 아님** |
| 동일한 `surgical_g5_e1` 테스트 | 원본 호출 2회, 스키마 요청 1회, 모델 회차 4회, 고정 스텁 입력+출력 276토큰 | 추가 왕복 비용 포함, 절감 주장 불가 |
| 12개 경로의 `all_visible` | `BLOCKED_MENU_CAP` | 기존 주체별 공개 한도는 5개이며, 분할 공개로 우회하지 않음 |
| 네 비교군 비용·정확도 비교 | `INCOMPARABLE_FULL_MENU_CAP`, `task_success_rate: null` | 12개 FULL 메뉴의 동일 조건 분모가 존재하지 않음 |
| 거부 / 불완전 / over-K | `BLOCKED_AUTHORIZATION` / `BLOCKED_NO_PROVEN_HIT` / `BLOCKED_OVER_K_UNRANKED` | 원본 실행 0회, 모델 스키마 공개 0회 |
| 실제 로컬 Qwen 시도 | `BLOCKED_MODEL_RUNTIME`, 등록 경로 12개 확인 | 실제 모델 결과·토큰·성공률 분모 없음 |

12개 FULL 도구 정의를 공개하기 위해 5개씩 여러 번 호출하는 방식은 기존 보안 상한을 우회하고 비교 비용을 왜곡할 수 있어 구현하지 않았습니다. 따라서 다수 도구 원본 등록 및 선택적 실행은 확인했으나 **모델에 10개 이상을 동시에 공개하는 상황의 공정한 절감 효과는 미측정**입니다. 코호트 B는 항상 `E1_LOCAL_SOURCE_CONTROL`이며, 실제 원격 공급자 근거나 독립 E2 성능 실험이 아닙니다.

## 재현 절차와 소스 리비전

전용 E1 기능 브랜치에서 검증한 구현 커밋은 다음과 같습니다.

- `02a7bee`: 선택한 원본 스키마의 권한 재검증 및 안전 공개.
- `484cbee`: 모델 요청과 원본 스코프 내 읽기 전용 실행 프로토콜.
- `4a527dd`: 원본 Open-Meteo 네 비교군; 기존 세 비교군 유지.
- `9a0e2b4`: 원본 등록형 12개 도구, 로컬 실행과 실패 조건 검증.

프로젝트용 Python 환경에서 저장소 루트를 기준으로 실행합니다.

```bash
python -m pytest -q tests/test_research_codegraph_scoped_materializer.py tests/test_research_codegraph_surgical_agent_e1.py
python -m pytest -q tests/test_research_real_qwen_codegraph_surgical_e1.py tests/test_research_codegraph_local_multiroute_e1.py
python -m scripts.research_real_qwen_open_meteo_two_hop_e1 --compare-surgical --documented-noncommercial-e1 --out /tmp/schemarouter-codegraph-surgical-e1-open-meteo.json
python -m scripts.research_codegraph_local_multiroute_e1 --cohort local-source --language en --out /tmp/schemarouter-codegraph-surgical-e1-local.json
```

두 명시적 CPU 실행 명령은 먼저 원본 계약과 주체 권한을 검증한 다음 로컬에 이미 있는 고정 모델만 오프라인 모드로 실행합니다. 모델 가중치를 다운로드하지 않으며 모델 부재를 스크립트 성공으로 대체하지 않습니다. 테스트에서 쓰는 로컬 콜백과 Open-Meteo HTTP 모의 응답은 검증 기반시설일 뿐 실제 모델·공급자의 성공 결과가 아닙니다. `/tmp`에 기록한 민감정보 없는 시도 결과도 일시적 로컬 증거이며, Git에 포함된 실제 측정 데이터나 외부 공급자 가용성 증명은 아닙니다. 구현 커밋은 재현 기준점을 나타내며, 향후 유효한 실제 실행에는 환경·모델·원본 리비전을 별도로 기록해야 합니다.

관련 문서: [E0 실험](codegraph-surgical-context-e0.md), [E1 설계](../superpowers/specs/2026-10-23-codegraph-surgical-context-e1-design.md), [승인된 A 방식 구현 계획](../superpowers/plans/2026-10-23-codegraph-surgical-context-e1.md). #1711은 실제 모델 성능 검증 전까지 열어둡니다. [#1346](https://github.com/JDeun/SchemaRouter/issues/1346)의 독립 공급자 분리 E2 검증은 계속 차단 상태이며, [#1356](https://github.com/JDeun/SchemaRouter/issues/1356) 릴리스도 **HARD HOLD**입니다. 이번 E1 구현만으로 이슈 종료, 모델 기본값 변경, PR 자동 병합 또는 제품 릴리스를 승인할 수 없습니다.

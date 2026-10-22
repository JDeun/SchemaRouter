# 연구 프로그램 및 이슈 정리 (2026-10-19)

**문서 성격:** 연구 방향과 검증 기준을 정렬하는 관리 문서입니다. 새로운 벤치마크나 독립 성능 결과, 릴리스 승인을 뜻하지 않습니다. 이 저장소는 별도의 GitHub Wiki 대신 리뷰와 CI가 가능한 [한·영 병렬 MkDocs 연구 위키](tool-routing-landscape.md)를 공식 위키로 운영합니다. 점검 기준: 2026-10-19, main `a6ec24cf3fa1a4c0c0869e3853ab65d5fda1db83`. G5 opt-in 통합 증거는 2026-10-22 전용 구현 브랜치에서 갱신했으며 릴리스·기본값 승격은 아닙니다.

## 1. 연구 목적과 범위

**핵심 연구 질문:** 출처와 타입이 검증되고 주체별 권한이 적용된 스키마 그래프가 외부 에이전트에 필요한 Tool/Endpoint/Parameter/ResponseField만 적은 K·토큰·CPU 비용으로 제공하면서도, 전체 카탈로그와 비교해 **실제 과제 성공률, 미지원 요청 거절, 실행 안전성**을 유지하거나 개선할 수 있는가?

SchemaRouter의 책임은 **기능 검색과 검증된 타입 기반 실행 경계**입니다. 별도의 자율 에이전트, LLM 게이트웨이, 자동 번역기, 벤치마크 정답 오라클, 그래프 DB, 새로운 도구 실행기를 만드는 것이 아닙니다. OpenAPI, MCP, OPTIMADE, Python 및 기타 프로토콜은 **하나의 원본 등록 카탈로그**를 사용합니다. 개념→FieldGroup 해석, 생산자→소비자 엣지, 출처·권한 증거는 후보를 제한할 뿐 새로운 실행 권한을 만들지 않습니다. 실제 도구 호출을 제안하는 외부 모델/호스트와 신뢰 실행 정책은 구분합니다.

[SchemaRouter 원 논문](https://arxiv.org/abs/2608.21375)은 110문항의 특정 도메인 실험입니다. 대규모 이질적 도구 및 실제 에이전트 일반화의 보증은 아닙니다. 독립 0.14 실험의 **부정적 결과**도 보존해야 합니다. FULL 49.62%, SR-5 29.19%, SR-10 31.03%, SR-PROGRESSIVE 25.09%, ORACLE 70.98% 과제 성공률([이슈 #432](https://github.com/JDeun/SchemaRouter/issues/432), [#1339](https://github.com/JDeun/SchemaRouter/issues/1339)). 이후 공개 DEV 점수가 올라가도 이 결과를 바꾸지 않습니다.

### 2026-10-22 G5 opt-in 통합: 구현 범위와 E1 선행 조건

**제품 기능(명시적 opt-in):** `schemarouter.retrieve_authorized_concept_graph`는 이미 존재하는 소유자 선언 기반 `resolve_native_concepts` → 완전한 권한 범위의 FieldGroup 검색 → 버전 일치 `NativeSchemaGraphIndex.lookup`을 조합합니다. 불변 `NativeConceptGraphSelection` 결과에는 `route_sets`, 원본 도구/엔드포인트 fingerprint 삼중항, 요구 semantic ID, 검증된 생산자 출력 필드→소비자 파라미터 바인딩 전체가 들어갑니다. **입력이 없는 완전한 직접 엔드포인트**를 먼저 선택합니다. 필수 입력이 충족되지 않은 엔드포인트는 입력 없는 직접 경로로 승격하지 않고, 기존의 완전한 타입 기반 한 홉 연결로만 사용할 수 있습니다. 이는 검색 기능이므로 언제나 `executable_authority=False`입니다.

다음은 명시적 권한 정책과 검토된 원본 메타데이터가 이미 있는 호스트에서만 사용할 수 있는 연결 예시입니다.

```python
from schemarouter import (
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    retrieve_authorized_concept_graph,
)

# router: 명시적 authorization_policy와 원본 도구가 등록된 SchemaRouter
# catalog: EN/KO/JA 별칭과 정확한 타입 필드를 가진 소유자 검토 NativeConceptCatalog
# principal: 현재 요청 범위의 PrincipalContext
index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
result = retrieve_authorized_concept_graph(
    router, "문의 상태", principal=principal, catalog=catalog, index=index, k=5,
)
if result.status == "complete":
    print(result.route_ids)  # 호출 허가가 아닌 승인된 원본 경로 ID
```

이 예시는 호스트가 원래 카탈로그에 `"문의 상태"`를 실제로 선언했을 때만 성립합니다. SchemaRouter가 해당 개념을 번역하거나 추론하지는 않습니다. 검토된 EN/KO/JA 별칭은 같은 타입 제약으로 해석됩니다. `no_proven_hit`은 숨긴 ID를 노출하지 않습니다. 완전한 대안이 필요한 **고유 원본 경로 ID**가 5개를 초과하고 검증된 순위가 없으면 `over_k_unranked`는 임의의 상위 5개가 아닌 **빈 경로**를 반환합니다. 그래프 인덱스·레지스트리 버전·정책·데이터 범위·가용성·원본 fingerprint·카탈로그 내용은 재확인됩니다. 질의나 검색 결과에 호출 권한은 없습니다. 첫 통합 범위는 **직접 경로+한 홉**이며 자동 여러 홉 오케스트레이션은 아닙니다.

**에이전트 연결:** `scripts/research_authorized_concept_fixed5_agent_bridge.py`의 `AuthorizedConceptGraphFixed5Selector`가 기존 `EVAL-FIXED5-OPTIN` 에이전트 생성 경로의 콜백을 확장합니다. 요청자·원래 질의·소스 버전 범위에 속하는 `AuthorizedAgentToolSurface` 정의만 표시됩니다. 선택기는 실시간 정책 내용, 숨김·ref 필드의 안전한 투영, 모든 소스 fingerprint, K5, 실제 직렬화된 모델 도구 스키마의 바이트 예산을 확인합니다. 이전 개념 선택기와 통상 검색 기본값은 변하지 않습니다. 제어된 E0 통합 테스트에서는 기존 에이전트 루프가 생산자·소비자 두 경로를 보고 두 호출을 완료했지만, **모의 모델·fixture 결과를 실제 E1 또는 독립 E2 증거로 부르지 않습니다**.

**실제 E1 사전 검사:** `scripts.research_real_qwen_open_meteo_two_hop_e1`에 `concept_graph_optin`, `compare_graph_native_e1`, 기존 `all_visible`, `lexical_k5`와의 대응 비교가 추가됐습니다. 원래 Open-Meteo 호출·소스 상태 검사·엄격한 최종 사실 검증기를 재사용합니다. 모델 가중치·공급자 호출 없이 원본 소스 적격성만 검사하는 명령은 다음과 같습니다.

```bash
PYTHONPATH=src:. python -m scripts.research_real_qwen_open_meteo_two_hop_e1 \
  --compare-graph --out /tmp/schemarouter-native-g5-e1.json
```

**별도 승인된** 원본 소스 입력이 있을 때는 같은 CLI에 `--host-catalog /path/to/reviewed-concepts.json`과 반복 가능한 `--approved-host-root tool.endpoint`를 전달할 수 있습니다. 이는 E1 질의나 평가 정답에서 추론한 것이 아니라 **호스트 검토 선언**입니다. E1 모듈은 모든 호출 전에 실시간 원본 소스·정책·타입 그래프를 다시 검증하며, 자격 요건을 통과한 뒤에만 고정 모델 가중치를 **오프라인으로** 불러옵니다. 플래그만 지정했다고 검증되지 않은 소스가 적격해지지는 않습니다.

**2026-10-22 관측 결과:** `BLOCKED_SOURCE_SEMANTICS`, `task_success_rate: null`, 제공자 HTTP 시도 0회, 모델 턴 0회(사전 검사에서 차단). 기존 `build_live_router`에는 소스 종류는 있지만 라이선스 선언, 정확한 스칼라 출력 semantic ID, 생산자 좌표→날씨 입력 G5 타입 엣지, 명시적 요청자 권한 정책, 검토된 호스트 시작 경로 입력 계약이 없습니다. 이는 실제 소스·호스트 선행 조건입니다. E1 점수를 올리기 위해 필드나 권한을 임의로 채워서는 안 됩니다. 실제 대응 실험 전에 [Open-Meteo 사용 조건](https://open-meteo.com/en/terms)과 원본 스키마를 별도로 확인해야 합니다. 모델 가중치는 적재되지 않았고 새로운 G5 부문의 과제 성공률은 **존재하지 않습니다**. 향후 요건을 충족해도 원본 도구가 두 작업뿐이므로 K5에서 FULL 대비 스키마 비용 절감은 입증되지 않으며 우선 **두 단계 과제 정답성**을 확인합니다.

**작업 순서:** 소유자가 실제 검토한 소스 의미·권한 메타데이터와 모델 가용성을 확보하고, 원본 EN/KO/JA E1 대응 실험을 재실행합니다. 소스·관측값 변경은 비교 불가로, 제공자 장애는 모델 최종 답 오류와 분리해 기록합니다. 공급자/과제 작성자가 분리된 독립 E2는 [#1346](https://github.com/JDeun/SchemaRouter/issues/1346)에서 `BLOCKED_EXTERNAL`이며 [#1535](https://github.com/JDeun/SchemaRouter/issues/1535), [#1560](https://github.com/JDeun/SchemaRouter/issues/1560), [#1477](https://github.com/JDeun/SchemaRouter/issues/1477)도 열려 있습니다. 기본값은 변경되지 않고 [릴리스 PR #1356](https://github.com/JDeun/SchemaRouter/pull/1356)의 병합 권한도 생기지 않습니다. 현재 마일스톤 기록은 [#1700](https://github.com/JDeun/SchemaRouter/issues/1700)→M1(실측된 통합 병목만 최적화), CodeGraph [#1711](https://github.com/JDeun/SchemaRouter/issues/1711)→M5(비차단), 전체 추적용 [#200](https://github.com/JDeun/SchemaRouter/issues/200)은 의도적으로 미배정입니다. [실시간 보충 기록](https://github.com/JDeun/SchemaRouter/blob/main/.github/RESEARCH_MILESTONES.md)을 참조하십시오. 초기 30건 매니페스트는 보호된 과거 초기화 스냅샷입니다.

## 2. 연구 아키텍처와 변경 불가 원칙

1. **기능의 진실 원본:** 등록된 원본 스키마, 엔드포인트 fingerprint, 검토자가 승인한 semantic ID, 타입·단위·라이선스·스키마 버전·파라미터와 반환 필드 제약입니다. 임의의 설명문과 LLM 의도 추출은 **실행 권한**이 아닙니다.
2. **검색:** 질의의 개념을 완전한 합집합이 아닌 **논리곱 FieldGroup**으로 구성하고, K 자르기 전에 권한 및 데이터 스코프가 충족되는 후보만 추립니다. 기존 `capability_graph.py`와 G5 인덱스를 재사용하며, 독립적인 검색 엔진을 추가하지 않습니다. 검증된 경로가 5개를 초과하면 검증되지 않은 임의 순위를 만들지 않고 `over_k_unranked`를 반환합니다.
3. **적합성 및 거절:** 경로 재현율, 필수 파라미터 적합성, 필드 집합 충족과 독립 보정된 `NO_FIT` 판정은 서로 다른 계층입니다. `score > 0`이나 cosine similarity는 권한·실행 가능성의 확률이 아닙니다.
4. **실행:** 외부 에이전트가 경로·인수를 제안하더라도 신뢰 호스트가 주체, 가시성, 스냅샷, JSON Schema, 파괴적 작업, 실행 후 관측값과 출처를 다시 검증합니다. 검색 후보는 실행 승인서가 아닙니다.
5. **측정:** 안전성과 필드 집합·도구·operation 재현율, 미지원 오수용 및 지원 오거절, 최종 과제 성공률, 노출 토큰, CPU/RSS를 구분합니다. 정답 경로, 다음 예상 도구 또는 숨겨진 정답을 모델 입력에 넣지 않습니다.

## 3. 실측 현황과 우선순위

| 우선 | 담당 연구 트랙과 대표 이슈 | 현재 검증 수준 | 다음 통과 조건 |
| --- | --- | --- | --- |
| P0 | 출처·보안·필드 프라이버시: [#1450](https://github.com/JDeun/SchemaRouter/issues/1450), [#1532](https://github.com/JDeun/SchemaRouter/issues/1532), [#1269](https://github.com/JDeun/SchemaRouter/issues/1269) | 일부 코드 수정과 합성 음성/양성 테스트 존재. 중첩·참조 필드 누출 및 독립 행위 근거는 계속 점검 필요 | 숨겨진 메타데이터 및 무단 파괴적 실행 0건, 변경 중 권한·출처 검증 |
| P1 | 전체 카탈로그 typed graph G5: [#1560](https://github.com/JDeun/SchemaRouter/issues/1560), [#1530](https://github.com/JDeun/SchemaRouter/issues/1530) | 선택형 1-hop G5, 합성 5천 도구 CPU, 권한 0/1/5/6 경로 시험 병합. 기본 랭커·외부 검증 미완료 | 독립 작성 필드 라벨 기반 고정 K5 Recall 및 타입/스코프/토큰 검증 |
| P1 | 다국어 교차언어 검색: [#1339](https://github.com/JDeun/SchemaRouter/issues/1339), [#1473](https://github.com/JDeun/SchemaRouter/issues/1473), [#1403](https://github.com/JDeun/SchemaRouter/issues/1403) | 과거 500-tool 초기 필수 경로 재현율 EN 153/160, KO 0/160, JA 0/160. Unicode 수정만으로 영문 카탈로그를 번역할 수 없음 | 질의와 출처가 분리된 EN/KO/JA + OOD 코호트에서 도구와 필드 재현율 동시 평가 |
| P1 | No-fit 및 순위화: [#1582](https://github.com/JDeun/SchemaRouter/issues/1582), [#1444](https://github.com/JDeun/SchemaRouter/issues/1444) | 공개 BFCL V4 LIVE 기준 지원 8/16, 부적합 오수용 144/880. 강한 보정은 지원 4/16, 오수용 91/880으로 정상 요청 오거절 악화 | 공개 E1 모델 비교 뒤 미사용 원본의 독립 보정·검증 |
| P1 | 에이전트 실사용 성과: [#1477](https://github.com/JDeun/SchemaRouter/issues/1477), [#1348](https://github.com/JDeun/SchemaRouter/issues/1348) | 실제 Qwen3/Open-Meteo 공개 EN/KO/JA E1 엄격 성공 0–1/3 반복. 모델 조기 종료와 공급자 장애 구분 필요 | 기존 `FrozenCorpusExecutor` 재사용, 독립 과제별 FULL/SR5/G5/Hybrid/No-fit 비교와 출처 검증 답변 |
| P2 | 외부 검증 및 릴리스: [#1346](https://github.com/JDeun/SchemaRouter/issues/1346), [#1345](https://github.com/JDeun/SchemaRouter/issues/1345), [#1344](https://github.com/JDeun/SchemaRouter/issues/1344) | ClicShopping, SafeAct, CYT, Xerrion, Laya/pi-jev는 DEV·준비 작업 진행. 독립 연구자가 제공해야 할 원본 데이터 일부 `BLOCKED_EXTERNAL` | 실행 가능한 조건 완료→미제공 외부 자료 명시→보호된 CI/배포 검사→v0.18→사후 검증 |

**우선순위 결론:** Qwen3의 공개 2단계 예제에 계속 다른 알림 프롬프트를 추가하기보다, **No-fit 실험과 실제 에이전트 전체 과제 평가**를 우선합니다. Draft [#1580](https://github.com/JDeun/SchemaRouter/pull/1580), [#1584](https://github.com/JDeun/SchemaRouter/pull/1584)는 진단이며 성능 개선 근거가 아닙니다. [릴리스 PR #1356](https://github.com/JDeun/SchemaRouter/pull/1356)은 HOLD입니다.

## 4. 비교 실험 및 반증 조건

동일한 원본 출처/버전, 주체별 권한, K=5, 노출 스키마 용량, 에이전트 모델/설정, 실행 호스트 및 데이터 분할에서 **FULL**, 기본 **lexical SR-5**, 선택형 **semantic SR-5**, **typed concept/FieldGroup G5 SR-5**, **hybrid + 독립 보정 거절**을 비교합니다. ORACLE은 원인 분석 전용입니다. 합성 실행기가 실제 API 결과를 대체해서는 안 되며, 평가용 외부 작성 정답은 결과 확인 전에 동결해야 합니다.

| 측정 지표 | 분모 / 단위 | 반증 사례 |
| --- | --- | --- |
| 경로·operation·필수 필드 집합 재현율 | 지원 질의와 모든 필수 경로·필드; 완전 집합 재현율 별도 | Top-1이 맞더라도 2단계 도구나 필드 누락 |
| 정상 요청 오거절과 미지원 오수용 | 지원, 무관/OOD/금지 요청을 나눠 집계; 빈 메뉴 별도 | 오수용이 줄어도 정상 요청을 대량 거절하면 개선으로 간주하지 않음 |
| 실제 과제·최종 근거 정합성 | 관측된 응답을 검증한 독립 과제 단위, 단계별 실패 원인 | HTTP 성공이나 CI 통과가 에이전트 과제 성공을 뜻하지 않음 |
| 안전성·출처 | 무단 시도와 무단 실행 효과, 숨김 필드 노출, 변경 감지, 원본 관측 일치 | 무단 파괴적 실행·은닉 정보 노출은 중단 조건 |
| 효율 | 에이전트가 실제 본 스키마 byte/token, 빌드 비용, CPU p50/p95/p99, RSS, 전체 지연 | 단일 GitHub Actions 합성 타이밍은 상용 SLO가 아님 |

사전 등록된 주 지표는 **실제 과제 완료율 및 안전 게이트**입니다. 별도로 도구·필드 재현율과 토큰·CPU를 보고, task-paired 신뢰구간 및 언어/카탈로그별 결과를 명시합니다. 공개 개발(`E1`) 점수로 임계값을 다시 맞추지 않고 독립 평가(`E2`)가 실패하면 `VALID_NEGATIVE`를 보존합니다. 합성 구현 검증은 `E0`, 이미 공개·반복 조회된 원본은 `E1`, 독립 작성된 미사용 데이터는 `E2`로 구분합니다. 네트워크 타임아웃은 `SOURCE_FAILURE`이며 라우팅 실패로 위장하지 않습니다.

## 5. 추가 선행연구와 실제 적용 의미

| 논문·공식 자료 | 핵심 연구 결과 | SchemaRouter에 적용할 범위와 한계 |
| --- | --- | --- |
| [SchemaRouter (Cho, 2026)](https://arxiv.org/abs/2608.21375) | 필드 인식 스키마 그래프, 출처 정보와 특정 도메인 효율 | 원본의 필드 중심 그래프 가설 유지. 110문항 결과를 다국적 공급자/에이전트 일반화로 확대 해석 금지 |
| [ToolRet (Shi 외, ACL 2025)](https://aclanthology.org/2025.findings-acl.1258/) | 7,600 도구 검색 과제, 43,000 도구; 일반 검색 모델이 도구 검색에 취약할 수 있음 | 일반 임베딩 점수보다 원본 타입·필드·과제 충족 평가 우선. 데이터 사용권 및 실행 가능성 검토 |
| [ToolRerank (Zheng 외, LREC-COLING 2024)](https://aclanthology.org/2024.lrec-main.1413/) | 계층형 재정렬과 단일/다중 도구별 적응적 후보 수 결정 | 권한 기반 사전 필터 **이후** 선택형 재순위화 가설. 임의 적합성/권한 판단으로 승격 금지 |
| [BFCL V4 (Berkeley)](https://gorilla.cs.berkeley.edu/leaderboard) | 함수 relevance·irrelevance, 실제 함수·다단계·응답 형식 평가 | 관련/무관 혼동행렬·원본 source label 유지. 반복 사용한 LIVE 범주는 E1 |
| [ToolSandbox (Lu 외, 2024)](https://arxiv.org/abs/2408.04682) | 상태 유지 도구 실행과 도구 사이 숨은 의존성, 중간 단계 관측 | 노출된 도구의 재현율뿐 아니라 상태·실행·최종 응답 성공 측정 |
| [FAIL-TaLMs (Treviño 외, NAACL 2025)](https://aclanthology.org/2025.naacl-long.149/) | 부족한 사용자 정보와 사용할 수 없는 도구가 에이전트에 어려움 | 무관 질의, 빠진 인수, 권한 거부, 일시적인 제공자 장애를 다른 분류로 처리 |
| [SafeActBench (Lin 외, 2026)](https://arxiv.org/abs/2610.07753) | 최종 결과가 맞아도 해당 행동을 정당화하는 관측 근거가 없을 수 있음 | case ID 기반 정답 누설 금지, 사전 작성 정책과 관측값·실행 인수 연결. V1 393개 실제 trajectory 미완료 |
| [EDGE / KOPA-Bench (Kim 외, 2026 사전공개)](https://arxiv.org/abs/2609.05395) | 실제 한국 공공 API의 다단계 과제 145개와 **실제 API 호출로 검증한** 출력→입력 의존성 그래프 | G5의 typed join 연구와 직접 연결됩니다. [원 저자 저장소](https://github.com/dneirfi/EDGE-KOPA)의 벤치마크, 1,781개 EDGE trajectory, 학습 모델은 이번 검토 시점에 **coming soon**입니다. 내려받아 실행하지 않은 KOPA 점수 또는 임의 생성한 독립 정답을 주장하지 않습니다 |
| [ACEBench (Chen 외, EMNLP 2025)](https://aclanthology.org/2025.findings-emnlp.697/) | 일반·모호/불완전·대화형 에이전트 도구 사용을 구분한 평가 | 모호함·필수 인수 누락·미지원 요청·operation 적합성을 분리해 사전등록하고 도구 이름 일치뿐 아니라 실제 모델·호스트 결과를 평가 |
| [tau2-bench (Sierra Research)](https://github.com/sierra-research/tau2-bench) | 정책이 적용된 상태 유지형 가상 고객지원 대화의 과제 완수 평가 | 최종 과제 성공·상태·정책 위반 평가 방법을 참고하되, 시뮬레이션을 **원본 OpenAPI 실제 실행 검증**으로 표시하지 않습니다 |
| [AgentDojo (Debenedetti 외, NeurIPS 2024)](https://arxiv.org/abs/2406.13352) | 도구 응답 속 악의적 지시의 프롬프트 인젝션 공격과 방어 평가 | 신뢰도가 낮은 도구 관측에 악성 텍스트를 넣고 정당한 과제 성공률과 무단 행동을 함께 측정. 외부 응답이 권한 정책을 바꾸지 못하게 제한 |
| [CaMeL (Debenedetti 외, 2025)](https://arxiv.org/abs/2503.18813) | 신뢰된 제어/데이터 흐름 및 capability 기반 외부 효과 제한 | 사용자 요청의 제어 지시와 비신뢰 관측을 분리하고 출처·권한·데이터흐름을 재검증합니다. 다만 **SchemaRouter에서 성능이 검증된 즉시 적용 코드라는 뜻은 아닙니다** |
| [International Tool Calling (Zhang·Zhu, 2026 사전공개)](https://arxiv.org/abs/2603.05515) | 여러 국가·언어의 실제 API 및 도구 호출 평가 | 영문 소스 스키마와 자연스러운 KO/JA/EN 요청 간 이식성 평가. 채택 전 라이선스/데이터 출처 심사 |
| [MCP 2026-07-28 사양 변경](https://blog.modelcontextprotocol.io/posts/2026-07-28/) | 인증 강화 및 도구/리소스 목록 캐시 메타데이터 | 주체 권한과 출처 revision을 캐시 키에 포함하고 tool/list 결과를 실행 허가로 오인하지 않음 |

**지금 가장 부족한 연구 자산:** 필드·operation·다단계 관계·미지원/권한 거부까지 포함한 **독립 작성 EN/KO/JA 원본 질의/도구/정답 세트**입니다. 새로운 모델 선택보다 먼저 해결해야 하는 외부 증거 병목입니다. 합성 라벨을 외부 독립 정답이라고 부르지 않습니다.

## 6. 이슈 수명주기와 최소 포트폴리오

열린 이슈는 **담당 트랙, 단일 검증 가능한 완료조건, 증거 수준, 종결 판단, 상위 정본 이슈**가 있어야 합니다. 작은 E0/E1 구현은 코드와 증거가 병합되면 `completed`로 닫되, 상위 독립 검증 완료와 혼동하지 않습니다. 가설이 실제 실험에서 부정되면 관련 PR을 병합하지 않고 `not_planned`로 닫아 부정적 결과를 기록합니다. 정확한 커밋·CI run·artifact·분모를 남깁니다.

**좁은 범위 완료 후 닫을 대상:** [#1538](https://github.com/JDeun/SchemaRouter/issues/1538) G1, [#1540](https://github.com/JDeun/SchemaRouter/issues/1540) G2, [#1551](https://github.com/JDeun/SchemaRouter/issues/1551) 개념 구성, [#1558](https://github.com/JDeun/SchemaRouter/issues/1558) G4, [#1562](https://github.com/JDeun/SchemaRouter/issues/1562) G5, [#1566](https://github.com/JDeun/SchemaRouter/issues/1566) 밀도별 CPU, [#1572](https://github.com/JDeun/SchemaRouter/issues/1572) 상태별 메뉴 E1, [#1574](https://github.com/JDeun/SchemaRouter/issues/1574) 제한적 GET 재시도, [#1452](https://github.com/JDeun/SchemaRouter/issues/1452) 위조된 권한 객체가 포함된 보안 반례까지 기록한 직접 필드 스캔 비용 연구, [#1473](https://github.com/JDeun/SchemaRouter/issues/1473) 고정 K 다국어 후보 검색 및 실제 원본 공개 E1, [#1444](https://github.com/JDeun/SchemaRouter/issues/1444) OpenAPI 다중 enum 조건 보수적 검증. 모두 **작은 E0/E1 범위의 결과이며 독립 정확도나 제품 기본 승격의 증거가 아닙니다.** **실패한 가설로 종결:** [#1576](https://github.com/JDeun/SchemaRouter/issues/1576) familywise 거절, [#1579](https://github.com/JDeun/SchemaRouter/issues/1579) 진행 알림 및 [#1578](https://github.com/JDeun/SchemaRouter/issues/1578) 1회 피드백(실제 E1 개선이 확인되지 않아 PR #1580 미병합 종료). 실험 증거는 삭제하지 않습니다. 상위 [#1560](https://github.com/JDeun/SchemaRouter/issues/1560)과 [#1477](https://github.com/JDeun/SchemaRouter/issues/1477)은 계속 엽니다.

**병합되었어도 자동 종료 금지:** [#1532](https://github.com/JDeun/SchemaRouter/issues/1532) 중첩·ref 스코프 누출 잔여, [#1535](https://github.com/JDeun/SchemaRouter/issues/1535) 외부 필드 집합 평가, [#1545](https://github.com/JDeun/SchemaRouter/issues/1545) 프로토콜 분리 검증, [#1583](https://github.com/JDeun/SchemaRouter/issues/1583) 실제 JSON 실패 관측 부족. [#1585](https://github.com/JDeun/SchemaRouter/issues/1585)는 새로운 프롬프트 표현만 제안했으나 실제 실험 없이 통합·보류했습니다. 따라서 실측 부정적 결과로 표시하지 않습니다. 측정된 실패가 아닌 연구 범위 제외 항목: [#1405](https://github.com/JDeun/SchemaRouter/issues/1405) 별도 자동 반복 연구기, [#1428](https://github.com/JDeun/SchemaRouter/issues/1428) K24–64 탐색, [#1324](https://github.com/JDeun/SchemaRouter/issues/1324) 호스팅 모델 후보, [#582](https://github.com/JDeun/SchemaRouter/issues/582) 별도 마케팅 캠페인. 도입 상위 이슈, 보안, 독립 외부 검증, 릴리스는 계속 유지합니다.

**정본 작업 큐:** [#200](https://github.com/JDeun/SchemaRouter/issues/200) 세션 트래커, [#1560](https://github.com/JDeun/SchemaRouter/issues/1560) 그래프, [#1339](https://github.com/JDeun/SchemaRouter/issues/1339) 다국어, [#1582](https://github.com/JDeun/SchemaRouter/issues/1582) No-fit, [#1477](https://github.com/JDeun/SchemaRouter/issues/1477) 과제 성공, [#1346](https://github.com/JDeun/SchemaRouter/issues/1346) 외부 검증, [#1345](https://github.com/JDeun/SchemaRouter/issues/1345) 릴리스. 새로운 연구는 이 중 하나에 사전 가설·원본 버전·승인 조건을 기록하고 중간 실험마다 이슈를 증식시키지 않습니다.

## 7. 다음 세션 체크리스트

1. 이 문서와 [OSS 조사 위키](tool-routing-landscape.md), [기존 선행연구](prior-art-roadmap.md), [원 연구 목표](product-north-star-and-test-matrix.md), [실험 원장](experiment-index.md)을 읽습니다.
2. 현재 main·열린 PR·종결 CI·원본 SHA·#200을 확인하며, 녹색 CI만으로 실제 모델 결과를 추정하지 않습니다.
3. P0 보안 반례가 있으면 우선 처리하고, 없으면 Linux CPU에서 **하나의 사전등록 가설만** 재현 가능하게 실험합니다.
4. 정상 도구 재현율과 무관 도구 오수용을 **동시에** 발표하고 외부 에이전트의 완전한 과제 결과로 검증합니다. 실패한 실험도 논문 근거입니다.
5. 이슈 #1345와 #1346의 필수 검증 전에는 v0.18 PR #1356의 병합·태깅을 금지합니다. 미사용 독립 정답 없이는 E2 자격을 주장하지 않습니다.

**과거 자료:** [설계 이력](design-and-experiment-history.md), [선행연구](prior-art-roadmap.md), [논문 근거](paper-evidence-package.md), [외부 검증 동결](external-validation-freeze.md).

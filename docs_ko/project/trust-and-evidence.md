# 신뢰성, 안정성 및 공개 근거

SchemaRouter는 **안정적인 제품 보장**, **릴리스/프로세스 근거**, **연구 근거**를 구분합니다. 이 페이지는 마케팅 문구에 의존하지 않고 프로젝트를 검증하려는 엔지니어를 위한 검증 인덱스입니다.

## 현재 안정판

| 항목 | 검증된 공개 상태 |
| --- | --- |
| 안정판 | `0.17.0` |
| 릴리스 날짜 | 2026-10-07 |
| 상태 | Beta / pre-1.0 |
| Python | 3.10–3.14는 릴리스 차단 CI 대상이며, 3.15는 비차단 preview입니다 |
| 라이선스 | MIT |
| 릴리스 | [SchemaRouter 0.15.0](https://github.com/JDeun/SchemaRouter/releases/tag/v0.15.0) |
| 안정 코어 계약 | [안정 코어](../stable-core.md) |
| 보안 정책 | [SECURITY.md](https://github.com/JDeun/SchemaRouter/blob/main/SECURITY.md) |

0.14.0 이후에는 정확한 릴리스 소스 SHA와 아티팩트 digest가 GitHub Release에 첨부되는 기계 생성 `release-manifest.json` 및 `SHA256SUMS.txt`에 기록됩니다.
annotated tag를 GPG 서명 태그라고 표현하지 않으며, 아티팩트 provenance는 GitHub artifact attestation으로 제공합니다.

## 과거 0.13.0 아티팩트 digest

0.13.0 릴리스는 생성형 manifest 도입 이전 버전이므로 고정된 과거 digest 기록으로 이곳에 보존합니다.

| 아티팩트 | SHA-256 |
| --- | --- |
| `schemarouter-0.13.0-py3-none-any.whl` | `1fad74f9b0604a3a8309fe71a729670aed4c0b37be2980e00c652f702ffb4ed5` |
| `schemarouter-0.13.0.tar.gz` | `5436dfae9058504fa8ef2c56ddad57a151668bf7d996ef5ddab3d329e9c4a659` |
| `schemarouter-0.13.0.spdx.json` | `a1c62770a10d33cc366d487d696ed67dcf220e930cbbd087d9ca69e6a96a760d` |

릴리스 워크플로는 다음을 수행합니다.

1. 현재 `main` SHA에 대한 성공한 CI 실행만 허용합니다.
2. 개발 버전을 거부하고 일치하는 릴리스 노트/changelog 메타데이터를 요구합니다.
3. 확정된 릴리스 SHA에서 wheel과 sdist를 빌드합니다.
4. 두 빌드 아티팩트를 clean install하고 smoke test합니다.
5. SPDX JSON SBOM을 생성합니다.
6. 배포물의 GitHub artifact provenance attestation과 SBOM attestation을 생성합니다.
7. PyPI Trusted Publishing으로 게시합니다.
8. 공개 PyPI에서 정확히 같은 게시 버전을 다운로드합니다.
9. 공개 wheel/sdist digest를 신뢰된 빌드 아티팩트와 비교합니다.
10. 게시된 wheel, sdist, 경량 extras 및 통합 extras 조합을 설치합니다.

구현:
[release.yml](https://github.com/JDeun/SchemaRouter/blob/main/.github/workflows/release.yml)

0.14.0 이후 버전의 아티팩트 digest는 해당 릴리스에 첨부된 `release-manifest.json` 또는 `SHA256SUMS.txt`로 검증하십시오. GitHub CLI attestation 검증을 사용할 수 있다면 다음과 같이 실행합니다.

```bash
gh attestation verify schemarouter-0.15.0-py3-none-any.whl --repo JDeun/SchemaRouter
```

저장소 릴리스 체크리스트는 provenance, SBOM, 공개 PyPI digest 동등성, 게시 후 설치를 선택적 문서 작업이 아니라 명시적인 릴리스 절차로 취급합니다.

0.14.0부터는 checksum을 문서에 수동 복사하지 않도록 릴리스 워크플로가 다음 두 기계 생성 기록도 첨부합니다.

- `SHA256SUMS.txt` — wheel, sdist, SPDX SBOM의 SHA-256 digest
- `release-manifest.json` — 패키지 버전, 태그, 정확한 소스 commit, 아티팩트 이름·크기·SHA-256 digest

이 릴리스 에셋이 각 릴리스 checksum의 정본입니다. 위의 정적 0.13.0 표는 manifest 도입 전 마지막 릴리스에 대한 과거 근거입니다.

## CI 및 보안 자동화

보호되는 제품 표면은 장식용 badge 하나가 아니라 독립적인 워크플로들로 테스트됩니다.

### 필수 CI 매트릭스

주 CI 워크플로에는 다음이 포함됩니다.

- Python 3.10, 3.11, 3.12, 3.13, 3.14
- Windows + Python 3.14 smoke coverage
- 84% 하한의 branch coverage
- 최소 dependency 테스트
- 정적 타입 검사
- 빌드된 wheel/sdist의 clean-environment acceptance
- LangChain 및 LangGraph 통합
- LlamaIndex 통합
- MCP 통합
- Jev/System-One, Laya, OpenTelemetry 통합 job
- dependency audit
- strict documentation build

Python 3.15는 의도적으로 릴리스 차단 조건이 아니라 preview 신호로 취급합니다.

### 독립 보안 자동화

저장소는 다음도 실행합니다.

- CodeQL
- 별도 Security Audit 워크플로
- OpenSSF Scorecard
- 외부 GitHub Actions의 immutable commit pinning
- credential, policy, destructive operation, schema drift, binding, redaction, budget, authentication contract에 대한 regression test

따라서 CI badge가 green이라고 해서 모든 보안 문제가 해결되었다는 근거로 취급하지 않습니다. 보안 모델과 보고 경로는 [SECURITY.md](https://github.com/JDeun/SchemaRouter/blob/main/SECURITY.md)에 별도로 문서화합니다.

## 안정적인 런타임 보장

안정 제품에 대한 주장은 의도적으로 "router가 항상 정확하다"보다 좁게 정의합니다.

### 제한된 권한

검색 및 모델 보조 결정은 실행 권한을 부여하지 **않습니다**. 실행 가능한 tool, endpoint, field, parameter, credential, policy, side-effect permission은 신뢰된 등록 계약과 로컬 애플리케이션 상태에서 옵니다.

### 호출 전후 검증

SchemaRouter는 다음을 검증합니다.

- 필수/허용 argument
- 현재 schema 및 tool fingerprint
- binding readiness
- 로컬 policy 및 approval requirement
- 등록된 output schema에 대한 raw provider output
- `ToolResult`를 반환하기 전 선언된 field projection

### 파괴적 작업은 fail-closed

Mutation/destructive/unclassified 원격 작업을 안전한 read로 암묵 처리하지 않습니다. Permission과 approval 의미론은 로컬에서 명시적으로 유지합니다.

### Schema drift는 권한을 조용히 대체하지 않음

원격 metadata 변경은 승인된 계약과 비교합니다. 동일한 계약은 쓰기가 필요 없고, 호환 변경은 명시적으로 승인할 수 있으며, breaking/security-relevant drift는 검토 대상으로 보류합니다. 오래된 binding은 fail-closed합니다.

### 런타임 invariant는 fail-closed

프로덕션 런타임 계약 위반은 Python 최적화로 제거될 수 있는 `assert`에 의존하지 않고 명시적인 invariant error를 발생시킵니다. 이 hardening은 [#627](https://github.com/JDeun/SchemaRouter/issues/627)에서 추적되었습니다.

그 밖의 공개 hardening 사례:

- [#594 — schema-watch contract/source credential cross-binding](https://github.com/JDeun/SchemaRouter/issues/594)
- [#602 — canonical execution contract의 authentication requirement](https://github.com/JDeun/SchemaRouter/issues/602)

세 항목 모두 현재 개발 이력에서 닫혀 있습니다.

## 호환성 근거

Protocol compatibility와 routing quality는 서로 다른 근거 범주입니다.

예약/수동 live compatibility matrix는 다음을 실행합니다.

- APIs.guru OpenAPI
- COD OPTIMADE
- Rick and Morty GraphQL
- OData.org V4
- pinned OpenRPC / JSON-RPC reference implementation
- pinned MCP Streamable HTTP reference implementation

이 검사는 기계 판독 가능한 compatibility evidence를 생성하지만, 제3자 provider uptime은 릴리스 차단 dependency가 아닙니다.

[Live compatibility matrix](../guides/live-compatibility-matrix.md)와 [Compatibility testing](../compatibility.md)을 참고하십시오.

## 연구 근거: 허용되는 주장

Benchmark가 긍정적이라는 이유만으로 연구 근거를 안정적인 제품 보장으로 승격하지 않습니다.

현재 canonical 0.14 evidence checkpoint에는 다음 결과 등이 기록되어 있습니다.

| 근거 | 결과 | 허용되는 해석 |
| --- | --- | --- |
| B1 controlled Qwen3-0.6B | SR-5 task pass 91.30% vs FULL 68.48%; SR-5 schema-token ratio 5.42%; required-route recall 100% | 고정된 23-task 표면에서의 controlled mechanism evidence |
| Structural K3 vs K5 | K3 task-pass delta -3.2609 pp; preregistered -2 pp promotion floor failed | negative evidence; K3는 승격하지 않음 |
| 보고된 B1/K3 근거에서의 unauthorized destructive execution | 0 | 해당 기록 실험 표면에만 한정 |

B1 결과는 population-level production superiority, 모든 agent로의 일반화, final-answer factual quality를 주장하지 **않습니다**. Structural K3 결과는 숨기지 않고 negative result로 공개 보존합니다.

정본 출처:

- [0.14 paper-evidence checkpoint](../research/0.14-paper-evidence-checkpoint.md)
- [Research evidence package](../research/paper-evidence-package.md)
- `benchmarks/research-experiment-ledger.json`

Issue [#15](https://github.com/JDeun/SchemaRouter/issues/15)는 재현 가능한 **live decision-backend** 측정을 위해 열려 있습니다. 이 작업이 종결되기 전에는 Jev, Laya, Ollama, hosted model 또는 다른 decision backend가 live routing quality, latency, token use, cost에서 우월하다고 주장하지 않습니다.

## 공개 보고 및 hardening 로그

이 페이지는 프로젝트 자체가 발견한 hardening 작업과 외부에서 보고된 incident를 구분합니다.

| 출처 | 항목 | 상태 |
| --- | --- | --- |
| project hardening | #594 credential/source cross-binding boundary | closed |
| project hardening | #602 canonical authentication contract | closed |
| project hardening | #627 fail-closed runtime invariant checks | closed |

2026-10-01 기준, 이 페이지를 위해 검토한 저장소 issue 이력에서 **공개적으로 공개된 외부** security/reliability report로 식별되는 항목은 없습니다. 이 문장은 비공개 vulnerability report의 존재를 공개하거나 부정하지 않습니다. 공개 advisory 또는 외부 report는 공개가 적절해지는 시점에 상태, 영향 버전, 수정 버전, advisory/reference link와 함께 이 표에 추가해야 합니다.

민감한 취약점은 공개 issue가 아니라 [GitHub private vulnerability reporting](https://github.com/JDeun/SchemaRouter/security/advisories/new)을 통해 보고해야 합니다.

## 여전히 필요한 외부 검증

저장소 자체 CI는 필요하지만 독립 검증은 아닙니다. 더 강한 근거에는 다음이 포함됩니다.

- downstream 프로젝트가 자체 CI에서 SchemaRouter 실행
- benchmark artifact의 독립 재현
- framework integration에 대한 외부 maintainer review
- 실제 agent/RAG 프로젝트의 재현 가능한 integration PR
- 실행 가능한 코드를 연결하고 한계를 공개하는 공개 발표/blog
- 외부 security review 또는 책임 있는 vulnerability disclosure

이는 이미 달성했다고 주장하는 내용이 아니라 adoption/evidence 목표입니다. 외부 adopter 및 case-study 작업은 #584에서 별도로 추적합니다.

## 향후 주장에 대한 검증 규칙

공개 주장은 최소한 다음 중 하나로 연결되어야 합니다.

- released artifact
- protected CI/security workflow
- versioned compatibility report
- reproducible benchmark artifact/ledger row
- 문서화된 external adopter 또는 independent reproduction

그렇지 못한 주장은 안정 제품 설명이 아니라 roadmap 또는 hypothesis 섹션에 속합니다.

# 신뢰성, 안정성, 공개 근거

SchemaRouter 문서에서는 **안정판이 보장하는 동작**, **릴리스 과정의 검증 기록**, **연구 결과**를
서로 구분합니다. 이 페이지에는 각 주장을 확인할 수 있는 공개 근거를 모아 둡니다.

## 현재 안정판

| 항목 | 공개 상태 |
| --- | --- |
| 안정판 | `0.16.0` |
| 릴리스 날짜 | 2026-10-04 |
| 상태 | Beta / pre-1.0 |
| Python | 3.10–3.14는 릴리스 차단 대상, 3.15는 preview |
| License | MIT |
| Release | [SchemaRouter 0.14.0](https://github.com/JDeun/SchemaRouter/releases/tag/v0.14.0) |
| Stable core | [Stable core](../stable-core.md) |
| Security | [SECURITY.md](https://github.com/JDeun/SchemaRouter/blob/main/SECURITY.md) |

## 0.14.0부터의 artifact 기록

0.14.0부터는 GitHub Release에 함께 올라가는 `release-manifest.json`과
`SHA256SUMS.txt`가 source SHA와 artifact digest의 정본입니다. 문서에 새 checksum을 손으로
복사하지 않습니다.

### 과거 0.13.0 digest

0.13.0은 이 manifest 도입 전 릴리스이므로 아래 값을 과거 기록으로 남깁니다.

| Artifact | SHA-256 |
| --- | --- |
| `schemarouter-0.13.0-py3-none-any.whl` | `1fad74f9b0604a3a8309fe71a729670aed4c0b37be2980e00c652f702ffb4ed5` |
| `schemarouter-0.13.0.tar.gz` | `5436dfae9058504fa8ef2c56ddad57a151668bf7d996ef5ddab3d329e9c4a659` |
| `schemarouter-0.13.0.spdx.json` | `a1c62770a10d33cc366d487d696ed67dcf220e930cbbd087d9ca69e6a96a760d` |

Release workflow는 CI를 통과한 `main` commit만 사용합니다. wheel/sdist를 새 환경에 설치해
확인하고, SPDX SBOM과 GitHub attestation을 만들며, PyPI Trusted Publishing으로 배포한 뒤
공개 PyPI에서 다시 받은 파일의 digest까지 비교합니다.

0.14.0부터 checksum은 문서에 수동으로 옮겨 적지 않습니다. Release workflow가
`SHA256SUMS.txt`와 `release-manifest.json`을 직접 만들고 GitHub Release에 첨부합니다.
manifest에는 버전, tag, source commit, artifact 이름·크기·SHA-256이 기록됩니다.

```bash
gh attestation verify schemarouter-0.15.0-py3-none-any.whl --repo JDeun/SchemaRouter
```

## CI / Security

Release-blocking CI에는 다음이 포함됩니다.

- Python 3.10–3.14
- Windows smoke
- branch coverage
- minimum dependencies
- pyright
- wheel/sdist clean-environment acceptance
- LangChain/LangGraph/LlamaIndex
- MCP
- Jev/System-One, Laya, OpenTelemetry
- dependency audit
- strict documentation build

별도로 CodeQL, Security Audit, OpenSSF Scorecard를 실행합니다.

## Stable runtime guarantee

안정판이 보장하는 범위는 “라우팅이 언제나 정답이다”가 아니라 아래의 실행 경계입니다.

### Retrieval은 authority가 아닙니다

모델의 ranking이나 retrieval 결과만으로 새 tool, endpoint, field, credential, permission이
생기지 않습니다. 실행할 수 있는 범위는 등록된 계약과 애플리케이션의 로컬 정책이 정합니다.

### 실행 전후 검증

실행 시 다음을 확인합니다.

- argument contract
- current schema/tool fingerprint
- binding readiness
- policy / approval
- raw provider output schema
- declared field projection

### 위험 동작은 fail-closed

Mutation/destructive/unclassified remote operation을 safe read로 간주하지 않습니다.

### Schema drift는 권한을 조용히 바꾸지 않습니다

원격 schema가 바뀌면 현재 승인된 계약과 먼저 비교합니다. 호환되지 않거나 보안 의미가 달라지는
변경은 검토 없이 기존 계약을 대체하지 않습니다.

## Compatibility evidence

Scheduled/manual live compatibility matrix는 APIs.guru OpenAPI, COD OPTIMADE, Rick and Morty
GraphQL, OData.org V4, pinned OpenRPC/JSON-RPC, pinned MCP Streamable HTTP를 다룹니다.

외부 provider가 잠시 내려가는 것은 SchemaRouter 릴리스 실패로 처리하지 않습니다.

## 연구 근거의 경계

연구 결과는 안정판의 제품 보장과 별도로 기록합니다.

현재 공개된 0.14 근거 중:

- B1 controlled Qwen3-0.6B에서 SR-5 task pass 91.30%, FULL 68.48%
- SR-5 schema-token ratio 5.42%
- 같은 frozen B1 surface에서 required-route recall 100%
- structural K3는 preregistered promotion gate를 통과하지 못해 **승격되지 않음**
- 보고된 B1/K3 surface에서 unauthorized destructive execution 0

이 결과만으로 실제 운영 환경 전체에서 더 낫다고 주장하지 않습니다.

[0.14 근거 체크포인트 →](../research/0.14-paper-evidence-checkpoint.md)

## 향후 claim 원칙

공개 문서의 주장은 적어도 다음 근거 중 하나로 추적할 수 있어야 합니다.

- released artifact
- protected CI/security workflow
- versioned compatibility report
- reproducible benchmark artifact/ledger
- documented external adopter/reproduction

근거가 아직 없다면 안정판의 보장으로 쓰지 않고 roadmap이나 연구 가설로 남깁니다.

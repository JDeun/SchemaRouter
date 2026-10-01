# 신뢰성, 안정성, 공개 근거

SchemaRouter는 **stable product guarantee**, **release/process evidence**, **research evidence**를
구분합니다. 이 페이지는 마케팅 문구가 아니라 공개적으로 검증 가능한 근거의 인덱스입니다.

## 현재 안정판

| 항목 | 공개 상태 |
| --- | --- |
| 안정판 | `0.13.0` |
| 릴리스 날짜 | 2026-10-01 |
| 상태 | Beta / pre-1.0 |
| Python | 3.10–3.14 release-blocking, 3.15 preview |
| License | MIT |
| Release | [SchemaRouter 0.13.0](https://github.com/JDeun/SchemaRouter/releases/tag/v0.13.0) |
| Stable core | [Stable core](../stable-core.md) |
| Security | [SECURITY.md](https://github.com/JDeun/SchemaRouter/blob/main/SECURITY.md) |

## 공개 artifact digest

| Artifact | SHA-256 |
| --- | --- |
| `schemarouter-0.13.0-py3-none-any.whl` | `1fad74f9b0604a3a8309fe71a729670aed4c0b37be2980e00c652f702ffb4ed5` |
| `schemarouter-0.13.0.tar.gz` | `5436dfae9058504fa8ef2c56ddad57a151668bf7d996ef5ddab3d329e9c4a659` |
| `schemarouter-0.13.0.spdx.json` | `a1c62770a10d33cc366d487d696ed67dcf220e930cbbd087d9ca69e6a96a760d` |

Release workflow는 green main SHA만 사용하고, wheel/sdist clean install, SPDX SBOM, GitHub artifact
attestation, PyPI Trusted Publishing, 공개 PyPI artifact digest 재검증을 수행합니다.

```bash
gh attestation verify schemarouter-0.13.0-py3-none-any.whl --repo JDeun/SchemaRouter
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

SchemaRouter가 보장하는 것은 “항상 올바른 router”라는 문구가 아니라 더 구체적인 실행 경계입니다.

### Retrieval은 authority가 아닙니다

Model-assisted ranking이나 retrieval 결과는 tool/endpoint/field/credential/permission을 만들 수
없습니다. 실행 권한은 trusted registered contract와 local application state에서 옵니다.

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

Remote metadata가 바뀌면 accepted contract와 비교합니다. Breaking/security-relevant drift는
review 없이 기존 authority를 대체하지 않습니다.

## Compatibility evidence

Scheduled/manual live compatibility matrix는 APIs.guru OpenAPI, COD OPTIMADE, Rick and Morty
GraphQL, OData.org V4, pinned OpenRPC/JSON-RPC, pinned MCP Streamable HTTP를 다룹니다.

외부 provider uptime은 release-blocking dependency가 아닙니다.

## 연구 근거의 경계

연구 결과는 stable product guarantee와 분리됩니다.

현재 공개된 0.14 근거 중:

- B1 controlled Qwen3-0.6B에서 SR-5 task pass 91.30%, FULL 68.48%
- SR-5 schema-token ratio 5.42%
- 같은 frozen B1 surface에서 required-route recall 100%
- structural K3는 preregistered promotion gate를 통과하지 못해 **승격되지 않음**
- 보고된 B1/K3 surface에서 unauthorized destructive execution 0

이 수치를 production population 전체에 대한 우월성으로 일반화하지 않습니다.

[0.14 근거 체크포인트 →](../research/0.14-paper-evidence-checkpoint.md)

## 향후 claim 원칙

Public claim은 적어도 다음 중 하나로 추적 가능해야 합니다.

- released artifact
- protected CI/security workflow
- versioned compatibility report
- reproducible benchmark artifact/ledger
- documented external adopter/reproduction

그렇지 않으면 stable guarantee가 아니라 roadmap 또는 hypothesis로 남겨야 합니다.

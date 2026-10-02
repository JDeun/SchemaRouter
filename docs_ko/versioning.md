# 버전과 호환성

SchemaRouter released Python package는 Semantic Versioning을 따릅니다. 현재 pre-1.0이며 0.x 동안 public API가 계속 다듬어질 수 있지만 compatibility change는 의도적이고 문서화되어야 합니다.

## Development branch version

default branch는 unreleased work에 PEP 440 development version을 사용합니다. release tag는 `pyproject.toml` version과 일치해야 합니다.

releasable version이 main에 merge되면 top-level Release workflow는 일반 CI 성공을 기다리고 tested SHA가 여전히 current main인지 검증합니다. `.dev` version을 거부하고 matching release note와 dated changelog를 요구하며 tag가 없을 때만 `v<version>`을 생성합니다.

이후 exact release SHA에서 wheel/sdist를 build·clean-install·smoke-test하고 SPDX SBOM, `SHA256SUMS.txt`, `release-manifest.json`을 생성해 GitHub Release와 PyPI Trusted Publisher로 게시합니다. manifest에는 source SHA와 artifact digest가 기록됩니다.

## Public API / 0.x 정책

문서화되고 top-level package 또는 명시적 integration module에서 export된 typed contract, SchemaRouter public retrieval/planning/execution method, RunConfig/RetryPolicy/Budget/Event/Policy, documented adapter/integration은 public contract로 취급합니다. underscore-prefixed/undocumented helper는 아닙니다.

patch release는 security/correctness fail-closed invariant를 제외하면 backward-compatible해야 합니다. minor release는 pre-1.0 동안 breaking change를 포함할 수 있지만 changelog와 migration note가 필요합니다.

## Persisted SQLite 호환성

`SQLiteRegistry`, `SQLiteRunTraceStore`는 package version과 별도의 explicit storage-format contract를 가집니다. storage/document format을 metadata로 versioning하고 legacy v0를 upgrade source로 지원합니다. valid v0는 모든 document/replay invariant를 검증한 뒤 transaction에서 v1 metadata migration을 수행합니다.

unknown/newer/incomplete/corrupt version은 추측하지 않고 `StorageFormatError`로 fail-closed합니다. production에서는 upgrade 전 `schemarouter storage inspect`, 필요하면 backup을 만드는 `storage migrate`를 권장합니다.

## Deprecation과 integration

non-alpha 0.x에 등장한 API의 계획된 제거는 일반적으로 deprecation 문서화 → 최소 한 minor release 유지 → replacement/migration path → 후속 minor에서 제거 순서를 따릅니다. security-sensitive behavior는 필요하면 즉시 fail-closed할 수 있습니다.

core는 LangChain/LlamaIndex/Jev/MCP/OpenTelemetry extra 없이 동작해야 하고 integration dependency는 bounded major range를 사용하며 CI에서 supported range를 검증해야 합니다. integration은 underlying transport를 직접 호출해 SchemaRouter policy/validation을 우회하면 안 됩니다.

trade-off 우선순위는 execution authority/credential safety → schema/fingerprint correctness → deterministic plan semantics → public API compatibility → convenience입니다.

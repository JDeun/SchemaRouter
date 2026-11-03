# Release checklist

SchemaRouter alpha, beta, release candidate 또는 stable tag를 promote하기 전에 사용합니다.

## Blocking gates

- [ ] 모든 supported Python version에서 Core CI 통과
- [ ] Warning을 failure로 처리
- [ ] typed package surface static type check 통과
- [ ] 84% branch-coverage floor 통과
- [ ] minimum declared runtime dependency로 core suite 통과
- [ ] LangChain, LlamaIndex, Jev, Laya, MCP, OpenTelemetry 포함 optional integration CI 통과
- [ ] Linux Python 3.10–3.14 core CI 통과
- [ ] Windows + Python 3.14 smoke 통과
- [ ] 별도 Python 3.15 preview는 forward-compatibility signal로 검토하되 blocker는 아님
- [ ] Quickstart example 성공
- [ ] wheel/sdist build 성공
- [ ] clean environment에서 wheel/sdist 설치 및 quickstart 성공
- [ ] package metadata inspect 가능
- [ ] public trust/evidence page가 intended stable release와 changed verification limitation을 명시; per-release digest는 generated release manifest에서 가져오고 수동 복사 금지
- [ ] README/PyPI summary·keywords/docs home/release notes positioning과 stable-version language 일치
- [ ] 공개 전 [발견 가능성 체크리스트](project/discoverability.md#release-discoverability-checklist)를 검토하고 GitHub description/topics/homepage 확인
- [ ] public API change를 README/architecture docs에 반영
- [ ] CHANGELOG release entry 및 breaking migration note
- [ ] security invariant regression test
- [ ] 모든 external GitHub Action reference를 immutable 40-char SHA에 pin
- [ ] SECURITY.md가 URL/credential/retry/observability behavior와 일치
- [ ] credential/token/secret fixture/generated local state 미커밋
- [ ] MIT license metadata와 root LICENSE가 artifact에 존재
- [ ] README/docs header/favicon/brand guide가 approved SchemaRouter mark 사용
- [ ] GitHub social preview를 approved 1280×640 brand source에서 export하여 repository setting에 적용

## Compatibility gates

- [ ] 최근 공개 OpenAPI 실제 연동 스모크 테스트 통과
- [ ] 최근 공개 OPTIMADE 실제 연동 스모크 테스트 통과
- [ ] native DB adapter 변경 release는 affected representative Tier A runtime의 recent current-`main` Compatibility Smoke green
- [ ] MCP extra 포함 시 real MCP Streamable HTTP integration green
- [ ] release에 포함된 모든 extra의 optional framework/provider integration green
- [ ] merge-blocking dependency audit 통과; latest independent audit, PR/main CodeQL, OpenSSF Scorecard green 또는 triaged
- [ ] property-based OpenAPI serialization test 통과
- [ ] 교차 출처 OpenAPI 동작에 대한 명시적 로컬 승인 테스트 통과
- [ ] schema drift/stale binding test 통과
- [ ] input/output JSON Schema validation test 통과
- [ ] mutation/destructive policy test 통과
- [ ] non-read-only operation default no-retry 증명
- [ ] event payload redaction default 증명
- [ ] OpenTelemetry가 payload value/exception message를 export하지 않음 증명
- [ ] missing/denied/error approval fail closed 증명
- [ ] retry가 invocation 전 attempt/remote/cost limit 소비 증명
- [ ] adapter plugin discovery no-import 및 loading allowlist 요구 증명
- [ ] MCP credential transport-local/protected header no-override 증명
- [ ] unsupported OpenAPI semantics가 compatibility test에서 visible

## Release mechanics

- [ ] `pyproject.toml` development version을 intended release version으로 교체
- [ ] `docs/releases/<version>.md` 추가; release metadata 자동 derivation
- [ ] release commit main merge 및 normal CI green
- [ ] top-level `Release` workflow가 successful main CI event를 소비하고 tested SHA가 current main head인지 확인
- [ ] workflow는 `.dev` reject, matching release note와 dated changelog heading 요구
- [ ] 후보 태그 생성·빌드 전에 `prepare`가 기존 자격·외부 증거 원장, 명시된 검토자의 보류 PR 최신 head 승인과 현재 저장소 write/maintain/admin 권한, 해당 PR의 병합 SHA, 정확한 릴리스 SHA의 Post-merge Qualification 성공을 확인하며 API 오류는 배포를 차단
- [ ] `v<version>` 없으면 exact green main SHA에 annotated tag 생성
- [ ] tag는 있지만 GitHub release가 없으면 green current main의 ancestor이고 same version일 때만 resume
- [ ] resolved release SHA에서 unprivileged job으로 wheel/sdist build
- [ ] publication 전 두 artifact clean-install/smoke-test
- [ ] upload 전 build job에서 wheel/sdist GitHub artifact provenance attestation 생성
- [ ] SPDX JSON SBOM 생성, GitHub release attach, wheel/sdist SBOM attestation 생성
- [ ] exact built artifact에서 `SHA256SUMS.txt`, `release-manifest.json` 생성 및 attach
- [ ] GitHub release asset/PyPI artifact는 separate job publish; PyPI job만 OIDC `id-token: write`
- [ ] PyPI Trusted Publisher가 `pypi` GitHub environment로 구성됨 확인
- [ ] 모든 blocking gate green 후 package index publish
- [ ] public PyPI exact wheel/sdist download 후 trusted build와 SHA-256 byte-for-byte 검증
- [ ] GitHub Release/PyPI 성공 후 exact public version을 wheel/sdist/isolated lightweight extras(MCP,Jev,OpenTelemetry)/combined extras로 checkout 밖에서 재설치
- [ ] clean environment install/import 검증
- [ ] published artifact 최소 하나의 provenance/SPDX SBOM attestation을 GitHub CLI로 검증

보류된 후보는 기존 승인 증빙을 커밋하고 릴리스 PR을 동결한 다음, 명시된 검토자가 최종 PR head를 승인하고 병합 후 생성된 커밋을 검증합니다. 이후의 최종 결정이 `CHANGES_REQUESTED` 또는 `DISMISSED`이거나 이전 head에 대한 승인이면 배포를 차단합니다. 증빙의 `exact_head_ci_url`은 증거 참조로 유지하고 최종 병합 커밋의 검증은 별도로 확인하므로, 증빙에 자기 커밋의 미래 CI 실행 URL을 넣을 필요가 없습니다. 기존 `source_sha256`·`artifact_sha256`는 출처 증빙 역할을 유지합니다. 형식 검사로 실제 바이트를 인증하지 않으며, 승인 기록과 검토자가 해당 바이트를 식별해야 합니다. 릴리스 승인은 모델·기본값 승격 및 독립 E2 검증과 별개입니다.

## Post-release

- [ ] 게시 후 정확히 해당 버전의 PyPI 검증 작업이 wheel 및 sdist 설치, MCP/Jev/OpenTelemetry 각각의 독립 extra 설치, MCP/LangChain/LangGraph/LlamaIndex/Jev/OpenTelemetry 결합 extra 설치 조건을 모두 통과했는지 확인
- [ ] `SHA256SUMS.txt`/`release-manifest.json` GitHub Release attach 및 exact source SHA 확인
- [ ] docs example이 released package와 일치
- [ ] compatibility regression을 next patch blocker로 기록
- [ ] 가능하면 security/correctness fix를 convenience refactor와 분리

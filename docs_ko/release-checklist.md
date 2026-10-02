# Release 체크리스트

stable release 전 version/changelog/release note/docs/README/PyPI surface가 같은 version과 product boundary를 가리키는지 확인합니다. public API/compatibility/security/docs/package tests와 clean wheel/sdist consumer acceptance가 모두 통과해야 합니다.

Release workflow는 exact tested main SHA를 확인하고 wheel/sdist, SPDX SBOM, `SHA256SUMS.txt`, `release-manifest.json`을 생성합니다. manifest에는 source SHA, artifact name/size/SHA256을 기록하고 GitHub Release와 PyPI Trusted Publisher publication을 검증합니다.

optional extras, integration examples, docs navigation, social preview/metadata, release discoverability도 점검합니다. research evidence와 stable product claim은 분리하며 외부 provider outage나 미완료 연구가 package correctness gate와 혼동되지 않게 합니다.

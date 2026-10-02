# 도입 지표와 성장 scorecard

SchemaRouter는 별 수가 아니라 **검증 가능한 사용과 도입**을 성장으로 측정합니다. 마케팅 분석만을 위해 침습적인 product telemetry를 추가하지 않습니다.

## 기준선

캠페인 전 GitHub 기준선은 **2026-10-01**에 기록했습니다.

| 지표 | 기준선 |
| --- | ---: |
| GitHub stars | 1 |
| Forks | 0 |
| Subscribers | 1 |
| Network count | 0 |
| Open issues + PRs | 26 |

자동 scorecard는 PyPIStats download와 GitHub rolling 14-day traffic도 조회합니다. 이 값들은 시간창 기반 외부 데이터이므로 최초 성공한 scorecard run을 canonical baseline으로 사용합니다.

## 자동 수집

**Growth Scorecard** GitHub Actions workflow는 매주 월요일 실행되며 수동 실행도 가능합니다. GitHub repository metadata, PyPI 일/주/월 download, 권한이 있을 때 14-day views/clones, timestamp와 metric limitation을 JSON/Markdown artifact로 기록합니다.

traffic API는 별도 repository traffic 권한이 필요하므로 기본 token으로 읽지 못하면 전체 snapshot을 실패시키지 않고 `unavailable`로 기록합니다.

## 선행/후행 지표

선행 지표는 PyPI download, 가능한 경우 repository view/clone, issue로 드러난 onboarding failure, downstream이 공개한 integration/package-extra 사용 근거입니다. 후행 지표는 star/fork/subscriber, external contributor, 검증 가능한 downstream adopter/case study입니다.

star 증가만으로 product adoption을 주장하지 않습니다.

## 수동 근거가 필요한 지표

외부 repository의 SchemaRouter dependency/reference, downstream CI 사용, install-to-first-success, framework/plugin adoption, case study, independent reproduction은 검증 가능한 공개 근거가 있을 때만 추가합니다.

weekly snapshot, monthly representative artifact, campaign 전후 exact run ID, 데이터가 지원하는 경우 release별 download 비교를 사용합니다. PyPI download는 unique user가 아니고 GitHub traffic은 rolling window이며 star는 사용보다 awareness에 가깝다는 한계를 함께 해석해야 합니다.

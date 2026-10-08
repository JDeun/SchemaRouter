# 도입 지표와 성장 스코어카드

SchemaRouter는 별(star) 수만이 아니라 **검증된 사용과 도입**을 성장 지표로 봅니다. 마케팅 분석만을 위해
침습적인 제품 텔레메트리를 추가하지 않습니다.

## 기준선

캠페인 이전 GitHub 기준선은 **2026-10-01**에 기록했습니다.

| 지표 | 기준선 |
| --- | ---: |
| GitHub stars | 1 |
| Forks | 0 |
| Subscribers | 1 |
| Network count | 0 |
| Open issues + PRs | 26 |

자동 스코어카드는 PyPIStats의 패키지 다운로드 수와 GitHub의 최근 14일 traffic endpoint도 조회합니다.
이 값들은 시간 창에 따라 변하는 외부 데이터이므로 소스 코드에 추정값을 넣지 않고, 최초로 성공한
스코어카드 실행 결과를 PyPI/traffic의 정식 기준선으로 사용합니다.

## 자동 수집

**Growth Scorecard** GitHub Actions workflow는 매주 월요일 실행되며 수동 실행도 가능합니다.

다음을 기록합니다.

- GitHub stars, forks, subscribers, 열린 issue/PR, network count, topics, repository 날짜;
- 최근 일/주/월 PyPI 다운로드 수;
- token에 충분한 traffic 권한이 있을 때 최근 14일 GitHub views와 clones;
- 수집 시각과 명시적인 지표 한계.

각 실행은 JSON과 Markdown artifact를 90일간 보존하고 workflow UI에 Markdown 요약을 표시합니다.

수집기는 다음과 같습니다.

```bash
python scripts/capture_growth_scorecard.py \
  --json-out /tmp/growth-scorecard.json \
  --markdown-out /tmp/growth-scorecard.md
```

## 권한 모델

공개 GitHub repository metadata와 PyPIStats에는 비공개 텔레메트리가 필요하지 않습니다.
Repository traffic은 별도 API surface이며 GitHub는 repository traffic 접근 권한이 있는
사용자/token으로 이를 제한합니다.

따라서 workflow는 traffic을 선택적 근거로 취급합니다. 기본 `GITHUB_TOKEN`으로 읽을 수 없다면
전체 snapshot을 실패시키지 않고 artifact에 `unavailable`로 기록합니다.

Maintainer는 필요할 경우 traffic metric을 읽는 데 필요한 최소 read 권한만 가진
`SCHEMAROUTER_GROWTH_GITHUB_TOKEN` secret을 설정할 수 있습니다. Write 권한은 필요하지 않습니다.

## 선행 지표와 후행 지표

**선행 지표**

- 일/주/월 PyPI 다운로드;
- 가능한 경우 repository views와 unique visitors;
- 가능한 경우 repository clones와 unique cloners;
- issue로 확인되는 quickstart/example 실행 실패;
- downstream project가 공개한 integration/package-extra 사용 근거.

**후행 지표**

- stars;
- forks;
- subscribers;
- 외부 contributor;
- 검증 가능한 downstream adopter와 case study.

설치/도입 근거 없이 star만 증가한 경우 제품 도입으로 보고하지 않습니다.

## 근거 기반으로 수동 관리하는 지표

일부 유용한 신호에는 신뢰할 수 있고 privacy-preserving한 공개 API가 없습니다.

- SchemaRouter를 의존하거나 참조하는 외부 repository;
- downstream CI 사용;
- 설치부터 최초 성공까지의 시간;
- framework/plugin integration 도입;
- case study와 독립 재현.

이 항목들은 검증 가능한 공개 근거가 있을 때만 추가합니다. GitHub 검색 노이즈나 traffic counter에서
추론하거나 만들어내지 않습니다.

## Snapshot 주기

- **매주:** 자동 workflow snapshot.
- **매월:** 대표 workflow artifact 하나를 보존하고 #583에 중요한 변화를 요약.
- **캠페인 전/후:** 비교에 사용한 정확한 run ID를 기록.
- **릴리스별:** 데이터 소스가 해당 주장을 뒷받침할 수 있을 때만 버전별 다운로드를 비교.

## 해석상의 한계

PyPI 다운로드에는 CI와 반복 설치가 포함되며 unique user 수가 아닙니다. GitHub traffic은 최근
14일 이동 창입니다. Star는 사용량보다 인지도를 더 많이 반영합니다. 열린 issue 수에는 bug report,
research tracker, 계획 작업이 섞여 있습니다.

따라서 성장 판단은 여러 신호를 함께 사용하고, 외부 adopter 근거를 단순 counter와 분리해야 합니다.

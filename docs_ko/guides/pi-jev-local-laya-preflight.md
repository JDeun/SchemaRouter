# Native pi-jev + 무료 로컬 Laya: 점수 산정 전 프로토콜 사전 검증

목적: #1312 / #796. **호스팅 Jev 서비스도, SchemaRouter 0.14 실험도 아닙니다.**

## 소스 버전 고정과 실험 경계

- pi-jev는 `TheoOliveira/pi-jev@c5b5847aa189fe5ffec52893b7051fe8f9e7a548`의 변경 없는 체크아웃을 사용합니다.
- 공식 Laya는 `NandhaKishorM/laya@c73908d96ff73c0062c340a11bf7c54ec7d8bc4d` (`0.4.6`)입니다. `laya[serve]`, HTTP `/v1/systemone`, `GET /health`, `LAYA_JEV_STRICT=1`을 제공합니다. 체크포인트 SHA와 실제 CPU/장치 정보는 독립적으로 기록해야 합니다.
- 신규 연구에 더 이상 유지되지 않는 `stiermid/laya-serve`를 설치하지 마세요.
- 원본 pi-jev는 어휘 기반 **후보 10개 + 도구별 noul**을 사용하지만, SchemaRouter의 고정 비교 조건은 **Top-K=3**이며 직접 Laya 연동은 **단일 choice 선택**을 사용합니다. 후보 예산이 다르므로 동일 조건의 비교군이 아닙니다. 공정한 지표와 채점 프로토콜을 사전 등록하기 전까지 결과는 점수화하지 않습니다.
- `TYPESAFE_API_KEY` 및 TypeSafe SDK 비밀 키 파일을 두지 않아야 합니다. HTTP 루프백 주소만 허용하며 실제 도구는 실행하지 않습니다.

## 수동 설정: 독립된 버전 고정 체크아웃

```bash
# 공식 Laya의 고정 소스 체크아웃에서 (전용 환경 권장):
python -m pip install -e '.[serve]'
unset TYPESAFE_API_KEY TYPESAFE_BASE_URL PI_JEV_BASE_URL LAYA_API_KEY
export LAYA_HOST=127.0.0.1 LAYA_PORT=8000 LAYA_DEVICE=cpu
export LAYA_THREADS=2 LAYA_PRELOAD=0 LAYA_JEV_STRICT=1
laya-serve
# 고정된 pi-jev 소스 체크아웃에서: npm ci
# SchemaRouter에서: python scripts/external_validation_jev_contract.py --input-out /tmp/jev-input.json
# pi-jev 소스 디렉터리에서 (node --import tsx는 로컬 npm 패키지가 필요):
node --import tsx /absolute/path/to/SchemaRouter/scripts/run_pi_jev_local_laya.mjs \
 --input /tmp/jev-input.json --pi-jev-root "$PWD" \
 --output /tmp/jev-unscored.json --local-url http://127.0.0.1:8000
# 다시 SchemaRouter에서:
python scripts/external_validation_jev_contract.py --validate-output /tmp/jev-unscored.json
node --test tests/test_pi_jev_local_laya_runner.mjs
```

캐시되지 않은 체크포인트는 Hugging Face에서 가중치를 다운로드할 수 있습니다. **오프라인 재현성을 주장하기 전에 가중치를 고정하고 다운로드한 파일의 다이제스트를 기록하세요.** 로컬 소스, HF 가중치 확보, 실행 예산을 구분해야 합니다. `LAYA_PRELOAD=0`일 때 첫 요청은 예열 후 요청보다 상당히 느릴 수 있습니다. 초기 `/health` 응답만으로는 모델 적재를 입증할 수 없으므로, 실행기는 **추론 후** 상태를 다시 확인하고 실제 적재된 모델 리비전 및 관측된 장치 정보가 없으면 결과를 거부합니다.

실행기는 SchemaRouter Python 생성기로 정본 82개 도구/16개 사례 입력 전체를 다시 만들고, 카탈로그 설명·질의·다이제스트·프로토콜 필드의 변경을 거부합니다. 다이제스트 형태의 문자열만으로는 출처가 입증되지 않습니다. Python 실행 파일과 import 가능한 SchemaRouter 소스 체크아웃이 필요합니다. 실제 고정 버전 pi-jev의 `JevClient` 및 `ToolRouter`를 동적으로 불러오며, 실행되지 않는 Pi 도구 레지스트리만 모의 구현합니다. 제공자 폴백(확률 0의 대체 경로는 실제 결과가 아님), 잘못된 활성화 집합·확률·지연 시간·소스 리비전 변경·비로컬 서버를 거부합니다. 실제 도구를 실행하지 않습니다.

이 스크립트는 **수동으로 명시적으로 선택하는 사전 검증 전용**입니다. CI는 Node 보호 검사만 실행하고 실제 모델 가중치를 실행하지 않습니다. 실제 로컬 실행과 독립적인 모델 품질 평가는 아직 남아 있습니다. 0.11 실패 확인 데이터, 0.14 홀드아웃, ClicShopping 독립 사례로 튜닝하지 마세요.

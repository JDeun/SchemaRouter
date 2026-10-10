# 사용자 관점의 인수 검증

SchemaRouter는 `scripts/consumer_acceptance.py`에 소규모 종단 간 인수 테스트를 유지합니다. 단위 테스트나 어댑터 계약 테스트와는 별개입니다. 공개 패키지 인터페이스만 사용하며, 하위 애플리케이션이 설치된 wheel 또는 sdist를 사용하는 환경을 재현하도록 설계했습니다.

이 테스트는 다음 운영 경계를 검증합니다.

- 일반 Python 도구의 계획 수립과 실행
- 기본적인 데이터 변경 거부 및 신뢰된 승인 게이트
- 스키마 변경과 invoker 바인딩 변경을 안전하게 거부하는 동작
- 런타임 출력 JSON Schema 검증
- 읽기 전용 작업의 재시도 동작과 실행 시간 예산
- SQLite 레지스트리의 영속성
- 민감 정보를 가린 실행 추적 기록의 영속성
- 읽기 전용 상태 검사와 대시보드 생성
- 영속 SQLite 아티팩트에 대한 설치된 `schemarouter inspect`와 `schemarouter dashboard` CLI 실행

로컬에서 실행하는 명령:

```bash
python scripts/consumer_acceptance.py
```

기계 판독 가능한 결과 보고서를 보관하려면:

```bash
python scripts/consumer_acceptance.py --json-out artifacts/consumer-acceptance.json
```

## CI 검증 범위

동일한 스크립트를 지원되는 Linux Python 매트릭스, Windows 스모크 테스트, 최소 의존성 작업, 그리고 깨끗한 wheel·sdist 가상환경에서 다시 실행합니다.

패키징 CI 작업은 빌드한 wheel을 `mcp`, `langchain`, `langgraph`, `llamaindex`, `jev`, `otel` 등 경량 선택적 추가 의존성과 함께 설치합니다. MCP, Jev, OpenTelemetry에서는 네트워크를 사용하지 않는 SDK·임포트 스모크 테스트를 진행하고 LangChain, LangGraph, LlamaIndex의 실행 가능한 예제를 실행합니다.

이어 종단 간 예제에서 만든 SQLite 레지스트리와 추적 기록 아티팩트를 대상으로 설치된 검사 CLI를 실행합니다. 출력 JSON을 검증하고 설치된 콘솔 스크립트로 대시보드를 내보냅니다. 이는 편집 가능한 설치 환경에서는 발견하기 어려운 패키지 메타데이터, 선택적 의존성, CLI 엔트리 포인트의 회귀 결함을 탐지합니다. Laya의 PyTorch 의존성은 별도로 관리하므로 전용 CPU 통합 작업에서 검증합니다.

공개 OpenAPI 및 OPTIMADE 호환성 스모크 테스트는 외부 서비스에 의존하므로 별도로 유지합니다. 이 검사에서는 현재 소스 트리를 편집 가능 모드가 아닌 방식으로 설치하고 `pip check`를 실행한 뒤 공개 서비스를 호출하며 기계 판독 가능한 아티팩트를 보존합니다. 이러한 검사는 결정론적 패키지 인수 테스트의 필수 게이트로 취급하지 않습니다.

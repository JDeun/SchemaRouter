# 계약을 고려한 대체 경로 적격성

대체 경로의 적격성은 호스트 권한 부여, 접근 방법 상태, 기능 계약 검증, 계약 변경, 타입이 정의된 상태의 적격성, 검색 결과 포함 여부를 함께 평가할 수 있습니다.

```python
from schemarouter import evaluate_fallback_eligibility

result = evaluate_fallback_eligibility(
    authorized=True,
    healthy=True,
    contract_validation=validation,
)
```

전송 계층이 정상이어도 선언된 계약이 없거나, 호환되지 않거나, 검증할 수 없거나, 변경된 경우 해당 경로를 제외할 수 있습니다. `eligible_fallback_ids()`는 호스트가 전달한 순서대로 **이미 평가된 후보**를 필터링할 뿐 직접 실행하지 않습니다.

이전 버전과의 호환성도 명시적입니다. 계약 및 상태 메타데이터를 제공하지 않으면 기존의 권한 확인과 상태 검사 동작을 유지합니다. 호스트의 거부 판단은 언제나 우선하며 대체 경로가 권한을 확대할 수 없습니다. SchemaRouter는 적격성 및 후보 정보만 반환하며 실제 실행, 변환, 재시도, 응답 처리는 호스트가 담당합니다.

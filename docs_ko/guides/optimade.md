# OPTIMADE

OPTIMADE는 서로 다른 재료 데이터베이스 사이의 상호운용성을 위한 표준 API입니다. SchemaRouter는 공급자마다 별도의 사용자 정의 통합을 만드는 대신 OPTIMADE를 일급 프로토콜 어댑터로 지원합니다.

어댑터는 표준 탐색 모델을 따릅니다.

```text
base URL
  -> /v1/info
  -> available entry types
  -> /v1/info/<entry_type>
  -> properties / units / output fields
  -> ToolSpec
```

## 공급자 연결하기

```python
from schemarouter import PlanRequest, SchemaRouter

router = await SchemaRouter.from_url(
    "https://www.crystallography.net/cod/optimade",
    kind="optimade",
)
```

버전이 없는 공급자 루트와 이미 버전이 포함된 `.../v1` 기본 주소를 모두 지원합니다.

## 탐색된 엔드포인트

사용할 수 있는 항목 유형(entry type)마다 SchemaRouter가 읽기 전용 엔드포인트를 생성합니다.

```text
search_structures
get_structures
search_references
get_references
...
```

항목 정보 문서에서 유효한 스키마를 제공하면 해당 공급자 고유의 항목 유형과 속성도 보존합니다.

## 검색

```python
results = await router.ainvoke(
    PlanRequest(
        query="chemical formula",
        arguments={
            "filter": 'elements HAS ALL "Si","O" AND nelements=2',
            "page_limit": 5,
        },
    )
)
```

어댑터가 노출하는 표준 쿼리 파라미터에는 다음 항목이 포함됩니다.

- `filter`
- `page_limit`
- `sort`
- `include`
- `page_offset`
- `page_number`
- `page_cursor`
- `email_address`

## 필드를 인식하는 실행

OPTIMADE에는 프로토콜 자체에 필드 투영 기능이 있어 SchemaRouter의 구조와 잘 맞습니다.

계획 단계에서 다음 필드를 선택하면

```text
id
chemical_formula_descriptive
nelements
```

호출 정보를 인식하는 invoker가 다음 값을 전송합니다.

```text
response_fields=chemical_formula_descriptive,nelements
```

OPTIMADE가 리소스 객체 수준에서 요구하는 `id`와 `type`은 정규화된 결과에 계속 포함됩니다.

반환된 JSON:API 리소스는 다음 형태에서

```json
{
  "id": "123",
  "type": "structures",
  "attributes": {
    "chemical_formula_descriptive": "O2Si",
    "nelements": 2
  }
}
```

다음 형태로 정규화됩니다.

```json
{
  "id": "123",
  "type": "structures",
  "chemical_formula_descriptive": "O2Si",
  "nelements": 2
}
```

이 정규화는 SchemaRouter의 출력 검증 전에 이루어집니다.

## 공급자 고유의 필드

`/info/<entry_type>`를 통해 노출되는 속성은 일반적인 `FieldSpec` 객체가 됩니다. `x-optimade-unit` 등의 OPTIMADE 단위 메타데이터는 `FieldSpec.unit`으로 보존합니다.

선언된 딕셔너리 목록 속성은 레코드 구조를 보존하는 항목 필드를 노출합니다. 예를 들어 `trajectories[].energy`는 내부적으로 `["trajectories", "*", "energy"]` 경로를 사용합니다. 전송 요청에는 공급자 최상위 필드인 `response_fields=trajectories`만 사용하며, 목록을 병렬 배열로 변환하지 않고 로컬에서 항목별 필드 투영을 수행합니다.

따라서 공급자 고유의 밴드갭이나 생성 에너지 같은 필드도 표준 필드와 동일한 플래너 및 증거 처리 로직에 참여할 수 있습니다.

## 안전 경계

- OPTIMADE 엔드포인트는 읽기 전용으로 분류합니다.
- 인덱스 메타 데이터베이스를 실행 가능한 항목 데이터베이스로 조용히 취급하지 않습니다.
- URL을 구성하기 전에 항목 유형 경로 구간을 검증합니다.
- 런타임 리디렉션을 비활성화합니다.
- 탐색 응답과 데이터 응답에는 엄격한 바이트 제한을 적용합니다.
- 런타임 헤더는 모델이 선택하는 인자 밖에 유지합니다.

## 현재 지원 범위

v0.2는 구체적인 OPTIMADE 공급자 데이터베이스와 표준 항목 목록·단일 항목 조회 의미 체계를 지원합니다.

추후 확장 대상으로 남겨 둔 기능은 다음과 같습니다.

- 인덱스 메타 데이터베이스 순회와 공급자 연합
- 임의의 자연어를 OPTIMADE 필터 표현식으로 자동 컴파일하는 기능
- 공급자 간 정규화 및 결과 병합
- 공급자 상태 점수화와 폴백

프로토콜의 의미 체계는 [OPTIMADE 공식 명세](https://www.optimade.org/specification/latest/)를 참고하십시오.

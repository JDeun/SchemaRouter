# OPTIMADE

OPTIMADE는 상호운용 가능한 재료 데이터베이스를 위한 표준 API입니다. SchemaRouter는 provider별 custom integration 대신 first-class protocol adapter로 지원합니다.

```text
base URL
  -> /v1/info
  -> available entry types
  -> /v1/info/<entry_type>
  -> properties / units / output fields
  -> ToolSpec
```

## Provider 연결

```python
from schemarouter import PlanRequest, SchemaRouter

router = await SchemaRouter.from_url(
    "https://www.crystallography.net/cod/optimade",
    kind="optimade",
)
```

version이 없는 provider root와 이미 version이 붙은 `.../v1` base를 모두 지원합니다.

## 탐색되는 endpoint

사용 가능한 각 entry type마다 `search_structures`, `get_structures`, `search_references`, `get_references` 같은 read-only endpoint를 만듭니다. entry-info 문서가 유효한 schema를 제공하면 provider-specific entry type/property도 보존합니다.

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

표준 query parameter에는 `filter`, `page_limit`, `sort`, `include`, `page_offset`, `page_number`, `page_cursor`, `email_address`가 포함됩니다.

## Field-aware 실행

planning에서 `id`, `chemical_formula_descriptive`, `nelements`를 선택하면 call-aware invoker는 `response_fields=chemical_formula_descriptive,nelements`를 전송합니다. OPTIMADE resource-object 규칙 때문에 `id`, `type`은 normalized result에 유지됩니다.

provider-specific property도 일반 `FieldSpec`이 되며 `x-optimade-unit` 같은 unit metadata는 `FieldSpec.unit`으로 보존됩니다. list-of-dictionary property는 record-preserving item field를 사용하고 wire request에는 provider의 top-level `response_fields`만 보냅니다.

## 안전 경계

- OPTIMADE endpoint는 read-only로 분류
- index meta-database를 실행 가능한 entry database로 자동 취급하지 않음
- URL 생성 전 entry-type path segment 검증
- runtime redirect 비활성화
- discovery/data response byte limit 적용
- runtime header를 model-selected argument와 분리

## 현재 범위

현재 concrete OPTIMADE provider database와 표준 entry-list/single-entry semantics를 지원합니다. index meta-database traversal/federation, 자연어→OPTIMADE filter 자동 컴파일, cross-provider normalization/merging 등은 별도 확장 영역입니다.

프로토콜 semantics는 [OPTIMADE 공식 명세](https://www.optimade.org/specification/latest/)를 참고하세요.

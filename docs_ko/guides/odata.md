# OData

SchemaRouter는 OData v4 CSDL metadata를 수집해 entity set을 canonical typed capability로 컴파일할 수 있습니다.

## 서비스 등록

service root 또는 `$metadata` URL을 전달합니다.

```python
router = await SchemaRouter.from_url(
    "https://service.example/odata",
    kind="odata",
)
```

CSDL metadata에서 entity type, complex type, entity key, entity set을 가져옵니다.

## Entity set → read endpoint

`Products` 같은 entity set은 `list_products` 같은 read-only endpoint가 됩니다. 표준 제한 query control은 typed parameter로 노출됩니다.

- `filter` → `$filter`
- `orderby` → `$orderby`
- `top` → `$top`
- `skip` → `$skip`

write operation/action은 자동 허용되지 않습니다.

## Native field projection

OData의 `$select`를 server-side projection으로 사용합니다. plan이 `ID`, `Address.City`를 요청하면 transport는 `$select=ID,Address/City`를 전송하고, SchemaRouter는 반환된 `value[]` collection의 각 object를 projection하면서 record alignment를 유지합니다.

complex property는 planner에서 dotted identity를 사용하고 provider selector에서는 OData slash notation을 사용합니다. complex value collection도 다른 adapter와 동일한 record-preserving array-item contract를 사용하므로 여러 child field를 서로 무관한 parallel array로 평탄화하지 않습니다.


```text
ID
Address.City
```

```text
$select=ID,Address/City
```

## Type과 unit contract

일반적인 `Edm.*` primitive를 JSON Schema로 매핑합니다. entity key는 identifier field, complex type은 nested object schema가 됩니다.

선언된 structured CSDL measure annotation도 보존합니다. 특히 `Org.OData.Measures.V1.Unit`, `Org.OData.Measures.V1.ISOCurrency` 값은 `FieldSpec.unit`이 됩니다.

SchemaRouter는 이 label에서 물리 차원이나 변환 계수를 추론하지 않습니다. normalization contract는 신뢰된 local enrichment가 담당합니다.

## Credential과 보안

schema-fetch credential과 runtime credential은 분리합니다.

```python
router = await SchemaRouter.from_url(
    "https://service.example/odata",
    kind="odata",
    schema_headers={"Authorization": schema_token},
    trusted_headers={"Authorization": runtime_token},
)
```

어느 credential도 planner-visible contract에 들어가지 않습니다. entity-set read는 명시적으로 read-only이고 action/write는 자동 활성화하지 않으며, redirect를 자동 추적하지 않고 metadata/result 크기를 제한합니다. XML parsing 전 DTD/entity declaration을 거부하며 일반 SchemaRouter validation/fingerprint/health/fallback/drift 규칙도 그대로 적용합니다.

## 범위

초기 first-class adapter는 entity-set read, complex property, paging/query control, structured unit annotation, `$select`를 지원합니다. function/action과 더 풍부한 OData query semantics는 canonical planner model을 바꾸지 않고 점진적으로 추가할 수 있습니다.

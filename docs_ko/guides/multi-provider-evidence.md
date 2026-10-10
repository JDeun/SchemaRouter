# 다중 제공자 검색 및 근거 집계

SchemaRouter는 흔히 혼동되는 두 결정을 분리합니다:

1. **Retrieval:** 한 provider로 충분한지, 독립 provider들을 조회해야 하는지
2. **Aggregation:** 반환 record가 한 entity의 중복 설명인지, 별도로 보존해야 하는 독립 observation인지

## Retrieval mode

`PlanRequest.retrieval_mode="coverage"`가 기본값입니다. planner는 중복 호출을 최소화하고 필요한 semantic-field coverage를 추가하는 경우에만 추가 route를 선택합니다.

`PlanRequest.retrieval_mode="corroborate"`는 `max_calls`까지 요청 semantic field를 지원하는 서로 다른 provider를 계속 선택합니다. 같은 provider의 endpoint는 독립 corroboration으로 계산하지 않습니다. 두 번째 provider는 선택 field의 semantic identity/name, datatype contract, qualifier, unit이 호환될 때만 corroborating evidence로 인정됩니다.

따라서 cost가 명시적입니다. application이 의도적으로 fan-out을 선택하며 우연히 발생하지 않습니다.

## Aggregation

provider result를 `SourceRecord` object로 normalize한 뒤 `aggregate_records()`를 사용합니다.

### Scientific observation

`material`과 `chemical` entity는 기본적으로 `preserve_observations`를 사용합니다. 다른 provider가 동일 semantic field를 제공한다는 이유만으로 density, band gap, lattice parameter, molecular property 등의 값을 버리지 않습니다.

각 observation은 다음을 보존합니다:

- provider
- value
- unit
- method, temperature, phase, calculation context 등의 qualifier
- provenance metadata

value, unit, qualifier가 모두 일치할 때만 agreement를 보고합니다. 따라서 서로 다른 context를 조용히 동일한 확인 측정으로 취급하지 않습니다.

### Literature와 metadata

`document`와 `generic` entity는 기본적으로 `deduplicate`를 사용합니다. 동일한 trusted canonical identifier를 가진 record는 하나의 entity로 묶지만 provider observation은 audit용으로 계속 사용할 수 있습니다.

document identity는 현재 DOI를 우선하고 이어 PMID, PMCID, arXiv identifier를 사용합니다. DOI URL과 `doi:` prefix는 비교 전에 normalize됩니다.

material/chemical identity는 retrieval matching보다 엄격합니다. `SiO2`, `C2H6O` 같은 formula는 candidate provider 탐색에는 유용하지만 반환된 두 record가 동일 structure/compound를 설명한다는 증거로는 충분하지 않습니다. material record에는 `material_id`, `structure_id`, `structure_hash`, `crystal_id` 같은 명시적 material/structure identity가 필요하며 chemical record는 InChIKey, InChI, canonical/isomeric SMILES, CID 같은 structural identifier를 사용합니다. formula-only record는 별도 entity로 유지됩니다.

SchemaRouter는 title이나 name이 비슷해 보인다는 이유만으로 record를 merge하지 **않습니다**. application은 별도의 fuzzy entity-resolution 단계를 수행할 수 있지만 불확실한 match가 자동으로 trusted canonical identity가 되어서는 안 됩니다.

## 예제

```python
from schemarouter import PlanRequest, SourceRecord, aggregate_records

request = PlanRequest(
    query="GaAs density",
    concepts=["density"],
    retrieval_mode="corroborate",
    max_calls=3,
)

records = [
    SourceRecord(
        provider="materials-project",
        entity_kind="material",
        identifiers={"structure_id": "gaas-zincblende"},
        fields={"density": 5.32},
        field_units={"density": "g/cm^3"},
        qualifiers={"method": "computed"},
    ),
    SourceRecord(
        provider="cod",
        entity_kind="material",
        identifiers={"structure_id": "gaas-zincblende"},
        fields={"density": 5.41},
        field_units={"density": "g/cm^3"},
        qualifiers={"method": "experimental"},
    ),
]

entity = aggregate_records(records)[0]
assert len(entity.fields["density"].observations) == 2
assert entity.fields["density"].agreement is False
```

literature에서는 Crossref와 OpenAlex의 동일 DOI를 duplicate context가 아닌 하나의 canonical document entity로 만들며 provider-specific metadata와 provenance는 계속 검사할 수 있습니다.

## 경계

SchemaRouter는 충돌하는 scientific value 중 하나를 truth로 결정하지 않습니다. 대신 downstream domain policy/application이 명시적으로 판단하는 데 필요한 routing, identity, provenance, unit/context, conflict structure를 제공합니다.

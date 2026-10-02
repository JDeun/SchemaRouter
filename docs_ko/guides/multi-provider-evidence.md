# Multi-provider evidence

여러 provider가 같은 semantic field를 제공할 때 SchemaRouter는 source identity와 provenance를 보존한 채 corroboration/aggregation을 구성할 수 있습니다. 서로 다른 access mode가 같은 provider를 가리키는 경우와 독립 provider는 구분합니다.

cross-provider 비교는 semantic ID, datatype, unit/normalization, qualifier, identifier contract가 명시적으로 호환될 때만 수행합니다. fuzzy entity identity나 scientific truth adjudication은 core가 추론하지 않습니다.

결과는 provider별 observation과 provenance를 유지해야 하며 agreement/disagreement를 숨겨 하나의 값으로 합성하지 않습니다. evidence requirement는 selected field 전체에 적용되고 executor가 현재 trusted schema에서 다시 검증합니다.

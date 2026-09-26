# Multi-provider retrieval and evidence aggregation

SchemaRouter separates two decisions that are often conflated:

1. **Retrieval:** should one provider be enough, or should independent providers be queried?
2. **Aggregation:** are returned records duplicate descriptions of one entity, or independent observations that must remain distinct?

## Retrieval modes

`PlanRequest.retrieval_mode="coverage"` is the default. The planner minimizes redundant calls and selects additional routes only when they add required semantic-field coverage.

`PlanRequest.retrieval_mode="corroborate"` keeps selecting distinct providers that cover the requested semantic fields, up to `max_calls`. Endpoints declared under the same provider do not count as independent corroboration. A second provider is accepted as corroborating evidence only when the selected fields are semantically compatible: semantic identity/name, datatype contract, qualifiers, and units must be compatible.

This makes cost explicit: applications opt into fan-out instead of receiving it accidentally.

## Aggregation

Use `aggregate_records()` after provider results have been normalized into `SourceRecord` objects.

### Scientific observations

`material` and `chemical` entities default to `preserve_observations`. A density, band gap, lattice parameter, molecular property, or other value is not discarded merely because another provider exposes the same semantic field.

Each observation keeps:

- provider;
- value;
- unit;
- qualifiers such as method, temperature, phase, or calculation context;
- provenance metadata.

Agreement is reported only when value, unit, and qualifiers agree. Different contexts are therefore not silently treated as confirming measurements.

### Literature and metadata

`document` and `generic` entities default to `deduplicate`. Records with the same trusted canonical identifier are grouped into one entity, while provider observations remain available for audit.

Document identity currently prefers DOI, then PMID, PMCID, and arXiv identifiers. DOI URLs and `doi:` prefixes are normalized before comparison.

Material and chemical identity is intentionally stricter than retrieval matching. A formula such as `SiO2` or `C2H6O` may be useful for finding candidate providers, but it is not sufficient to prove that two returned records describe the same structure or compound. Material records require an explicit material/structure identity such as `material_id`, `structure_id`, `structure_hash`, or `crystal_id`; chemical records use structural identifiers such as InChIKey, InChI, canonical/isomeric SMILES, or CID. Formula-only records remain separate entities.

SchemaRouter deliberately does **not** merge records solely because titles or names look similar. Applications may perform a separate fuzzy entity-resolution step, but an uncertain match should not become a trusted canonical identity automatically.

## Example

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

For literature, the same DOI from Crossref and OpenAlex becomes one canonical document entity rather than duplicate context, while provider-specific metadata and provenance remain inspectable.

## Boundary

SchemaRouter does not decide that one conflicting scientific value is the truth. It provides the routing, identity, provenance, unit/context, and conflict structure required for a downstream domain policy or application to make that decision explicitly.

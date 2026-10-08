# OPTIMADE

OPTIMADE는 interoperable materials database를 위한 표준 API입니다. SchemaRouter는 각 provider를 별도의 custom integration으로 취급하지 않고 first-class protocol adapter로 지원합니다.

The adapter follows the standard discovery model:

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

Both an unversioned provider root and an already versioned `.../v1` base are supported.

## 발견된 endpoint

For each usable entry type, SchemaRouter creates read-only endpoints:

```text
search_structures
get_structures
search_references
get_references
...
```

Provider-specific entry types and properties are preserved when their entry-info documents expose
valid schemas.

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

The standard query parameters exposed by the adapter include:

- `filter`
- `page_limit`
- `sort`
- `include`
- `page_offset`
- `page_number`
- `page_cursor`
- `email_address`

## Field-aware execution

OPTIMADE is especially well aligned with SchemaRouter because it has protocol-native field
projection.

If planning selects:

```text
id
chemical_formula_descriptive
nelements
```

the call-aware invoker sends:

```text
response_fields=chemical_formula_descriptive,nelements
```

`id` and `type` remain part of the normalized result because OPTIMADE requires them at the
resource-object level.

The returned JSON:API resource is normalized from:

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

to:

```json
{
  "id": "123",
  "type": "structures",
  "chemical_formula_descriptive": "O2Si",
  "nelements": 2
}
```

before SchemaRouter output validation.

## Provider-specific fields

Properties exposed through `/info/<entry_type>` become normal `FieldSpec` objects. OPTIMADE unit
metadata such as `x-optimade-unit` is preserved as `FieldSpec.unit`.

Declared list-of-dictionary properties expose record-preserving item fields. For example,
`trajectories[].energy` uses `["trajectories", "*", "energy"]` internally. The wire request still
uses only the provider's top-level `response_fields=trajectories`; item projection happens locally
without converting the list into parallel arrays.

This means fields such as provider-specific band gaps or formation energies can participate in the
same planner and evidence logic as standard fields.

## Safety boundaries

- OPTIMADE endpoints are classified read-only.
- Index meta-databases are not silently treated as executable entry databases.
- Entry-type path segments are validated before URL construction.
- Runtime redirects are disabled.
- Discovery responses and data responses have hard byte limits.
- Runtime headers stay outside model-selected arguments.

## Current scope

v0.2 supports concrete OPTIMADE provider databases and standard entry-list/single-entry semantics.

Deferred extensions include:

- traversing index meta-databases and provider federation;
- automatically compiling arbitrary natural language into OPTIMADE filter expressions;
- cross-provider normalization/merging;
- provider health scoring and fallback.

See the official [OPTIMADE specification](https://www.optimade.org/specification/latest/) for the
protocol semantics.

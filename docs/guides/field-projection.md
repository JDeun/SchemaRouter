# Field projection

SchemaRouter validates the full raw tool output before applying any projection. Projection therefore
cannot hide an invalid response.

## Top-level fields

The default field contract remains unchanged:

```python
from schemarouter import FieldSpec

FieldSpec(name="temperature")
```

With no explicit path, the field projects the top-level key with the same name.

## Nested object fields

Use `FieldSpec.path` when the logical field ID should map to a nested JSON object path:

```python
FieldSpec(
    name="display_name",
    path=["user", "profile", "name"],
    aliases=["name", "profile name"],
)
```

The logical ID remains `display_name`. A plan selects that declared ID rather than supplying an
arbitrary JSONPath:

```python
call.fields == ["display_name"]
```

Given this raw response:

```json
{
  "user": {
    "id": "42",
    "profile": {
      "name": "Ada",
      "address": {
        "city": "Seoul",
        "secret": "internal"
      }
    }
  }
}
```

the projected result preserves the declared object shape:

```json
{
  "user": {
    "profile": {
      "name": "Ada"
    }
  }
}
```

## Security boundary

`FieldSpec.path` is trusted schema metadata. It is not model-produced execution authority.

SchemaRouter:

- accepts only declared logical field IDs in `ToolCall.fields`;
- rejects forged path strings that are not declared field IDs;
- rejects duplicate or ancestor/descendant-overlapping declared paths;
- validates the full raw output schema before extracting nested values;
- copies projected values so consumers cannot mutate the original invoker result through the
  projection result;
- forces local projection when explicit nested paths are present, even if a call-aware invoker
  advertises transport-level field projection.

## Planner behavior

Planner matching considers the logical field name, aliases, and explicit path segments. The emitted
`ToolCall.fields` still contains only logical field IDs.

This keeps transport/schema representation separate from the bounded decision surface.

## Array-item fields

Array traversal is explicit and record-preserving. Use the reserved `"*"` path segment only in
trusted `FieldSpec.path` / `result_path` metadata:

```python
FieldSpec(
    name="results[].title",
    path=["results", "*", "title"],
    result_path=["results", "*", "title"],
    json_schema={"type": "string"},
)
```

Selecting both `results[].title` and `results[].url` preserves each source record:

```json
{
  "results": [
    {"title": "A", "url": "https://a.example"},
    {"title": "B"}
  ]
}
```

SchemaRouter does not flatten those children into independent arrays because that could destroy
row/entity alignment. Missing optional children remain missing in the corresponding record.

Wildcard array paths have stricter invariants:

- the source path must declare an explicit `result_path`;
- source and result paths must contain wildcards at the same positions;
- wildcards traverse only declared JSON Schema arrays;
- server-projected schemas are narrowed through array `items`;
- unit normalization and selected-field validation operate per preserved record;
- selecting the parent array does not implicitly select every descendant.

The `"*"` segment is an internal typed path marker, not arbitrary JSONPath syntax supplied by a
model.

## Current scope

Explicit paths support nested objects and explicit record-preserving array-item traversal. General
JSONPath expressions, filters, slices, and inferred wildcard traversal remain unsupported.

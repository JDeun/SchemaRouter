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

## Current scope

Explicit paths currently traverse nested JSON objects. Array-element projection and wildcard/JSONPath
semantics are intentionally not inferred. Those require a separate typed contract rather than
special string syntax.

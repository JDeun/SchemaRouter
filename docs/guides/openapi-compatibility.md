# OpenAPI compatibility report

SchemaRouter imports a deliberately bounded OpenAPI subset. Unsupported semantics should be visible,
not silently reinterpreted.

Every imported OpenAPI `ToolSpec` now contains a machine-readable report at:

```python
tool.metadata["compatibility"]
```

You can also inspect a document before registration:

```python
from schemarouter import analyze_openapi_compatibility

report = analyze_openapi_compatibility(document)

print(report.status)
for issue in report.issues:
    print(issue.support, issue.construct, issue.location, issue.message)
```

## Status values

- `supported` — no known compatibility limitation was detected for the imported surface;
- `partial` — at least one construct is preserved or only partially interpreted;
- `unsupported` — the document contains operations but none can be imported safely.

The report also includes total/importable operation counts and issue counts.

## Constructs reported explicitly

The current analyzer reports, among other cases:

- unresolved cross-document `$ref` targets (bounded same-origin resolution is available only by
  explicit URL-ingestion opt-in; same-document URI refs are normalized automatically);
- `allOf`, `oneOf`, and `anyOf`;
- recursive local component references;
- OpenAPI 3.0 `nullable`;
- discriminators;
- cookie parameters;
- multiple request/response content types;
- non-JSON request or response bodies;
- non-object JSON request bodies;
- callbacks and webhooks;
- server variables;
- operation security requirements.

Some constructs are marked `partial` because the full JSON Schema is retained for runtime
validation even when planner-side interpretation is intentionally bounded. For `allOf`,
SchemaRouter now flattens object properties and required fields when safely derivable, but does not
claim complete support for every JSON Schema composition interaction.

## Why this is separate from parsing

A parser can successfully create a `ToolSpec` while still losing semantics that matter to a
caller. Compatibility reporting therefore answers a different question:

> "What did SchemaRouter understand faithfully, and what requires explicit application review?"

When bounded external-ref resolution succeeds, those references are rewritten into local bundle
pointers before this report is produced and therefore no longer appear as `external_ref` issues.

Do not treat a `partial` report as an error automatically. Instead, inspect the reported
constructs and decide whether they affect the operations your application intends to expose.

# Tool and endpoint contracts

The schema model is deliberately explicit.

```text
ToolSpec
  └─ EndpointSpec
       ├─ ParameterSpec
       ├─ FieldSpec
       ├─ input_schema
       └─ output_schema
```

## ToolSpec

A `ToolSpec` groups related operations. A namespace can disambiguate tools from different sources.

```python
ToolSpec(
    name="materials",
    namespace="lab",
    endpoints=[...],
)
```

The registry key becomes `lab.materials`.

## EndpointSpec

An endpoint represents one callable operation. Depending on the adapter it may represent:

- an OpenAPI operation;
- an MCP tool;
- a Python callable;
- an approved documentation-derived endpoint.

Endpoint identity carries method/path metadata, side-effect classification, parameter contracts,
output contracts, and a schema fingerprint.

## ParameterSpec

Parameters distinguish **logical argument keys** from wire representation. This matters for OpenAPI
operations where the same wire name can legally exist in multiple locations.

For example, collisions can be represented as:

```text
path__id   -> path parameter "id"
query__id  -> query parameter "id"
header__id -> header parameter "id"
body__id   -> JSON body field "id"
```

The planner and executor work with the logical key; the transport writes the original wire name.

## FieldSpec

Top-level output fields are used by the planner for response projection. The complete output JSON
Schema remains available for raw response validation, including nested structures and local refs.

## Fingerprints

Endpoint and tool fingerprints are canonical hashes of executable schema contracts. Descriptive
metadata is excluded from the fingerprint.

A stale plan cannot execute against a different endpoint fingerprint, and a stale invoker binding
cannot execute after its tool contract is replaced.

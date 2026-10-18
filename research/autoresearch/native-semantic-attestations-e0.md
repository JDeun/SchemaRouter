# Host-pinned semantic ontology ingress E0 — real adapter source contract

Tracks [#1556](https://github.com/JDeun/SchemaRouter/issues/1556),
original [#1530](https://github.com/JDeun/SchemaRouter/issues/1530),
actual OpenAPI/MCP/OPTIMADE parser boundary [#1546](https://github.com/JDeun/SchemaRouter/pull/1546),
native G3 [#1548](https://github.com/JDeun/SchemaRouter/pull/1548),
and product FieldGroup pre-K [#1550](https://github.com/JDeun/SchemaRouter/pull/1550).

## A source-native metadata gap, not a reason to hallucinate semantics

The earlier published 13-tool Qwen3/E5 synthetic DEV fixture
`evaluate_authorized_e5_hybrid_cpu_dev.build_source_router` registered
only operation IDs and prose descriptions — no native output fields,
typed inputs, semantic IDs, or reviewed source/licensing. Applying the
typed FieldGroup search to this fixture cannot honestly find verified
output fields. Filling field schemas from expected benchmark answers
would leak the evaluation gold. This change intentionally **refuses**
semantic mapping to nonexistent source fields rather than reporting
fictional recall.

## Exact host-approved contract

`HostSemanticAttestation` pins the **entire original ToolSpec fingerprint**,
full source key, source_type, license and a human-identified local reviewer.
Every `HostSemanticMapping` pins its original native endpoint
fingerprint, member kind (existing output FieldSpec or existing input
ParameterSpec), exact native member name and a bounded semantic ID.

`apply_host_semantic_attestation(source_tool, attestation=...)` returns a
new fully validated ToolSpec with only `semantic_id` added to
already-present, exact scalar `{"type":"..."}` members. It never
adds fields, parameters, evidence, output values, conversions, license
permission, execution metadata, `read_only` or destructive authority,
or changes the original ToolSpec. The annotated fingerprint changes
intentionally; register that new tool explicitly through existing
trusted host registration and revoke/re-review on a provider revision.

Offline E0 exercises real production OpenAPI, MCP and OPTIMADE converter
outputs, refuses remote MCP `readOnlyHint` authority, field/parameter
invention, unsupported nested/pattern constraints, source/endpoint
revision drift, missing source license, conflicting ontology, invalid
semantic IDs and duplicate mappings.

**Important trust assumption:** this is an in-process *structural*
attestation guard. `reviewed_by` and `license` are **host-supplied**
metadata, not cryptographic evidence of reviewer identity, permission
or legal reuse rights. A malicious caller with full host code execution
is outside this trust boundary. No inference or external network call
authorizes the mapping.

## Intended future evidence

- Gather independently approved native source schemas with truthful
  typed fields, source revisions, permission/field gold and original
  EN/KO/JA task text before any external validation.
- Then benchmark same-authority lexical vs host-approved semantic K5,
  include both single-endpoint FieldGroups and G3 typed source→consumer
  graph candidates. Report explicit missing coverage and OOD negatives.
- The next independent step is *not* to invent 13 source-field schemas
  from disclosed Qwen3 DEV task gold, call this a real generalization
  success, or default-enable any model/graph.
- Independent #1346 and real agent/provider #1477 remain blocked;
  frozen #432 outcome and v0.18 #1356 HARD HOLD unchanged.

# Source-declared input parameter semantic identity (research qualification)

Issue [#1542](https://github.com/JDeun/SchemaRouter/issues/1542);
architectural source [#1530](https://github.com/JDeun/SchemaRouter/issues/1530),
[initial paper](https://arxiv.org/abs/2608.21375).

The product's `ParameterSpec` previously contained a name, aliases, required
flag and JSON schema, but no canonical **input field semantic ID**.
Thus graph G1/G2 [#1539](https://github.com/JDeun/SchemaRouter/pull/1539),
[#1541](https://github.com/JDeun/SchemaRouter/pull/1541)
rely on separately host-declared parameter-semantic bindings; they must
never infer them from coincidentally equal native parameter names.

## Additive model contract

- `ParameterSpec.semantic_id: str | None = None` expresses a **trusted
  source-owner-declared ontology reference**, not learned translation,
  an argument value, a license grant or authority to execute.
- Reject empty, surrounding whitespace, internal whitespace/control
  characters and over-160-character semantic identifiers.
- **Legacy byte/schema-revision preservation:** when unset,
  `ParameterSpec.model_dump()` and nested `EndpointSpec/ToolSpec` dumps
  omit the new key (using a wrap serializer), ensuring unannotated
  tool/endpoint source fingerprints remain based on the identical wire
  object. Explicit opt-in `semantic_id` is serialized and changes the
  endpoint and tool source fingerprints as a real contract revision.
- No adapter fills a semantic ID by guessing; unannotated data continues
  to use the existing default lexical routing and trusted host bindings.
- No `retrieve_authorized` scoring or permission policy change; the
  metadata is available only as an explicitly declared future graph edge
  input, and remains subject to all principal/data-scope/availability
  checks and source revision witnesses.

## Promotion and follow-on

An opt-in native G3 graph adapter must require an exact declared input
semantic, compatible typed output field and verified source identity for
each returned graph predecessor. It must not treat the annotation as
permission, as availability of an actual value, or as a multi-step
agent execution schedule. Versioned independent publisher-authored
#1346 EN/KO/JA and external-agent #1477 completion evaluations
are necessary to change production defaults. Frozen #432 negative
results and v0.18 #1356 HARD HOLD remain unchanged.

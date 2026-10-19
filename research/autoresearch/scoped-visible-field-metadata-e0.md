# Scoped visible field descriptive metadata noninterference — targeted E0

Date: 2026-10-19; owner M0 #1532. Builds on merged #1600; no change to original execution source contract.

## Reproduced source-authorable exposure class

The existing data-scope projection checks `FieldSpec.name` against the actor's declared visible output fields, and strips nested JSON Schema. However, an **allowed FieldSpec** may include arbitrary source-owned `description`, `aliases`, `path`, `result_path` and `qualifiers` referencing an otherwise denied field name. These descriptions and source projection path segments must NOT imply the principal can inspect referenced source metadata.

A local fixture puts a unique hidden-name canary in all five annotation channels on the visible field while declaring a distinct, denied output field. Both a user-visible `CapabilityRetrieval` and a custom analyzer's `_scoped_analysis_registry` endpoint are checked. The trusted original registry is checked separately for preserved values.

## Change and intentional retention

In both public/data-scoped endpoint and returned candidate, sanitize the *visible* field's `description`, `aliases`, `path`, `result_path`, `qualifiers` and nested provider JSON keywords, keeping canonical `name`, `semantic_id` and primitive `json_schema.type`. The normalized output schema still uses only visible names and primitive shape. This is a **non-executable descriptor**, never a source-side selector, and the original registry, endpoint/tool fingerprints and native registered executor projection retain raw paths and constraints.

This removes unreviewed alias-based retrieval hints under an explicit output data-scope, which **can lower per-language alias recall**. Requiring host reviewed alias provenance is preferable to treating arbitrary source synonyms as privacy grants. The dedicated contract tests prove only canonical/semantic exact-match retention, not EN/KO/JA semantic recall or downstream E2 agent utility. No unscoped/default route changes intended.

## Acceptance and limitations

The E0 regression is failure-oriented: hidden-name canary absent from both serialized public candidate and scoped analyzer endpoint; original source unchanged; exact host field-name and semantic-ID contract succeeds and denied field-name contract abstains. Run existing #1600 input-ref safety, host completeness/policy drift, authorization and graph scope suite, Linux Py3.12 lint/typecheck. Full protected CI/CodeQL and performance parity must pass before merge.

**Residual #1532:** ToolSpec-level `description`/`metadata`, EndpointSpec `description`/`operation_aliases`/`path`/`metadata`/`execution_metadata`, score snippets, semantic IDs, unit/provenance strings and external adapter free text are NOT proven noninterfering. Each needs independent canary and explicit trusted-source contract; do not blanket claim zero leakage or completed M0. Frozen #432 negatives, #1346/#1477 E2, and v0.18 release HOLD #1356 remain unchanged.

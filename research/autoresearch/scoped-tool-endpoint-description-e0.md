# M0 #1532 — Scoped tool/endpoint free-text boundary (E0)

Date: 2026-10-19. Builds on merged #1600 and #1601. Registered source and trusted executor are unchanged. Release #1356 remains HOLD.

## Reproduced direct metadata disclosure

After field-level data scoping, the original ToolSpec description/metadata and EndpointSpec description/operation_aliases/path/metadata/execution_metadata may still contain an otherwise denied field name. The scoped analyzer registry cloned the unsanitized tool; public CapabilityCandidate tool_description and endpoint_description likewise echoed raw source-authored text.

The E0 patch restricts only public/analyzer descriptors under an explicit output-field DataScopeRule. It blanks the tool description, metadata, execution_metadata in the scoped analyzer registry. It blanks endpoint description, operation_aliases, path, metadata and execution_metadata in the principal-scoped endpoint view; the public authorized candidate has blank tool_description and endpoint_description. Original registry source, method, fingerprints, output field canonical identity, read-only policy, server-side execution path and validators stay unchanged. No extra predicate/authorization evaluation was introduced during scoped catalog construction.

Local tests place one distinctive canary in each source-controlled descriptive field, capture the custom analyzer's complete ToolSpec plus the authorized public candidate, and assert the canary and denied field name are absent from both. They assert original source values/fingerprints are intact and HostFieldContract positive and negative decisions remain the same. This is only a direct-descriptor E0 proof.

## Critical remaining side channels and tradeoffs

This is NOT full information-flow noninterference. The original planner still uses raw tool.description for lexical scoring, which may affect public rank, numeric score, score_components and route inclusion. This remains an explicit #1532 defect candidate requiring a separate ranking-path adversarial test and patch before a confidentiality claim. Source type/license/provider and server_projection may also require provenance review, as may auth requirement aliases. Do not erase trusted original execution data to hide source descriptions.

Suppressing unreviewed operation_aliases/tool descriptions may reduce scoped English/Korean/Japanese recall. Prospective principal-paired dev recall and no-fit experiments are necessary, not a new estimate derived from the frozen #432 dataset. Release #1356 stays HARD HOLD and #1346/#1477 independent E2 remain blocked.

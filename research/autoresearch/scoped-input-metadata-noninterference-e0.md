# Data-scoped public input metadata noninterference — E0 only

Date: 2026-10-19. Issue: #1532, milestone M0. This is a narrow, local metadata exposure fix, not an end-to-end data confidentiality or provider execution certificate.

## Reproduced failure class before this patch

When a principal's DataScopeRule restricts visible output fields, the existing output-schema projection already strips nested output $defs/$ref material. However, the scoped analyzer registry still exposed the **raw input_schema**, including undeclared $defs and allOf references to hidden output names. Even a normally visible required input ParameterSpec could carry descriptions, examples, aliases and nested JSON Schema refs referring to restricted data. Public retrieval's post-scoping pass only filtered top-level input properties and preserved arbitrary nested property values. This is schema/name metadata disclosure, *not* demonstrated provider value exfiltration.

## Conservative remediation

Both the analyzer-visible endpoint and post-retrieval CapabilityCandidate now receive one common principal-scoped argument view:

- Keep only still-allowed native parameter names, required flags and primitive JSON type information, **plus only the trusted DataScopeRule-origin** relationship-type allowlist and max-hop ceiling; never copy unreviewed provider parameter refs, nested definitions, examples, descriptions, aliases or raw inputSchema keywords.
- Reconstruct a minimal input descriptor from those allowed names rather than filtering the top-level raw schema while leaving unreviewed definitions behind.
- Leave the original registered input_schema, parameter validators, read-only/authorization policy, fingerprinted provider contract and execution validation unchanged.
- The opt-in HostFieldContract selector validates source-native required enum fit **internally from the current authorized original parameters**, restricted to parameter names still present in the principal-scoped view, while the principal-visible candidate and returned receipt never serialize those raw enum values. Original source fingerprints, authorization scans and stale-revision/forgery refusal still apply.
- The public descriptor is deliberately not a substitute for an executable request schema; host and registered executor must still validate full original constraints and policy.
- No input normalization, new permission or execution path is introduced, and defaults outside a scoped data-rule view are untouched.

## Verification

No-network tests assert that the private field name is absent from both custom analyzer's scoped endpoint model dump and user-facing CapabilityRetrieval JSON, including when all declared output fields happen to be visible. They assert raw source schemas remain identical. Dedicated Linux Ruff/Pyright/pytest runs alongside existing scoped ref, authorization, **HostFieldContract enum-fit and fingerprint**, and graph DataScopeRule relationship/max-hop regressions; protected CI and CodeQL required before merge.

## Remaining issue gates

Issue #1532 stays OPEN: arbitrary ToolSpec/EndpointSpec/FieldSpec descriptions, aliases, paths, provider metadata, reference-shaped input semantics, semantic joins and total information-flow noninterference require separate threat-model review. Sanitizing descriptors can reduce model-visible argument detail; evaluate planning recall and false refusals against an independent principal-scoped corpus before claiming product quality. Keep #1450 authority semantics, #432 frozen negatives, #1346/#1477 independent E2 and #1356 v0.18 HARD HOLD unchanged.

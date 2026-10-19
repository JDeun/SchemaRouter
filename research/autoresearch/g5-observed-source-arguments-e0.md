# Native G5 one-hop observed scalar argument validation (E0, nonexecuting)

**2026-10-19, stacked on [PR #1592](https://github.com/JDeun/SchemaRouter/pull/1592).** Source-native multi-required-input typed G5 graph edge is only schema evidence; it does not establish a real provider response, identifier value, permission to invoke a downstream service, or task success.

## What this narrow experimental helper actually does

The opt-in `materialize_native_observed_arguments` takes:
- One **current, explicitly principal-authorized G5 route candidate**, original pinned `NativeSchemaGraphIndex`, host-declared EN/KO/JA-capable `NativeDeclaredFieldGroup` and query
- One caller-provided `ToolResult`, with matching producer route, selected/projected field names, source semantic field contracts and `has_observed_value=True` for each required source identifier

It **repeats the current G5 lookup** before and after validation, verifies the candidate still occurs under original catalog fingerprints and current policy/availability/scope checks, checks co-record structural proof for multi-input routes, and confirms **each** observed scalar is non-null and matches both producer value schema and consumer argument schema. It validates the **complete** native consumer input envelope against the original endpoint. Result is a frozen evidence record with a defensive-copy arguments property.

It **does not call any tool**, certify actual external response authenticity, infer missing values, authorize a separate consumer invocation, create a `ToolCall`/`ExecutionPlan`, expose hidden root fields, log raw identifiers, alter default routing or run an agent. A perfectly spoofed caller-owned `ToolResult` can pass schema validation, so `provider_provenance_verified=False` and `executable_authority=False` are **always** fixed to false. A source-owned executor invocation with trustworthy provenance, runtime principal and existing execution-policy checks is a future independent boundary; this helper is not its substitute.

## E0 test/control matrix

- EN/KO/JA host-declared alias paths, required two-input values and fresh dict copy
- Wrong result route; unprojected, absent, null, list, wrong-scalar-type, nonfinite values
- Missing/false observed presence metadata; spoofed value metadata stays untrusted
- Current principal hidden data-field denial, stale registered tool source/fingerprint
- Caller-provided model cannot grant tool call or independent E2 authority

## Remaining work and release controls

Use original provider-authored public, license-authorized data and actual invoker receipts in a **separate** E1, with nonce/timestamp/binding provenance and source-specific response semantics. Validate caller provenance *independently* of schema shape; protect against output transforms, pagination, array co-occurrence, time-of-check/time-of-use, replay and recursive/multi-root flows. Then evaluate unseen EN/KO/JA and actual downstream agent full-task utility on original disjoint E2 #1346/#1477.

No assumptions of significant generalization or commercial-quality scores. Do not modify historical #432, production defaults or v0.18 release PR #1356 (**HARD HOLD**).

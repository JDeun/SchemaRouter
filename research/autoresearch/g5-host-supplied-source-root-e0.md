# G5 explicitly host-supplied original source parameters (strict bounded E0)

**2026-10-19; M1 / #1560 / #1545.** Existing published G5 build only indexed producer roots with no required input. This limits graph participation of actual `GET /posts/{id}` and `GET /documents/{id}` sources. This experiment does NOT infer the source ID from a query or extend a host's authority.

## Opt-in contract, never implicit fallback

1. The host must pass an **explicit bounded frozenset of exact original registered route IDs** to `NativeSchemaGraphIndex.build(..., approved_host_roots=...)`. The default remains an empty set, identical to the existing source graph. Nonexistent or ineligible routes fail the entire index build.
2. The named producer endpoint must be currently read-only, licensed, typed, source-attested and non-destructive, with 1–4 **required, scalar, non-header, no-auth** original input parameters. Its native `input_schema` must have an exact closed `type/properties/required` declaration matching every parameter and no additional unmodeled constraints. Do not silently drop `minLength`, `enum`, `additionalProperties`, `$ref`, optional inputs or authentication requirements to gain an edge.
3. Keep the original canonical typed graph and all K5, source fingerprint, current principal authorization, data-field scope and endpoint availability gates. Opt-in source routes must still prove all consumer required inputs originate from visible, properly typed original source identifiers. The candidate contains **source parameter NAMES ONLY**, never values or credentials.
4. The `execute_native_graph_one_hop(..., source_arguments={...})` caller supplies **every** required root value explicitly, independent of query wording. Exact keys, primitive JSON types (boolean not integer), finiteness, scalar size and the complete original native source JSON Schema are validated **before any invocation**. The *existing* executor validates both source and destination again with current policy/registered version, source/field projection, original tool fingerprints and budgets. No new executor or implicit input synthesis.
5. Default no-input root rejects any supplied root arguments. Host-parameterized root refuses missing, extra, unsupported or wrong-typed source arguments. A stale registered source or principal denial blocks the source invoker; post-source scope/availability changes block the downstream invocation.

## What passes or fails

Synthetic two bound read-only local functions: host provides `post_id=1`; actual first source produces `userId`; native typed G5 connects to second required `user_id` consumer and existing runner executes both. EN/KO/JA host-owned exact aliases only; no model translation measured. Default graph without explicit route approval must return no proven hit. Negative tests cover missing/wrong/bool/float/array input, extra argument, stale source, unknown explicitly allowed root, raw input schema with extra properties, and unchanged legacy source with empty input.

## Evidence limits and future provider qualification

**E0 only**. User or model natural-language interpretation never chooses `post_id` nor authenticates supplied source values. The trust assumption is that a **host already approved both the route and concrete arguments**. A caller-controlled approval flag alone is NOT cryptographic authorization; the original principal/policy and actual executor remain independently necessary. This does not handle root-search pagination, arrays/co-record joins, two-input original provider contracts with constraint refinements, server credentials, independently authored benchmark, unseen Korean/Japanese tool retrieval, native MCP production interoperability or agent final-answer E2.

The existing JSONPlaceholder public fake-data live E1 #1595 (fixed `GET /posts/1`) is separate; it does not count as proof of this new dynamic-root code until an actual source run exercises it with source-authorized inputs and is checked as a new E1. Independent E2 #1346/#1477 and release PR #1356 HARD HOLD remain unchanged.

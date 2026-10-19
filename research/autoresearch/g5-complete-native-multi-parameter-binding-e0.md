# G5 native typed graph: complete one-producer/multi-required-input binding (E0)

**2026-10-19 · architecture and native-tool fixtures only.** Existing parent [#1560](https://github.com/JDeun/SchemaRouter/issues/1560), required-group [#1535](https://github.com/JDeun/SchemaRouter/issues/1535), existing canonical [graph code](../../src/schemarouter/native_graph_index.py). This is not the fully executable source-native multi-hop graph or independent task E2.

## Previously unimplemented
`NativeSchemaGraphIndex` only accepted a native consumer endpoint with **exactly one** required scalar argument. Its `NativeIndexedGraphCandidate` exposed one `producer_identifier_field` and one `consumer_required_parameter`. A normal native operation requiring both `contact_id` and `region_id` was rejected even if an original source-authorized root returned both well-typed identifiers. A naïve extension that emitted only the first binding would falsely imply complete dataflow.

## Bounded new contract
1. At build, an opt-in consumer with **1–4 parameters** is considered only if **every** parameter is required, has an exact trusted semantic ID and one primitive scalar type, is not header/body-root, and its optional explicit input JSON Schema is exactly the closed *declared* set of parameter properties and required names. Unknown optional values, schema combinators, extra properties, unmodeled auth requirements and `>4` arguments have **no proven graph edge**.
2. Reuse existing canonical `build_capability_dependency_graph` and `compare_capability_composition` to test **all** consumer requirements against the **same** attested producer; do not join unrelated producers by shared words or infer a missing input from user text.
3. At query, re-check source identity, principal authorization, current data-scope/field visibility, availability and typed compatibility for **each** required parameter. Ambiguous or duplicate producer field matches and reused identifiers fail closed. For multiple consumer inputs, **the original source response must explicitly declare a flat root JSON object with all selected scalar identifier properties listed as required**; the selected native field paths must point to exactly those root properties. Missing/optional root fields, `$ref`-only roots, arrays and distinct nested collection records **cannot** prove values co-occur in one source observation and must abstain.
4. Expose `parameter_bindings: ((consumer_parameter, producer_identifier_field), ...)` in the native G5 E0 evidence. Legacy single-binding fields remain for 1-input routes but are **None on multi-input routes**, so callers do not accidentally interpret partial evidence as an executable argument map.
5. All source fingerprint and same-source snapshot, strict K5 and `over_k_unranked` invariants remain. No agent execution, source invocation, automatic argument extraction, policy grant, default `retrieve` change, latency claim or E2 evidence.

## Verification
Dedicated Linux 3.12 G5 regression checks original 1-input adapter path and a new explicitly source-owned direct native-tool fixture. EN/KO/JA approved aliases, 2-input complete join, missing or incompatible type, optional input, undeclared raw input property, ambiguous producer semantic, hidden field for Viewer, availability rejection, registry revision invalidation and >4 required inputs. These are **synthetic E0**, not independent source/provider data. Release PR #1356 remains HOLD pending #1346 external independently authored E2 and #1477 paired real-agent utility.

## Remaining for M1/M3
- Tool/Endpoint/FieldGroup and operation matching from unknown multilingual natural language still requires independent source-normalized evaluation.
- Native root fields must become independently verified **available values** with actual identifier propagation and provider-side input validity, not just matching declared types.
- Two-hop chained paths, independent multi-root joins and optional/credential-bearing inputs need separate fail-closed contracts and authority proofs.
- A justified ranking model for `>K5` eligible verified paths is **not** supplied; no-fit and supported recall E1/E2 remain separate metrics.

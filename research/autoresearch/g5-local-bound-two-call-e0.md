# G5 two registered, authorized, read-only calls with observed value propagation (E0)

**2026-10-19 · opt-in engineering proof, NOT independent external provider verification or E2.** Builds on [#1592](https://github.com/JDeun/SchemaRouter/pull/1592) and [#1593](https://github.com/JDeun/SchemaRouter/pull/1593); tracks [#1560](https://github.com/JDeun/SchemaRouter/issues/1560) and [#1477](https://github.com/JDeun/SchemaRouter/issues/1477).

## Original code reused, not duplicated

- Registered `SchemaRouter.add_bound_tool` invokers and `SchemaRouter.execute` perform the **real in-process local source and consumer calls**, not handwritten fake `ToolResult` injection into the validator.
- The original `ToolCall` carries original tool and schema fingerprints, exactly selected output fields, and `RunConfig(principal=...)` with one-attempt/one-call budget. Both producer and consumer go through the **existing executor authorization, input/output JSON Schema, projection and fingerprint checks**, not a new permissions service.
- After the first actual result, only `materialize_native_observed_arguments` from [#1593](https://github.com/JDeun/SchemaRouter/pull/1593) creates a complete validated argument mapping; it rechecks the current principal/field scope and G5 original source before and after value validation. A second original typed `ExecutionPlan` is then passed through the existing executor; the runtime rechecks permissions and source identity again before invoking.
- The helper exposes two actual `ToolResult` objects as `NativeOneHopExecutionEvidence`; the original observed data is not logged by this function. Result carries only **`producer_via_registered_executor=True`, `consumer_via_registered_executor=True`**; **`independent_provider_identity_verified=False` and `independent_agent_e2=False`**.
- Only a **one-hop**, **read-only**, **fully required flat scalar**, **one-root and one-consumer** fixed G5 candidate under an explicitly supplied principal is eligible. Never merge unrelated observations, infer missing parameters, extract arbitrary recursive JSON references, select random candidate when K>5 or change default `retrieve` behavior.

## Required adversarial controls

The dedicated Linux E0 fixture binds **two separately registered local invokers** and asserts actual invoker call order and copied input values (plus EN/KO/JA host-approved aliases). It tests missing, `null`, array and wrong typed source values; explicit local policy denial on the downstream; hidden `region_id` for a restricted principal; stale source fingerprint; and an extra hidden provider property removed by the local allowlist projection. Any failed preflight must mean **zero downstream calls**, with no mutation or second call.

## Evidence that is still missing

This local experiment **does NOT** authenticate original remote provider identity, prove transport timestamps, freshness or replay protection; validate multi-hop chains or a source-of-truth factual oracle; improve unseen EN/KO/JA search, no-fit calibration, supported recall or agent task success. An arbitrary registered local invoker may be malicious or buggy; the registry controls *which code* is executed, not whether a response is factually correct. For real public OpenAPI/MCP providers, obtain source/license-authorized independent validation and provider execution under #1545/#1346/#1477 before any release claim. The frozen #432 negative comparison and #1356 v0.18 HOLD remain untouched.

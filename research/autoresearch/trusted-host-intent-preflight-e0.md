# Trusted-host intent preflight (R05 engineering-only E0)

**Owner:** #1477, with authorization dependencies #1450 and independent tasks #1346.

This is a **separate, opt-in pre-model read-only guard** against confusing a typed missing input, multiple *authorized* candidate operations, and an unavailable capability. It works exclusively on the real `capture_authorized_agent_tool_surface` snapshot, which already enforces principal scopes, hidden fields, registry/policy version and in-place mutation checks.

A *trusted host* must supply exact candidate-route hypotheses and structured input fields. **Do not accept arbitrary model-generated classifications or a user's claim to be a trusted host.** The function is not a language model, a classifier, an automatic host-parser, an execution authorization, or an independent acceptance oracle.

| Situation in trusted host frame | Safe read-only preflight disposition |
| --- | --- |
| One visible authorized route, all required public fields satisfy the conservative schema | `ready` (still non-executable) |
| One visible authorized route, required field missing, typed incorrectly or unknown input supplied | `needs_input` |
| More than one visible authorized route | `ambiguous` |
| Empty hypothesis, nonexistent operation, authorization-hidden operation, or any mixture containing one hidden operation | **same opaque `unavailable`** |

**Critical security property:** A principal must not learn whether a route exists but is forbidden. If a host hypothesis is inaccessible or unknown, the model-facing response contains neither its name nor a denied-vs-nonexistent bit; the distinct test-only `forbidden` gold is **never** copied into user/model view. The host itself remains responsible for authenticating and deciding whether to provide a user-facing generic error. This guard does not let an untrusted model ask for a denied operation.

The conservative typed check supports bounded primitive public argument types only. Formats, regexes, JSON references, nested/complex objects and unsupported constraints *cannot* establish `ready`. Production provider-specific JSON Schema validation and a last-mile **fresh policy/registry check** remain mandatory before physical I/O. The preflight deliberately does not distinguish protected resource absence as forbidden and does not dispatch actions.

The EN/KO/JA tests reuse the *same* typed public source while changing request language; they demonstrate structural protocol invariants rather than native multilingual natural-language understanding. Original exact-head synthetic Qwen5-class strict scores remain 1/15 per arm; EOS-boundary research PR #1502 measures separate output formatting only. No pretrained model, routing threshold, registered catalog, historical #432/#424/#506 results or release settings change.

### Acceptance and promotion contract

- Fail closed on stale policy (including same-object in-place rule drift), unknown route hypotheses, malformed/oversized host inputs, wrong original query or complex schema.
- **No unauthorized route name, hidden field, host gold or user text in the receipt.**
- Report `real_native_provider_execution=false`, `executable_authority=false`, `independent_e2_qualified=false`, `model_default_promoted=false`.
- No external author, real required typed native provider adapter, full conversation state, open-set calibration or factual answer oracle is provided. This remains **E0 engineering evidence only**; R05 **NOT_VERIFIED**, 0/19 E2 and release #1356 / model-promotion **HOLD**.

Local check: `python -m pytest -q tests/test_research_trusted_host_intent_preflight_e0.py`.

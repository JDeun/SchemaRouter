# Source-view integrity receipt: E0 safety hardening (#1477)

**2026-10-17.** No model weights, routing ranking, endpoint permissions,
public default, provider execution behavior or E2 outcome are changed.

## Found gap

[#1487](https://github.com/JDeun/SchemaRouter/pull/1487)
improved same-request authorized source reuse, but its frozen
`AuthorizedAgentToolSurface` contains mutable nested Python dictionaries
and a replaceable tuple of immutable semantic route records. A caller
holding a source-view instance can replace a captured route's description
with arbitrary text while preserving route ID and tool/endpoint fingerprints.
ID, principal and registry checks alone do not notice this change before
the model receives the descriptor. Likewise, mutation of the nested
agent-visible definition or observation projector can expose fields never
approved by the original snapshot.

## Narrow correction

At trusted capture, compute a **process-local HMAC-SHA256 integrity
receipt** over the exact original query, original principal claims
snapshot, source registry version and physical route count, ordered
visible route IDs, full sanitized agent tool definitions, source-visible
observation field names, and semantic route ID/description/fingerprint
tuples. Store only the internal receipt on the frozen source view;
never print or export the plaintext or receipt in benchmark artifacts.
Before disclosure, observation projection, model backend selection,
and sanitized public trace, assert the normal authority/principal
witness **and** compare the receipt. Missing/forged/malformed receipts
fail closed with `PolicyViolationError` before model visibility.

This is **not a general sandbox/security perimeter against arbitrary
hostile Python code running in the same interpreter**: such code could
inspect private runtime state or bypass Python object protections.
The improvement protects against accidental mutation and untrusted
object-envelope replacement at the modeled source-view boundary. The
HMAC key is ephemeral, per Python process, and not a provider credential
or executable permission. It is not a cross-user/cross-request cache.
Using HMAC instead of requerying all native source routes preserves
the same-request performance research purpose of #1487.

## Regression contract

Synthetic no-model tests replace a captured semantic description while
keeping original route ID and tool/endpoint fingerprints, mutate nested
agent tool schema, expose hidden output fields, tamper with capture
order, and mutate the snapshot during `DecisionBackend.decide`.
All must fail before disclosing or publishing a selected tool. Original
EN/KO/JA request equivalence, genuine read-only bound host calls,
no-fit nonqualification and standard empty authorized catalog behavior
must remain unchanged.

**Evidence classification:** E0 security correctness only. Model
inference benchmarking and fresh independent native EN/KO/JA/OOD task
cohorts (#1346/#1477) are separate. Release #1356 remains HARD HOLD,
frozen #432 unchanged.

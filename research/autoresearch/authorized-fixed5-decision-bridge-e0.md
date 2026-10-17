# Source-authorized fixed-K5 backend bridge — E0 only

**2026-10-17, #1477 milestone A; do not promote to product routing or
commercial accuracy claims.**

## Previously disconnected components

- `propose_bounded_semantic_shortlist` (#1473) already builds authorized
  native source options, independently bounded input descriptions and K,
  but returns a **non-executable, uncalibrated** suggestion.
- `run_generated_episode` (#1478) already supports an isolated
  `EVAL-FIXED5-OPTIN` callback and a principal-scoped tool view (#1479).
  Its callback receives query and authorized route IDs only, so directly
  implementing semantic option descriptions inside that callback would
  duplicate the source-scoped comparator.

This PR adds `AuthorizedFixed5DecisionSelector(view, backend)` as the
minimal callable bridge to those existing interfaces; it **does not**
introduce a new executor, a new DecisionBackend, a new retrieval algorithm
or a new test corpus.

The caller first builds the real `AuthorizedAgentToolSurface` under a
trusted original `PrincipalContext`. The selector pins current visible
native tool/endpoint fingerprints. During selection it requires the exact
original query and the exact authorized source tuple, passes the **same**
host principal and router through the existing bounded semantic diagnostic,
and validates authority before/after inference, source fingerprints, native
registered ID membership, endpoint fingerprints and strict `K=5`.

The selected routes are passed to the existing frozen synthetic agent
executor and its principal-scoped **model disclosure**, not to
`router.execute`. The decision model sees a `DecisionRequest` containing
the original query and only currently authorized source-derived route
descriptions. For field-scoped sources, the comparator omits untrusted
publisher prose. No `required_routes`, executor fixture, internal state,
provider invoker, credentials or independent labels are supplied to it.
Returned model choices remain suggestions; a later trusted host must
compile execution through the product runtime.

## Reproducible E0 checks

No-model `CallableDecisionBackend` tests assert a source-selected actual
synthetic agent episode completes using the original executor, without
leaking hidden schema prose; original EN/KO/JA query bytes are forwarded
without translated gold, but these checks DO NOT measure multilingual
semantic accuracy. Negative tests cover forged/duplicate IDs, wrong source
tuple/query, explicit abstention, revoked principal, native in-place
schema mutation, input budget violation and unexpected plan/execution.

**Limitations:** The callback adds a second authorized retrieval scan and
is therefore only a research baseline, not an optimized product hot path.
The selector only checks fingerprints at construction and selection; it
does not atomically lock native state during later model generation or
in-flight host execution. The underlying principal-scoped view and product
runtime remain separate authorities. The synthetic replay is not an
independently authored E2 task or a real model run. Backend abstention
is **not calibrated no-fit** and cannot be called a correct refusal
without independent case labels.

This bridge prepares a genuine future lexical-vs-E5-vs-hybrid fixed-K5
comparison on exactly the same source-native task cases without adapting
rankers to disclosed results. Such a study remains blocked on #1346
independent source/case authoring and task-level final-pass evaluation.
`#432` history and `#1356` v0.18 release hold are unchanged.

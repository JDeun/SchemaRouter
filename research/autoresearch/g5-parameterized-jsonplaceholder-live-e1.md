# G5 host-approved parameterized original HTTPS root — E1 only

Date: 2026-10-19. Research owner: #1560; interoperability: #1545. Follows merged #1596 host-approved required source inputs and #1595 fixed-source public demo HTTPS E1.

## Hypothesis and fixed test

The original G5 E0 contract can transport **two different host-owned bounded required root IDs** through the registered real executor (not a fixture-only Python function). The provider's actual *projected observed* integer userId must be the downstream second call's required user_id argument, not an assumed, hardcoded, or query-guessed value.

Original source: JSONPlaceholder public seeded **FAKE demo records**. Strict fixed HTTPS host, no redirects or environment proxy; host explicitly chooses post IDs 1 and 11 (input IDs themselves are not inferred from natural language). Two trials each call GET /posts/{post_id} and then GET /users/{actual_userId}. G5 lookup must discover exactly one current approved source-to-consumer typed edge and the executor must enforce principal, schema/fingerprint, output field projection and budgets for both calls. Source response must contain the requested post ID and a positive integer author ID; consumer response ID must match the actually bound author ID.

The same graph built without explicitly approved source routes must report no_proven_hit. Source input must have exactly one post_id integer field; missing, extra, strings, booleans, floats or out-of-range values reject without a remote call. Malformed source identity blocks the second original HTTP call; mismatched user identity cannot be counted as a completed pair.

## Evidence collection and acceptance

- Dedicated no-network httpx.MockTransport contracts test exact four-call order for two source IDs and negative admission/identity controls.
- Separate CI job executes actual Python httpx.AsyncClient HTTPS against original public provider; **mock tests are not treated as network results**. Missing/timeout/changed provider content fails, never falls back to fixture values.
- Report persists only counts, categorical boolean provenance and elapsed seconds. It excludes actual source IDs, usernames, email addresses, provider response bodies and observed IDs, even though the underlying provider is public fake-data.
- E1 passes only if both original producer and consumer invokers validate all four source responses, G5 candidate is fully typed, and original executor returns projected outputs. Offline CI, Pyright, Ruff and protected CodeQL must pass on the exact PR head before considering merge.

## Strict limitations and future work

This is **provider-transport E1 over fabricated public content**, not genuine business-data truth, not independent publisher-authored E2, not an LLM task or model route selection, and not an EN/KO/JA semantic generalization test. Host explicitly selects the route, authorizes the original source and provides both original IDs. It is not evidence that any untrusted caller can self-grant root approval; the trusted host and current principal/policy are prerequisites.

The original negative #432 remains frozen. Independent source-native benchmark #1346 and same-agent end-to-end #1477 remain release gates. v0.18 release PR #1356 remains **HARD HOLD**; passing the demo E1 is never a release go decision. No new production default or graph/agent engine is introduced.

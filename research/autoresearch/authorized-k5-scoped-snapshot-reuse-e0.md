# Reuse checked scoped native catalog within one K5 decision — E0 research

**Status:** source-safe opt-in performance experiment, **not** product
authorization, E2 task confirmation, calibrated no-fit or release approval.

## Measured problem

Pinned real multilingual E5 at 500 registered synthetic native source
routes retained DEV Recall@5 42/48 but incurred roughly **527ms p95**
candidate selection in [profile run #38993847383](https://github.com/JDeun/SchemaRouter/actions/runs/38993847383).
Stage p95:
- model decision backend: **89.86ms**
- non-model source + model-option and validation processing: **419.66ms**
- principal-scoped source view initially captured: **119.12ms**,
  previously excluded from the selection timer

Hybrid RRF(60) non-model stage was **712.48ms** p95. Percentiles are
marginal and must not be added. Original exposed DEV cannot be reused
as confirmation or tuned into independent E2.

## Single-request reuse change

Before, a trusted host created an `AuthorizedAgentToolSurface` by
running `retrieve_authorized(query, principal, k=all_native_routes)`.
The opt-in semantic decision bridge then called
`propose_bounded_semantic_shortlist`, which independently repeated
the **same full authorized retrieval** on the **same query**. Hybrid
also did its own lexical retrieval; the second semantic full retrieval
was particularly wasteful at 500 source routes.

Now the host's original capture also freezes an immutable tuple of
`CapturedAuthorizedSemanticRoute` values — exactly the ordered,
policy-projected original registered route ID, minimal safe description
and native tool/endpoint fingerprints. The same pure
`scoped_semantic_model_description` generator feeds the legacy live
comparator and the captured path, so model input JSON bytes and route
rank/order are unchanged for the same source.

The opt-in fixed-K5 bridge passes the **existing** captured view
to the comparator. The comparator **never** bypasses mandatory:
- same router object, original query, **identical principal object**
  and original authority witness and registry version
- bounded physical native route count, original ordered visible routes
  with no duplicate or foreign choices, and immutable captured record type
- view-principal claims and source-policy drift checks before model
  disclosure and after inference; bridge independently rechecks
  original tool/endpoint fingerprint mapping before/after
- existing 128KiB default or explicitly configured max-256KiB research
  byte cap *before* invoking the model; exact K=5
- unchanged untrusted backend option-ID validation via `choose_sync`
  and original post-hoc selected fingerprint validation

If any identity, policy or fingerprint changes, **fail closed**. The
new code creates no cross-request cache, no cross-principal catalog
mapping, no new model weights, no provider invocation, and no
calibrated no-fit. The old comparator without an authorized view
still performs its original full authorized retrieval as before.
A synthetic test actively disables subsequent `retrieve_authorized`
to witness lack of a second native full catalog read.

## Evidence and limits

The E0 regression tests compare model input JSON byte-for-byte and
route/order/byte budget for EN/KO/JA with field-scope redaction, as
well as spoofed principal/query and malformed captured source; existing
mutation/revocation/host-executor tests continue to run unchanged.
The benchmark still measures lexical/E5/hybrid retrieval on previously
disclosed 84-case synthetic DEV at 13/100/250/500 source routes;
R@1 and R@5 and output provenance must be **identical** to earlier
original baseline to consider this an invariant-preserving speed
optimization. Any measured speedup must be stated at a given
GitHub Actions Linux runner and under shared warm-cache order;
it is not production SLA or proof of independent generalization.

A fresh native external publisher-authored disjoint task split (#1346)
and comparable real-agent final task utility (#1477) remain
BLOCKED_EXTERNAL. #432 historical negatives and v0.18 #1356 HARD
HOLD must remain unchanged.

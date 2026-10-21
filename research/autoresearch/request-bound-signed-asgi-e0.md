# Request-bound signed offline ASGI identity E0 — scope and limits

**Status: E0 RESEARCH ONLY. NOT DEPLOYABLE OR PRODUCTION AUTHENTICATION.**
This is a narrow continuation of merged #1645 and operational issue #1639.

## Why the previous step was not enough

Merged #1645 signs **who** the synthetic caller is (tenant, role, workload,
audience and short expiry). The resulting Bearer is reusable within its
expiry, and changing the unsigned POST body or endpoint does not change
that Bearer. The existing SQLite `(tenant, request_id)` de-duplication
prevents the exact same *execute request_id* from re-running, but cannot
prevent a stolen identity assertion being used with a NEW request ID.

## Experimental bound-request contract

An additional **independent test-only HMAC-SHA256 request proof**, checked
before forwarding to the merged #1645 fixture verifier, covers:

- The **exact signed Bearer bytes** (to prevent swapping identity tokens)
- The exact HTTP method (only POST) and **fixed** E0 ASGI path
- SHA256 of the **raw HTTP body bytes** (not semantic or reordered JSON)

The ASGI wrapper validates signed identity **before** reading the request
body, then reads no more than 2048 bytes in at most 32 body chunks, checks
the request proof and replays the identical body exactly once into the
underlying synthetic E0 gateway. No provider HTTP GET, socket, real identity
provider, TLS or external system is used. Both Bearer and request proof
headers are scrubbed from the downstream scope. Distinct wrong method,
body, path, duplicate or missing proof, expired identity, and oversized
body are denied without using an E0 reservation or calling a synthetic sink.

**Crucial limitation:** the proof is still a **bearer capability**. Anyone
who steals the entire signed assertion, matching request proof and body can
replay *the exact same request* during validity. The existing SQLite E0
idempotency key makes duplicate execute requests nonrepeatable; tenant and
global operator stop is already irreversible/idempotent. This does NOT
supply sender-constrained identity, real token revocation, an issuer or
durable global replay ledger. A genuine production solution needs actual
workload identity/mTLS or another binding approved by security, protected
issuance/rotation, cross-host policy, valid sender/channel proof and
audited replay handling.

The proof signing key and token signing key are separately supplied fake
unit-test bytes only. There is **no signing service** or actual trust root.
The app has no real provider egress client and cannot linearize remote
network handoff with operator revocation; #1639 remains OPEN. v0.18.0
#1356 remains HARD HOLD, external E2/uptime not proven and #432 frozen.

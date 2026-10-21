# Central egress ASGI request-boundary E0 — preregistered

**TEST-ONLY. Not deployable as an authenticated gateway and not a real provider egress service.**

## Purpose

Merged #1640–#1643 exercise a trusted in-process model and one-host SQLite
reservation, global/tenant stop, durable single-use synthetic handoff and
cross-process coordination. They have no request-layer boundary.

This E0 creates a **default-deny ASGI protocol prototype**. It accepts a
`SyntheticScopeIdentityE0` ONLY through an explicitly injected ASGI
`scope["schemarouter.e0_fixture_identity"]` originating from the test
harness. Headers, body, JSON-declared roles, query strings and tokens
cannot construct identity. Absent or invalid scope identity denies before
reading the body; unknown identity/source/epoch/route uses the already merged
fixed SQLite E0 reservation model, and all responses use allowlisted reason
codes. This is **not** real authentication: fixture injection is a testing
convention, not verified mTLS or IAM attestation.

## Exact routes and rules

| E0 POST path | Test-only role | Effect |
|---|---|---|
| `/e0/execute` | `workload` | Validate a fixed 4-field request envelope. Reserve one tenant/native-route allowance and invoke the TEST-ONLY sink through the permanent single-use synthetic handoff |
| `/e0/stop-tenant` | `tenant_operator` | Stop **only** the tenant derived from trusted ASGI scope; ignore any HTTP body claiming a different tenant |
| `/e0/stop-all` | `emergency_operator` | Globally revoke the synthetic authority; cannot be invoked by a normal tenant role |

Requests never contain a privileged tenant/workload/role claim. Typed,
size-limited JSON input is only a query for a preprovisioned route,
source fingerprint, epoch and opaque idempotency key. Full evaluation is
executed on an AnyIO worker to avoid SQLite blocking the ASGI event loop.
The only sink injected in tests is a local in-memory collection; the source
contains **no provider URL or outbound httpx client**.

## Acceptance tests

- Forged `Authorization`, role and tenant headers cannot grant scope rights.
- No identity returns 403 for execute and both revoke endpoints without
  consuming allowance. Scope is tied to tenant/workload labels by fixture.
- User JSON cannot elevate tenant/operator; malformed/bool epoch or extra
  authority keys fail with 400 before a reservation.
- Distinct tenant/operator scope allows one tenant stop without stopping
  another tenant; emergency stop requires a distinct role.
- Two synthetic ASGI clients contend for the same durable two-attempt
  tenant+route quota and cannot cause more than two local sink calls.
- Unknown/corrupt/unavailable durable authority fails closed; public
  responses never include path, raw payloads, exceptions or credentials.

All HTTPX ASGITransport requests are **in-process mock protocol calls**;
there are no sockets, provider GETs, network access, credentials or E2 model
runs in these tests.

## Explicit production blockers

**DO NOT expose this app to public or internal production traffic.**
No mTLS verifier, workload/operator role attestation, tenant IAM,
centrally replicated durable DB, gateway-owned provider egress interface,
TLS termination, safe provider allowlist/URL validation, workload egress ACL,
admission latency/SLO, audit trail, fault-tested multi-host deployment or
provider-approved monitoring contract is implemented.

Even a successfully executed local sink callback does not demonstrate
that a real remote HTTP provider request can be atomically coordinated
with revocation. #1639 remains open. #1618 remains open, v0.18 #1356 is
HARD HOLD, independent E2 and frozen historical #432 remain unchanged.

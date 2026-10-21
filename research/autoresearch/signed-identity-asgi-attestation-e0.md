# E0: signed synthetic scope attestation for an offline ASGI boundary

**STRICTLY NONPRODUCTION.** This is an in-memory, no-network validation
contract for request identity against the merged #1644 deny-default ASGI
boundary. It is NOT a public credential issuer, operator account system,
mTLS integration, real workload IAM or provider-network gateway.

## What changes

Previously, a trusted harness directly injected
`schemarouter.e0_fixture_identity` into ASGI scope. The offline prototype
`SignedFixtureScopeMiddlewareE0` now overwrites any preexisting scope
identity and accepts only a short-lived, audience-scoped HMAC-SHA256 assertion
from a **preconfigured test-only verification key**. An HTTP `Authorization`
header alone is not trusted: its signature, identity role, tenant, workload,
issuer time/expiry and audience must validate. Header multiplicity, malformed
encodings, incorrect/rotated keys, incorrect role, overlong expiry and forged
upstream ASGI scope all DENY. Verified fixture identity is handed to the
unchanged #1644 synthetic gateway, which applies its exact tenant/source
allowlist, finite SQLite budget, durable revocation and one-shot local sink.

The signing key is a known fake constant in *unit tests only*. The library
offers a verifier, not a public token-minting service. The HMAC context is
specific to this research prototype. Workload assertions cannot stop a tenant;
tenant operators cannot stop all tenants; a distinct synthetic emergency
operator role can revoke the full E0 model. No raw token, key, user query,
database path, source response or prompt is returned in HTTP decisions.

## Tests, all offline via HTTPX ASGITransport

- An unsigned, forged, tampered, expired, wrong-audience, wrong-role,
  overlong TTL or wrong-key assertion cannot invoke synthetic sink callbacks.
- A malicious upstream middleware that pre-populates the trusted fixture
  field is stripped at the verifier boundary; it cannot invoke emergency
  operator controls without the valid signature.
- Distinct signed tenant roles enforce scoped vs global stop, and unrelated
  tenants remain independently permitted up to their reserved synthetic cap.
- The same signed workload plus request ID cannot replay the durable
  reservation. Duplicate or oversized authentication headers are denied.
- No real remote HTTP client/server, provider GET, credential issuer, key
  management, workload CA, certificate verification or independent E2 is used.

## Nonclaims / blocked production steps

A shared HMAC verification key is NOT equivalent to independently validated
mTLS client identity. Actual identity/role issuance, protected key delivery,
revocation/rotation/audience enforcement, security auditing, clock anomaly
policy and operator incident recovery require outside infrastructure and
review. Any attacker who obtains the test signing key can construct tokens.
A production deployment also requires gateway-controlled actual provider
egress and network ACLs forbidding bypass; SQLite synthetic callbacks remain
insufficient to guarantee remote revocation. #1639 and #1618 remain OPEN;
v0.18 release #1356 remains HOLD; independently qualified E2 is unchanged.

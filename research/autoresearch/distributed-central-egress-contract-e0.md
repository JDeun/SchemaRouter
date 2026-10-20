# #1639 — central egress authority / operator revocation, preregistered E0

**Status:** ABSTRACT DESIGN + SYNTHETIC E0 ONLY. The working source is
`scripts/research_central_egress_admission_e0.py`. It is NOT a service, an
authentication implementation, a gateway, or a replacement for SchemaRouter's
product executor. No requests to a real external provider are performed.

## 1. Prior verified boundary

- Merged #1634–#1637: finite operator-owned same-host SQLite approval, active
  router health withdrawal, source runner wiring, explicit cross-process
  read-through and spawned child-process regression.
- Draft #1638: a final local read inside the already fixed source
  allowlisted async transport. A local read and remote HTTP send remain
  separate operations; revocation can race at any point between them.
- Existing authorization is still on the canonical principal/source-scoped
  SchemaRouter planner and RegistryExecutor. Presentation is NOT authority.

## 2. Choose a truthful revocation guarantee

**Strategy A — remote authorization lookup:** a host asks a central service
whether a route is currently permitted, then sends its own provider GET. This
cannot guarantee zero post-revoke GETs because the operator can revoke between
lookup and GET. Suitable only when a bounded eventual propagation window is
explicitly accepted, plus short TTL, no caching and a fail-closed fallback.

**Strategy B — central trusted egress proxy (target):** all actual provider
network access is exclusively owned by the proxy. Per-source admission,
nonrefundable quota reservation, monotonic revocation epoch and the handoff
into its own tightly controlled outgoing transport share one server-side
ordering boundary. An operator revoke that *commits* before another request's
proxy egress admission must prevent that request from being emitted. A request
admitted earlier can already be in flight; a revoke cannot undo it. The
guarantee is about **admission order**, not magical provider cancellation.
This requires enforceable workload network egress policies to prevent bypass.

## 3. Provisional external contract; DO NOT deploy until owner supplies evidence

| Property | Required contract |
|---|---|
| Host identity | Workload identity / mTLS + namespace-tenant scope, NOT test strings |
| Operator revocation | Independently authenticated, authorized, audited identity |
| Registration | Exact native source revision SHA, tool fingerprint, read-only GET path and parameter allowlist |
| Request | Opaque idempotency key, tenant, principal, route, source revision, epoch, finite remaining cap |
| Decision | `admitted`, `revoked`, `stale_epoch`, `denied_scope`, `exhausted`, `duplicate`, `proxy_unavailable` |
| Durability | Serialized centrally durable epoch, spent counters, replay protection and audit receipt |
| Failure | No local permission bypass, no auto-renewal, no untrusted status success |
| Error redaction | Public allowlisted labels/counts only; never raw body, URL params, city or credentials |
| Recovery | New *independently authorized* epoch plus separate trusted source-health proof |
| Performance | Report p50/p95/p99 admission latency, CPU/memory and serialized-contention impact |

**External gate:** provider terms and paid/free limits, safe approved probes,
actual workload and operator identity, storage/secret and network policy,
deployment control plane and independently authored source test gold all
remain unavailable. They cannot be manufactured by the model or tests.

## 4. Abstract model (E0 — not a central server)

`CentralEgressLinearizationModelE0` has a single in-process `RLock` to
represent the proxy's atomic admission + synthetic handoff point. Its
preprovisioned tenant/workload strings are **fixture labels**, not
authenticated credentials. There is no network transport, API endpoint,
server restart recovery, persistence, multi-host sync or production ACL. The
test-only callback is a local synthetic counter, not a provider invoker.

Deterministic tests cover 20 contending requests from two synthetic
workloads, a fixed two-attempt budget, a revoked epoch that never renews,
wrong tenant/source/route/identity, duplicate idempotency key, nonrefundable
sink exceptions, and handoff/revoke serialization. These validate *model
invariants*, not an external service or an E2 task outcome.

## 5. Real implementation gates, in order

1. Obtain an independent operator threat model, provider agreement, real
   identities, tenant separation, network rules, authoritative source
   fingerprints, and review of revocation ordering.
2. Specify durable transaction and proxy actual network handoff semantics
   under host partitions/restarts, duplicate retry, queueing, partial failure
   and clock skew. Verify direct provider egress is unavailable to clients.
3. Replace the E0 in-process model with an authenticated, centrally durable,
   production-authored gateway in its own security boundary; never expose a
   public toggle claiming identity and never import synthetic test labels.
4. Execute two independent hosts against that genuine gateway using
   no-network controlled source sinks. Revoke concurrently and verify zero
   admissions after the centrally recorded revoke commit; report all
   earlier admitted/in-flight calls separately.
5. Only then, with explicit operator/provider authorization, run a bounded
   live end-to-end two-hop E1 and independently authored multilingual
   model-task E2. Keep outcome, availability and policy scores separate.

**Non-goals:** changes to `SchemaRouter.retrieve_authorized`, external
network auto-probes, default watchdog enablement, published v0.18, modifying
frozen #432 or assigning independent E2 status to any generated test.

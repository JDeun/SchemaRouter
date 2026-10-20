# #1639 — Durable same-host central reservation: E0 contract

**Research scope only.** This PR is a persistence/cross-OS-process test stage
between merged #1640 in-memory synthetic egress-ordering model and an eventual
authenticated centrally owned **provider egress proxy**. It is NOT a
deployable gateway, multi-host proof, or real provider traffic permission.

## Pre-registered claim and operation ordering

The prior #1640 E0 model holds a single in-process lock while calling a
test-only synthetic handoff. That model *cannot survive process restarts* and
must not be confused with a real network gateway.

This new `DurableCentralReservationE0` uses an explicitly created, absolute
local SQLite file. One-time test fixture provisioning defines tenant,
workload, fixed native route, source fingerprint and a finite per-tenant-route
budget. The path is created exclusively (0600 where supported). Reopening
never re-provisions, reactivates, or refunds revoked/spent authority.

- `reserve()` executes SQLite `BEGIN IMMEDIATE`, verifies the exact
  pre-provisioned tuple, current global epoch, global and tenant stops,
  idempotency key and quota, then commits a nonrefundable test reservation.
- `revoke_tenant()` and `revoke_all()` take the same SQLite write lock
  to commit irreversible stop state; global stop also increments an epoch.
- A synthetic tenant stop does not alter other tenants' previously issued
  quotas or source registrations. Duplicate reservations are not charged
  again. A corrupt/absent/replaced DB denies new reservations.
- An existing one-shot finite lease cannot be magically renewed by a new
  local process. Real operator authentication is still unavailable.

**Critical guarantee limit:** An acknowledged `synthetic_reservation` is
only a test database row. It is NOT provider execution authority, actual
network handoff or an atomic guarantee that a remote HTTP request cannot be
sent *after* revocation. A client calling `reserve()` and then directly
issuing HTTP still has the same TOCTOU race as a remote authorization lookup.
Production needs a separately authenticated egress gateway that owns and
serializes the *actual network handoff* with revocation, plus network ACLs
that prevent clients bypassing it.

## Deterministic no-network E0 coverage

- Reopened database preserves spent count, revocation and idempotency state.
- Two tenants and multiple workloads share quotas **only** inside the
  correct (tenant, fixed native route) partition.
- A spawned Python OS process (not a second in-memory object) races other
  spawned workers for a shared local DB quota.
- Another spawned process commits tenant stop; parent process's next
  reservation fails. Other tenant remains operational.
- Concurrent local stop and reservation must never exceed finite budget,
  and no post-stop reservation is permitted.
- Unknown workload, tenant, route revision, stale epoch, malformed/unhashable
  identity, absent/corrupt/partial DB and attempt to re-provision fail closed.

## Threat-model non-claims

SQLite here is on one local host with cooperative test processes and a
trusted filesystem path. It does not defend against arbitrary privileged
filesystem replacement, compromise of a local writable DB, multi-host
partitions, NFS locking quirks, genuine IAM/tenant proof, mTLS certificate
rotation, secrets, durable replicated consensus, nor a crashed gateway whose
outgoing network handoff already happened. No sockets/HTTP/curl/providers are
used in tests; no model generations or independent E2 evaluations.

Do not import this research helper into the production
`RegistryExecutor` as an authority. #1639 remains OPEN; #1618 remains OPEN;
#1356 remains HOLD; frozen #432 scores remain unchanged.


## 2026-10-21 additional synthetic last-handoff ordering contract

Merely committing a durable SQLite reservation then sending a provider GET
is NOT safe against `reservation → revoke → send`. The test-only
`synthetic_handoff_after_reservation` adds two intentionally separate
serialized phases:

1. Under `BEGIN IMMEDIATE`, confirm an already reserved, exact
   tenant/workload/source/epoch/idempotency tuple and commit a permanent
   **single-use synthetic handoff claim**. This survives any crash or
   synthetic sink error; an interrupted attempt is never retried.
2. Reacquire the SQLite writer lock and **recheck the current revocation
   and exact registration** immediately before calling the synthetic sink,
   still holding the SQLite lock until that local callback completes.
   If another process stopped this tenant between phases, sink calls are
   forbidden, while its nonrefundable claim stays consumed. A stop that
   commits afterward necessarily occurs after this synthetic callback has
   returned. Duplicate execution is blocked after process restart.

The same-host spawned-process test commits a tenant stop between claim
commit and final serialized sink check, expecting **zero callback
invocations**, with the unrelated tenant still able to proceed. Additional
tests validate sink-error nonrefundability, single-use after restart,
concurrent stop/execute ordering and absent prior reservation rejection.

**Do not use this for real HTTP/network.** Its arbitrary sink is only
trusted no-network test instrumentation. It holds a local SQLite transaction
around a brief synchronous in-process callback. A real provider request has
latency, timeouts, connection resets, network delivery uncertainty and
eventual in-flight effects that cannot safely be held under this test-only
lock. Production needs independently authenticated centrally owned egress,
durably recorded admission/handoff semantics, host network ACLs preventing
bypass, and genuine multi-host crash/partition testing. Synthetic success
proves *only the narrow local ordering model*, not operator authentication
or commercially qualified availability.

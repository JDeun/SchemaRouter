# #1618 — bounded 48-episode health flap / recovery soak (offline E1)

This is a **deterministic no-network** regression for the already-existing
`LongLivedOpenMeteoHealthSessionE1`, **not** real provider uptime evidence.

- One original principal-scoped Router, original source-native typed
  planner/RegistryExecutor, one HTTPX client and explicit host-owned trusted
  simulated probes are reused for all 48 consecutive sessions.
- Six states, repeated eight times: all-healthy; geocode-unhealthy;
  recovered; weather-unhealthy; both-unhealthy; recovered.
- Before each source task the host explicitly invokes the original
  `check_health_once()` without inventing provider health or changing
  source/permissions. Simulated probe callbacks do not make any HTTP GET.
- An in-memory `httpx.MockTransport` records original geocode/forecast
  source operations. Required invariant: 24 two-hop successes, 24 genuine
  temporary-unavailable results, exactly 32 geocode and 24 forecast
  **synthetic provider-like** calls, zero wrong source calls while the
  corresponding source is unavailable.
- Every result is sanitized (no user query, coordinates, private exception,
  exact response contents). The actual monitor must be running in each
  episode and shut down at the end. Runtime source and executor are reused;
  no alternative routing agent or gold-dependent oracle is added.
- The test intentionally avoids a slow wall-clock sleep or high-frequency
  real provider polling. It proves only repeated state transitions in
  a synthetic environment, not an hours/days production reliability SLO.

## External evidence still required

A real multi-hour/day soak needs an independent operator-approved provider
health-check contract (not automated business GET abuse), externally agreed
rate/usage limit and legal terms, actual credentials/identity, controlled
outage injection, deployment environment, authenticated central coordinator
from #1639, and continuously reported p50/p95/p99, CPU/RSS, denial reasons,
request timeouts and recovery times. None is claimed by this test or authorized
automatically. Do not promote core watchdog defaults or remove v0.18 #1356
HARD HOLD. Frozen #432 and independent E2 #1477 are unchanged.

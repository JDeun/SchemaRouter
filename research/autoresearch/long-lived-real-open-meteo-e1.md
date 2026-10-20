# Bounded live Open-Meteo source observation with persistent E1 router

## Purpose and experiment split

Issue #1618 already has a merged read-only source-native health-scoped router and a testable long-lived background monitor. Prior same-router tests were **MockTransport** only; separate actual Open-Meteo and Qwen experiments often rebuilt routers between episodes. This strictly opt-in E1 witness executes a tiny set of **real, public Open-Meteo business GET requests** through the original source-native planner and the SAME long-lived router across three sequential disclosed EN/KO/JA cases.

**This is explicitly NOT a genuine independent health-probe experiment.** Because official model-update metadata are NOT an endpoint-specific geocoding/forecast liveness guarantee and no free dedicated independently trusted health URL is verified, the model-menu probes here are clearly named **SIMULATED callbacks returning True**. Their purpose is only to allow an actual source **invocation** to exercise the real provider network, errors and cooldown while preserving principal authorization; they are not to be used in any production service. The artifact always declares `health_probes_are_simulated=true`, `per_endpoint_health_independently_verified=false`, and `external_provider_success_qualified=false`. Do not count it as a production watchdog or independent E2. The original live E1 and frozen #432 remain unchanged.

## Consent and maximum outbound traffic

The CLI is **default off**. It requires `--acknowledge-readonly-business-gets` and runs ONE finite session (no cron, watch or recurring external probe). An `httpx.AsyncBaseTransport` allowlist permits only:
- HTTPS GET `geocoding-api.open-meteo.com/v1/search`
- HTTPS GET `api.open-meteo.com/v1/forecast`

No redirects, posts, unknown ports or foreign domains; a hard monotonic per-run cap of **six actual HTTP attempts** shared across all languages and native routes, zero invoker transport retries, bounded HTTP timeouts. The research-only registered HealthMonitor polls **simulated in-memory callbacks**, never a business endpoint: it contributes **zero additional external provider requests**.

Each original native source operation still uses the established `PrincipalContext`, endpoint schemas, input requirements, source fingerprint, output field projection and scoped host executor. The preselected plan is *host orchestrated*, **not Qwen/model selected**. The explicit EN Seoul, KO Seoul, JA Tokyo sample cases are already public DEV fixture cases, not newly acquired independent publisher E2 gold.

## Measurements and controls

Print one JSON receipt with only a fixed language key, per-case allowlisted status, native successful call count, total outbound requests, geocoding-vs-forecast request count, approximate elapsed milliseconds, whether a single router/monitor remained active and the above negative qualification flags. Never print request URL, city names, coordinates, unredacted provider body, raw model output, auth data or hidden gold. A transient outage may produce a **valid negative observation** while GitHub Actions remains green; status and HTTP attempt counts are evidence, green workflow alone is NOT source success.

Tests exercise exact HTTPX MockTransport success for all three source-native two-hop cases, first geocoding ConnectTimeout → trusted executor cooldown → no additional GET on later requests, source authorization constraints, HTTPS GET allowlist, hard six-GET limit, non-GET/redirect/unknown host rejection, explicit operator acknowledgement and no accidental secrets. The live CI job is an intentionally bounded, non-recurring **one-shot observational** remote API check; no model inference and no benchmark p95.

## Remaining #1618 gates

Verified independently approved per-endpoint probe callbacks that can be reused indefinitely without excessive business traffic, outage detection/recovery measured with those probes, model-selected actual provider usage with correct final outputs, independent published E2, genuine production SLO and safe startup behavior with UNKNOWN remain unqualified. v0.18 #1356 HARD HOLD remains in effect.

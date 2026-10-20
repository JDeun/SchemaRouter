# Operator-approved in-band Open-Meteo canary — limited background E1

## Motivation: no provider-designated independent health service

The existing #1619–#1627 opt-in integration already has an explicit `AccessHealthMonitor`, trusted callback registration, cooldown, authorization-scoped tool JSON and real native business GETs. The previous real Open-Meteo E1 passed all six external business GETs but used **in-memory always-true** health callbacks. This does not qualify actual watchdog behavior.

Open-Meteo's [Geocoding API](https://open-meteo.com/en/docs/geocoding-api) and [Weather Forecast API](https://open-meteo.com/en/docs) are real public data endpoints. The [Terms](https://open-meteo.com/en/terms) and [pricing](https://open-meteo.com/en/pricing) establish noncommercial free-tier request limits and no free-tier uptime guarantee. The [model-update metadata API](https://open-meteo.com/en/docs/model-updates) does not confirm actual geocoding or forecast request reachability. We do **not** invent or claim a separate independent health URL.

This E1 intentionally uses the *same exact two public read-only business endpoints*, with fixed operator-declared canary inputs, as **in-band liveness canaries**. They have stronger provenance than simulated callbacks but **cannot** be reported as independent health infrastructure, end-to-end provider uptime/SLO or continuous production qualification. Healthy here means only *that fixed read-only request returned a source-schema-valid payload at the checked time*.

## Explicit bounded execution contract

- Default OFF. CLI requires `--operator-approves-inband-business-gets` and underlying helper requires `approved_public_business_canaries=True`; false or absent consent fails before any network request.
- Reuse the merged original `OpenMeteoBoundInvoker` source schema and `AvailabilityClassifiedInvoker` health router, the original principal, authorization-scoped host executor, and existing `AccessHealthMonitor`. A probe is NOT delegated to Qwen.
- Fixed geocoder canary asks public `name=Seoul,language=en,countryCode=KR,count=10,format=json`, then validates a real country-matching location ID and WGS84 coordinates through the existing parser. Fixed forecast canary asks `latitude=37.5665,longitude=126.978,current=temperature_2m,timezone=auto`, then validates real timestamp/Celsius/finite temperature via the existing parser. These are **only canary test inputs**, not an independent gold corpus.
- Shared outbound `CappedOpenMeteoTransport` restricts HTTPS GET to precisely the original geocoder/forecast host+path, expected parameter-name sets, no embedded userinfo/redirect, and **at most six HTTP attempts TOTAL for canaries plus source calls**; no retries. On a fully healthy four-call observation, two are canaries and two are the source-native two-hop business path. These are real API traffic, not free or metadata calls.
- Only ONE background monitor sweep is authorized per one-shot session, through the actual monitor's first scheduled tick at `interval_seconds=60`; there is deliberately no eager duplicate call to `check_health_once`. Each trusted in-band callback is budgeted once. If invoked again after its budget is exhausted it returns **False**, never a cached True with an artificial post-failure timestamp; after one observation the monitor/router closes and will not poll again. No cron or indefinite global watchdog activation.
- Each actual canary results in either bounded `healthy` or `unhealthy`; unverified (not checked) is `unknown`. If **both** exact source-specific in-band canaries are healthy, use **the original principal-scoped host executor** to perform two native read-only steps; otherwise execute **zero** native business calls and report the safe `inband_canary_unhealthy` state. All model-visible tool definitions remain constrained by source authorization and freshness.
- No model invocation, no hidden source arguments or raw HTTP body in public output. Return only allowlisted stage, provider attempt and canary attempt counts, native success count, elapsed runtime, and explicit negative claims `independent_dedicated_health_endpoint_verified=false`, `long_term_availability_verified=false`, `independent_e2_qualified=false`, `production_default_changed=false`.

## Tests, metrics and interpretation

Deterministic MockTransport controls validate success (two actual canary GETs + two native GETs = four total), first real canary transport timeout => zero business calls, 5xx forecast => zero business calls, malformed response => unhealthy, strict explicit opt-in, denial of cached-health reuse on exhausted canary budget, bounded per-route budgets and sanitized public receipts.

A separate bounded one-shot Linux job makes actual public HTTPS GET requests only when its own embedded operator-acknowledged flag is used. This is explicitly **research and prototyping**; do not use Open-Meteo's free/noncommercial endpoint for commercial production. GitHub workflow success by itself means the request cap/reporting contract held, **NOT that live provider checks or data succeeded**. The summary displays actual safe status and counts to differentiate these.

## Remaining production qualification

This does not establish a provider-official health endpoint, operational continuous background polling cadence/traffic agreement, production failover, actual provider outage-recovery under fault conditions, reliability SLO, model-selected tool final-answer correctness or independently authored E2. Follow-up must obtain approved per-source probe policy / quota for the *real deployment*, optionally paid provider access with commercial-use licensing, sustained failure/recovery testing, and independent tasks. #1618 remains OPEN; v0.18 #1356 HARD HOLD.

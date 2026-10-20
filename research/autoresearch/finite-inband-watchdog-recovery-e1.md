# E1 finite background in-band watchdog outage / recovery witness

## Exact question

PR #1628 demonstrates one actual approved background health-sweep using the original geocoding and weather read-only business endpoints, but not automatic recovery on a future tick. This dependent experiment specifically tests **the original `AccessHealthMonitor` loop**, with one router and a two-probe callback budget per route, over TWO bounded monitoring intervals.

## Design and reproducibility

- Separate opt-in `observe_finite_background_recovery` requires an *explicit* `httpx.AsyncBaseTransport` factory and strict `operator_approved=True`, so running the module cannot accidentally contact any provider. Deterministic Linux `httpx.MockTransport` injects `httpx.ConnectTimeout` ONLY at the first geocoding canary and returns valid original native JSON on the second attempt; the forecast canary is healthy on both.
- The monitor's **own background coroutine** (not a manual `router.check_health_once`) observes Unhealthy then Healthy across successive ticks; an actual principal-scoped, source-ready model tool menu initially has **zero** geocoding definitions (`temporary_unavailable`) and then **one** (`ready`) after a real second callback returns valid provider JSON.
- Fixed original `OpenMeteoBoundInvoker` validates the exact native source response JSON. `InBandCanaryCallbacksE1` and shared `CappedOpenMeteoTransport` allow at most **two actual fixed canary GETs per route, four attempts total** in this scenario, with a global six-request ceiling. The monitor/router are always closed even if the test times out.
- Output contains only source-neutral statuses, visible counts and finite duration. Absolutely no city/coordinate/provider body, URL, bearer token, raw exception or model-generation text. No model/proposed tool is executed; the host only observes actual model-visible authorization-scoped schema presence.
- No actual remote service is accessed in this workflow. **Both the outage and recovery are injected**, so this is E1 functional policy evidence, not real Open-Meteo outage/recovery, independent health service, production polling policy, long-run uptime, an SLO sample or independent E2.

## Boundaries

Production requires a source-operator-approved recurring request quota/terms; the one-shot real #1628 automatically expires its budget and does NOT enable indefinite network polling. A finite 2-cycle deterministic witness cannot prove a sustainable 24/7 refresh policy or fallback quality. Frozen #432 unchanged; #1356 v0.18 stays HARD HOLD. Dependent on #1628 merging before rebasing this new draft to main.

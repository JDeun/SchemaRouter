# E1 host-operated long-lived Open-Meteo health integration (2026-10-20)

## Motivation

Original real Open-Meteo E1 creates new routers per language/arm, has no trusted health probe wired and cannot demonstrate between-request health retention. The parent [#1619](https://github.com/JDeun/SchemaRouter/pull/1619) adds strict health and model-visibility integration with per-call typed temporary-unavailable classification. This **dependent** PR adds a separate opt-in host-orchestrated session to demonstrate a shared router and background watchdog across consecutive operations, without changing old experiments.

## Operational contract

- The host explicitly supplies an already configured caller-owned `httpx.AsyncClient` and **independent, approved, cheap, read-only** per-route probe callbacks. It is not acceptable to use an arbitrary city geocoding or forecast request as a probe, invent a health endpoint, infer an arbitrary remote URL, or mark a route healthy without a qualified actual probe.
- A single `SchemaRouter` with the source-registered exact two native Open-Meteo endpoints, their original invokers wrapped by the parent typed-transient E1 adapters, the existing planner/RegistryExecutor, process-local cooldown and one owned background `AccessHealthMonitor` remains alive for the entire host session.
- `__aenter__` explicitly checks registered host-owned probes once and then starts the existing bounded background monitor; `__aexit__` closes **only** router-owned monitor and offload tasks, not caller-owned HTTP client. The original product default does not auto-start it.
- `get_current_weather` is deliberately **host-orchestrated**, never Qwen-model-selected or independent factual correctness evidence. For each sequential request it builds source and principal scoped **actual model-visible** descriptions via `capture_health_scoped_model_menu`, and invokes the normal host path only after `execute_health_scoped_host_call` re-checks the scoped snapshot. Projected geocoding fields pass only into the current-weather second hop; NO response body, query, coordinate, city, credential, private error text or model generation leaves the function.
- The returned receipt contains a small allowlisted status (`success`, `temporary_unavailable`, `inputs_missing`, `execution_failure`, `invalid_source_observation`), coarse completed native source call count, model-visible candidate counts, elapsed wall-clock milliseconds, and explicit `independent_e2_qualified=false`, `real_provider_success_qualified=false`, `model_selected_routes=false`. It cannot be presented as actual live-provider performance because deterministic CI uses HTTPX MockTransport.
- Test scenarios deliberately run multiple host requests through one object: two-hop successful source output, geocode probe failure and zero network calls, positive probe recovery, independent weather failure and recovery, passive call-time timeout then no re-invocation while cooldown, no-probe=unknown, actual background monitor recovery and lifecycle ownership. No external network in CI.

## Boundary

A strict model menu requires a **new post-failure positive health probe**, so simple expiry of the passive cooldown cannot automatically re-expose a route to the model. An independently authorized fallback must already exist in native source contracts; this experimental flow does not invent one. Real Qwen-selected tool routing, actual external Open-Meteo health evidence, independent E2, final-answer correctness, production degradation/fallback policy and v0.18 release remain out of scope.

The parent draft #1619 must merge before this PR is rebased and retargeted to `main`. No new runtime product defaults.